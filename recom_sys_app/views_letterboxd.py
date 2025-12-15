# recom_sys_app/views_letterboxd.py
import csv
import io
import requests
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Interaction
import os


@login_required
@require_http_methods(["POST"])
def upload_letterboxd_csv(request):
    """
    Handle Letterboxd CSV file upload and import watched movies.

    Expected CSV format:
    Date,Name,Year,Letterboxd URI
    2025-12-15,The Godfather,1972,https://boxd.it/2aNK
    """
    print(f"[DEBUG] Letterboxd upload endpoint hit by user: {request.user.username}")
    print(f"[DEBUG] FILES: {request.FILES.keys()}")
    print(f"[DEBUG] POST: {request.POST.keys()}")

    if "csv_file" not in request.FILES:
        print("[DEBUG] ERROR: No csv_file in request.FILES")
        return JsonResponse({"error": "No file uploaded"}, status=400)

    csv_file = request.FILES["csv_file"]

    # Validate file type
    if not csv_file.name.endswith(".csv"):
        return JsonResponse({"error": "File must be a CSV"}, status=400)

    # Validate file size (max 10MB)
    if csv_file.size > 10 * 1024 * 1024:
        return JsonResponse({"error": "File size too large (max 10MB)"}, status=400)

    try:
        # Read and parse CSV
        decoded_file = csv_file.read().decode("utf-8")
        csv_reader = csv.DictReader(io.StringIO(decoded_file))

        print(
            f"[DEBUG] Starting Letterboxd CSV import for user: {request.user.username}"
        )

        stats = {
            "total": 0,
            "imported": 0,
            "already_watched": 0,
            "not_found": 0,
        }

        # Get TMDB API credentials
        tmdb_token = os.getenv("TMDB_TOKEN") or os.getenv("TMDB_API_KEY")
        if not tmdb_token:
            return JsonResponse({"error": "TMDB API not configured"}, status=500)

        headers = {
            "Authorization": f"Bearer {tmdb_token}",
            "Content-Type": "application/json;charset=utf-8",
        }

        for row in csv_reader:
            stats["total"] += 1

            # Extract movie details from CSV
            movie_name = row.get("Name", "").strip()
            year = row.get("Year", "").strip()

            if not movie_name:
                continue

            # Search for movie in TMDB
            tmdb_id = search_movie_in_tmdb(movie_name, year, headers)
            print(f"[DEBUG] Movie: '{movie_name}' ({year}) -> TMDB ID: {tmdb_id}")

            if tmdb_id:
                # Check if already watched
                existing = Interaction.objects.filter(
                    user=request.user, tmdb_id=tmdb_id
                ).first()

                if existing:
                    # Update to WATCHED_LIKED if it's not already in a watched state
                    if existing.status not in [
                        Interaction.Status.WATCHED,
                        Interaction.Status.WATCHED_LIKED,
                        Interaction.Status.WATCHED_DISLIKED,
                    ]:
                        existing.status = Interaction.Status.WATCHED_LIKED
                        existing.save()
                        print(
                            f"[DEBUG] Updated existing interaction for {tmdb_id} to WATCHED_LIKED"
                        )
                        stats["imported"] += 1
                    else:
                        print(f"[DEBUG] Already watched: {tmdb_id}")
                        stats["already_watched"] += 1
                else:
                    # Create new WATCHED_LIKED interaction (so it appears in "Watched & Liked" list)
                    interaction = Interaction.objects.create(
                        user=request.user,
                        tmdb_id=tmdb_id,
                        status=Interaction.Status.WATCHED_LIKED,
                        source="letterboxd_import",
                    )
                    print(
                        f"[DEBUG] Created new interaction for {tmdb_id}: {interaction.id}"
                    )
                    stats["imported"] += 1
            else:
                stats["not_found"] += 1

        print(f"[DEBUG] Import complete: {stats}")

        # Force preference update after import to ensure recommendations reflect new data
        if stats["imported"] > 0:
            try:
                from .services import PreferenceService

                PreferenceService.update_user_preferences(
                    request.user, force_recalculate=True
                )
                print(f"[DEBUG] Updated preferences for user: {request.user.username}")
            except Exception as e:
                print(f"[DEBUG] Error updating preferences: {e}")

        return JsonResponse(
            {
                "message": f"Successfully imported {stats['imported']} movies!",
                "stats": stats,
            }
        )

    except Exception as e:
        print(f"Error processing CSV: {e}")
        return JsonResponse({"error": f"Error processing file: {str(e)}"}, status=500)


def search_movie_in_tmdb(movie_name, year, headers):
    """
    Search for a movie in TMDB and return its ID.

    Args:
        movie_name: Movie title
        year: Release year (optional)
        headers: TMDB API headers

    Returns:
        TMDB ID if found, None otherwise
    """
    try:
        # Build search query
        query = movie_name.strip()

        # Search TMDB
        url = f"https://api.themoviedb.org/3/search/movie?query={requests.utils.quote(query)}"
        if year:
            url += f"&year={year}"

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])

            if results:
                # Return the first result (most relevant)
                return results[0]["id"]

        return None

    except Exception as e:
        print(f"Error searching TMDB for '{movie_name}': {e}")
        return None
