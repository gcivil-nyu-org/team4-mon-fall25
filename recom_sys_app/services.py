# movies/services.py
from django.db.models import Count, Q
from collections import Counter
from .models import GroupSwipe, GroupMember, Interaction, UserProfile

class RecommendationService:
    """电影推荐服务"""
    
    @staticmethod
    def get_group_deck(group_session, limit=50):
        """
        为群组生成个性化电影列表
        
        参数:
            group_session: GroupSession 实例
            limit: 返回电影数量
            
        返回:
            list: tmdb_id 列表
        """
        # 1. 获取群组所有成员
        members = GroupMember.objects.filter(
            group_session=group_session,
            is_active=True
        ).select_related('user')
        
        if not members.exists():
            return []
        
        # 2. 收集所有成员喜欢的类型
        all_genres = []
        for member in members:
            try:
                profile = member.user.profile
                if profile.favourite_genre1:
                    all_genres.append(profile.favourite_genre1)
                if profile.favourite_genre2:
                    all_genres.append(profile.favourite_genre2)
            except UserProfile.DoesNotExist:
                continue
        
        # 3. 找出最受欢迎的类型
        genre_counts = Counter(all_genres)
        top_genres = [genre for genre, count in genre_counts.most_common(3)]
        
        # 4. 获取群组已经滑过的电影
        swiped_movie_ids = GroupSwipe.objects.filter(
            group_session=group_session
        ).values_list('tmdb_id', flat=True).distinct()
        
        # 5. 这里你需要从 TMDB API 或本地缓存获取电影
        # 暂时返回示例数据结构
        # TODO: 集成 TMDB API
        recommended_movies = []
        
        print(f"Group {group_session.group_code} - Top genres: {top_genres}")
        print(f"Already swiped: {len(swiped_movie_ids)} movies")
        
        return recommended_movies
    
    @staticmethod
    def check_group_match(group_session, tmdb_id):
        """
        检查是否所有成员都喜欢这部电影
        
        参数:
            group_session: GroupSession 实例
            tmdb_id: 电影的 TMDB ID
            
        返回:
            bool: 是否匹配
        """
        # 获取活跃成员总数
        total_members = GroupMember.objects.filter(
            group_session=group_session,
            is_active=True
        ).count()
        
        if total_members == 0:
            return False
        
        # 统计喜欢这部电影的人数
        likes_count = GroupSwipe.objects.filter(
            group_session=group_session,
            tmdb_id=tmdb_id,
            action=GroupSwipe.Action.LIKE
        ).count()
        
        return likes_count == total_members