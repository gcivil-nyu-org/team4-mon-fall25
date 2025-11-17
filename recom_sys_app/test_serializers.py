"""
Unit Tests for Serializers (serializers.py)

Tests cover:
- All serializer classes and their fields
- Validation logic
- Create/update operations
- Read-only fields
- Nested serializers
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from recom_sys_app.serializers import (
    UserSerializer,
    UserProfileSerializer,
    UserProfileUpdateSerializer,
    InteractionSerializer,
    InteractionCreateUpdateSerializer,
    UserRegistrationSerializer,
    MovieRecommendationSerializer,
    RecommendationResponseSerializer,
)
from recom_sys_app.models import UserProfile, Interaction, Sex, Genre
from datetime import date

User = get_user_model()


class UserSerializerTest(TestCase):
    """Test suite for UserSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
        )

    def test_serializer_fields(self):
        """Test that serializer has correct fields"""
        serializer = UserSerializer(instance=self.user)
        data = serializer.data
        expected_fields = ["id", "username", "email", "first_name", "last_name", "date_joined"]
        for field in expected_fields:
            self.assertIn(field, data)

    def test_serializer_read_only_fields(self):
        """Test that read-only fields cannot be written"""
        serializer = UserSerializer(
            instance=self.user,
            data={"id": 999, "date_joined": "2020-01-01"},
            partial=True,
        )
        # Read-only fields should be ignored during validation
        self.assertTrue(serializer.is_valid())

    def test_serializer_data(self):
        """Test serializer output data"""
        serializer = UserSerializer(instance=self.user)
        data = serializer.data
        self.assertEqual(data["username"], "testuser")
        self.assertEqual(data["email"], "test@example.com")
        self.assertEqual(data["first_name"], "Test")
        self.assertEqual(data["last_name"], "User")


class UserProfileSerializerTest(TestCase):
    """Test suite for UserProfileSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            name="Test User",
            sex=Sex.MALE,
            age=25,
            country="USA",
            favourite_genre1=Genre.ACTION,
            favourite_genre2=Genre.COMEDY,
        )

    def test_serializer_fields(self):
        """Test that serializer has all expected fields"""
        serializer = UserProfileSerializer(instance=self.profile)
        data = serializer.data
        expected_fields = [
            "id",
            "user",
            "name",
            "sex",
            "age",
            "date_of_birth",
            "computed_age",
            "country",
            "favourite_genre1",
            "favourite_genre2",
            "liked_g1_tmdb_id",
            "liked_g1_title",
            "liked_g2_tmdb_id",
            "liked_g2_title",
            "language",
            "timezone",
            "onboarding_complete",
            "created_at",
            "updated_at",
        ]
        for field in expected_fields:
            self.assertIn(field, data)

    def test_serializer_nested_user(self):
        """Test that user field is nested UserSerializer"""
        serializer = UserProfileSerializer(instance=self.profile)
        data = serializer.data
        self.assertIsInstance(data["user"], dict)
        self.assertIn("username", data["user"])
        self.assertIn("email", data["user"])

    def test_serializer_computed_age(self):
        """Test computed_age field"""
        serializer = UserProfileSerializer(instance=self.profile)
        data = serializer.data
        self.assertIn("computed_age", data)

    def test_serializer_computed_age_with_dob(self):
        """Test computed_age when date_of_birth is set"""
        self.profile.date_of_birth = date(1995, 1, 1)
        self.profile.save()
        serializer = UserProfileSerializer(instance=self.profile)
        data = serializer.data
        self.assertIsNotNone(data["computed_age"])
        self.assertIsInstance(data["computed_age"], int)

    def test_serializer_read_only_fields(self):
        """Test that read-only fields are marked correctly"""
        serializer = UserProfileSerializer(
            instance=self.profile,
            data={"id": 999, "user": 999, "computed_age": 99},
            partial=True,
        )
        # Read-only fields should be ignored
        self.assertTrue(serializer.is_valid())


class UserProfileUpdateSerializerTest(TestCase):
    """Test suite for UserProfileUpdateSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.profile = UserProfile.objects.create(
            user=self.user, name="Test User", country="USA"
        )

    def test_serializer_fields(self):
        """Test that serializer has correct fields"""
        serializer = UserProfileUpdateSerializer(instance=self.profile)
        data = serializer.data
        # Should not have id, user, computed_age, created_at, updated_at
        self.assertNotIn("id", data)
        self.assertNotIn("user", data)
        self.assertNotIn("computed_age", data)
        self.assertIn("name", data)
        self.assertIn("sex", data)

    def test_serializer_update(self):
        """Test updating profile with serializer"""
        serializer = UserProfileUpdateSerializer(
            instance=self.profile,
            data={"name": "Updated Name", "age": 30, "sex": Sex.FEMALE},
            partial=True,
        )
        self.assertTrue(serializer.is_valid())
        updated_profile = serializer.save()
        self.assertEqual(updated_profile.name, "Updated Name")
        self.assertEqual(updated_profile.age, 30)
        self.assertEqual(updated_profile.sex, Sex.FEMALE)


class InteractionSerializerTest(TestCase):
    """Test suite for InteractionSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.interaction = Interaction.objects.create(
            user=self.user,
            tmdb_id=550,
            status=Interaction.Status.LIKE,
            rating=8,
            source="solo",
        )

    def test_serializer_fields(self):
        """Test that serializer has all expected fields"""
        serializer = InteractionSerializer(instance=self.interaction)
        data = serializer.data
        expected_fields = [
            "id",
            "user",
            "tmdb_id",
            "status",
            "rating",
            "source",
            "created_at",
            "updated_at",
        ]
        for field in expected_fields:
            self.assertIn(field, data)

    def test_serializer_user_field(self):
        """Test that user field is string representation"""
        serializer = InteractionSerializer(instance=self.interaction)
        data = serializer.data
        self.assertIsInstance(data["user"], str)

    def test_serializer_read_only_fields(self):
        """Test that read-only fields cannot be written"""
        serializer = InteractionSerializer(
            instance=self.interaction,
            data={"id": 999, "user": 999, "created_at": "2020-01-01"},
            partial=True,
        )
        # Read-only fields should be ignored
        self.assertTrue(serializer.is_valid())


class InteractionCreateUpdateSerializerTest(TestCase):
    """Test suite for InteractionCreateUpdateSerializer"""

    def test_serializer_fields(self):
        """Test that serializer has correct fields"""
        serializer = InteractionCreateUpdateSerializer()
        data = serializer.fields
        expected_fields = ["tmdb_id", "status", "rating", "source"]
        for field in expected_fields:
            self.assertIn(field, data)

    def test_serializer_create(self):
        """Test creating interaction with serializer"""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        serializer = InteractionCreateUpdateSerializer(
            data={
                "tmdb_id": 550,
                "status": Interaction.Status.LIKE,
                "rating": 9,
                "source": "solo",
            }
        )
        self.assertTrue(serializer.is_valid())
        interaction = Interaction.objects.create(user=user, **serializer.validated_data)
        self.assertEqual(interaction.tmdb_id, 550)
        self.assertEqual(interaction.status, Interaction.Status.LIKE)
        self.assertEqual(interaction.rating, 9)


class UserRegistrationSerializerTest(TestCase):
    """Test suite for UserRegistrationSerializer"""

    def test_serializer_fields(self):
        """Test that serializer has all expected fields"""
        serializer = UserRegistrationSerializer()
        expected_fields = [
            "username",
            "email",
            "password",
            "password_confirm",
            "name",
            "sex",
            "age",
            "country",
            "favourite_genre1",
            "favourite_genre2",
            "liked_g1_tmdb_id",
            "liked_g1_title",
            "liked_g2_tmdb_id",
            "liked_g2_title",
        ]
        for field in expected_fields:
            self.assertIn(field, serializer.fields)

    def test_serializer_password_min_length(self):
        """Test password minimum length validation"""
        serializer = UserRegistrationSerializer(
            data={
                "username": "testuser",
                "email": "test@example.com",
                "password": "short",
                "password_confirm": "short",
                "name": "Test User",
                "country": "USA",
                "sex": Sex.MALE,
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors)

    def test_serializer_password_mismatch(self):
        """Test password confirmation validation"""
        serializer = UserRegistrationSerializer(
            data={
                "username": "testuser",
                "email": "test@example.com",
                "password": "testpass123",
                "password_confirm": "differentpass",
                "name": "Test User",
                "country": "USA",
                "sex": Sex.MALE,
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors)

    def test_serializer_password_match(self):
        """Test that matching passwords are valid"""
        serializer = UserRegistrationSerializer(
            data={
                "username": "testuser",
                "email": "test@example.com",
                "password": "testpass123",
                "password_confirm": "testpass123",
                "name": "Test User",
                "country": "USA",
                "sex": Sex.MALE,
            }
        )
        self.assertTrue(serializer.is_valid())

    def test_serializer_create_user(self):
        """Test that create() creates a user"""
        serializer = UserRegistrationSerializer(
            data={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "testpass123",
                "password_confirm": "testpass123",
                "name": "New User",
                "country": "USA",
                "sex": Sex.MALE,
                "age": 25,
            }
        )
        self.assertTrue(serializer.is_valid())
        user = serializer.create(serializer.validated_data)
        self.assertIsNotNone(user.id)
        self.assertEqual(user.username, "newuser")
        self.assertEqual(user.email, "newuser@example.com")

    def test_serializer_create_profile(self):
        """Test that create() creates a UserProfile"""
        serializer = UserRegistrationSerializer(
            data={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "testpass123",
                "password_confirm": "testpass123",
                "name": "New User",
                "country": "USA",
                "sex": Sex.MALE,
                "age": 25,
            }
        )
        self.assertTrue(serializer.is_valid())
        user = serializer.create(serializer.validated_data)
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.name, "New User")
        self.assertEqual(profile.country, "USA")
        self.assertEqual(profile.sex, Sex.MALE)
        self.assertEqual(profile.age, 25)

    def test_serializer_create_with_genres(self):
        """Test create() with genre preferences"""
        serializer = UserRegistrationSerializer(
            data={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "testpass123",
                "password_confirm": "testpass123",
                "name": "New User",
                "country": "USA",
                "sex": Sex.MALE,
                "favourite_genre1": Genre.ACTION,
                "favourite_genre2": Genre.COMEDY,
            }
        )
        self.assertTrue(serializer.is_valid())
        user = serializer.create(serializer.validated_data)
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.favourite_genre1, Genre.ACTION)
        self.assertEqual(profile.favourite_genre2, Genre.COMEDY)

    def test_serializer_create_without_name_uses_username(self):
        """Test that missing name uses username"""
        serializer = UserRegistrationSerializer(
            data={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "testpass123",
                "password_confirm": "testpass123",
                "country": "USA",
                "sex": Sex.MALE,
            }
        )
        self.assertTrue(serializer.is_valid())
        user = serializer.create(serializer.validated_data)
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.name, "newuser")

    def test_serializer_optional_fields(self):
        """Test that optional fields can be omitted"""
        serializer = UserRegistrationSerializer(
            data={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "testpass123",
                "password_confirm": "testpass123",
                "country": "USA",
                "sex": Sex.MALE,
            }
        )
        self.assertTrue(serializer.is_valid())

    def test_serializer_age_validation(self):
        """Test age field validation"""
        serializer = UserRegistrationSerializer(
            data={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "testpass123",
                "password_confirm": "testpass123",
                "name": "New User",
                "country": "USA",
                "sex": Sex.MALE,
                "age": 150,  # Too high
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("age", serializer.errors)


class MovieRecommendationSerializerTest(TestCase):
    """Test suite for MovieRecommendationSerializer"""

    def test_serializer_fields(self):
        """Test that serializer has all expected fields"""
        serializer = MovieRecommendationSerializer()
        expected_fields = [
            "query",
            "found",
            "title",
            "tmdb_id",
            "year",
            "overview",
            "vote_average",
            "vote_count",
            "poster_url",
            "reason",
        ]
        for field in expected_fields:
            self.assertIn(field, serializer.fields)

    def test_serializer_required_fields(self):
        """Test that required fields are marked correctly"""
        serializer = MovieRecommendationSerializer()
        self.assertTrue(serializer.fields["query"].required)
        self.assertTrue(serializer.fields["found"].required)

    def test_serializer_optional_fields(self):
        """Test that optional fields are not required"""
        serializer = MovieRecommendationSerializer()
        self.assertFalse(serializer.fields["title"].required)
        self.assertFalse(serializer.fields["tmdb_id"].required)

    def test_serializer_validation(self):
        """Test serializer with valid data"""
        serializer = MovieRecommendationSerializer(
            data={
                "query": "Fight Club",
                "found": True,
                "title": "Fight Club",
                "tmdb_id": 550,
                "year": "1999",
                "overview": "A great movie",
                "vote_average": 8.4,
                "vote_count": 20000,
            }
        )
        self.assertTrue(serializer.is_valid())


class RecommendationResponseSerializerTest(TestCase):
    """Test suite for RecommendationResponseSerializer"""

    def test_serializer_fields(self):
        """Test that serializer has all expected fields"""
        serializer = RecommendationResponseSerializer()
        expected_fields = ["agent_response", "recommendations", "user_movies", "user_genres"]
        for field in expected_fields:
            self.assertIn(field, serializer.fields)

    def test_serializer_recommendations_field(self):
        """Test that recommendations field uses MovieRecommendationSerializer"""
        serializer = RecommendationResponseSerializer()
        recommendations_field = serializer.fields["recommendations"]
        self.assertEqual(
            recommendations_field.child.__class__, MovieRecommendationSerializer
        )

    def test_serializer_list_fields(self):
        """Test that list fields are correctly configured"""
        serializer = RecommendationResponseSerializer()
        self.assertTrue(serializer.fields["user_movies"].many)
        self.assertTrue(serializer.fields["user_genres"].many)

    def test_serializer_validation(self):
        """Test serializer with valid data"""
        serializer = RecommendationResponseSerializer(
            data={
                "agent_response": "Here are some recommendations",
                "recommendations": [
                    {
                        "query": "Action",
                        "found": True,
                        "title": "The Matrix",
                        "tmdb_id": 603,
                    }
                ],
                "user_movies": ["Movie 1", "Movie 2"],
                "user_genres": ["Action", "Comedy"],
            }
        )
        self.assertTrue(serializer.is_valid())

