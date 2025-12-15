# recom_sys_app/views_community.py
"""
Community Mode Views - Genre-based movie browsing with AI agent recommendations
Separated from group views for better organization and clarity
"""

from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
import json

from .models import GroupSession, GroupMember, Interaction
from .services import RecommendationService

# ============================================
# AI Agent Configuration for Recommendations (SAFE / LAZY)
# ============================================
import os

USE_COMMUNITY_AI = os.getenv("COMMUNITY_AI_ENABLED", "0") == "1"  # opt-in only
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("GROQ_API_TOKEN")

# Optional deps
try:
    from phi.agent import Agent  # type: ignore
    from phi.model.groq import Groq  # type: ignore
except Exception:
    Agent = None  # type: ignore
    Groq = None  # type: ignore

_movie_agent = None  # lazy singleton


def get_movie_agent():
    """
    Return a lazily-created movie recommendation agent, or None if disabled/missing deps.
    Never throws during import or when disabled.
    """
    global _movie_agent
    if not USE_COMMUNITY_AI:
        return None
    if Agent is None or Groq is None or not GROQ_API_KEY:
        return None
    if _movie_agent is None:
        _movie_agent = Agent(
            model=Groq(
                id="llama-3.3-70b-versatile", api_key=GROQ_API_KEY, temperature=0.7
            ),
            description="Movie recommendation expert assistant.",
            instructions=[
                "Analyze user's movie preferences and viewing history.",
                "Suggest movies that match their taste in the requested genre.",
                "Provide short, engaging reasons for each recommendation.",
                "Prefer movies after 2018; weigh ratings & popularity.",
                "Return 3–5 suggestions.",
            ],
            markdown=True,
        )
    return _movie_agent


# ============================================
# Page Views
# ============================================


@login_required
def community_lobby_view(request, group_code):
    """
    Community lobby page view
    URL: /communities/<group_code>/lobby/

    Displays community information, members, and chat before entering the movie deck.
    Communities are organized by genre (Action, Horror, Comedy, etc.)
    """
    try:
        # Get community session
        community = get_object_or_404(
            GroupSession,
            group_code=group_code,
            is_active=True,
            kind=GroupSession.Kind.COMMUNITY,
        )

        # Verify user is a member
        is_member = GroupMember.objects.filter(
            group_session=community, user=request.user, is_active=True
        ).exists()

        if not is_member:
            return render(
                request,
                "recom_sys_app/error.html",
                {
                    "error_message": "You are not a member of this community",
                    "group_code": group_code,
                },
            )

        # Get member count
        member_count = GroupMember.objects.filter(
            group_session=community, is_active=True
        ).count()

        # Extract genre name from community_key
        genre_name = ""
        if community.community_key and community.community_key.startswith("genre:"):
            genre_name = community.community_key.split(":", 1)[1]
        elif community.genre_filter:
            genre_name = community.genre_filter

        context = {
            "group_code": group_code,
            "community": community,
            "member_count": member_count,
            "user": request.user,
            "genre_name": genre_name,
        }

        return render(request, "recom_sys_app/community_lobby.html", context)

    except Exception as e:
        return render(
            request,
            "recom_sys_app/error.html",
            {"error_message": str(e), "group_code": group_code},
        )


@login_required
def community_deck_view(request, group_code):
    """
    Community movie deck page view
    URL: /communities/<group_code>/deck/

    Displays the movie swipe interface for genre-based browsing.
    Movies are filtered by the community's genre.
    """
    try:
        # Get community session
        community = get_object_or_404(
            GroupSession,
            group_code=group_code,
            is_active=True,
            kind=GroupSession.Kind.COMMUNITY,
        )

        # Verify user is a member
        is_member = GroupMember.objects.filter(
            group_session=community, user=request.user, is_active=True
        ).exists()

        if not is_member:
            return render(
                request,
                "recom_sys_app/error.html",
                {
                    "error_message": "You are not a member of this community",
                    "group_code": group_code,
                },
            )

        # Get member count
        member_count = GroupMember.objects.filter(
            group_session=community, is_active=True
        ).count()

        # Extract genre name
        genre_name = ""
        if community.community_key and community.community_key.startswith("genre:"):
            genre_name = community.community_key.split(":", 1)[1]
        elif community.genre_filter:
            genre_name = community.genre_filter

        context = {
            "group_code": group_code,
            "community": community,
            "member_count": member_count,
            "user": request.user,
            "genre_name": genre_name,
            "is_community": True,
        }

        return render(request, "recom_sys_app/community_deck.html", context)

    except Exception as e:
        return render(
            request,
            "recom_sys_app/error.html",
            {"error_message": str(e), "group_code": group_code},
        )


# ============================================
# API Endpoints
# ============================================


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_community_deck(request, group_code):
    """
    Get movie recommendations for a community (filtered by genre)
    GET /api/communities/<group_code>/deck/

    Response:
    {
        "success": true,
        "movies": [...],
        "total": 20,
        "genre": "Action"
    }
    """
    try:
        # Get community
        community = get_object_or_404(
            GroupSession,
            group_code=group_code,
            is_active=True,
            kind=GroupSession.Kind.COMMUNITY,
        )

        # Verify membership
        is_member = GroupMember.objects.filter(
            group_session=community, user=request.user, is_active=True
        ).exists()

        if not is_member:
            return Response(
                {"error": "You are not a member of this community"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Extract genre name and convert to TMDB genre ID
        genre_name = ""
        if community.community_key and community.community_key.startswith("genre:"):
            genre_name = community.community_key.split(":", 1)[1]
        elif community.genre_filter:
            genre_name = community.genre_filter

        # Convert genre name to TMDB genre ID for filtering
        selected_genre_ids = None
        if genre_name:
            # Use the same genre mapping as in services
            genre_name_to_id = {
                "Action": 28,
                "Adventure": 12,
                "Animation": 16,
                "Comedy": 35,
                "Crime": 80,
                "Documentary": 99,
                "Drama": 18,
                "Family": 10751,
                "Fantasy": 14,
                "History": 36,
                "Horror": 27,
                "Music": 10402,
                "Mystery": 9648,
                "Romance": 10749,
                "Science Fiction": 878,
                "TV Movie": 10770,
                "Thriller": 53,
                "War": 10752,
                "Western": 37,
            }
            genre_id = genre_name_to_id.get(genre_name)
            if genre_id:
                selected_genre_ids = [genre_id]

        # Get movie IDs from RecommendationService with genre filtering and collaborative filtering
        from recom_sys_app.services import CollaborativeFilteringService
        from recom_sys_app.models import Interaction

        # Check if user has enough interactions for CF
        interaction_count = Interaction.objects.filter(user=request.user).count()
        use_cf = (
            interaction_count >= CollaborativeFilteringService.MIN_INTERACTIONS_FOR_CF
        )

        # Get movie IDs with CF enabled
        movie_ids = RecommendationService.get_group_deck(
            community,
            user=request.user,  # Pass user for CF
            limit=50,
            selected_genre_ids=selected_genre_ids,
            use_collaborative_filtering=use_cf,  # Enable CF if user qualifies
        )

        # Get CF movie IDs to mark them
        cf_movie_ids = set()
        if use_cf:
            try:
                cf_movie_ids = set(
                    CollaborativeFilteringService.get_collaborative_recommendations(
                        request.user, limit=50
                    )
                )
            except Exception:
                pass  # If CF fails, continue without marking

        # Fetch movie details from TMDB
        movies = []
        for tmdb_id in movie_ids[:20]:  # Return first 20 movies
            movie_details = RecommendationService.get_movie_details(tmdb_id)
            if movie_details:
                # Add recommendation source
                if tmdb_id in cf_movie_ids:
                    movie_details["recommendation_reason"] = (
                        "Users like you also liked this"
                    )
                    movie_details["recommendation_source"] = "collaborative_filtering"
                else:
                    movie_details["recommendation_reason"] = (
                        "Based on community preferences"
                    )
                    movie_details["recommendation_source"] = "community_based"
                movies.append(movie_details)

        return Response(
            {
                "success": True,
                "movies": movies,
                "total": len(movies),
                "genre": genre_name,
                "recommendation_method": "hybrid" if use_cf else "community_based",
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return Response(
            {"error": f"Server Error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def community_swipe_like(request, group_code):
    """
    Record a like swipe in community mode
    POST /api/communities/<group_code>/swipe/like/

    Request Body:
    {
        "tmdb_id": 123,
        "movie_title": "Movie Name"
    }

    Response:
    {
        "success": true,
        "interaction_id": 456,
        "action": "LIKE"
    }
    """
    try:
        # Get community
        community = get_object_or_404(
            GroupSession,
            group_code=group_code,
            is_active=True,
            kind=GroupSession.Kind.COMMUNITY,
        )

        # Verify membership
        is_member = GroupMember.objects.filter(
            group_session=community, user=request.user, is_active=True
        ).exists()

        if not is_member:
            return Response(
                {"error": "You are not a member of this community"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get tmdb_id from request
        tmdb_id = request.data.get("tmdb_id")

        if not tmdb_id:
            return Response(
                {"error": "The tmdb_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if already swiped
        existing_interaction = Interaction.objects.filter(
            user=request.user, tmdb_id=tmdb_id
        ).first()

        if existing_interaction:
            # Update existing interaction
            existing_interaction.status = Interaction.Status.LIKE
            existing_interaction.source = "community"
            existing_interaction.save()

            return Response(
                {
                    "success": True,
                    "interaction_id": existing_interaction.id,
                    "action": "LIKE",
                    "tmdb_id": tmdb_id,
                    "timestamp": existing_interaction.updated_at.isoformat(),
                },
                status=status.HTTP_200_OK,
            )
        else:
            # Create new interaction
            interaction = Interaction.objects.create(
                user=request.user,
                tmdb_id=tmdb_id,
                status=Interaction.Status.LIKE,
                source="community",
            )

            return Response(
                {
                    "success": True,
                    "interaction_id": interaction.id,
                    "action": "LIKE",
                    "tmdb_id": tmdb_id,
                    "timestamp": interaction.created_at.isoformat(),
                },
                status=status.HTTP_201_CREATED,
            )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return Response(
            {"error": f"Server Error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def community_swipe_dislike(request, group_code):
    """
    Record a dislike swipe in community mode
    POST /api/communities/<group_code>/swipe/dislike/

    Request Body:
    {
        "tmdb_id": 123,
        "movie_title": "Movie Name"
    }

    Response:
    {
        "success": true,
        "interaction_id": 456,
        "action": "DISLIKE"
    }
    """
    try:
        # Get community
        community = get_object_or_404(
            GroupSession,
            group_code=group_code,
            is_active=True,
            kind=GroupSession.Kind.COMMUNITY,
        )

        # Verify membership
        is_member = GroupMember.objects.filter(
            group_session=community, user=request.user, is_active=True
        ).exists()

        if not is_member:
            return Response(
                {"error": "You are not a member of this community"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get tmdb_id from request
        tmdb_id = request.data.get("tmdb_id")

        if not tmdb_id:
            return Response(
                {"error": "The tmdb_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if already swiped
        existing_interaction = Interaction.objects.filter(
            user=request.user, tmdb_id=tmdb_id
        ).first()

        if existing_interaction:
            # Update existing interaction
            existing_interaction.status = Interaction.Status.DISLIKE
            existing_interaction.source = "community"
            existing_interaction.save()

            return Response(
                {
                    "success": True,
                    "interaction_id": existing_interaction.id,
                    "action": "DISLIKE",
                    "tmdb_id": tmdb_id,
                    "timestamp": existing_interaction.updated_at.isoformat(),
                },
                status=status.HTTP_200_OK,
            )
        else:
            # Create new interaction
            interaction = Interaction.objects.create(
                user=request.user,
                tmdb_id=tmdb_id,
                status=Interaction.Status.DISLIKE,
                source="community",
            )

            return Response(
                {
                    "success": True,
                    "interaction_id": interaction.id,
                    "action": "DISLIKE",
                    "tmdb_id": tmdb_id,
                    "timestamp": interaction.created_at.isoformat(),
                },
                status=status.HTTP_201_CREATED,
            )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return Response(
            {"error": f"Server Error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def get_ai_recommendations(request, group_code):
    try:
        community = get_object_or_404(
            GroupSession,
            group_code=group_code,
            is_active=True,
            kind=GroupSession.Kind.COMMUNITY,
        )
        is_member = GroupMember.objects.filter(
            group_session=community, user=request.user, is_active=True
        ).exists()
        if not is_member:
            return Response(
                {"error": "You are not a member of this community"},
                status=status.HTTP_403_FORBIDDEN,
            )

        agent = get_movie_agent()
        if agent is None:
            # Disabled or missing deps/keys -> respond cleanly instead of throwing
            return Response(
                {
                    "success": False,
                    "error": "Community AI is disabled or not configured",
                },
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        genre = request.data.get("genre") or (
            community.community_key.split(":", 1)[1]
            if community.community_key and community.community_key.startswith("genre:")
            else community.genre_filter or ""
        )
        preferences = request.data.get("preferences", "")

        prompt = (
            f"I'm looking for {genre or 'popular'} movie recommendations.\n"
            f"My preferences: {preferences or 'No special preferences; keep it mainstream.'}\n"
            f"Please suggest 3–5 specific movies with one-line reasons."
        )

        resp = agent.run(prompt)
        text = getattr(resp, "content", str(resp))
        return Response(
            {"success": True, "recommendations": text}, status=status.HTTP_200_OK
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return Response(
            {"error": f"Server Error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@login_required
@require_http_methods(["POST"])
def join_community(request):
    """
    Join or create a community based on genre
    POST /api/communities/join/

    Request Body:
    {
        "genre": "Action",
        "genre_id": 28
    }

    Response:
    {
        "success": true,
        "redirect_url": "/communities/<group_code>/deck/",
        "community_code": "ABC123"
    }
    """
    try:
        print(f"[DEBUG join_community] Request body: {request.body}")
        data = json.loads(request.body)
        print(f"[DEBUG join_community] Parsed data: {data}")
        genre_name = data.get("genre")
        genre_id = data.get("genre_id")
        print(f"[DEBUG join_community] genre_name: {genre_name}, genre_id: {genre_id}")

        if not genre_name or not genre_id:
            print(
                f"[DEBUG join_community] Missing data - genre_name: {genre_name}, genre_id: {genre_id}"
            )
            return JsonResponse(
                {
                    "success": False,
                    "message": f"Genre name and ID are required. Received: genre={genre_name}, genre_id={genre_id}",
                },
                status=400,
            )

        # Get or create community for this genre
        with transaction.atomic():
            community, _ = GroupSession.get_or_create_community_by_genre(
                genre_value=genre_name, creator=request.user
            )

            # Add user as member if not already
            membership, member_created = GroupMember.objects.get_or_create(
                group_session=community,
                user=request.user,
                defaults={"role": GroupMember.Role.MEMBER, "is_active": True},
            )

            if not member_created and not membership.is_active:
                membership.is_active = True
                membership.save()

        return JsonResponse(
            {
                "success": True,
                "redirect_url": f"/communities/{community.group_code}/deck/",
                "community_code": community.group_code,
                "message": f"Joined {genre_name} community",
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "message": str(e)}, status=500)
