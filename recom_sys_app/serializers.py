from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile, Interaction, Genre, Sex


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "date_joined"]
        read_only_fields = ["id", "date_joined"]


class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    computed_age = serializers.IntegerField(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
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
        read_only_fields = ["id", "user", "computed_age", "created_at", "updated_at"]


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """Simplified serializer for profile updates"""

    class Meta:
        model = UserProfile
        fields = [
            "name",
            "sex",
            "age",
            "date_of_birth",
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
        ]


class InteractionSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Interaction
        fields = [
            "id",
            "user",
            "tmdb_id",
            "status",
            "rating",
            "source",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "created_at", "updated_at"]


class InteractionCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating interactions"""

    class Meta:
        model = Interaction
        fields = ["tmdb_id", "status", "rating", "source"]


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    # Profile fields
    name = serializers.CharField(required=False)
    sex = serializers.ChoiceField(choices=Sex.choices, required=False)
    age = serializers.IntegerField(required=False, min_value=1, max_value=120)
    country = serializers.CharField(required=False, allow_blank=True)
    favourite_genre1 = serializers.ChoiceField(
        choices=Genre.choices, required=False, allow_blank=True
    )
    favourite_genre2 = serializers.ChoiceField(
        choices=Genre.choices, required=False, allow_blank=True
    )
    liked_g1_tmdb_id = serializers.IntegerField(required=False, allow_null=True)
    liked_g1_title = serializers.CharField(required=False, allow_blank=True)
    liked_g2_tmdb_id = serializers.IntegerField(required=False, allow_null=True)
    liked_g2_title = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
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

    def validate(self, data):
        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError({"password": "Passwords do not match"})
        return data

    def create(self, validated_data):
        # Remove password_confirm and profile fields
        validated_data.pop("password_confirm")
        profile_data = {
            "name": validated_data.pop("name", ""),
            "sex": validated_data.pop("sex", Sex.UNSPECIFIED),
            "age": validated_data.pop("age", None),
            "country": validated_data.pop("country", ""),
            "favourite_genre1": validated_data.pop("favourite_genre1", ""),
            "favourite_genre2": validated_data.pop("favourite_genre2", ""),
            "liked_g1_tmdb_id": validated_data.pop("liked_g1_tmdb_id", None),
            "liked_g1_title": validated_data.pop("liked_g1_title", ""),
            "liked_g2_tmdb_id": validated_data.pop("liked_g2_tmdb_id", None),
            "liked_g2_title": validated_data.pop("liked_g2_title", ""),
        }

        # Create user
        user = User.objects.create_user(**validated_data)

        # Create profile
        if not profile_data.get("name"):
            profile_data["name"] = user.username

        UserProfile.objects.create(user=user, **profile_data)

        return user


class MovieRecommendationSerializer(serializers.Serializer):
    """Serializer for movie recommendation response"""

    query = serializers.CharField()
    found = serializers.BooleanField()
    title = serializers.CharField(required=False)
    tmdb_id = serializers.IntegerField(required=False)
    year = serializers.CharField(required=False)
    overview = serializers.CharField(required=False)
    vote_average = serializers.FloatField(required=False)
    vote_count = serializers.IntegerField(required=False)
    poster_url = serializers.URLField(required=False, allow_null=True)
    reason = serializers.CharField(required=False)


class RecommendationResponseSerializer(serializers.Serializer):
    """Complete recommendation response"""

    agent_response = serializers.CharField()
    recommendations = MovieRecommendationSerializer(many=True)
    user_movies = serializers.ListField(child=serializers.CharField())
    user_genres = serializers.ListField(child=serializers.CharField())
