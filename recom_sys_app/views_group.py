# recom_sys_app/views_group.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction

from .models import GroupSession, GroupMember, GroupSwipe, GroupMatch
from .services import RecommendationService


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_group_deck(request, group_code):
    """
    获取群组的电影推荐列表
    
    URL: /api/groups/<group_code>/deck/
    Method: GET
    """
    try:
        # 获取群组
        group_session = get_object_or_404(GroupSession, group_code=group_code, is_active=True)
        
        # 验证用户是否是群组成员
        is_member = GroupMember.objects.filter(
            group_session=group_session,
            user=request.user,
            is_active=True
        ).exists()
        
        if not is_member:
            return Response(
                {"error": "你不是这个群组的成员"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 获取推荐电影列表
        movie_ids = RecommendationService.get_group_deck(group_session, limit=50)
        
        # 获取群组信息
        member_count = GroupMember.objects.filter(
            group_session=group_session,
            is_active=True
        ).count()
        
        response_data = {
            "group_code": group_session.group_code,
            "member_count": member_count,
            "movies": movie_ids,  # TODO: 后续需要从 TMDB 获取完整电影信息
            "message": "电影列表获取成功"
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def swipe_like(request, group_code):
    """
    记录用户对电影的 Like 操作
    
    URL: /api/groups/<group_code>/swipe/like/
    Method: POST
    Body: {"tmdb_id": 12345}
    """
    try:
        # 获取群组
        group_session = get_object_or_404(GroupSession, group_code=group_code, is_active=True)
        
        # 验证成员身份
        is_member = GroupMember.objects.filter(
            group_session=group_session,
            user=request.user,
            is_active=True
        ).exists()
        
        if not is_member:
            return Response(
                {"error": "你不是这个群组的成员"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # 获取电影 ID
        tmdb_id = request.data.get('tmdb_id')
        if not tmdb_id:
            return Response(
                {"error": "tmdb_id 是必需的"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 检查是否已经滑过
        existing_swipe = GroupSwipe.objects.filter(
            group_session=group_session,
            user=request.user,
            tmdb_id=tmdb_id
        ).first()
        
        if existing_swipe:
            return Response(
                {"error": "你已经对这部电影做过操作了"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 使用事务确保数据一致性
        with transaction.atomic():
            # 创建滑动记录
            swipe = GroupSwipe.objects.create(
                group_session=group_session,
                user=request.user,
                tmdb_id=tmdb_id,
                action=GroupSwipe.Action.LIKE
            )
            
            # 检查是否所有人都喜欢（匹配）
            is_match = RecommendationService.check_group_match(group_session, tmdb_id)
            
            match_data = None
            if is_match:
                # 创建匹配记录
                match, created = GroupMatch.objects.get_or_create(
                    group_session=group_session,
                    tmdb_id=tmdb_id
                )
                
                if created:
                    match_data = {
                        "match_id": match.id,
                        "tmdb_id": tmdb_id,
                        "message": "🎉 匹配成功！所有成员都喜欢这部电影！"
                    }
        
        response_data = {
            "success": True,
            "swipe_id": swipe.id,
            "action": swipe.action,
            "is_match": is_match,
            "match_data": match_data
        }
        
        return Response(response_data, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )