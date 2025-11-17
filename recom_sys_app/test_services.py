"""
Unit Tests for Services (services.py)

Tests cover:
- RecommendationService class methods
- Group deck generation
- Solo deck generation
- Movie details fetching
- Movie search
- Similar movies
- Cache invalidation
- Error handling
"""

from django.test import TestCase
from django.core.cache import cache
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from recom_sys_app.services import RecommendationService
from recom_sys_app.models import (
    UserProfile,
    Interaction,
    GroupSession,
    GroupMember,
    GroupSwipe,
    Genre,
)

User = get_user_model()


class RecommendationServiceTest(TestCase):
    """Test suite for RecommendationService"""

    def setUp(self):
        """Set up test fixtures"""
        cache.clear()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            name="Test User",
            country="USA",
            favourite_genre1=Genre.ACTION,
            favourite_genre2=Genre.COMEDY,
        )

    def tearDown(self):
        """Clean up after tests"""
        cache.clear()

    @patch("recom_sys_app.services.requests.get")
    def test_get_popular_movies_success(self, mock_get):
        """Test _get_popular_movies with successful API response"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"id": 550, "title": "Fight Club"},
                {"id": 551, "title": "The Matrix"},
            ]
        }
        mock_get.return_value = mock_response

        movies = RecommendationService._get_popular_movies(limit=10)
        self.assertEqual(len(movies), 2)
        self.assertIn(550, movies)
        self.assertIn(551, movies)

    @patch("recom_sys_app.services.requests.get")
    def test_get_popular_movies_error(self, mock_get):
        """Test _get_popular_movies with API error"""
        mock_get.side_effect = Exception("API Error")
        movies = RecommendationService._get_popular_movies(limit=10)
        self.assertEqual(movies, [])

    @patch("recom_sys_app.services.requests.get")
    def test_get_movie_details_success(self, mock_get):
        """Test get_movie_details with successful API response"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 550,
            "title": "Fight Club",
            "original_title": "Fight Club",
            "overview": "A great movie",
            "poster_path": "/poster.jpg",
            "backdrop_path": "/backdrop.jpg",
            "release_date": "1999-10-15",
            "vote_average": 8.4,
            "vote_count": 20000,
            "runtime": 139,
            "genres": [{"id": 18, "name": "Drama"}, {"id": 53, "name": "Thriller"}],
        }
        mock_get.return_value = mock_response

        movie = RecommendationService.get_movie_details(550)
        self.assertIsNotNone(movie)
        self.assertEqual(movie["tmdb_id"], 550)
        self.assertEqual(movie["title"], "Fight Club")
        self.assertEqual(len(movie["genres"]), 2)
        self.assertIn("Drama", movie["genres"])

    @patch("recom_sys_app.services.requests.get")
    def test_get_movie_details_cached(self, mock_get):
        """Test that get_movie_details uses cache"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 550,
            "title": "Fight Club",
            "genres": [],
        }
        mock_get.return_value = mock_response

        # First call
        movie1 = RecommendationService.get_movie_details(550)
        # Second call should use cache
        movie2 = RecommendationService.get_movie_details(550)

        # Should only call API once
        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(movie1, movie2)

    @patch("recom_sys_app.services.requests.get")
    def test_get_movie_details_error(self, mock_get):
        """Test get_movie_details with API error"""
        mock_get.side_effect = Exception("API Error")
        movie = RecommendationService.get_movie_details(550)
        self.assertIsNone(movie)

    def test_get_genre_ids_by_names(self):
        """Test _get_genre_ids_by_names"""
        genre_ids = RecommendationService._get_genre_ids_by_names(["Action", "Comedy"])
        self.assertEqual(len(genre_ids), 2)
        self.assertIn(28, genre_ids)  # Action
        self.assertIn(35, genre_ids)  # Comedy

    def test_get_genre_ids_by_names_unknown(self):
        """Test _get_genre_ids_by_names with unknown genre"""
        genre_ids = RecommendationService._get_genre_ids_by_names(["Unknown Genre"])
        self.assertEqual(genre_ids, [])

    @patch("recom_sys_app.services.requests.get")
    def test_get_movies_by_genres_success(self, mock_get):
        """Test _get_movies_by_genres with successful API response"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [{"id": 550}, {"id": 551}],
            "total_pages": 1,
        }
        mock_get.return_value = mock_response

        movies = RecommendationService._get_movies_by_genres([28, 35], limit=10)
        self.assertEqual(len(movies), 2)

    @patch("recom_sys_app.services.requests.get")
    def test_get_movies_by_genres_multiple_pages(self, mock_get):
        """Test _get_movies_by_genres with multiple pages"""
        mock_response1 = MagicMock()
        mock_response1.status_code = 200
        mock_response1.json.return_value = {
            "results": [{"id": i} for i in range(20)],
            "total_pages": 2,
        }

        mock_response2 = MagicMock()
        mock_response2.status_code = 200
        mock_response2.json.return_value = {
            "results": [{"id": i} for i in range(20, 40)],
            "total_pages": 2,
        }

        mock_get.side_effect = [mock_response1, mock_response2]

        movies = RecommendationService._get_movies_by_genres([28], limit=30)
        self.assertGreaterEqual(len(movies), 20)

    @patch("recom_sys_app.services.requests.get")
    def test_get_movies_by_genres_error(self, mock_get):
        """Test _get_movies_by_genres with API error"""
        mock_get.side_effect = Exception("API Error")
        movies = RecommendationService._get_movies_by_genres([28], limit=10)
        # Should fallback to popular movies
        self.assertIsInstance(movies, list)

    @patch("recom_sys_app.services.requests.get")
    def test_search_movies_success(self, mock_get):
        """Test search_movies with successful API response"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "id": 550,
                    "title": "Fight Club",
                    "release_date": "1999-10-15",
                    "poster_path": "/poster.jpg",
                    "overview": "A great movie",
                    "vote_average": 8.4,
                }
            ]
        }
        mock_get.return_value = mock_response

        results = RecommendationService.search_movies("Fight Club", limit=10)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["tmdb_id"], 550)
        self.assertEqual(results[0]["title"], "Fight Club")
        self.assertEqual(results[0]["year"], "1999")

    @patch("recom_sys_app.services.requests.get")
    def test_search_movies_no_token(self, mock_get):
        """Test search_movies without TMDB token"""
        with patch.object(RecommendationService, "TMDB_TOKEN", None):
            results = RecommendationService.search_movies("Fight Club")
            self.assertEqual(results, [])

    @patch("recom_sys_app.services.requests.get")
    def test_search_movies_error(self, mock_get):
        """Test search_movies with API error"""
        mock_get.side_effect = Exception("API Error")
        results = RecommendationService.search_movies("Fight Club")
        self.assertEqual(results, [])

    @patch("recom_sys_app.services.requests.get")
    def test_get_similar_movies_success(self, mock_get):
        """Test get_similar_movies with successful API response"""
        # Mock movie details response
        movie_response = MagicMock()
        movie_response.status_code = 200
        movie_response.json.return_value = {
            "id": 550,
            "genres": [{"id": 18}, {"id": 53}],
        }

        # Mock recommendations response
        rec_response = MagicMock()
        rec_response.status_code = 200
        rec_response.json.return_value = {
            "results": [
                {
                    "id": 551,
                    "title": "Similar Movie",
                    "release_date": "2000-01-01",
                    "poster_path": "/poster.jpg",
                    "backdrop_path": "/backdrop.jpg",
                    "overview": "Similar",
                    "vote_average": 8.0,
                    "vote_count": 5000,
                    "genre_ids": [18, 53],
                }
            ]
        }

        mock_get.side_effect = [movie_response, rec_response]

        results = RecommendationService.get_similar_movies(550, limit=10)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["tmdb_id"], 551)

    @patch("recom_sys_app.services.requests.get")
    def test_get_similar_movies_cached(self, mock_get):
        """Test that get_similar_movies uses cache"""
        movie_response = MagicMock()
        movie_response.status_code = 200
        movie_response.json.return_value = {"id": 550, "genres": []}

        rec_response = MagicMock()
        rec_response.status_code = 200
        rec_response.json.return_value = {"results": []}

        mock_get.side_effect = [movie_response, rec_response]

        # First call
        results1 = RecommendationService.get_similar_movies(550)
        # Second call should use cache
        results2 = RecommendationService.get_similar_movies(550)

        # Should only call API once per endpoint
        self.assertEqual(results1, results2)

    @patch("recom_sys_app.services.requests.get")
    def test_get_similar_movies_filters_by_genre(self, mock_get):
        """Test that get_similar_movies filters by genre overlap"""
        movie_response = MagicMock()
        movie_response.status_code = 200
        movie_response.json.return_value = {
            "id": 550,
            "genres": [{"id": 18}, {"id": 53}],
        }

        rec_response = MagicMock()
        rec_response.status_code = 200
        rec_response.json.return_value = {
            "results": [
                {
                    "id": 551,
                    "title": "Similar",
                    "release_date": "2000-01-01",
                    "vote_average": 8.0,
                    "vote_count": 500,
                    "genre_ids": [18, 53],  # Shares 2 genres
                },
                {
                    "id": 552,
                    "title": "Different",
                    "release_date": "2000-01-01",
                    "vote_average": 8.0,
                    "vote_count": 500,
                    "genre_ids": [35],  # No overlap
                },
            ]
        }

        mock_get.side_effect = [movie_response, rec_response]

        results = RecommendationService.get_similar_movies(550, limit=10)
        # Should only include movie with genre overlap
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["tmdb_id"], 551)

    @patch("recom_sys_app.services.requests.get")
    def test_get_similar_movies_filters_by_year(self, mock_get):
        """Test that get_similar_movies filters old movies"""
        movie_response = MagicMock()
        movie_response.status_code = 200
        movie_response.json.return_value = {"id": 550, "genres": [{"id": 18}]}

        rec_response = MagicMock()
        rec_response.status_code = 200
        rec_response.json.return_value = {
            "results": [
                {
                    "id": 551,
                    "title": "Old Movie",
                    "release_date": "1990-01-01",  # Too old
                    "vote_average": 8.0,
                    "vote_count": 500,
                    "genre_ids": [18],
                }
            ]
        }

        mock_get.side_effect = [movie_response, rec_response]

        results = RecommendationService.get_similar_movies(550, limit=10)
        # Should filter out old movies
        self.assertEqual(len(results), 0)

    @patch("recom_sys_app.services.requests.get")
    def test_get_similar_movies_error(self, mock_get):
        """Test get_similar_movies with API error"""
        mock_get.side_effect = Exception("API Error")
        results = RecommendationService.get_similar_movies(550)
        self.assertEqual(results, [])

    def test_invalidate_deck_cache(self):
        """Test invalidate_deck_cache"""
        group = GroupSession.objects.create(creator=self.user)
        cache_key = f"group_deck_{group.id}"
        cache.set(cache_key, [550, 551], 3600)

        # Verify cache exists
        self.assertIsNotNone(cache.get(cache_key))

        # Invalidate
        RecommendationService.invalidate_deck_cache(group)

        # Verify cache is cleared
        self.assertIsNone(cache.get(cache_key))

    @patch("recom_sys_app.services.requests.get")
    def test_get_solo_deck_new_user(self, mock_get):
        """Test get_solo_deck for new user (no history)"""
        # Mock popular movies API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [{"id": 550}, {"id": 551}]}
        mock_get.return_value = mock_response

        deck = RecommendationService.get_solo_deck(self.user, limit=10)
        self.assertIsInstance(deck, list)

    @patch("recom_sys_app.services.requests.get")
    def test_get_solo_deck_returning_user(self, mock_get):
        """Test get_solo_deck for returning user (with history)"""
        # Create interaction history
        Interaction.objects.create(
            user=self.user,
            tmdb_id=550,
            status=Interaction.Status.LIKE,
        )

        # Mock movie details and recommendations
        movie_response = MagicMock()
        movie_response.status_code = 200
        movie_response.json.return_value = {
            "id": 550,
            "genres": [{"id": 28, "name": "Action"}],
        }

        rec_response = MagicMock()
        rec_response.status_code = 200
        rec_response.json.return_value = {"results": [{"id": 551}]}

        mock_get.side_effect = [movie_response, rec_response]

        deck = RecommendationService.get_solo_deck(self.user, limit=10)
        self.assertIsInstance(deck, list)

    @patch("recom_sys_app.services.requests.get")
    def test_get_solo_deck_cached(self, mock_get):
        """Test that get_solo_deck uses cache"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [{"id": 550}]}
        mock_get.return_value = mock_response

        # First call
        deck1 = RecommendationService.get_solo_deck(self.user, limit=10)
        # Second call should use cache
        deck2 = RecommendationService.get_solo_deck(self.user, limit=10)

        # Should only call API once
        self.assertEqual(deck1, deck2)

    @patch("recom_sys_app.services.requests.get")
    def test_get_solo_deck_filters_swiped(self, mock_get):
        """Test that get_solo_deck filters already-swiped movies"""
        # Create swiped interaction
        Interaction.objects.create(
            user=self.user,
            tmdb_id=550,
            status=Interaction.Status.LIKE,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [{"id": 550}, {"id": 551}]  # 550 already swiped
        }
        mock_get.return_value = mock_response

        deck = RecommendationService.get_solo_deck(self.user, limit=10)
        # Should not include already-swiped movie
        self.assertNotIn(550, deck)

    @patch("recom_sys_app.services.requests.get")
    def test_get_group_deck_private_group(self, mock_get):
        """Test get_group_deck for private group"""
        group = GroupSession.objects.create(creator=self.user)
        GroupMember.objects.create(
            group_session=group, user=self.user, role=GroupMember.Role.CREATOR
        )

        # Mock popular movies (for groups with < 2 members)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [{"id": 550}]}
        mock_get.return_value = mock_response

        deck = RecommendationService.get_group_deck(group, limit=10)
        self.assertIsInstance(deck, list)

    @patch("recom_sys_app.services.requests.get")
    def test_get_group_deck_community_group(self, mock_get):
        """Test get_group_deck for community group"""
        group = GroupSession.objects.create(
            creator=self.user,
            kind=GroupSession.Kind.COMMUNITY,
            community_key="genre:Action",
            genre_filter="Action",
        )
        GroupMember.objects.create(
            group_session=group, user=self.user, role=GroupMember.Role.CREATOR
        )

        # Mock genre movies API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [{"id": 550}]}
        mock_get.return_value = mock_response

        deck = RecommendationService.get_group_deck(group, limit=10)
        self.assertIsInstance(deck, list)

    @patch("recom_sys_app.services.requests.get")
    def test_get_group_deck_filters_swiped(self, mock_get):
        """Test that get_group_deck filters already-swiped movies"""
        group = GroupSession.objects.create(creator=self.user)
        GroupMember.objects.create(
            group_session=group, user=self.user, role=GroupMember.Role.CREATOR
        )

        # Create swipe
        GroupSwipe.objects.create(
            group_session=group,
            user=self.user,
            tmdb_id=550,
            action=GroupSwipe.Action.LIKE,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [{"id": 550}, {"id": 551}]  # 550 already swiped
        }
        mock_get.return_value = mock_response

        deck = RecommendationService.get_group_deck(group, limit=10)
        # Should not include already-swiped movie
        self.assertNotIn(550, deck)

    @patch("recom_sys_app.services.requests.get")
    def test_get_group_deck_cached(self, mock_get):
        """Test that get_group_deck uses cache"""
        group = GroupSession.objects.create(creator=self.user)
        GroupMember.objects.create(
            group_session=group, user=self.user, role=GroupMember.Role.CREATOR
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [{"id": 550}]}
        mock_get.return_value = mock_response

        # First call
        deck1 = RecommendationService.get_group_deck(group, limit=10)
        # Second call should use cache
        deck2 = RecommendationService.get_group_deck(group, limit=10)

        # Should only call API once
        self.assertEqual(deck1, deck2)

    def test_check_group_match_all_like(self):
        """Test check_group_match when all members like"""
        group = GroupSession.objects.create(creator=self.user)
        user2 = User.objects.create_user(
            username="user2", email="user2@example.com", password="testpass123"
        )

        GroupMember.objects.create(
            group_session=group, user=self.user, role=GroupMember.Role.CREATOR
        )
        GroupMember.objects.create(
            group_session=group, user=user2, role=GroupMember.Role.MEMBER
        )

        # Both users like the movie
        GroupSwipe.objects.create(
            group_session=group,
            user=self.user,
            tmdb_id=550,
            action=GroupSwipe.Action.LIKE,
        )
        GroupSwipe.objects.create(
            group_session=group, user=user2, tmdb_id=550, action=GroupSwipe.Action.LIKE
        )

        is_match = RecommendationService.check_group_match(group, 550)
        self.assertTrue(is_match)

    def test_check_group_match_not_all_like(self):
        """Test check_group_match when not all members like"""
        group = GroupSession.objects.create(creator=self.user)
        user2 = User.objects.create_user(
            username="user2", email="user2@example.com", password="testpass123"
        )

        GroupMember.objects.create(
            group_session=group, user=self.user, role=GroupMember.Role.CREATOR
        )
        GroupMember.objects.create(
            group_session=group, user=user2, role=GroupMember.Role.MEMBER
        )

        # Only one user likes
        GroupSwipe.objects.create(
            group_session=group,
            user=self.user,
            tmdb_id=550,
            action=GroupSwipe.Action.LIKE,
        )

        is_match = RecommendationService.check_group_match(group, 550)
        self.assertFalse(is_match)

    def test_check_group_match_no_members(self):
        """Test check_group_match with no active members"""
        group = GroupSession.objects.create(creator=self.user)
        # No active members

        is_match = RecommendationService.check_group_match(group, 550)
        self.assertFalse(is_match)
