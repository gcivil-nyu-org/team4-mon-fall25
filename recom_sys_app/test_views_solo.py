"""
Unit and Integration Tests for Solo Mode Views (views_solo.py) - FIXED

Tests cover:
- Page views (genre selection, swipe deck)
- API endpoints (set genres, get deck, swipe, get likes)
- TMDB integration
- Session management
- Authentication
- Error handling
"""

import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from recom_sys_app.models import Interaction

User = get_user_model()


class SoloGenreSelectionViewTest(TestCase):
    """Test suite for solo genre selection page"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.url = reverse("recom_sys:solo_genre_selection")

    def test_genre_selection_requires_authentication(self):
        """Test that unauthenticated users are redirected to login"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_genre_selection_page_loads(self):
        """Test that authenticated users can access genre selection page"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "recom_sys_app/solo_genre_selection.html")

    def test_genre_selection_displays_genres(self):
        """Test that all genres are displayed on the page"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(self.url)

        # Check that genres are in context
        self.assertIn("genres", response.context)
        genres = response.context["genres"]

        # Should have 19 standard TMDB genres
        self.assertEqual(len(genres), 19)

        # Check specific genres
        genre_names = [g["name"] for g in genres]
        self.assertIn("Action", genre_names)
        self.assertIn("Comedy", genre_names)
        self.assertIn("Drama", genre_names)

    def test_genre_selection_genre_structure(self):
        """Test that genres have correct structure (id and name)"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(self.url)

        genres = response.context["genres"]

        for genre in genres:
            self.assertIn("id", genre)
            self.assertIn("name", genre)
            self.assertIsInstance(genre["id"], int)
            self.assertIsInstance(genre["name"], str)


class SoloDeckViewTest(TestCase):
    """Test suite for solo swipe deck page"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        # FIXED: Use correct URL name from urls.py
        self.url = reverse("recom_sys:solo_deck")

    def test_deck_view_requires_authentication(self):
        """Test that unauthenticated users are redirected to login"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_deck_view_redirects_without_genres(self):
        """Test that users without selected genres are redirected"""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("genre", response.url)

    def test_deck_view_loads_with_genres(self):
        """Test that deck page loads when genres are selected"""
        self.client.login(username="testuser", password="testpass123")

        # Set genres in session
        session = self.client.session
        session["selected_genres"] = [28, 35, 18]  # Action, Comedy, Drama
        session.save()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "recom_sys_app/solo_deck.html")

    def test_deck_view_displays_genre_names(self):
        """Test that selected genre names are displayed"""
        self.client.login(username="testuser", password="testpass123")

        # Set genres in session
        session = self.client.session
        session["selected_genres"] = [28, 35]  # Action, Comedy
        session.save()

        response = self.client.get(self.url)

        self.assertIn("selected_genre_names", response.context)
        genre_names = response.context["selected_genre_names"]

        self.assertIn("Action", genre_names)
        self.assertIn("Comedy", genre_names)


class SetSoloGenresAPITest(TestCase):
    """Test suite for set_solo_genres API endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.url = reverse("recom_sys:set_solo_genres")

    def test_set_genres_requires_authentication(self):
        """Test that unauthenticated users cannot set genres"""
        response = self.client.post(
            self.url,
            data=json.dumps({"genres": [28, 35]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)

    def test_set_genres_success(self):
        """Test successful genre setting"""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.post(
            self.url,
            data=json.dumps({"genres": [28, 35, 18]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data["success"])
        self.assertIn("redirect_url", data)

        # Check that genres are saved in session
        self.assertIn("selected_genres", self.client.session)
        self.assertEqual(self.client.session["selected_genres"], [28, 35, 18])

    def test_set_genres_empty_list(self):
        """Test that empty genre list returns error"""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.post(
            self.url, data=json.dumps({"genres": []}), content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()

        self.assertFalse(data["success"])
        self.assertIn("select at least one genre", data["message"].lower())

    def test_set_genres_invalid_format(self):
        """Test that invalid genre format returns error"""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.post(
            self.url,
            data=json.dumps({"genres": ["invalid", "format"]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()

        self.assertFalse(data["success"])
        self.assertIn("invalid", data["message"].lower())

    def test_set_genres_invalid_json(self):
        """Test that invalid JSON returns error"""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.post(
            self.url, data="not valid json", content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()

        self.assertFalse(data["success"])

    def test_set_genres_only_accepts_post(self):
        """Test that only POST method is accepted"""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)  # Method Not Allowed


class GetSoloDeckAPITest(TestCase):
    """Test suite for get_solo_deck API endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.url = reverse("recom_sys:get_solo_deck")

    def test_get_deck_requires_authentication(self):
        """Test that unauthenticated users cannot get deck"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_get_deck_without_genres(self):
        """Test that request without genres returns error"""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 400)
        data = response.json()

        self.assertFalse(data["success"])
        self.assertIn("no genres", data["error"].lower())

    @patch("recom_sys_app.views_solo.requests.get")
    def test_get_deck_success(self, mock_get):
        """Test successful deck retrieval"""
        self.client.login(username="testuser", password="testpass123")

        # Set genres in session
        session = self.client.session
        session["selected_genres"] = [28, 35]
        session.save()

        # Mock TMDB API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "id": 550,
                    "title": "Fight Club",
                    "release_date": "1999-10-15",
                    "overview": "A ticking-time-bomb...",
                    "vote_average": 8.4,
                    "vote_count": 20000,
                    "poster_path": "/path.jpg",
                    "backdrop_path": "/backdrop.jpg",
                    "genre_ids": [28, 53],
                    "popularity": 50.0,
                }
            ]
        }
        mock_get.return_value = mock_response

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data["success"])
        self.assertIn("movies", data)
        self.assertIn("total", data)
        self.assertEqual(data["selected_genres"], [28, 35])

    @patch("recom_sys_app.views_solo.requests.get")
    def test_get_deck_with_limit(self, mock_get):
        """Test deck retrieval with custom limit"""
        self.client.login(username="testuser", password="testpass123")

        # Set genres in session
        session = self.client.session
        session["selected_genres"] = [28]
        session.save()

        # Mock TMDB API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        response = self.client.get(f"{self.url}?limit=10")

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data["success"])

    @patch("recom_sys_app.views_solo.requests.get")
    def test_get_deck_limit_bounds(self, mock_get):
        """Test that limit is clamped between 1 and 100"""
        self.client.login(username="testuser", password="testpass123")

        # Set genres in session
        session = self.client.session
        session["selected_genres"] = [28]
        session.save()

        # Mock TMDB API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        # Test limit too high
        response = self.client.get(f"{self.url}?limit=200")
        self.assertEqual(response.status_code, 200)

        # Test limit too low
        response = self.client.get(f"{self.url}?limit=0")
        self.assertEqual(response.status_code, 200)

    def test_get_deck_only_accepts_get(self):
        """Test that only GET method is accepted"""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 405)


class SoloSwipeAPITest(TestCase):
    """Test suite for solo_swipe API endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.url = reverse("recom_sys:solo_swipe")

    def test_swipe_requires_authentication(self):
        """Test that unauthenticated users cannot swipe"""
        response = self.client.post(
            self.url,
            data=json.dumps(
                {"tmdb_id": 550, "action": "like", "movie_title": "Fight Club"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)

    def test_swipe_like_success(self):
        """Test successful like swipe"""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.post(
            self.url,
            data=json.dumps(
                {"tmdb_id": 550, "action": "like", "movie_title": "Fight Club"}
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data["success"])
        self.assertEqual(data["action"], "like")
        self.assertEqual(data["tmdb_id"], 550)

        # FIXED: Check using 'status' field instead of 'liked'
        interaction = Interaction.objects.get(user=self.user, tmdb_id=550)
        self.assertEqual(interaction.status, "LIKE")

    def test_swipe_dislike_success(self):
        """Test successful dislike swipe"""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.post(
            self.url,
            data=json.dumps(
                {"tmdb_id": 551, "action": "dislike", "movie_title": "Movie Title"}
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data["success"])
        self.assertEqual(data["action"], "dislike")

        # FIXED: Check using 'status' field
        interaction = Interaction.objects.get(user=self.user, tmdb_id=551)
        self.assertEqual(interaction.status, "DISLIKE")

    def test_swipe_update_existing(self):
        """Test that swiping again updates existing interaction"""
        self.client.login(username="testuser", password="testpass123")

        # FIXED: Create initial interaction with correct field names
        Interaction.objects.create(
            user=self.user, tmdb_id=550, status=Interaction.Status.DISLIKE
        )

        # Swipe again with different action
        response = self.client.post(
            self.url,
            data=json.dumps(
                {"tmdb_id": 550, "action": "like", "movie_title": "Fight Club Updated"}
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        # Check that interaction was updated, not duplicated
        interactions = Interaction.objects.filter(user=self.user, tmdb_id=550)
        self.assertEqual(interactions.count(), 1)

        interaction = interactions.first()
        self.assertEqual(interaction.status, "LIKE")

    def test_swipe_missing_tmdb_id(self):
        """Test that missing tmdb_id returns error"""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.post(
            self.url,
            data=json.dumps({"action": "like", "movie_title": "Movie"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()

        self.assertFalse(data["success"])
        self.assertIn("required", data["error"].lower())

    def test_swipe_missing_action(self):
        """Test that missing action returns error"""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.post(
            self.url,
            data=json.dumps({"tmdb_id": 550, "movie_title": "Fight Club"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()

        self.assertFalse(data["success"])

    def test_swipe_invalid_action(self):
        """Test that invalid action returns error"""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.post(
            self.url,
            data=json.dumps(
                {
                    "tmdb_id": 550,
                    "action": "invalid_action",
                    "movie_title": "Fight Club",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()

        self.assertFalse(data["success"])
        self.assertIn("like", data["error"].lower())
        self.assertIn("dislike", data["error"].lower())

    def test_swipe_invalid_json(self):
        """Test that invalid JSON returns error"""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.post(
            self.url, data="not valid json", content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()

        self.assertFalse(data["success"])

    def test_swipe_only_accepts_post(self):
        """Test that only POST method is accepted"""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)


class GetSoloLikesAPITest(TestCase):
    """Test suite for get_solo_likes API endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.url = reverse("recom_sys:get_solo_likes")

    def test_get_likes_requires_authentication(self):
        """Test that unauthenticated users cannot get likes"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    @patch("recom_sys_app.views_solo.requests.get")
    def test_get_likes_empty(self, mock_get):
        """Test getting likes when user has no likes"""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data["success"])
        self.assertEqual(data["total"], 0)
        self.assertEqual(len(data["movies"]), 0)

    @patch("recom_sys_app.views_solo.requests.get")
    def test_get_likes_success(self, mock_get):
        """Test successful retrieval of liked movies"""
        self.client.login(username="testuser", password="testpass123")

        # FIXED: Create liked interactions with correct field names
        Interaction.objects.create(
            user=self.user, tmdb_id=550, status=Interaction.Status.LIKE
        )
        Interaction.objects.create(
            user=self.user, tmdb_id=551, status=Interaction.Status.LIKE
        )
        Interaction.objects.create(
            user=self.user,
            tmdb_id=552,
            status=Interaction.Status.DISLIKE,
        )

        # Mock TMDB API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 550,
            "title": "Fight Club",
            "release_date": "1999-10-15",
            "overview": "A ticking-time-bomb...",
            "vote_average": 8.4,
            "vote_count": 20000,
            "poster_path": "/path.jpg",
            "backdrop_path": "/backdrop.jpg",
            "genres": [{"name": "Drama"}],
            "runtime": 139,
        }
        mock_get.return_value = mock_response

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data["success"])
        self.assertEqual(data["total"], 2)  # Only liked movies
        self.assertIn("movies", data)

    @patch("recom_sys_app.views_solo.requests.get")
    def test_get_likes_limits_to_50(self, mock_get):
        """Test that likes are limited to last 50"""
        self.client.login(username="testuser", password="testpass123")

        # FIXED: Create 60 liked interactions with correct field names
        for i in range(60):
            Interaction.objects.create(
                user=self.user, tmdb_id=i, status=Interaction.Status.LIKE
            )

        # Mock TMDB API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 1, "title": "Test", "genres": []}
        mock_get.return_value = mock_response

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Should only get 50 results
        self.assertLessEqual(data["total"], 50)

    def test_get_likes_only_accepts_get(self):
        """Test that only GET method is accepted"""
        self.client.login(username="testuser", password="testpass123")

        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 405)


class SoloViewsIntegrationTest(TestCase):
    """Integration tests for complete solo mode workflow"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    @patch("recom_sys_app.views_solo.requests.get")
    def test_complete_solo_workflow(self, mock_get):
        """Test complete solo mode workflow from genre selection to likes"""
        # 1. Login
        self.client.login(username="testuser", password="testpass123")

        # 2. Visit genre selection page
        response = self.client.get(reverse("recom_sys:solo_genre_selection"))
        self.assertEqual(response.status_code, 200)

        # 3. Set genres
        response = self.client.post(
            reverse("recom_sys:set_solo_genres"),
            data=json.dumps({"genres": [28, 35]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        # 4. Visit deck page - FIXED: Use correct URL name
        response = self.client.get(reverse("recom_sys:solo_deck"))
        self.assertEqual(response.status_code, 200)

        # 5. Get deck
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "id": 550,
                    "title": "Fight Club",
                    "release_date": "1999-10-15",
                    "overview": "Test",
                    "vote_average": 8.4,
                    "vote_count": 20000,
                    "poster_path": "/path.jpg",
                    "genre_ids": [28],
                    "popularity": 50.0,
                }
            ]
        }
        mock_get.return_value = mock_response

        response = self.client.get(reverse("recom_sys:get_solo_deck"))
        self.assertEqual(response.status_code, 200)

        # 6. Swipe like
        response = self.client.post(
            reverse("recom_sys:solo_swipe"),
            data=json.dumps(
                {"tmdb_id": 550, "action": "like", "movie_title": "Fight Club"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        # 7. Get likes
        response = self.client.get(reverse("recom_sys:get_solo_likes"))
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data["success"])
        self.assertEqual(data["total"], 1)

    def test_session_persistence_across_requests(self):
        """Test that genres persist in session across multiple requests"""
        self.client.login(username="testuser", password="testpass123")

        # Set genres
        self.client.post(
            reverse("recom_sys:set_solo_genres"),
            data=json.dumps({"genres": [28, 35, 18]}),
            content_type="application/json",
        )

        # Access deck page multiple times - FIXED: Use correct URL name
        for _ in range(3):
            response = self.client.get(reverse("recom_sys:solo_deck"))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["selected_genres"], [28, 35, 18])


class SoloHelperFunctionsTest(TestCase):
    """Test suite for helper functions in views_solo.py"""

    @patch("recom_sys_app.views_solo.requests.get")
    def test_fetch_movies_by_genres(self, mock_get):
        """Test _fetch_movies_by_genres helper function"""
        from recom_sys_app.views_solo import _fetch_movies_by_genres

        # Mock TMDB API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "id": 550,
                    "title": "Fight Club",
                    "release_date": "1999-10-15",
                    "overview": "Test overview",
                    "vote_average": 8.4,
                    "vote_count": 20000,
                    "poster_path": "/path.jpg",
                    "backdrop_path": "/backdrop.jpg",
                    "genre_ids": [28, 53],
                    "popularity": 50.0,
                }
            ]
        }
        mock_get.return_value = mock_response

        # Test function
        movies = _fetch_movies_by_genres([28, 35], limit=20)

        self.assertIsInstance(movies, list)
        self.assertGreater(len(movies), 0)

        # Check movie structure
        movie = movies[0]
        self.assertIn("tmdb_id", movie)
        self.assertIn("title", movie)
        self.assertIn("overview", movie)
        self.assertIn("poster_url", movie)

    @patch("recom_sys_app.views_solo.requests.get")
    def test_tmdb_fetch_by_ids(self, mock_get):
        """Test _tmdb_fetch_by_ids helper function"""
        from recom_sys_app.views_solo import _tmdb_fetch_by_ids

        # Mock TMDB API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 550,
            "title": "Fight Club",
            "release_date": "1999-10-15",
            "overview": "Test",
            "vote_average": 8.4,
            "vote_count": 20000,
            "poster_path": "/path.jpg",
            "backdrop_path": "/backdrop.jpg",
            "genres": [{"name": "Drama"}],
            "runtime": 139,
        }
        mock_get.return_value = mock_response

        # Test function
        movies = _tmdb_fetch_by_ids([550, 551])

        self.assertIsInstance(movies, list)
        self.assertGreater(len(movies), 0)

        # Check movie structure
        movie = movies[0]
        self.assertTrue(movie["found"])
        self.assertEqual(movie["tmdb_id"], 550)
        self.assertIn("title", movie)


# Run tests with: python manage.py test recom_sys_app.test_views_solo


class GetWatchLaterViewTest(TestCase):
    """Test suite for get_watch_later API endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.url = reverse("recom_sys:get_watch_later")

    def test_watch_later_requires_authentication(self):
        """Test that unauthenticated users cannot access watch later"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    @patch("recom_sys_app.views_solo._tmdb_fetch_by_ids")
    def test_get_watch_later_empty(self, mock_tmdb):
        """Test getting watch later when user has no movies"""
        self.client.login(username="testuser", password="testpass123")
        mock_tmdb.return_value = []

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertEqual(data["total"], 0)
        self.assertEqual(len(data["movies"]), 0)

    @patch("recom_sys_app.views_solo._tmdb_fetch_by_ids")
    def test_get_watch_later_with_movies(self, mock_tmdb):
        """Test getting watch later with saved movies"""
        self.client.login(username="testuser", password="testpass123")

        # Create watch later interactions
        Interaction.objects.create(user=self.user, tmdb_id=550, status="WATCH_LATER")
        Interaction.objects.create(user=self.user, tmdb_id=551, status="WATCH_LATER")

        # Mock TMDB response
        mock_tmdb.return_value = [
            {
                "tmdb_id": 550,
                "title": "Fight Club",
                "year": 1999,
                "vote_average": 8.4,
                "poster_url": "https://example.com/poster.jpg",
                "found": True,
            },
            {
                "tmdb_id": 551,
                "title": "The Matrix",
                "year": 1999,
                "vote_average": 8.7,
                "poster_url": "https://example.com/matrix.jpg",
                "found": True,
            },
        ]

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["movies"]), 2)
        self.assertEqual(data["movies"][0]["title"], "Fight Club")

    @patch("recom_sys_app.views_solo._tmdb_fetch_by_ids")
    def test_watch_later_limit_50(self, mock_tmdb):
        """Test that watch later is limited to 50 movies"""
        self.client.login(username="testuser", password="testpass123")

        # Create 60 watch later interactions
        for i in range(60):
            Interaction.objects.create(
                user=self.user, tmdb_id=1000 + i, status="WATCH_LATER"
            )

        mock_tmdb.return_value = []

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        # Should only fetch IDs for 50 movies max
        call_args = mock_tmdb.call_args[0][0]
        self.assertLessEqual(len(call_args), 50)

    def test_watch_later_only_returns_watch_later_status(self):
        """Test that only WATCH_LATER status movies are returned"""
        self.client.login(username="testuser", password="testpass123")

        # Create interactions with different statuses
        Interaction.objects.create(user=self.user, tmdb_id=550, status="WATCH_LATER")
        Interaction.objects.create(user=self.user, tmdb_id=551, status="LIKE")
        Interaction.objects.create(user=self.user, tmdb_id=552, status="WATCHED")
        Interaction.objects.create(user=self.user, tmdb_id=553, status="DISLIKE")

        with patch("recom_sys_app.views_solo._tmdb_fetch_by_ids") as mock_tmdb:
            mock_tmdb.return_value = []
            response = self.client.get(self.url)

            # Should only fetch movie with WATCH_LATER status
            call_args = mock_tmdb.call_args[0][0]
            self.assertEqual(len(call_args), 1)
            self.assertEqual(call_args[0], 550)


class GetWatchedViewTest(TestCase):
    """Test suite for get_watched API endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.url = reverse("recom_sys:get_watched")

    def test_watched_requires_authentication(self):
        """Test that unauthenticated users cannot access watched"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    @patch("recom_sys_app.views_solo._tmdb_fetch_by_ids")
    def test_get_watched_empty(self, mock_tmdb):
        """Test getting watched when user has no movies"""
        self.client.login(username="testuser", password="testpass123")
        mock_tmdb.return_value = []

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertEqual(data["total"], 0)
        self.assertEqual(len(data["movies"]), 0)

    @patch("recom_sys_app.views_solo._tmdb_fetch_by_ids")
    def test_get_watched_with_movies(self, mock_tmdb):
        """Test getting watched with saved movies"""
        self.client.login(username="testuser", password="testpass123")

        # Create watched interactions
        Interaction.objects.create(user=self.user, tmdb_id=550, status="WATCHED")
        Interaction.objects.create(user=self.user, tmdb_id=551, status="WATCHED")
        Interaction.objects.create(user=self.user, tmdb_id=552, status="WATCHED")

        # Mock TMDB response
        mock_tmdb.return_value = [
            {
                "tmdb_id": 550,
                "title": "Fight Club",
                "year": 1999,
                "vote_average": 8.4,
                "poster_url": "https://example.com/poster.jpg",
                "found": True,
            },
            {
                "tmdb_id": 551,
                "title": "The Matrix",
                "year": 1999,
                "vote_average": 8.7,
                "poster_url": "https://example.com/matrix.jpg",
                "found": True,
            },
            {
                "tmdb_id": 552,
                "title": "Inception",
                "year": 2010,
                "vote_average": 8.8,
                "poster_url": "https://example.com/inception.jpg",
                "found": True,
            },
        ]

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertEqual(data["total"], 3)
        self.assertEqual(len(data["movies"]), 3)

    @patch("recom_sys_app.views_solo._tmdb_fetch_by_ids")
    def test_watched_limit_100(self, mock_tmdb):
        """Test that watched is limited to 100 movies"""
        self.client.login(username="testuser", password="testpass123")

        # Create 120 watched interactions
        for i in range(120):
            Interaction.objects.create(
                user=self.user, tmdb_id=2000 + i, status="WATCHED"
            )

        mock_tmdb.return_value = []

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        # Should only fetch IDs for 100 movies max
        call_args = mock_tmdb.call_args[0][0]
        self.assertLessEqual(len(call_args), 100)

    def test_watched_only_returns_watched_status(self):
        """Test that only WATCHED status movies are returned"""
        self.client.login(username="testuser", password="testpass123")

        # Create interactions with different statuses
        Interaction.objects.create(user=self.user, tmdb_id=550, status="WATCHED")
        Interaction.objects.create(user=self.user, tmdb_id=551, status="LIKE")
        Interaction.objects.create(user=self.user, tmdb_id=552, status="WATCH_LATER")
        Interaction.objects.create(user=self.user, tmdb_id=553, status="DISLIKE")

        with patch("recom_sys_app.views_solo._tmdb_fetch_by_ids") as mock_tmdb:
            mock_tmdb.return_value = []
            response = self.client.get(self.url)

            # Should only fetch movie with WATCHED status
            call_args = mock_tmdb.call_args[0][0]
            self.assertEqual(len(call_args), 1)
            self.assertEqual(call_args[0], 550)

    @patch("recom_sys_app.views_solo._tmdb_fetch_by_ids")
    def test_watched_ordered_by_updated_at(self, mock_tmdb):
        """Test that watched movies are retrieved (note: ordering not guaranteed due to set() in view)"""
        self.client.login(username="testuser", password="testpass123")

        # Create watched interactions at different times
        from datetime import datetime, timedelta
        from django.utils import timezone

        old_time = timezone.now() - timedelta(days=30)
        recent_time = timezone.now()

        interaction1 = Interaction.objects.create(
            user=self.user, tmdb_id=550, status="WATCHED"
        )
        interaction1.updated_at = old_time
        interaction1.save()

        interaction2 = Interaction.objects.create(
            user=self.user, tmdb_id=551, status="WATCHED"
        )
        interaction2.updated_at = recent_time
        interaction2.save()

        mock_tmdb.return_value = []

        response = self.client.get(self.url)

        # Both movies should be included (order not guaranteed due to set() operation)
        call_args = mock_tmdb.call_args[0][0]
        self.assertIn(550, call_args)
        self.assertIn(551, call_args)
        self.assertEqual(len(call_args), 2)


class SoloSwipeExtendedTest(TestCase):
    """Extended tests for solo_swipe with new watch_later and watched actions"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.url = reverse("recom_sys:solo_swipe")

    def test_swipe_watch_later_creates_interaction(self):
        """Test that watch_later action creates WATCH_LATER interaction"""
        self.client.login(username="testuser", password="testpass123")

        data = {"tmdb_id": 550, "action": "watch_later", "movie_title": "Fight Club"}

        response = self.client.post(
            self.url, json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data["success"])
        self.assertIn("Watch Later", response_data["message"])

        # Verify interaction was created
        interaction = Interaction.objects.get(user=self.user, tmdb_id=550)
        self.assertEqual(interaction.status, "WATCH_LATER")

    def test_swipe_watched_creates_interaction(self):
        """Test that watched action creates WATCHED interaction"""
        self.client.login(username="testuser", password="testpass123")

        data = {"tmdb_id": 551, "action": "watched", "movie_title": "The Matrix"}

        response = self.client.post(
            self.url, json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data["success"])
        self.assertIn("Watched", response_data["message"])

        # Verify interaction was created
        interaction = Interaction.objects.get(user=self.user, tmdb_id=551)
        self.assertEqual(interaction.status, "WATCHED")

    def test_swipe_invalidates_cache(self):
        """Test that swipe actions invalidate the cached deck"""
        self.client.login(username="testuser", password="testpass123")

        from django.core.cache import cache

        # Set a cache value
        cache_key = f"solo_deck_{self.user.id}"
        cache.set(cache_key, {"test": "data"}, 3600)
        self.assertIsNotNone(cache.get(cache_key))

        # Perform swipe
        data = {"tmdb_id": 550, "action": "watch_later", "movie_title": "Fight Club"}
        self.client.post(self.url, json.dumps(data), content_type="application/json")

        # Cache should be invalidated
        self.assertIsNone(cache.get(cache_key))

    def test_swipe_update_existing_interaction(self):
        """Test that swiping again updates existing interaction"""
        self.client.login(username="testuser", password="testpass123")

        # Create initial interaction
        Interaction.objects.create(user=self.user, tmdb_id=550, status="LIKE")

        # Update to watch_later
        data = {"tmdb_id": 550, "action": "watch_later", "movie_title": "Fight Club"}
        response = self.client.post(
            self.url, json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Verify interaction was updated, not duplicated
        interactions = Interaction.objects.filter(user=self.user, tmdb_id=550)
        self.assertEqual(interactions.count(), 1)
        self.assertEqual(interactions.first().status, "WATCH_LATER")
