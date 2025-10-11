
from django.http import JsonResponse
from django.conf import settings
from django.shortcuts import render, redirect
import os, re, json, ast, requests, html

from dotenv import load_dotenv
from phi.agent import Agent
from phi.model.groq import Groq

from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.middleware.csrf import get_token
from django.contrib.auth import login

from .forms import UserProfileForm, SignUpForm
from .models import UserProfile, Interaction


load_dotenv(settings.BASE_DIR / ".env")

TMDB_TOKEN = (os.getenv("TMDB_TOKEN") or "").strip()
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_HEADERS = {
    "Authorization": f"Bearer {TMDB_TOKEN}",
    "Accept": "application/json",
}
IMG_BASE = "https://image.tmdb.org/t/p/w500"

# ---------------- TMDB helpers ----------------
def _normalize_title(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[\W_]+", "", s)
    return s

def _pick_best_hit(results, query_title: str):
    qn = _normalize_title(query_title)
    best, best_score = None, -1
    for r in results:
        title = r.get("title") or r.get("original_title") or ""
        tn = _normalize_title(title)
        rd = r.get("release_date") or ""
        year = int(rd[:4]) if rd[:4].isdigit() else 0
        pop = float(r.get("popularity") or 0)
        score = (100.0 if tn == qn else 0.0) + (20.0 if year >= 2020 else 0.0) + (pop / 50.0)
        if score > best_score:
            best_score, best = score, r
    return best

def _tmdb_search(title: str):
    if not TMDB_TOKEN:
        raise RuntimeError("TMDB_TOKEN missing in .env")
    r = requests.get(
        f"{TMDB_BASE}/search/movie",
        params={"query": title, "include_adult": "True", "language": "en-US"},
        headers=TMDB_HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    results = r.json().get("results") or []
    if not results:
        return None
    return _pick_best_hit(results, title)

def _tmdb_details(movie_id: int, append: str = "videos,credits"):
    r = requests.get(
        f"{TMDB_BASE}/movie/{movie_id}",
        params={"append_to_response": append} if append else {},
        headers=TMDB_HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()

def _tmdb_fetch_all(titles: list[str]) -> list[dict]:
    out = []
    for q in titles:
        if not q:
            continue
        hit = _tmdb_search(q)
        if not hit:
            out.append({"query": q, "found": False, "reason": "No TMDB results"})
            continue
        det = _tmdb_details(hit["id"])
        out.append({
            "query": q,
            "found": True,
            "title": det.get("title") or hit.get("title") or q,
            "tmdb_id": det.get("id"),
            "year": (det.get("release_date") or "")[:4],
            "overview": det.get("overview"),
            "vote_average": det.get("vote_average"),
            "vote_count": det.get("vote_count"),
            "poster_url": (IMG_BASE + det["poster_path"]) if det.get("poster_path") else None,
        })
    return out

# ---------------- Affinity helpers ----------------
def _get_signup_movies(user):
    """
    Read the two movies captured during signup from UserProfile and return a
    small, de-duped list of titles to seed recommendations.
    """
    row = (UserProfile.objects
           .filter(user=user)
           .values_list("liked_g1_title", "liked_g2_title")
           .first())
    if not row:
        return []
    m1, m2 = row #movie1,movie2
    titles = [t.strip() for t in (m1, m2) if t and t.strip()]
    seen, out = set(), []
    for t in titles:
        key = re.sub(r"[\W_]+", "", t.lower())
        if key and key not in seen:
            seen.add(key)
            out.append(t)
    return out
def _get_signup_genre(user):
    """
    Read the two movies captured during signup from UserProfile and return a
    small, de-duped list of titles to seed recommendations.
    """
    row = (UserProfile.objects
           .filter(user=user)
           .values_list("favourite_genre1", "favourite_genre2")
           .first())
    if not row:
        return []
    g1,g2 = row #movie1,movie2
    genres = [t.strip() for t in (g1,g2) if t and t.strip()]
    return genres


    

def _as_text(resp):
    if isinstance(resp, str):
        return resp
    text = getattr(resp, "content", None)
    if text:
        return text
    msgs = getattr(resp, "messages", None) or []
    for m in reversed(msgs):
        if getattr(m, "role", "") == "assistant" and getattr(m, "content", None):
            return m.content
    return str(resp)

def _extract_titles(agent_text: str) -> list[str]:
    matches = list(re.finditer(r"\[[^\]]+\]", agent_text, re.DOTALL))
    if not matches:
        return []
    block = matches[-1].group(0)
    try:
        data = json.loads(block)
        return [s for s in data if isinstance(s, str)][:3]
    except Exception:
        pass
    try:
        data = ast.literal_eval(block)
        return [s for s in data if isinstance(s, str)][:3]
    except Exception:
        return []

# ---------------- Views ----------------
@login_required
@require_http_methods(["GET", "POST"])
def profile_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user, defaults={"name": request.user.username})
    if request.method == "POST":
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.instance.user = request.user
            form.save()
            return redirect("profile")
    else:
        form = UserProfileForm(instance=profile)
    get_token(request)  # ensure CSRF cookie
    return render(request, "recom_sys_app/profile_form.html", {"form": form})

@login_required
@require_http_methods(["POST"])
def set_interaction_view(request, tmdb_id: int, status: str):
    status = status.upper()
    valid = {c for c, _ in Interaction.Status.choices}
    if status not in valid:
        return JsonResponse({"ok": False, "error": f"Invalid status {status}"}, status=400)
    obj, _created = Interaction.objects.update_or_create(
        user=request.user, tmdb_id=tmdb_id, defaults={"status": status, "source": "solo"}
    )
    return JsonResponse({"ok": True, "tmdb_id": tmdb_id, "status": obj.status})

@login_required
def recommend_view(request):
    groq_api_key = (os.getenv("GROQ_API_KEY") or "").strip()
    if not groq_api_key:
        return JsonResponse({"error": "GROQ_API_KEY missing in .env"}, status=500)

    # Use signup movies from DB instead of the text file
    movies = _get_signup_movies(request.user)
    genres = _get_signup_genre(request.user)
    agent = Agent(
        name="Recommendation Agent",
        model=Groq(id="openai/gpt-oss-120b", api_key=groq_api_key, temperature=0.9),
        instructions=[
            "You are a movie recommendation agent.",
            (f"The user has affinity to movies like: {', '.join(movies)}"
             if movies else "The user has not provided a movie affinity list."),
            "Recommend exactly 3 movies with a one-line reason for each.",
            "Search for movies released after 2020.",
            "For each movie provide a score of match out of 100% based on reviews and comparison with the user's movies affinity.",
            "Format each as: Title — Reason (Match: NN%).",
            "Use markdown to format your answers.",
            f"return three movies in {genres} of movies that the user likes along with the movies that they have liked during signup.",
            "Return the three movies in the end as a list of string",
        ],
        markdown=True,
    )

    try:
        resp = agent.run("Recommend 3 movies I might love next.")
    except Exception as e:
        return JsonResponse({"error": f"Agent error: {e.__class__.__name__}: {e}"}, status=500)

    agent_text = _as_text(resp) or ""
    titles = _extract_titles(agent_text)
    try:
        tmdb_results = _tmdb_fetch_all(titles) if titles else []
    except requests.HTTPError as e:
        return JsonResponse({"error": f"TMDB HTTP {e.response.status_code}: {e.response.text}"}, status=502)
    except Exception as e:
        return JsonResponse({"error": f"TMDB error: {e.__class__.__name__}: {e}"}, status=500)

    context = {"agent_text": agent_text, "results": tmdb_results}
    return render(request, "recom_sys_app/recommend_cards.html", context)

# ---- Signup with custom fields (name, email, age, sex, 2 genres, 2 liked movies) ----
def signup_view(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()  
            login(request, user)
            return redirect("profile")
    else:
        form = SignUpForm()
    return render(request, "recom_sys_app/signup.html", {"form": form})
