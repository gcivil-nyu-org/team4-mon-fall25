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

# ============================================
# TMDB Configuration
# ============================================

TMDB_TOKEN = (os.getenv("TMDB_TOKEN") or "").strip()
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_HEADERS = {
    "Authorization": f"Bearer {TMDB_TOKEN}",
    "Accept": "application/json",
}
IMG_BASE = "https://image.tmdb.org/t/p/w500"


# ============================================
# TMDB Helper Functions
# ============================================

def _normalize_title(s: str) -> str:
    """Normalize movie title for comparison"""
    s = s.lower().strip()
    s = re.sub(r"[\W_]+", "", s)
    return s


def _pick_best_hit(results, query_title: str):
    """Pick the best matching movie from TMDB search results"""
    qn = _normalize_title(query_title)
    best, best_score = None, -1
    
    for r in results:
        title = r.get("title") or r.get("original_title") or ""
        tn = _normalize_title(title)
        rd = r.get("release_date") or ""
        year = int(rd[:4]) if rd[:4].isdigit() else 0
        pop = float(r.get("popularity") or 0)
        
        # Scoring algorithm: exact match + recent + popularity
        score = (100.0 if tn == qn else 0.0) + (20.0 if year >= 2020 else 0.0) + (pop / 50.0)
        
        if score > best_score:
            best_score, best = score, r
    
    return best


def _tmdb_search(title: str):
    """Search for a movie on TMDB"""
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
    """Get detailed information about a movie from TMDB"""
    r = requests.get(
        f"{TMDB_BASE}/movie/{movie_id}",
        params={"append_to_response": append} if append else {},
        headers=TMDB_HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def _tmdb_fetch_all(titles: list[str]) -> list[dict]:
    """
    Fetch TMDB details for multiple movie titles.
    Returns a list of movie dictionaries with metadata.
    """
    out = []
    
    for q in titles:
        if not q:
            continue
        
        try:
            hit = _tmdb_search(q)
            if not hit:
                out.append({
                    "query": q,
                    "found": False,
                    "reason": "No TMDB results"
                })
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
                "backdrop_url": (IMG_BASE + det["backdrop_path"]) if det.get("backdrop_path") else None,
                "genres": [g.get("name") for g in det.get("genres", [])],
                "runtime": det.get("runtime"),
            })
        except Exception as e:
            out.append({
                "query": q,
                "found": False,
                "reason": f"Error: {str(e)}"
            })
    
    return out


# ============================================
# User Affinity Helper Functions
# ============================================

def _get_signup_movies(user):
    """
    Read the two movies captured during signup from UserProfile.
    Returns a de-duplicated list of movie titles.
    """
    try:
        row = (UserProfile.objects
               .filter(user=user)
               .values_list("liked_g1_title", "liked_g2_title")
               .first())
        
        if not row:
            return []
        
        m1, m2 = row
        titles = [t.strip() for t in (m1, m2) if t and t.strip()]
        
        # Remove duplicates
        seen, out = set(), []
        for t in titles:
            key = re.sub(r"[\W_]+", "", t.lower())
            if key and key not in seen:
                seen.add(key)
                out.append(t)
        
        return out
    except Exception as e:
        print(f"Error getting signup movies: {e}")
        return []


def _get_signup_genre(user):
    """
    Read the two genres captured during signup from UserProfile.
    Returns a list of genre preferences.
    """
    try:
        row = (UserProfile.objects
               .filter(user=user)
               .values_list("favourite_genre1", "favourite_genre2")
               .first())
        
        if not row:
            return []
        
        g1, g2 = row
        genres = [t.strip() for t in (g1, g2) if t and t.strip()]
        return genres
    except Exception as e:
        print(f"Error getting signup genres: {e}")
        return []


def _get_user_interactions(user, status=None):
    """
    Get user's movie interactions, optionally filtered by status.
    Returns list of tmdb_ids.
    """
    try:
        interactions = Interaction.objects.filter(user=user)
        
        if status:
            interactions = interactions.filter(status=status.upper())
        
        return [i.tmdb_id for i in interactions]
    except Exception as e:
        print(f"Error getting user interactions: {e}")
        return []


# ============================================
# AI Agent Helper Functions
# ============================================

def _as_text(resp):
    """Extract text content from agent response"""
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
    """
    Extract movie titles from agent response.
    Looks for JSON array in the response text.
    """
    matches = list(re.finditer(r"\[[^\]]+\]", agent_text, re.DOTALL))
    if not matches:
        return []
    
    block = matches[-1].group(0)
    
    # Try JSON parsing
    try:
        data = json.loads(block)
        return [s for s in data if isinstance(s, str)][:3]
    except Exception:
        pass
    
    # Try literal_eval as fallback
    try:
        data = ast.literal_eval(block)
        return [s for s in data if isinstance(s, str)][:3]
    except Exception:
        return []


def _build_recommendation_agent(user, groq_api_key: str):
    """
    Build and configure the recommendation agent with user preferences.
    """
    movies = _get_signup_movies(user)
    genres = _get_signup_genre(user)
    liked_movies = _get_user_interactions(user, status="LIKE")
    
    # Build context about user preferences
    affinity_text = f"The user has affinity to movies like: {', '.join(movies)}" if movies else "The user has not provided a movie affinity list."
    genre_text = f"The user prefers {' and '.join(genres)} genres." if genres else ""
    liked_text = f"The user has liked {len(liked_movies)} movies." if liked_movies else ""
    
    instructions = [
        "You are a movie recommendation agent.",
        affinity_text,
        genre_text,
        liked_text,
        "Recommend exactly 3 movies with a one-line reason for each.",
        "Search for movies released after 2020.",
        "For each movie provide a score of match out of 100% based on reviews and comparison with the user's movies affinity.",
        "Format each as: Title — Reason (Match: NN%).",
        "Use markdown to format your answers.",
        "Return the three movies at the end as a JSON array of strings like: [\"Movie 1\", \"Movie 2\", \"Movie 3\"]",
    ]
    
    agent = Agent(
        name="Recommendation Agent",
        model=Groq(id="openai/gpt-oss-120b", api_key=groq_api_key, temperature=0.9),
        instructions=instructions,
        markdown=True,
    )
    
    return agent


# ============================================
# Template-Based Views (Original)
# ============================================

@login_required
@require_http_methods(["GET", "POST"])
def profile_view(request):
    """
    User profile view for template rendering.
    GET: Display profile form
    POST: Update profile
    """
    profile, _ = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={"name": request.user.username}
    )
    
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
    """
    Set or update a movie interaction (AJAX endpoint).
    Used by template-based frontend.
    """
    status = status.upper()
    valid = {c for c, _ in Interaction.Status.choices}
    
    if status not in valid:
        return JsonResponse({
            "ok": False,
            "error": f"Invalid status {status}"
        }, status=400)
    
    obj, _created = Interaction.objects.update_or_create(
        user=request.user,
        tmdb_id=tmdb_id,
        defaults={"status": status, "source": "solo"}
    )
    
    return JsonResponse({
        "ok": True,
        "tmdb_id": tmdb_id,
        "status": obj.status
    })


@login_required
def recommend_view(request):
    """
    Movie recommendation view for template rendering.
    Generates recommendations using AI agent and TMDB.
    """
    groq_api_key = (os.getenv("GROQ_API_KEY") or "").strip()
    if not groq_api_key:
        return JsonResponse({
            "error": "GROQ_API_KEY missing in .env"
        }, status=500)
    
    try:
        # Build and run recommendation agent
        agent = _build_recommendation_agent(request.user, groq_api_key)
        resp = agent.run("Recommend 3 movies I might love next.")
    except Exception as e:
        return JsonResponse({
            "error": f"Agent error: {e.__class__.__name__}: {e}"
        }, status=500)
    
    # Extract recommendations from agent response
    agent_text = _as_text(resp) or ""
    titles = _extract_titles(agent_text)
    
    # Fetch TMDB details for recommended movies
    try:
        tmdb_results = _tmdb_fetch_all(titles) if titles else []
    except requests.HTTPError as e:
        return JsonResponse({
            "error": f"TMDB HTTP {e.response.status_code}: {e.response.text}"
        }, status=502)
    except Exception as e:
        return JsonResponse({
            "error": f"TMDB error: {e.__class__.__name__}: {e}"
        }, status=500)
    
    context = {
        "agent_text": agent_text,
        "results": tmdb_results,
        "user_movies": _get_signup_movies(request.user),
        "user_genres": _get_signup_genre(request.user),
    }
    
    return render(request, "recom_sys_app/recommend_cards.html", context)


def signup_view(request):
    """
    User registration view with custom fields.
    Creates user and profile with movie preferences.
    """
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("profile")
    else:
        form = SignUpForm()
    
    return render(request, "recom_sys_app/signup.html", {"form": form})


# ============================================
# Additional Helper Views
# ============================================

@login_required
def user_stats_view(request):
    """
    Get user statistics for dashboard.
    Returns JSON with interaction counts and preferences.
    """
    try:
        profile = UserProfile.objects.get(user=request.user)
        interactions = Interaction.objects.filter(user=request.user)
        
        stats = {
            "profile": {
                "name": profile.name,
                "favourite_genres": [
                    g for g in [profile.favourite_genre1, profile.favourite_genre2]
                    if g
                ],
                "onboarding_complete": profile.onboarding_complete,
            },
            "interactions": {
                "total": interactions.count(),
                "liked": interactions.filter(status="LIKE").count(),
                "disliked": interactions.filter(status="DISLIKE").count(),
                "watched": interactions.filter(status="WATCHED").count(),
                "watch_later": interactions.filter(status="WATCH_LATER").count(),
            },
            "preferences": {
                "movies": _get_signup_movies(request.user),
                "genres": _get_signup_genre(request.user),
            }
        }
        
        return JsonResponse({"success": True, "stats": stats})
    
    except UserProfile.DoesNotExist:
        return JsonResponse({
            "success": False,
            "error": "Profile not found"
        }, status=404)
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)


@login_required
def movie_details_view(request, tmdb_id: int):
    """
    Get detailed information about a specific movie.
    Includes TMDB data and user's interaction status.
    """
    try:
        movie_data = _tmdb_details(tmdb_id, append="videos,credits,recommendations")
        
        # Check if user has interacted with this movie
        interaction = None
        try:
            interaction = Interaction.objects.get(user=request.user, tmdb_id=tmdb_id)
        except Interaction.DoesNotExist:
            pass
        
        # Format response
        response_data = {
            "success": True,
            "movie": {
                "tmdb_id": movie_data.get("id"),
                "title": movie_data.get("title"),
                "original_title": movie_data.get("original_title"),
                "overview": movie_data.get("overview"),
                "release_date": movie_data.get("release_date"),
                "runtime": movie_data.get("runtime"),
                "vote_average": movie_data.get("vote_average"),
                "vote_count": movie_data.get("vote_count"),
                "popularity": movie_data.get("popularity"),
                "poster_url": (IMG_BASE + movie_data["poster_path"]) if movie_data.get("poster_path") else None,
                "backdrop_url": (IMG_BASE + movie_data["backdrop_path"]) if movie_data.get("backdrop_path") else None,
                "genres": [g.get("name") for g in movie_data.get("genres", [])],
                "tagline": movie_data.get("tagline"),
            },
            "user_interaction": {
                "status": interaction.status if interaction else None,
                "rating": interaction.rating if interaction else None,
            } if interaction else None,
        }
        
        return JsonResponse(response_data)
    
    except requests.HTTPError as e:
        return JsonResponse({
            "success": False,
            "error": f"TMDB API error: {e.response.status_code}"
        }, status=502)
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)


@login_required
def search_movies_view(request):
    """
    Search for movies using TMDB API.
    Query parameter: ?q=movie+title
    """
    query = request.GET.get("q", "").strip()
    
    if not query:
        return JsonResponse({
            "success": False,
            "error": "Query parameter 'q' is required"
        }, status=400)
    
    try:
        if not TMDB_TOKEN:
            raise RuntimeError("TMDB_TOKEN missing in .env")
        
        r = requests.get(
            f"{TMDB_BASE}/search/movie",
            params={
                "query": query,
                "include_adult": "False",
                "language": "en-US",
                "page": 1
            },
            headers=TMDB_HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        
        results = r.json().get("results", [])
        
        # Format results
        formatted_results = [{
            "tmdb_id": movie.get("id"),
            "title": movie.get("title"),
            "release_date": movie.get("release_date"),
            "year": movie.get("release_date", "")[:4],
            "overview": movie.get("overview"),
            "vote_average": movie.get("vote_average"),
            "poster_url": (IMG_BASE + movie["poster_path"]) if movie.get("poster_path") else None,
        } for movie in results[:10]]  # Limit to top 10 results
        
        return JsonResponse({
            "success": True,
            "query": query,
            "count": len(formatted_results),
            "results": formatted_results
        })
    
    except requests.HTTPError as e:
        return JsonResponse({
            "success": False,
            "error": f"TMDB API error: {e.response.status_code}"
        }, status=502)
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)


# ============================================
# Home / Landing Page
# ============================================

def home_view(request):
    """
    Landing page view.
    Shows login/signup for anonymous users, dashboard for authenticated users.
    """
    if request.user.is_authenticated:
        return redirect("profile")
    
    return render(request, "recom_sys_app/home.html")