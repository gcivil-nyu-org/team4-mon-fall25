# recom_sys_app/views_solo.py
"""
Solo Mode Views - Movie recommendation and swiping for individual users
Isolated from group matching functionality for better code organization
"""

from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.conf import settings
import os
import json
import requests

from dotenv import load_dotenv
from .models import Interaction

# Load environment variables
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
# Page Views
# ============================================


@login_required
def solo_genre_selection(request):
    """
    Genre selection page for solo mode
    URL: /solo/genres/

    Displays a grid of movie genres for the user to select from.
    User must select at least one genre to continue.
    """
    # TMDB standard genre list
    genres = [
        {"id": 28, "name": "Action"},
        {"id": 12, "name": "Adventure"},
        {"id": 16, "name": "Animation"},
        {"id": 35, "name": "Comedy"},
        {"id": 80, "name": "Crime"},
        {"id": 99, "name": "Documentary"},
        {"id": 18, "name": "Drama"},
        {"id": 10751, "name": "Family"},
        {"id": 14, "name": "Fantasy"},
        {"id": 36, "name": "History"},
        {"id": 27, "name": "Horror"},
        {"id": 10402, "name": "Music"},
        {"id": 9648, "name": "Mystery"},
        {"id": 10749, "name": "Romance"},
        {"id": 878, "name": "Science Fiction"},
        {"id": 10770, "name": "TV Movie"},
        {"id": 53, "name": "Thriller"},
        {"id": 10752, "name": "War"},
        {"id": 37, "name": "Western"},
    ]

    return render(
        request, "recom_sys_app/solo_genre_selection.html", {"genres": genres}
    )


@login_required
def solo_deck_view(request):
    """
    Solo swipe deck page
    URL: /solo/deck/

    Displays the movie swipe deck interface where users can swipe
    through movies based on their selected genres.
    Redirects to genre selection if no genres are selected.
    """
    # Get selected genres from session
    selected_genres = request.session.get("selected_genres", [])

    if not selected_genres:
        # Redirect back to genre selection if no genres selected
        return redirect("recom_sys:solo_genre_selection")

    # Map genre IDs to names for display
    genre_map = {
        28: "Action",
        12: "Adventure",
        16: "Animation",
        35: "Comedy",
        80: "Crime",
        99: "Documentary",
        18: "Drama",
        10751: "Family",
        14: "Fantasy",
        36: "History",
        27: "Horror",
        10402: "Music",
        9648: "Mystery",
        10749: "Romance",
        878: "Science Fiction",
        10770: "TV Movie",
        53: "Thriller",
        10752: "War",
        37: "Western",
    }

    selected_genre_names = [genre_map.get(int(g), "Unknown") for g in selected_genres]

    return render(
        request,
        "recom_sys_app/solo_deck.html",
        {
            "selected_genres": selected_genres,
            "selected_genre_names": ", ".join(selected_genre_names),
        },
    )


# ============================================
# API Endpoints
# ============================================


@login_required
@require_http_methods(["POST"])
def set_solo_genres(request):
    """
    API endpoint to set selected genres in session
    POST /api/solo/set-genres/

    Request Body:
        {
            "genres": [28, 35, 18]  // Array of TMDB genre IDs
        }

    Response:
        {
            "success": true,
            "message": "Genres saved successfully",
            "redirect_url": "/solo/deck/"
        }
    """
    try:
        data = json.loads(request.body)
        genres = data.get("genres", [])

        if not genres:
            return JsonResponse(
                {"success": False, "message": "Please select at least one genre"},
                status=400,
            )

        # Validate genre IDs (should be integers)
        try:
            genres = [int(g) for g in genres]
        except (ValueError, TypeError):
            return JsonResponse(
                {"success": False, "message": "Invalid genre format"}, status=400
            )

        # Store in session
        request.session["selected_genres"] = genres

        return JsonResponse(
            {
                "success": True,
                "message": "Genres saved successfully",
                "redirect_url": "/solo/deck/",
            }
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "message": "Invalid JSON data"}, status=400
        )
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_solo_deck(request):
    """
    API endpoint to get movie recommendations for solo mode
    GET /api/solo/deck/?limit=20

    Query Parameters:
        limit (int): Number of movies to return (default: 20, max: 100)

    Response:
        {
            "success": true,
            "movies": [...],
            "total": 20,
            "selected_genres": [28, 35, 18]
        }
    """
    try:
        # Get selected genres from session
        selected_genres = request.session.get("selected_genres", [])

        if not selected_genres:
            return JsonResponse(
                {"success": False, "error": "No genres selected"}, status=400
            )

        # Get limit parameter
        try:
            limit = int(request.GET.get("limit", 20))
            limit = min(max(limit, 1), 100)  # Clamp between 1-100
        except ValueError:
            limit = 20

        # Get movies from TMDB based on selected genres
        movies = _fetch_movies_by_genres(selected_genres, limit)

        return JsonResponse(
            {
                "success": True,
                "movies": movies,
                "total": len(movies),
                "selected_genres": selected_genres,
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def solo_swipe(request):
    """
    API endpoint to record a solo swipe (like/dislike)
    POST /api/solo/swipe/

    Request Body:
        {
            "tmdb_id": 123,
            "action": "like",  // or "dislike"
            "movie_title": "Movie Name"
        }

    Response:
        {
            "success": true,
            "tmdb_id": 123,
            "action": "like",
            "message": "Liked Movie Name"
        }
    """
    try:
        data = json.loads(request.body)
        tmdb_id = data.get("tmdb_id")
        action = data.get("action")  # 'like' or 'dislike'
        movie_title = data.get("movie_title", "")

        # Validate required fields
        if not tmdb_id or not action:
            return JsonResponse(
                {"success": False, "error": "tmdb_id and action are required"},
                status=400,
            )

        # Validate action value
        if action not in ["like", "dislike"]:
            return JsonResponse(
                {"success": False, "error": 'action must be "like" or "dislike"'},
                status=400,
            )

        # Check if user has already swiped on this movie
        existing_interaction = Interaction.objects.filter(
            user=request.user, tmdb_id=tmdb_id
        ).first()

        if existing_interaction:
            # Update existing interaction
            existing_interaction.status = action  # 'like' or 'dislike'
            existing_interaction.movie_title = movie_title
            existing_interaction.save()
        else:
            # Create new interaction
            Interaction.objects.create(
                user=request.user,
                movie_title=movie_title,
                tmdb_id=tmdb_id,
                liked=(action == "like"),
            )

        response_data = {
            "success": True,
            "tmdb_id": tmdb_id,
            "action": action,
            "message": f'{"Liked" if action == "like" else "Passed on"} {movie_title}',
        }

        return JsonResponse(response_data)

    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "Invalid JSON data"}, status=400
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_solo_likes(request):
    """
    API endpoint to get user's liked movies from solo mode
    GET /api/solo/likes/

    Response:
        {
            "success": true,
            "movies": [...],
            "total": 10
        }
    """
    try:
        # Get all liked interactions for this user
        liked_interactions = Interaction.objects.filter(
            user=request.user, status="like"
        ).order_by("-timestamp")[
            :50
        ]  # Get last 50 likes

        # Get unique tmdb_ids
        tmdb_ids = list(liked_interactions.values_list("tmdb_id", flat=True).distinct())

        # Fetch details from TMDB
        movies = _tmdb_fetch_by_ids(tmdb_ids)

        return JsonResponse({"success": True, "movies": movies, "total": len(movies)})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ============================================
# Helper Functions
# ============================================


def _fetch_movies_by_genres(genre_ids: list, limit: int = 20) -> list:
    """
    Fetch movies from TMDB based on selected genres

    Args:
        genre_ids: List of TMDB genre IDs
        limit: Maximum number of movies to return

    Returns:
        List of movie dictionaries with metadata
    """
    if not TMDB_TOKEN:
        raise RuntimeError("TMDB_TOKEN missing in .env")

    movies = []
    pages_to_fetch = min(3, (limit // 20) + 1)  # Fetch multiple pages if needed

    # Convert genre_ids to comma-separated string
    genre_string = ",".join(str(g) for g in genre_ids)

    for page in range(1, pages_to_fetch + 1):
        try:
            r = requests.get(
                f"{TMDB_BASE}/discover/movie",
                params={
                    "with_genres": genre_string,
                    "sort_by": "popularity.desc",
                    "page": page,
                    "include_adult": "false",
                    "language": "en-US",
                    "vote_count.gte": 100,  # Only movies with at least 100 votes
                },
                headers=TMDB_HEADERS,
                timeout=10,
            )
            r.raise_for_status()

            results = r.json().get("results", [])

            for movie in results:
                if len(movies) >= limit:
                    break

                # Build movie dict
                movies.append(
                    {
                        "tmdb_id": movie.get("id"),
                        "title": movie.get("title", ""),
                        "year": (movie.get("release_date") or "")[:4],
                        "overview": movie.get("overview", ""),
                        "vote_average": movie.get("vote_average"),
                        "vote_count": movie.get("vote_count"),
                        "poster_url": (
                            (IMG_BASE + movie["poster_path"])
                            if movie.get("poster_path")
                            else None
                        ),
                        "backdrop_url": (
                            (IMG_BASE + movie["backdrop_path"])
                            if movie.get("backdrop_path")
                            else None
                        ),
                        "genres": [g for g in movie.get("genre_ids", [])],
                        "popularity": movie.get("popularity"),
                    }
                )

            if len(movies) >= limit:
                break

        except Exception as e:
            print(f"Error fetching movies from TMDB: {e}")
            continue

    return movies


def _tmdb_fetch_by_ids(movie_ids: list) -> list:
    """
    Fetch TMDB details for multiple movie IDs.

    Args:
        movie_ids: List of TMDB movie IDs

    Returns:
        List of movie dictionaries with metadata
    """
    out = []

    for tmdb_id in movie_ids:
        if not tmdb_id:
            continue

        try:
            # Get movie details from TMDB
            r = requests.get(
                f"{TMDB_BASE}/movie/{tmdb_id}",
                headers=TMDB_HEADERS,
                timeout=10,
            )
            r.raise_for_status()
            det = r.json()

            out.append(
                {
                    "found": True,
                    "title": det.get("title", ""),
                    "tmdb_id": det.get("id"),
                    "year": (det.get("release_date") or "")[:4],
                    "overview": det.get("overview"),
                    "vote_average": det.get("vote_average"),
                    "vote_count": det.get("vote_count"),
                    "poster_url": (
                        (IMG_BASE + det["poster_path"])
                        if det.get("poster_path")
                        else None
                    ),
                    "backdrop_url": (
                        (IMG_BASE + det["backdrop_path"])
                        if det.get("backdrop_path")
                        else None
                    ),
                    "genres": [g.get("name") for g in det.get("genres", [])],
                    "runtime": det.get("runtime"),
                }
            )
        except Exception as e:
            print(f"Error fetching movie {tmdb_id}: {e}")
            continue

    return out
