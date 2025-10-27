"""
REST API Views for Movie Recommender System
This file contains all REST API endpoints using Django REST Framework.
Separate from views.py which contains template-based views.
"""

from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.conf import settings
import os
import requests

from dotenv import load_dotenv
from phi.agent import Agent
from phi.model.groq import Groq

from .models import UserProfile, Interaction
from .serializers import (
    UserProfileSerializer,
    UserProfileUpdateSerializer,
    InteractionSerializer,
    InteractionCreateUpdateSerializer,
    UserRegistrationSerializer,
)

# Import helper functions from views.py
from .views import (
    _get_signup_movies,
    _get_signup_genre,
    _tmdb_fetch_all,
    _extract_titles,
    _as_text,
    _build_recommendation_agent,
)

load_dotenv(settings.BASE_DIR / ".env")


# ============================================
# USER PROFILE API
# ============================================


class UserProfileViewSet(viewsets.ModelViewSet):
    """
    REST API ViewSet for user profiles.

    Endpoints:
        GET    /api/profile/         - Get current user's profile
        PUT    /api/profile/{id}/    - Update profile (full)
        PATCH  /api/profile/{id}/    - Update profile (partial)
    """

    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Users can only access their own profile
        return UserProfile.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action in ["update", "partial_update"]:
            return UserProfileUpdateSerializer
        return UserProfileSerializer

    def list(self, request, *args, **kwargs):
        """GET /api/profile/ - Get current user's profile"""
        try:
            profile = UserProfile.objects.get(user=request.user)
            serializer = self.get_serializer(profile)
            return Response({"success": True, "profile": serializer.data})
        except UserProfile.DoesNotExist:
            return Response(
                {"success": False, "error": "Profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    def update(self, request, *args, **kwargs):
        """PUT /api/profile/{id}/ - Update profile"""
        try:
            profile = UserProfile.objects.get(user=request.user)
        except UserProfile.DoesNotExist:
            return Response(
                {"success": False, "error": "Profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(profile, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "success": True,
                "message": "Profile updated successfully",
                "profile": UserProfileSerializer(profile).data,
            }
        )

    def partial_update(self, request, *args, **kwargs):
        """PATCH /api/profile/{id}/ - Partial update profile"""
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)


# ============================================
# INTERACTION API
# ============================================


class InteractionViewSet(viewsets.ModelViewSet):
    """
    REST API ViewSet for movie interactions.

    Endpoints:
        GET    /api/interactions/                      - List all interactions
        POST   /api/interactions/                      - Create interaction
        GET    /api/interactions/{id}/                 - Get specific interaction
        PUT    /api/interactions/{id}/                 - Update interaction
        DELETE /api/interactions/{id}/                 - Delete interaction
        GET    /api/interactions/stats/                - Get statistics
        POST   /api/interactions/set/{tmdb_id}/{status}/ - Quick set status
    """

    serializer_class = InteractionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Interaction.objects.filter(user=self.request.user)

        # Filter by status if provided (?status=LIKE)
        status_filter = self.request.query_params.get("status", None)
        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())

        # Filter by tmdb_id if provided (?tmdb_id=12345)
        tmdb_id = self.request.query_params.get("tmdb_id", None)
        if tmdb_id:
            queryset = queryset.filter(tmdb_id=tmdb_id)

        return queryset.order_by("-updated_at")

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return InteractionCreateUpdateSerializer
        return InteractionSerializer

    def list(self, request, *args, **kwargs):
        """GET /api/interactions/ - List all user interactions"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        return Response(
            {
                "success": True,
                "count": queryset.count(),
                "interactions": serializer.data,
            }
        )

    def create(self, request, *args, **kwargs):
        """POST /api/interactions/ - Create or update interaction"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Use update_or_create to handle duplicates
        interaction, created = Interaction.objects.update_or_create(
            user=request.user,
            tmdb_id=serializer.validated_data["tmdb_id"],
            defaults={
                "status": serializer.validated_data["status"],
                "rating": serializer.validated_data.get("rating"),
                "source": serializer.validated_data.get("source", "api"),
            },
        )

        return Response(
            {
                "success": True,
                "created": created,
                "interaction": InteractionSerializer(interaction).data,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="set/(?P<tmdb_id>[0-9]+)/(?P<interaction_status>[a-zA-Z_]+)",
    )
    def set_status(self, request, tmdb_id=None, interaction_status=None):
        """
        POST /api/interactions/set/{tmdb_id}/{status}/
        Quick endpoint to set movie status without full request body.

        Example: POST /api/interactions/set/438631/like/
        """
        interaction_status = interaction_status.upper()
        valid_statuses = {c for c, _ in Interaction.Status.choices}

        if interaction_status not in valid_statuses:
            return Response(
                {
                    "success": False,
                    "error": f'Invalid status. Valid options: {", ".join(valid_statuses)}',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        interaction, created = Interaction.objects.update_or_create(
            user=request.user,
            tmdb_id=int(tmdb_id),
            defaults={"status": interaction_status, "source": "api"},
        )

        return Response(
            {
                "success": True,
                "created": created,
                "interaction": InteractionSerializer(interaction).data,
            }
        )

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """
        GET /api/interactions/stats/
        Get user interaction statistics.
        """
        interactions = Interaction.objects.filter(user=request.user)

        stats = {
            "total": interactions.count(),
            "liked": interactions.filter(status="LIKE").count(),
            "disliked": interactions.filter(status="DISLIKE").count(),
            "watched": interactions.filter(status="WATCHED").count(),
            "watch_later": interactions.filter(status="WATCH_LATER").count(),
        }

        return Response({"success": True, "stats": stats})


# ============================================
# RECOMMENDATIONS API
# ============================================


class RecommendationsView(APIView):
    """
    REST API for movie recommendations using AI.

    Endpoint:
        GET /api/recommendations/ - Get personalized movie recommendations
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """GET /api/recommendations/ - Get 3 AI-powered recommendations"""
        groq_api_key = (os.getenv("GROQ_API_KEY") or "").strip()
        if not groq_api_key:
            return Response(
                {"success": False, "error": "GROQ_API_KEY not configured"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            # Build and run recommendation agent using helper from views.py
            agent = _build_recommendation_agent(request.user, groq_api_key)
            resp = agent.run("Recommend 3 movies I might love next.")
        except Exception as e:
            return Response(
                {"success": False, "error": f"Agent error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Extract recommendations from agent response
        agent_text = _as_text(resp) or ""
        titles = _extract_titles(agent_text)

        # Fetch TMDB details for recommended movies
        try:
            tmdb_results = _tmdb_fetch_all(titles) if titles else []
        except requests.HTTPError as e:
            return Response(
                {
                    "success": False,
                    "error": f"TMDB API error: {e.response.status_code}",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as e:
            return Response(
                {"success": False, "error": f"Error fetching movie details: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "success": True,
                "agent_response": agent_text,
                "recommendations": tmdb_results,
                "user_movies": _get_signup_movies(request.user),
                "user_genres": _get_signup_genre(request.user),
            }
        )


# ============================================
# AUTHENTICATION API
# ============================================


class RegisterView(generics.CreateAPIView):
    """
    REST API for user registration.

    Endpoint:
        POST /api/auth/register/ - Register new user with profile
    """

    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        """POST /api/auth/register/ - Create new user account"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                "success": True,
                "message": "User registered successfully",
                "user": {"id": user.id, "username": user.username, "email": user.email},
            },
            status=status.HTTP_201_CREATED,
        )


# ============================================
# UTILITY ENDPOINTS
# ============================================


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """
    GET /api/health/ - Health check endpoint

    Returns server status and version information.
    """
    return Response(
        {
            "success": True,
            "status": "healthy",
            "service": "movie-recommender-api",
            "version": "1.0.0",
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def get_options(request):
    """
    GET /api/options/ - Get available options for dropdowns

    Returns:
        - Available genres
        - Sex/gender options
        - Interaction status options
    """
    from .models import Genre, Sex

    return Response(
        {
            "success": True,
            "genres": [
                {"value": code, "label": label} for code, label in Genre.choices
            ],
            "sexes": [{"value": code, "label": label} for code, label in Sex.choices],
            "interaction_statuses": [
                {"value": code, "label": label}
                for code, label in Interaction.Status.choices
            ],
        }
    )


# ============================================
# API DOCUMENTATION
# ============================================
"""
REST API ENDPOINTS SUMMARY:

Authentication:
    POST   /api/auth/register/                     - Register new user
    POST   /api/auth/login/                        - Get auth token

Profile:
    GET    /api/profile/                           - Get current user profile
    PUT    /api/profile/{id}/                      - Update profile (full)
    PATCH  /api/profile/{id}/                      - Update profile (partial)

Interactions:
    GET    /api/interactions/                      - List all interactions
    POST   /api/interactions/                      - Create interaction
    GET    /api/interactions/{id}/                 - Get specific interaction
    PUT    /api/interactions/{id}/                 - Update interaction
    DELETE /api/interactions/{id}/                 - Delete interaction
    GET    /api/interactions/stats/                - Get statistics
    POST   /api/interactions/set/{tmdb_id}/{status}/ - Quick set status

Recommendations:
    GET    /api/recommendations/                   - Get AI recommendations

Utility:
    GET    /api/health/                            - Health check
    GET    /api/options/                           - Get dropdown options

Authentication:
    All endpoints except /health/, /options/, /auth/register/, and /auth/login/
    require authentication via Token in header:
    
    Authorization: Token YOUR_TOKEN_HERE
"""
