import requests
from django.conf import settings
from datetime import datetime
from .models import Movie


class TMDbService:
    def __init__(self):
        self.api_key = settings.TMDB_API_KEY
        self.base_url = settings.TMDB_BASE_URL

    def get_popular_movies(self, page=1):
        """Fetch popular movies from TMDb API"""
        url = f"{self.base_url}/movie/popular"
        params = {"api_key": self.api_key, "page": page, "language": "en-US"}

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching popular movies: {e}")
            return None

    def get_movie_details(self, tmdb_id):
        """Fetch detailed movie information from TMDb API"""
        url = f"{self.base_url}/movie/{tmdb_id}"
        params = {"api_key": self.api_key, "language": "en-US"}

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching movie details for ID {tmdb_id}: {e}")
            return None

    def save_movie_from_tmdb_data(self, movie_data):
        """Save movie data from TMDb API to database"""
        try:
            # Parse release date
            release_date = None
            if movie_data.get("release_date"):
                try:
                    release_date = datetime.strptime(
                        movie_data["release_date"], "%Y-%m-%d"
                    ).date()
                except ValueError:
                    pass

            # Extract genres
            genres = []
            if movie_data.get("genres"):
                genres = [genre["name"] for genre in movie_data["genres"]]
            elif movie_data.get("genre_ids"):
                # Map genre IDs to names (simplified mapping)
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
                genres = [
                    genre_map.get(genre_id, "Unknown")
                    for genre_id in movie_data["genre_ids"]
                ]

            # Create or update movie
            movie, created = Movie.objects.update_or_create(
                tmdb_id=movie_data["id"],
                defaults={
                    "title": movie_data.get("title", ""),
                    "overview": movie_data.get("overview", ""),
                    "release_date": release_date,
                    "runtime": movie_data.get("runtime"),
                    "vote_average": movie_data.get("vote_average", 0.0),
                    "vote_count": movie_data.get("vote_count", 0),
                    "popularity": movie_data.get("popularity", 0.0),
                    "poster_path": movie_data.get("poster_path", ""),
                    "backdrop_path": movie_data.get("backdrop_path", ""),
                    "genres": genres,
                },
            )

            return movie, created
        except Exception as e:
            print(f"Error saving movie data: {e}")
            return None, False

    def populate_popular_movies(self, pages=5):
        """Populate database with popular movies from TMDb"""
        movies_added = 0
        movies_updated = 0

        for page in range(1, pages + 1):
            print(f"Fetching page {page}...")
            data = self.get_popular_movies(page)

            if not data or "results" not in data:
                continue

            for movie_data in data["results"]:
                # Get detailed movie info
                detailed_data = self.get_movie_details(movie_data["id"])
                if detailed_data:
                    movie_data.update(detailed_data)

                movie, created = self.save_movie_from_tmdb_data(movie_data)
                if movie:
                    if created:
                        movies_added += 1
                        print(f"Added: {movie.title}")
                    else:
                        movies_updated += 1
                        print(f"Updated: {movie.title}")

        print(
            f"Completed! Added {movies_added} movies, updated {movies_updated} movies."
        )
        return movies_added, movies_updated
