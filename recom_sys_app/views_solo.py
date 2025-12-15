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
from django.core.cache import cache
import os
import json
import requests

from dotenv import load_dotenv
from .models import Interaction
from .geolocation import get_user_region

# Load environment variables
load_dotenv(settings.BASE_DIR / ".env")

# ============================================
# TMDB Configuration
# ============================================

TMDB_TOKEN = (os.getenv("TMDB_TOKEN") or os.getenv("TMDB_API_KEY") or "").strip()
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
    Uses hybrid approach: collaborative filtering + preference-based recommendations

    GET /api/solo/deck/?limit=20

    Query Parameters:
        limit (int): Number of movies to return (default: 20, max: 100)

    Response:
        {
            "success": true,
            "movies": [...],
            "total": 20,
            "selected_genres": [28, 35, 18],
            "recommendation_method": "hybrid" | "preference" | "popular"
        }
    """
    try:
        # Get selected genres from session
        selected_genres = request.session.get("selected_genres", [])

        if not selected_genres:
            return JsonResponse(
                {"success": False, "error": "No genres selected"}, status=400
            )

        # Get limit and offset parameters
        try:
            limit = int(request.GET.get("limit", 50))  # Default to 50 movies
            limit = min(max(limit, 50), 100)  # Clamp between 50-100 (minimum 50)
        except ValueError:
            limit = 50  # Default to 50 movies

        try:
            offset = int(request.GET.get("offset", 0))
            offset = max(offset, 0)  # Ensure non-negative
        except ValueError:
            offset = 0

        # Get user's region for watch providers
        user_region = get_user_region(request)

        # SIMPLIFIED: Just use genre-based recommendations (no CF, no preference-based)
        from recom_sys_app.services import RecommendationService

        # Simple genre-based approach
        recommendation_method = "genre_based"

        # Get movie IDs from genre-based recommendations only
        # Use offset for pagination to get different movies
        requested_limit = max(limit, 50)

        movie_ids = RecommendationService.get_solo_deck(
            request.user,
            limit=requested_limit
            * 2,  # Get more to account for filtering and ensure 50+
            use_collaborative_filtering=False,  # Disable CF for simplicity
            offset=offset,
            selected_genre_ids=selected_genres,  # Pass selected genres
        )

        # Get preference-based movie IDs from cache (stored by RecommendationService)
        from django.core.cache import cache

        cache_key = (
            f"solo_pref_ids_{request.user.id}_{'_'.join(map(str, selected_genres))}"
        )
        preference_movie_ids = cache.get(cache_key, set())

        # Fetch movie details from TMDB
        movies = _tmdb_fetch_by_ids(movie_ids[: limit * 2])

        # Filter out already-swiped movies
        swiped_ids = set(
            Interaction.objects.filter(user=request.user).values_list(
                "tmdb_id", flat=True
            )
        )

        # Filter movies by swiped status and verify genre match (strict filtering)
        filtered_movies = []
        selected_genre_set = set(selected_genres)  # Convert to set for faster lookup

        for movie in movies:
            if movie["tmdb_id"] in swiped_ids:
                continue

            # Strict genre filtering: movie MUST match at least one selected genre
            # Get genre IDs from movie (now included in _tmdb_fetch_by_ids response)
            movie_genre_ids = movie.get("genre_ids", [])

            # Fallback: if genre_ids not available, try to extract from genres array
            if not movie_genre_ids:
                movie_genres = movie.get("genres", [])
                for genre in movie_genres:
                    if isinstance(genre, dict) and "id" in genre:
                        movie_genre_ids.append(genre["id"])
                    elif isinstance(genre, int):
                        movie_genre_ids.append(genre)

            # Only include movies that match selected genres
            # Strict filtering: must have genre info and match at least one selected genre
            if movie_genre_ids and any(
                gid in selected_genre_set for gid in movie_genre_ids
            ):
                filtered_movies.append(movie)
            # If no genre info, exclude it (service should have filtered, but be strict)
            elif not movie_genre_ids:
                print(
                    f"[Warning] Movie {movie.get('tmdb_id')} has no genre info, excluding from results"
                )

            if len(filtered_movies) >= limit:
                break

        movies = filtered_movies[:limit]

        # Add recommendation source/reason to each movie
        # Watch providers are fetched lazily on the frontend to improve initial load time
        for movie in movies:
            # Mark preference-based movies
            if movie["tmdb_id"] in preference_movie_ids:
                movie["recommendation_reason"] = "Based on your preferences"
                movie["recommendation_source"] = "preference_based"
            else:
                movie["recommendation_reason"] = "Based on selected genres"
                movie["recommendation_source"] = "genre_based"

            # Initialize watch_providers as empty - can be fetched on demand
            movie["watch_providers"] = {
                "region": user_region,
                "flatrate": [],
                "rent": [],
                "buy": [],
                "link": "",
                "available": False,
            }

        return JsonResponse(
            {
                "success": True,
                "movies": movies,
                "total": len(movies),
                "selected_genres": selected_genres,
                "region": user_region,
                "recommendation_method": recommendation_method,
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def solo_swipe(request):
    """
    API endpoint to record a solo swipe/interaction
    POST /api/solo/swipe/

    Request Body:
        {
            "tmdb_id": 123,
            "action": "like",  // like, dislike, watch_later, watched, watched_liked, watched_disliked
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
        action = data.get("action")
        movie_title = data.get("movie_title", "")

        # Validate required fields
        if not tmdb_id or not action:
            return JsonResponse(
                {"success": False, "error": "tmdb_id and action are required"},
                status=400,
            )

        # Validate action value - now includes watched_liked and watched_disliked
        valid_actions = [
            "like",
            "dislike",
            "watch_later",
            "watched",
            "watched_liked",
            "watched_disliked",
        ]
        if action not in valid_actions:
            return JsonResponse(
                {
                    "success": False,
                    "error": f'action must be one of: {", ".join(valid_actions)}',
                },
                status=400,
            )

        # Check if user has already swiped on this movie
        existing_interaction = Interaction.objects.filter(
            user=request.user, tmdb_id=tmdb_id
        ).first()

        if existing_interaction:
            # Update existing interaction
            existing_interaction.status = (
                action.upper()
            )  # Convert to 'LIKE' or 'DISLIKE'
            existing_interaction.save()
        else:
            # Create new interaction
            Interaction.objects.create(
                user=request.user,
                tmdb_id=tmdb_id,
                status=action.upper(),  # Convert to 'LIKE' or 'DISLIKE'
            )

        # Invalidate the cached solo deck to ensure fresh recommendations
        cache_key = f"solo_deck_{request.user.id}"
        cache.delete(cache_key)

        # Generate appropriate message based on action
        action_messages = {
            "like": f"Liked {movie_title}",
            "dislike": f"Passed on {movie_title}",
            "watch_later": f"Added {movie_title} to Watch Later",
            "watched": f"Marked {movie_title} as Watched",
            "watched_liked": f"Marked {movie_title} as watched and liked",
            "watched_disliked": f"Marked {movie_title} as watched but didn't like",
        }

        response_data = {
            "success": True,
            "tmdb_id": tmdb_id,
            "action": action,
            "message": action_messages.get(action, f"Updated {movie_title}"),
        }

        return JsonResponse(response_data)

    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "Invalid JSON data"}, status=400
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@require_http_methods(["DELETE"])
def unlike_movie(request, tmdb_id):
    """
    API endpoint to remove a movie from user's liked movies (LIKE or WATCHED_LIKED)
    DELETE /api/solo/unlike/<tmdb_id>/

    Response:
        {
            "success": true,
            "message": "Movie removed from likes",
            "tmdb_id": 123
        }
    """
    try:
        # Find the interaction for this movie (either LIKE or WATCHED_LIKED)
        interaction = Interaction.objects.filter(
            user=request.user, tmdb_id=tmdb_id, status__in=["LIKE", "WATCHED_LIKED"]
        ).first()

        if not interaction:
            return JsonResponse(
                {"success": False, "error": "Movie not found in your likes"},
                status=404,
            )

        # Delete the interaction
        interaction.delete()

        # Invalidate the cached solo deck to ensure fresh recommendations
        cache_key = f"solo_deck_{request.user.id}"
        cache.delete(cache_key)

        return JsonResponse(
            {
                "success": True,
                "message": "Movie removed from likes",
                "tmdb_id": tmdb_id,
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
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
            "movies": [...],  # Each movie includes action_type: 'like' or 'watched_liked'
            "total": 10
        }
    """
    try:
        # Get all LIKE and WATCHED_LIKED interactions for this user (limit to 50)
        liked_interactions = Interaction.objects.filter(
            user=request.user, status__in=["LIKE", "WATCHED_LIKED"]
        ).order_by("-updated_at")[:50]

        # Build a map of tmdb_id to action_type
        action_map = {}
        for interaction in liked_interactions:
            # Map status to action_type for frontend
            action_type = (
                "watched_liked" if interaction.status == "WATCHED_LIKED" else "like"
            )
            action_map[interaction.tmdb_id] = action_type

        # Get unique tmdb_ids (already limited to 50 by the query)
        tmdb_ids = list(action_map.keys())

        # Fetch details from TMDB
        movies = _tmdb_fetch_by_ids(tmdb_ids)

        # Add action_type to each movie
        for movie in movies:
            tmdb_id = movie.get("tmdb_id")
            if tmdb_id in action_map:
                movie["action_type"] = action_map[tmdb_id]

        return JsonResponse({"success": True, "movies": movies, "total": len(movies)})

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_watch_later(request):
    """
    API endpoint to get user's Watch Later movies
    GET /api/solo/watch-later/

    Response:
        {
            "success": true,
            "movies": [...],
            "total": 10
        }
    """
    try:
        # Get all watch later interactions for this user
        watch_later_interactions = Interaction.objects.filter(
            user=request.user, status="WATCH_LATER"
        ).order_by("-updated_at")[
            :50
        ]  # Get last 50 watch later

        # Get unique tmdb_ids
        tmdb_ids = list(set(watch_later_interactions.values_list("tmdb_id", flat=True)))

        # Fetch details from TMDB
        movies = _tmdb_fetch_by_ids(tmdb_ids)

        return JsonResponse({"success": True, "movies": movies, "total": len(movies)})

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_watched(request):
    """
    API endpoint to get user's Watched movies
    GET /api/solo/watched/

    Response:
        {
            "success": true,
            "movies": [...],
            "total": 10
        }
    """
    try:
        # Get all watched interactions for this user (including watched_liked and watched_disliked)
        watched_interactions = Interaction.objects.filter(
            user=request.user,
            status__in=["WATCHED", "WATCHED_LIKED", "WATCHED_DISLIKED"],
        ).order_by("-updated_at")[
            :100
        ]  # Get last 100 watched

        # Build a map of tmdb_id to status
        status_map = {}
        for interaction in watched_interactions:
            status_map[interaction.tmdb_id] = interaction.status

        # Get unique tmdb_ids
        tmdb_ids = list(status_map.keys())

        # Fetch details from TMDB
        movies = _tmdb_fetch_by_ids(tmdb_ids)

        # Add status to each movie
        for movie in movies:
            tmdb_id = movie.get("tmdb_id")
            if tmdb_id in status_map:
                movie["status"] = status_map[tmdb_id]

        return JsonResponse({"success": True, "movies": movies, "total": len(movies)})

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ============================================
# Helper Functions
# ============================================


def _fetch_movies_by_genres(genre_ids: list, limit: int = 20, user=None) -> list:
    """
    Fetch movies from TMDB based on selected genres with improved recommendations

    Args:
        genre_ids: List of TMDB genre IDs
        limit: Maximum number of movies to return
        user: User object for personalized recommendations

    Returns:
        List of movie dictionaries with metadata
    """
    if not TMDB_TOKEN:
        raise RuntimeError("TMDB_TOKEN missing in .env")

    movies = []
    seen_ids = set()
    # Fetch more pages for variety (5 pages = ~100 movies before filtering)
    pages_to_fetch = min(5, (limit // 20) + 2)

    # Convert genre_ids to pipe-separated string (OR logic for TMDB API)
    genre_string = "|".join(str(g) for g in genre_ids)

    # First, try to get personalized recommendations based on liked movies
    if user:
        try:
            # Get recently liked and watched_liked movies for personalized recommendations
            liked_movies = list(
                Interaction.objects.filter(
                    user=user, status__in=["LIKE", "WATCHED_LIKED"]
                )
                .order_by("-updated_at")
                .values_list("tmdb_id", flat=True)[:10]
            )

            # Fetch recommendations based on liked movies
            for liked_id in liked_movies[:5]:  # Use top 5 liked movies
                try:
                    r = requests.get(
                        f"{TMDB_BASE}/movie/{liked_id}/recommendations",
                        params={"language": "en-US", "page": 1},
                        headers=TMDB_HEADERS,
                        timeout=10,
                    )
                    r.raise_for_status()
                    results = r.json().get("results", [])

                    for movie in results[:4]:  # Take top 4 from each liked movie
                        if movie.get("id") in seen_ids:
                            continue
                        seen_ids.add(movie.get("id"))
                        movies.append(_build_movie_dict(movie))

                        if len(movies) >= limit // 3:  # 1/3 from recommendations
                            break
                except Exception:
                    continue

        except Exception as e:
            print(f"Error fetching personalized recommendations: {e}")

    # Fetch discover movies by genre (the rest)
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
                    "vote_count.gte": 50,  # Lower threshold for more variety
                },
                headers=TMDB_HEADERS,
                timeout=10,
            )
            r.raise_for_status()

            results = r.json().get("results", [])

            for movie in results:
                if len(movies) >= limit:
                    break

                if movie.get("id") in seen_ids:
                    continue
                seen_ids.add(movie.get("id"))

                movies.append(_build_movie_dict(movie))

            if len(movies) >= limit:
                break

        except Exception as e:
            print(f"Error fetching movies from TMDB: {e}")
            continue

    # Also fetch trending movies for variety
    if len(movies) < limit:
        try:
            r = requests.get(
                f"{TMDB_BASE}/trending/movie/week",
                params={"language": "en-US"},
                headers=TMDB_HEADERS,
                timeout=10,
            )
            r.raise_for_status()
            results = r.json().get("results", [])

            for movie in results:
                if len(movies) >= limit:
                    break
                if movie.get("id") in seen_ids:
                    continue
                seen_ids.add(movie.get("id"))
                movies.append(_build_movie_dict(movie))

        except Exception as e:
            print(f"Error fetching trending movies: {e}")

    return movies


def _build_movie_dict(movie: dict) -> dict:
    """Build a standardized movie dictionary from TMDB response"""
    return {
        "tmdb_id": movie.get("id"),
        "title": movie.get("title", ""),
        "year": (movie.get("release_date") or "")[:4],
        "overview": movie.get("overview", ""),
        "vote_average": movie.get("vote_average"),
        "vote_count": movie.get("vote_count"),
        "poster_url": (
            (IMG_BASE + movie["poster_path"]) if movie.get("poster_path") else None
        ),
        "backdrop_url": (
            (IMG_BASE + movie["backdrop_path"]) if movie.get("backdrop_path") else None
        ),
        "genres": [g for g in movie.get("genre_ids", [])],
        "popularity": movie.get("popularity"),
    }


def _fetch_watch_providers(movie_id: int, region: str = "US") -> dict:
    """
    Fetch watch providers for a movie from TMDB

    Args:
        movie_id: TMDB movie ID
        region: ISO 3166-1 alpha-2 country code (e.g., "US", "GB", "IN")

    Returns:
        Dictionary with flatrate, rent, buy providers
    """
    try:
        r = requests.get(
            f"{TMDB_BASE}/movie/{movie_id}/watch/providers",
            headers=TMDB_HEADERS,
            timeout=5,
        )
        r.raise_for_status()
        data = r.json()

        results = data.get("results", {}).get(region, {})

        return {
            "region": region,
            "flatrate": results.get("flatrate", []),
            "rent": results.get("rent", []),
            "buy": results.get("buy", []),
            "link": results.get("link", ""),
            "available": bool(results),
        }
    except Exception:
        return {
            "region": region,
            "flatrate": [],
            "rent": [],
            "buy": [],
            "link": "",
            "available": False,
        }


def _tmdb_fetch_by_ids(movie_ids: list) -> list:
    """
    Fetch TMDB details for multiple movie IDs using parallel requests for better performance.

    Args:
        movie_ids: List of TMDB movie IDs

    Returns:
        List of movie dictionaries with metadata
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    out = []
    movie_ids = [mid for mid in movie_ids if mid]  # Filter out None/empty IDs

    if not movie_ids:
        return out

    def fetch_single_movie(tmdb_id):
        """Fetch a single movie's details"""
        try:
            r = requests.get(
                f"{TMDB_BASE}/movie/{tmdb_id}",
                headers=TMDB_HEADERS,
                timeout=10,
            )
            r.raise_for_status()
            det = r.json()

            # Extract genre IDs and names from TMDB response
            genre_objects = det.get("genres", [])
            genre_names = [g.get("name") for g in genre_objects]
            genre_ids = [g.get("id") for g in genre_objects if g.get("id")]

            return {
                "found": True,
                "title": det.get("title", ""),
                "tmdb_id": det.get("id"),
                "year": (det.get("release_date") or "")[:4],
                "overview": det.get("overview"),
                "vote_average": det.get("vote_average"),
                "vote_count": det.get("vote_count"),
                "poster_url": (
                    (IMG_BASE + det["poster_path"]) if det.get("poster_path") else None
                ),
                "backdrop_url": (
                    (IMG_BASE + det["backdrop_path"])
                    if det.get("backdrop_path")
                    else None
                ),
                "genres": genre_names,  # Keep genre names for display
                "genre_ids": genre_ids,  # Add genre IDs for filtering
                "runtime": det.get("runtime"),
            }
        except Exception as e:
            print(f"Error fetching movie {tmdb_id}: {e}")
            return None

    # Use ThreadPoolExecutor for parallel requests (max 10 concurrent)
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_id = {
            executor.submit(fetch_single_movie, tmdb_id): tmdb_id
            for tmdb_id in movie_ids
        }

        for future in as_completed(future_to_id):
            result = future.result()
            if result:
                out.append(result)

    return out


@login_required
def watched_movies_page(request):
    """
    Render the watched movies page
    """
    return render(request, "recom_sys_app/watched_movies.html")
