# recom_sys_app/views_group.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404, render
from django.db import transaction
from django.contrib.auth.decorators import login_required

from .models import GroupSession, GroupMember, GroupSwipe, GroupMatch
from .services import RecommendationService


# ====================  Page View ====================


@login_required
def group_room_view(request, group_code):
    """
    Group Room Page (Original)
    URL: /groups/<group_code>/room/
    """
    return render(request, "recom_sys_app/group_room.html", {"group_code": group_code})


@login_required
def group_deck_view(request, group_code):
    """
    Render Group Movie Recommendations Swipe Card Page (New)
    URL: /groups/<group_code>/deck/
    """
    try:
        # Retrieve group information
        group_session = get_object_or_404(
            GroupSession, group_code=group_code, is_active=True
        )

        # Verify whether the user is a member of the group
        is_member = GroupMember.objects.filter(
            group_session=group_session, user=request.user, is_active=True
        ).exists()

        if not is_member:
            return render(
                request,
                "recom_sys_app/error.html",
                {"error_message": "你不是这个群组的成员", "group_code": group_code},
            )

        # Get the number of members
        member_count = GroupMember.objects.filter(
            group_session=group_session, is_active=True
        ).count()

        context = {
            "group_code": group_code,
            "group_session": group_session,
            "member_count": member_count,
            "user": request.user,
        }

        return render(request, "recom_sys_app/group_deck.html", context)

    except Exception as e:
        return render(
            request,
            "recom_sys_app/error.html",
            {"error_message": str(e), "group_code": group_code},
        )


# ==================== API 视图 ====================


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_group_deck(request, group_code):
    """Retrieve the movie recommendation list for a group (API)"""
    try:
        # Add debug logs
        print(f"🔍 DEBUG: request.GET = {request.GET}")
        print(f"🔍 DEBUG: group_code = {group_code}")
        print(f"🔍 DEBUG: user = {request.user}")

        # Get Groups
        group_session = get_object_or_404(
            GroupSession, group_code=group_code, is_active=True
        )

        print(f"🔍 DEBUG: found group = {group_session}")

        # Verify whether the user is a member of the group
        is_member = GroupMember.objects.filter(
            group_session=group_session, user=request.user, is_active=True
        ).exists()

        print(f"🔍 DEBUG: is_member = {is_member}")

        if not is_member:
            return Response(
                {"error": "You are not a member of this group."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Retrieve query parameters
        limit = int(request.GET.get("limit", 20))
        with_details = request.GET.get("with_details", "false").lower() == "true"

        print(f"🔍 DEBUG: limit = {limit}, with_details = {with_details}")

        # Scope of Restriction
        limit = min(max(limit, 1), 100)

        # Get a list of recommended movies
        print(f"🔍 DEBUG: calling RecommendationService.get_group_deck()")
        movie_ids = RecommendationService.get_group_deck(group_session, limit=limit)

        print(f"🔍 DEBUG: got {len(movie_ids)} movie IDs")

        # For detailed information, retrieve it from TMDB.
        if with_details:
            print(f"🔍 DEBUG: fetching movie details from TMDB...")
            movies = []
            for tmdb_id in movie_ids:
                movie_info = RecommendationService.get_movie_details(tmdb_id)
                if movie_info:
                    movies.append(movie_info)
                    print(f"🔍 DEBUG: fetched movie {movie_info.get('title')}")
        else:
            movies = [{"tmdb_id": mid} for mid in movie_ids]

        # Retrieve group information
        member_count = GroupMember.objects.filter(
            group_session=group_session, is_active=True
        ).count()

        response_data = {
            "group_code": group_session.group_code,
            "member_count": member_count,
            "movies": movies,
            "total": len(movies),
            "message": "Movie list retrieved successfully",
        }

        print(f"🔍 DEBUG: returning response with {len(movies)} movies")

        return Response(response_data, status=status.HTTP_200_OK)

    except ValueError as e:
        print(f"❌ DEBUG ValueError: {e}")
        import traceback

        traceback.print_exc()
        return Response(
            {"error": f"Invalid parameter format: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        print(f"❌ DEBUG Exception: {e}")
        import traceback

        traceback.print_exc()
        return Response(
            {"error": f"Server Error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def swipe_like(request, group_code):
    """
    Record user Likes for movies (API)

    URL: POST /api/groups/<group_code>/swipe/like/
    Body:
    {
        "tmdb_id": 12345,
        "movie_title": "Fight Club"  // 可选
    }

    Response:
    {
        "success": true,
        "swipe_id": 123,
        "action": "LIKE",
        "is_match": true,
        "match_data": {...}
    }
    """
    try:
        # 获取群组
        group_session = get_object_or_404(
            GroupSession, group_code=group_code, is_active=True
        )

        # 验证成员身份
        is_member = GroupMember.objects.filter(
            group_session=group_session, user=request.user, is_active=True
        ).exists()

        if not is_member:
            return Response(
                {"error": "You are not a member of this group."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Retrieve Movie ID
        tmdb_id = request.data.get("tmdb_id")
        movie_title = request.data.get("movie_title", "")

        if not tmdb_id:
            return Response(
                {"error": "The tmdb_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if it has already been swiped.
        existing_swipe = GroupSwipe.objects.filter(
            group_session=group_session, user=request.user, tmdb_id=tmdb_id
        ).first()

        if existing_swipe:
            return Response(
                {
                    "error": "You have already performed an operation on this movie.",
                    "previous_action": existing_swipe.action,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use transactions to ensure data consistency.
        with transaction.atomic():
            # Create a sliding record
            swipe = GroupSwipe.objects.create(
                group_session=group_session,
                user=request.user,
                tmdb_id=tmdb_id,
                action=GroupSwipe.Action.LIKE,
            )

            # Check if everyone likes (matches)
            is_match = RecommendationService.check_group_match(group_session, tmdb_id)

            match_data = None
            if is_match:
                # Create or retrieve matching records
                match, created = GroupMatch.objects.get_or_create(
                    group_session=group_session,
                    tmdb_id=tmdb_id,
                    defaults={"movie_title": movie_title},
                )

                # If it is a newly created match
                if created:
                    match_data = {
                        "match_id": match.id,
                        "tmdb_id": tmdb_id,
                        "movie_title": movie_title or "this movie",
                        "matched_at": match.matched_at.isoformat(),
                        "message": f"🎉 Match successful! All members like {movie_title or 'this movie'}！",
                    }

            # Clear recommendation cache
            RecommendationService.invalidate_deck_cache(group_session)

        response_data = {
            "success": True,
            "swipe_id": swipe.id,
            "action": swipe.action,
            "tmdb_id": tmdb_id,
            "is_match": is_match,
            "match_data": match_data,
            "timestamp": swipe.created_at.isoformat(),
        }

        return Response(response_data, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response(
            {"error": f"Server Error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_group_matches(request, group_code):
    """
    Retrieve all matching records for a group (API)

    URL: GET /api/groups/<group_code>/matches/

    Response:
    {
        "group_code": "ABC123",
        "matches": [...],
        "total": 5
    }
    """
    try:
        group_session = get_object_or_404(
            GroupSession, group_code=group_code, is_active=True
        )

        # Verify Member Identity
        is_member = GroupMember.objects.filter(
            group_session=group_session, user=request.user, is_active=True
        ).exists()

        if not is_member:
            return Response(
                {"error": "You are not a member of this group."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get all matches
        matches = GroupMatch.objects.filter(group_session=group_session).order_by(
            "-matched_at"
        )

        matches_data = [
            {
                "match_id": match.id,
                "tmdb_id": match.tmdb_id,
                "movie_title": match.movie_title,
                "matched_at": match.matched_at.isoformat(),
            }
            for match in matches
        ]

        return Response(
            {
                "group_code": group_code,
                "matches": matches_data,
                "total": len(matches_data),
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return Response(
            {"error": f"Server Error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
