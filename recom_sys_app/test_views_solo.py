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
        self.assertEqual(interaction.status, "like")

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
        self.assertEqual(interaction.status, "dislike")

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
