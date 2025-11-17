from django.test import TestCase
from django.contrib.auth import get_user_model
from datetime import date
from .models import UserProfile, Interaction, GroupSession, GroupMember, Sex, Genre

User = get_user_model()


class UserProfileModelTest(TestCase):
    """Test cases for UserProfile model"""

    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_create_user_profile(self):
        """Test creating a user profile"""
        profile = UserProfile.objects.create(
            user=self.user,
            name="Test User",
            sex=Sex.MALE,
            age=25,
            country="USA",
            favourite_genre1=Genre.ACTION,
            favourite_genre2=Genre.COMEDY,
        )
        self.assertEqual(profile.name, "Test User")
        self.assertEqual(profile.sex, Sex.MALE)
        self.assertEqual(profile.age, 25)

    def test_user_profile_str_representation(self):
        """Test the string representation of UserProfile"""
        profile = UserProfile.objects.create(
            user=self.user, name="John Doe", country="USA"
        )
        self.assertEqual(str(profile), "John Doe")

    def test_user_profile_default_values(self):
        """Test default values for UserProfile"""
        profile = UserProfile.objects.create(
            user=self.user, name="Test User", country="USA"
        )
        self.assertEqual(profile.sex, Sex.UNSPECIFIED)
        self.assertFalse(profile.onboarding_complete)


class InteractionModelTest(TestCase):
    """Test cases for Interaction model"""

    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_create_like_interaction(self):
        """Test creating a LIKE interaction"""
        interaction = Interaction.objects.create(
            user=self.user,
            tmdb_id=12345,
            status=Interaction.Status.LIKE,
            rating=8,
            source="solo",
        )
        self.assertEqual(interaction.status, Interaction.Status.LIKE)
        self.assertEqual(interaction.rating, 8)

    def test_interaction_str_representation(self):
        """Test the string representation of Interaction"""
        interaction = Interaction.objects.create(
            user=self.user, tmdb_id=12345, status=Interaction.Status.LIKE
        )
        expected = f"{self.user.id}:12345 -> LIKE"
        self.assertEqual(str(interaction), expected)


class GroupSessionModelTest(TestCase):
    """Test cases for GroupSession model"""

    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_create_group_session(self):
        """Test creating a group session"""
        group = GroupSession.objects.create(creator=self.user)
        self.assertIsNotNone(group.id)
        self.assertIsNotNone(group.group_code)
        self.assertTrue(group.is_active)

    def test_group_code_generated(self):
        """Test that group code is automatically generated"""
        group = GroupSession.objects.create(creator=self.user)
        self.assertEqual(len(group.group_code), 6)


class GroupMemberModelTest(TestCase):
    """Test cases for GroupMember model"""

    def setUp(self):
        """Set up test fixtures"""
        self.creator = User.objects.create_user(
            username="creator", password="testpass123"
        )
        self.user = User.objects.create_user(username="member", password="testpass123")
        self.group = GroupSession.objects.create(creator=self.creator)

    def test_create_group_member(self):
        """Test creating a group member"""
        member = GroupMember.objects.create(
            group_session=self.group, user=self.user, role=GroupMember.Role.MEMBER
        )
        self.assertEqual(member.role, GroupMember.Role.MEMBER)
        self.assertTrue(member.is_active)

    def test_group_member_str_representation(self):
        """Test the string representation of GroupMember"""
        member = GroupMember.objects.create(
            group_session=self.group, user=self.user, role=GroupMember.Role.MEMBER
        )
        expected = f"member in {self.group.group_code}"
        self.assertEqual(str(member), expected)

    def test_computed_age_property_with_dob(self):
        """Test computed_age property with date of birth"""
        profile = UserProfile.objects.create(
            user=self.user,
            name="Test User",
            country="USA",
            date_of_birth=date(1995, 1, 1),
        )
        self.assertIsNotNone(profile.computed_age)

    def test_computed_age_property_without_dob(self):
        """Test computed_age property without date of birth"""
        profile = UserProfile.objects.create(
            user=self.user, name="Test User", country="USA"
        )
        self.assertIsNone(profile.computed_age)

    def test_interaction_unique_constraint(self):
        """Test that user and tmdb_id must be unique together"""
        Interaction.objects.create(
            user=self.user, tmdb_id=12345, status=Interaction.Status.LIKE
        )
        interaction, created = Interaction.objects.update_or_create(
            user=self.user,
            tmdb_id=12345,
            defaults={"status": Interaction.Status.DISLIKE},
        )
        self.assertFalse(created)
        self.assertEqual(interaction.status, Interaction.Status.DISLIKE)
