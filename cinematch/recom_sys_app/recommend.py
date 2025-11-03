# recommend/tmdb.py
import os
import requests
from typing import Iterable, Dict, Any, List

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_TOKEN = (os.getenv("TMDB_API_KEY") or "").strip()
HEADERS = {
    "Authorization": f"Bearer {TMDB_TOKEN}",
    "Accept": "application/json",
}


class TMDBError(RuntimeError):
    pass


def _check_token():
    if not TMDB_TOKEN:
        raise TMDBError("TMDB_TOKEN missing. Put it in your .env")


def search_movie(title: str) -> Dict[str, Any] | None:
    """Return the *best* search hit for a title, or None if not found."""
    _check_token()
    resp = requests.get(
        f"{TMDB_BASE}/search/movie",
        params={"query": title},
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    results: List[Dict[str, Any]] = data.get("results") or []
    if not results:
        return None
    # Pick the result with the highest popularity (more stable than index 0)
    return max(results, key=lambda r: r.get("popularity") or 0)


def movie_details(movie_id: int, append: str = "videos,credits") -> Dict[str, Any]:
    """Get movie details; optionally append extra sections."""
    _check_token()
    resp = requests.get(
        f"{TMDB_BASE}/movie/{movie_id}",
        params={"append_to_response": append} if append else {},
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_for_titles(titles: Iterable[str]) -> List[Dict[str, Any]]:
    """Loop over titles → search → details. Returns a list of summaries."""
    out: List[Dict[str, Any]] = []
    for raw in titles:
        title = (raw or "").strip()
        if not title:
            continue
        hit = search_movie(title)
        if not hit:
            out.append(
                {"title": title, "found": False, "reason": "No TMDB search results"}
            )
            continue
        details = movie_details(hit["id"])
        out.append(
            {
                "title": details.get("title") or hit.get("title") or title,
                "tmdb_id": details.get("id"),
                "year": (details.get("release_date") or "")[:4],
                "overview": details.get("overview"),
                "vote_average": details.get("vote_average"),
                "vote_count": details.get("vote_count"),
                "poster_path": details.get(
                    "poster_path"
                ),  # build an image URL later if you want
                "found": True,
            }
        )
    return out
