# recom_sys_app/views_group.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404, render
from django.db import transaction
from django.contrib.auth.decorators import login_required
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import GroupSession, GroupMember, GroupSwipe, GroupMatch
from .services import RecommendationService


# ====================  Helper Functions ====================

def _broadcast_match_event(group_code, match_id, tmdb_id, movie_title, movie_info, matched_by_users, matched_at):
    """
    Broadcast a match_found event to all WebSocket clients in the group.
    
    Args:
        group_code: Group code
        match_id: Match record ID
        tmdb_id: TMDB movie ID
        movie_title: Movie title
        movie_info: Movie details dict from TMDB
        matched_by_users: List of usernames who liked it
        matched_at: ISO timestamp of match
    """
    try:
        print(f"[_broadcast_match_event] Starting broadcast for group {group_code}")
        channel_layer = get_channel_layer()
        group_name = f'match_{group_code}'
        
        print(f"[_broadcast_match_event] Channel layer: {channel_layer}")
        print(f"[_broadcast_match_event] Group name: {group_name}")
        
        # Prepare movie poster URL
        poster_url = None
        if movie_info and movie_info.get('poster_path'):
            poster_url = f"https://image.tmdb.org/t/p/w500{movie_info['poster_path']}"
        
        # Build event data
        event_data = {
            'type': 'match_found',
            'match_id': match_id,
            'tmdb_id': tmdb_id,
            'movie_title': movie_title,
            'poster_url': poster_url,
            'year': movie_info.get('release_date', '')[:4] if movie_info else None,
            'genres': movie_info.get('genres', []) if movie_info else [],
            'overview': movie_info.get('overview', '') if movie_info else '',
            'vote_average': movie_info.get('vote_average') if movie_info else None,
            'matched_at': matched_at,
            'matched_by': matched_by_users,
            'member_count': len(matched_by_users),
            'message': f'🎉 Match! Everyone likes "{movie_title}"!'
        }
        
        # Broadcast to all clients in the group
        async_to_sync(channel_layer.group_send)(group_name, event_data)
        print(f"[WebSocket] Broadcast match event for group {group_code}, movie: {movie_title}")
        
    except Exception as e:
        print(f"[WebSocket] Error broadcasting match event: {e}")


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
        print(f"[DEBUG] request.GET = {request.GET}")
        print(f"[DEBUG] group_code = {group_code}")
        print(f"[DEBUG] user = {request.user}")
        
        print(f"🔍 DEBUG: request.GET = {request.GET}")
        print(f"🔍 DEBUG: group_code = {group_code}")
        print(f"🔍 DEBUG: user = {request.user}")

        # Get Groups
        group_session = get_object_or_404(
            GroupSession, group_code=group_code, is_active=True
        )
        
        print(f"[DEBUG] found group = {group_session}")
        

        print(f"🔍 DEBUG: found group = {group_session}")

        # Verify whether the user is a member of the group
        is_member = GroupMember.objects.filter(
            group_session=group_session, user=request.user, is_active=True
        ).exists()
        
        print(f"[DEBUG] is_member = {is_member}")
        

        print(f"🔍 DEBUG: is_member = {is_member}")

        if not is_member:
            return Response(
                {"error": "You are not a member of this group."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Retrieve query parameters
        limit = int(request.GET.get('limit', 20))
        with_details = request.GET.get('with_details', 'false').lower() == 'true'
        
        print(f"[DEBUG] limit = {limit}, with_details = {with_details}")
        
        limit = int(request.GET.get("limit", 20))
        with_details = request.GET.get("with_details", "false").lower() == "true"

        print(f"🔍 DEBUG: limit = {limit}, with_details = {with_details}")

        # Scope of Restriction
        limit = min(max(limit, 1), 100)

        # Get a list of recommended movies
        print(f"[DEBUG] calling RecommendationService.get_group_deck()")
        movie_ids = RecommendationService.get_group_deck(group_session, limit=limit)
        
        print(f"[DEBUG] got {len(movie_ids)} movie IDs")
        
        # For detailed information, retrieve it from TMDB.
        if with_details:
            print(f"[DEBUG] fetching movie details from TMDB...")
        print("🔍 DEBUG: calling RecommendationService.get_group_deck()")
        movie_ids = RecommendationService.get_group_deck(group_session, limit=limit)

        print(f"🔍 DEBUG: got {len(movie_ids)} movie IDs")

        # For detailed information, retrieve it from TMDB.
        if with_details:
            print("🔍 DEBUG: fetching movie details from TMDB...")
            movies = []
            for tmdb_id in movie_ids:
                movie_info = RecommendationService.get_movie_details(tmdb_id)
                if movie_info:
                    movies.append(movie_info)
                    print(f"[DEBUG] fetched movie {movie_info.get('title')}")
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
        
        print(f"[DEBUG] returning response with {len(movies)} movies")
        

        print(f"🔍 DEBUG: returning response with {len(movies)} movies")

        return Response(response_data, status=status.HTTP_200_OK)

    except ValueError as e:
        print(f"[ERROR] ValueError: {e}")
        import traceback

        traceback.print_exc()
        return Response(
            {"error": f"Invalid parameter format: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        print(f"[ERROR] Exception: {e}")
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
    print(f"[DEBUG swipe_like] Called for group {group_code} by user {request.user.username}")
    try:
        # 获取群组
        group_session = get_object_or_404(
            GroupSession, group_code=group_code, is_active=True
        )
        print(f"[DEBUG swipe_like] Group found: {group_code}")
        

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
            is_match = RecommendationService.check_group_match(
                group_session, 
                tmdb_id
            )
            
            print(f"[DEBUG] Match check result: is_match = {is_match} for movie {tmdb_id}")
            
            match_data = None
            if is_match:
                print(f"[DEBUG] MATCH DETECTED! Broadcasting to group {group_session.group_code}")
                try:
                    # Create or retrieve matching records
                    match, created = GroupMatch.objects.get_or_create(
                        group_session=group_session,
                        tmdb_id=tmdb_id,
                        defaults={'movie_title': movie_title}
                    )
                    
                    print(f"[DEBUG] Match object created: created={created}, match_id={match.id}")
                    
                    # Get movie details for response and broadcasting
                    movie_info = RecommendationService.get_movie_details(tmdb_id)
                    
                    # Get list of users who matched this movie
                    matched_by_users = list(
                        GroupSwipe.objects.filter(
                            group_session=group_session,
                            tmdb_id=tmdb_id,
                            action=GroupSwipe.Action.LIKE
                        ).values_list('user__username', flat=True)
                    )
                    
                    # Build match_data for response
                    poster_url = None
                    if movie_info and movie_info.get('poster_path'):
                        poster_url = f"https://image.tmdb.org/t/p/w500{movie_info['poster_path']}"
                    
                    # Handle genres - could be list of dicts or list of strings
                    genres_list = []
                    if movie_info and movie_info.get('genres'):
                        genres = movie_info.get('genres', [])
                        if isinstance(genres, list) and len(genres) > 0:
                            if isinstance(genres[0], dict):
                                genres_list = [g.get('name', str(g)) for g in genres]
                            elif isinstance(genres[0], str):
                                genres_list = genres
                    
                    match_data = {
                        "match_id": match.id,
                        "tmdb_id": tmdb_id,
                        "movie_title": movie_title or (movie_info.get('title') if movie_info else 'this movie'),
                        "poster_url": poster_url,
                        "year": movie_info.get('release_date', '')[:4] if movie_info and movie_info.get('release_date') else None,
                        "genres": genres_list,
                        "overview": movie_info.get('overview', '') if movie_info else '',
                        "vote_average": movie_info.get('vote_average') if movie_info else None,
                        "matched_at": match.matched_at.isoformat(),
                        "matched_by": matched_by_users,
                        "member_count": len(matched_by_users),
                        "message": f"[MATCH] Everyone likes '{movie_title or (movie_info.get('title') if movie_info else 'this movie')}'!"
                    }
                    
                    # Only broadcast if this is a newly created match (to avoid duplicate broadcasts)
                    if created:
                        print(f"[DEBUG] New match created, broadcasting to WebSocket...")
                        _broadcast_match_event(
                            group_session.group_code,
                            match.id,
                            tmdb_id,
                            match_data["movie_title"],
                            movie_info,
                            matched_by_users,
                            match.matched_at.isoformat()
                        )
                        print(f"[DEBUG] Match event broadcast completed")
                    else:
                        print(f"[DEBUG] Match already existed, skipping broadcast")
                        
                except Exception as e:
                    print(f"[ERROR] Exception in match handling: {e}")
                    import traceback
                    traceback.print_exc()
                    raise
            
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
