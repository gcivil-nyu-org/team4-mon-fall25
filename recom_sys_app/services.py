# recom_sys_app/services.py
from django.core.cache import cache
from collections import Counter
import requests
import os
from .models import GroupMember, GroupSwipe, Interaction, UserProfile


class RecommendationService:
    """群组电影推荐服务"""

    TMDB_TOKEN = os.getenv("TMDB_TOKEN") or os.getenv("TMDB_API_KEY")
    TMDB_BASE_URL = "https://api.themoviedb.org/3"
    TMDB_HEADERS = (
        {
            "Authorization": f"Bearer {TMDB_TOKEN}",
            "Accept": "application/json",
        }
        if TMDB_TOKEN
        else {}
    )
    CACHE_TIMEOUT = 3600  # 1小时缓存

    @classmethod
    def get_group_deck(cls, group_session, limit=50):
        """
        为群组生成个性化电影推荐列表

        For COMMUNITY groups: filter movies by community genre
        For PRIVATE groups: generate recommendations based on group member history

        Args:
            group_session: GroupSession 实例
            limit: 返回电影数量

        Returns:
            list: 电影 tmdb_id 列表
        """
        # 检查缓存
        cache_key = f"group_deck_{group_session.id}"
        cached_deck = cache.get(cache_key)
        if cached_deck:
            return cached_deck[:limit]

        # For COMMUNITY groups, filter by genre only
        if group_session.kind == "COMMUNITY":
            # Get genre from community_key or genre_filter
            genre_name = group_session.genre_filter or ""
            if not genre_name and group_session.community_key:
                # Extract from community_key (format: "genre:Action")
                if group_session.community_key.startswith("genre:"):
                    genre_name = group_session.community_key.split(":", 1)[1]

            print(f"[DEBUG get_group_deck] COMMUNITY mode - genre_name: {genre_name}")
            print(
                f"[DEBUG get_group_deck] community_key: {group_session.community_key}, genre_filter: {group_session.genre_filter}"
            )

            if genre_name:
                # Get genre IDs and fetch movies
                genre_ids = cls._get_genre_ids_by_names([genre_name])
                print(f"[DEBUG get_group_deck] genre_ids: {genre_ids}")
                if genre_ids:
                    movie_ids = cls._get_movies_by_genres(genre_ids, limit * 2)
                    print(
                        f"[DEBUG get_group_deck] Fetched {len(movie_ids)} movies for genre {genre_name}"
                    )
                else:
                    movie_ids = cls._get_popular_movies(limit * 2)
                    print(
                        f"[DEBUG get_group_deck] No genre IDs found, using popular movies"
                    )
            else:
                movie_ids = cls._get_popular_movies(limit * 2)
                print(
                    f"[DEBUG get_group_deck] No genre name found, using popular movies"
                )

            # For communities, filter out movies user already swiped via Interaction model
            from .models import Interaction

            # Get all users in community
            user_ids = GroupMember.objects.filter(
                group_session=group_session, is_active=True
            ).values_list("user_id", flat=True)

            # Get all swiped movie IDs by community members
            swiped_ids = set(
                Interaction.objects.filter(user_id__in=user_ids).values_list(
                    "tmdb_id", flat=True
                )
            )
        else:
            # For PRIVATE groups, use original logic
            # 获取活跃成员
            members = GroupMember.objects.filter(
                group_session=group_session, is_active=True
            ).select_related("user")

            if members.count() < 2:
                # 人数不足，返回热门电影
                movie_ids = cls._get_popular_movies(limit * 2)
            else:
                # 基于群组历史 likes 生成推荐（传递 group_session）
                movie_ids = cls._generate_group_recommendations(
                    group_session, members, limit * 2
                )

            # 过滤已经滑过的电影
            swiped_ids = set(
                GroupSwipe.objects.filter(group_session=group_session).values_list(
                    "tmdb_id", flat=True
                )
            )

        # 移除已滑过的电影
        filtered_movies = [mid for mid in movie_ids if mid not in swiped_ids]

        # 缓存结果
        cache.set(cache_key, filtered_movies, cls.CACHE_TIMEOUT)

        return filtered_movies[:limit]

    @classmethod
    def get_solo_deck(cls, user, limit=50):
        """
        Generate personalized movie recommendations for solo mode

        Args:
            user: User instance
            limit: Number of movies to return

        Returns:
            list: Movie tmdb_id list
        """
        # Check cache
        cache_key = f"solo_deck_{user.id}"
        cached_deck = cache.get(cache_key)
        if cached_deck:
            return cached_deck[:limit]

        # Get user's interaction history
        liked_interactions = Interaction.objects.filter(
            user=user, status=Interaction.Status.LIKE
        ).values_list("tmdb_id", flat=True)

        has_history = liked_interactions.count() > 0

        if has_history:
            # Returning user: use swipe history
            movie_ids = cls._generate_solo_recommendations_from_history(
                user, list(liked_interactions), limit * 2
            )
        else:
            # New user: use onboarding preferences
            movie_ids = cls._generate_solo_recommendations_from_profile(user, limit * 2)

        # Filter out already-swiped movies
        swiped_ids = set(
            Interaction.objects.filter(user=user).values_list("tmdb_id", flat=True)
        )

        # Remove already-swiped movies
        filtered_movies = [mid for mid in movie_ids if mid not in swiped_ids]

        # Cache results
        cache.set(cache_key, filtered_movies, cls.CACHE_TIMEOUT)

        return filtered_movies[:limit]

    @classmethod
    def _generate_solo_recommendations_from_history(
        cls, user, liked_movie_ids, limit=100
    ):
        """
        Generate recommendations based on user's like history

        Strategy:
        1. Analyze genres from liked movies
        2. Recommend similar movies from those genres
        """
        if not liked_movie_ids:
            return cls._get_popular_movies(limit)

        # Extract genres from liked movies
        all_genres = []
        for tmdb_id in liked_movie_ids[:10]:  # Analyze up to 10 recent likes
            movie_details = cls.get_movie_details(tmdb_id)
            if movie_details and movie_details.get("genres"):
                all_genres.extend(movie_details["genres"])

        if not all_genres:
            return cls._get_popular_movies(limit)

        # Count genre frequency
        genre_counter = Counter(all_genres)

        # Get top 3 genres
        top_genres = [genre for genre, _ in genre_counter.most_common(3)]

        # Fetch movies from TMDB by those genres
        genre_ids = cls._get_genre_ids_by_names(top_genres)

        if genre_ids:
            movie_ids = cls._get_movies_by_genres(genre_ids, limit)
        else:
            movie_ids = cls._get_popular_movies(limit)

        return movie_ids

    @classmethod
    def _generate_solo_recommendations_from_profile(cls, user, limit=100):
        """
        Generate recommendations based on user's onboarding preferences

        Strategy:
        1. Use favourite_genre1 and favourite_genre2 from UserProfile
        2. Fetch popular movies from those genres
        """
        try:
            profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            return cls._get_popular_movies(limit)

        # Get user's favorite genres from profile
        favorite_genres = []
        if profile.favourite_genre1:
            favorite_genres.append(profile.favourite_genre1)
        if profile.favourite_genre2:
            favorite_genres.append(profile.favourite_genre2)

        if not favorite_genres:
            return cls._get_popular_movies(limit)

        # Convert genre names to IDs
        genre_ids = cls._get_genre_ids_by_names(favorite_genres)

        if genre_ids:
            movie_ids = cls._get_movies_by_genres(genre_ids, limit)
        else:
            movie_ids = cls._get_popular_movies(limit)

        return movie_ids

    @classmethod
    def _generate_group_recommendations(cls, group_session, members, limit=100):
        """
        基于群组历史 likes 生成推荐

        Args:
            group_session: GroupSession 实例
            members: GroupMember QuerySet
            limit: 返回电影数量

        策略：
        1. 找出群组成员都喜欢过的电影类型
        2. 基于这些类型推荐新电影
        """
        # 获取群组所有成员喜欢过的电影
        liked_movie_ids = list(
            GroupSwipe.objects.filter(
                group_session=group_session, action=GroupSwipe.Action.LIKE
            )
            .values_list("tmdb_id", flat=True)
            .distinct()
        )

        if not liked_movie_ids:
            # 没有历史数据，返回热门电影
            return cls._get_popular_movies(limit)

        # 从喜欢的电影中提取类型
        all_genres = []
        for tmdb_id in liked_movie_ids[:10]:  # 只分析最近10部
            movie_details = cls.get_movie_details(tmdb_id)
            if movie_details and movie_details.get("genres"):
                # genres 是字符串列表，如 ['Action', 'Thriller']
                all_genres.extend(movie_details["genres"])

        if not all_genres:
            return cls._get_popular_movies(limit)

        # 统计类型频率
        genre_counter = Counter(all_genres)

        # 选择最常见的3个类型
        top_genres = [genre for genre, _ in genre_counter.most_common(3)]

        # 从 TMDB 获取这些类型的电影
        # 注意：需要先将类型名转换为 genre_id
        genre_ids = cls._get_genre_ids_by_names(top_genres)

        if genre_ids:
            movie_ids = cls._get_movies_by_genres(genre_ids, limit)
        else:
            movie_ids = cls._get_popular_movies(limit)

        return movie_ids

    @classmethod
    def _get_genre_ids_by_names(cls, genre_names):
        """
        将类型名称转换为 TMDB genre_id

        TMDB 类型映射（常见的）:
        """
        genre_map = {
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
            "Thriller": 53,
            "War": 10752,
            "Western": 37,
        }

        genre_ids = []
        for name in genre_names:
            if name in genre_map:
                genre_ids.append(genre_map[name])

        return genre_ids

    @classmethod
    def _get_movies_by_genres(cls, genre_ids, limit=100):
        """
        从 TMDB 获取指定类型的高评分电影
        """
        try:
            # 构建类型筛选参数
            genre_str = "|".join(map(str, genre_ids))

            params = {
                "with_genres": genre_str,
                "sort_by": "vote_average.desc",
                "vote_count.gte": 100,  # 至少100个投票
                "page": 1,
            }

            response = requests.get(
                f"{cls.TMDB_BASE_URL}/discover/movie",
                params=params,
                headers=cls.TMDB_HEADERS,
                timeout=10,
            )
            response.raise_for_status()

            data = response.json()
            movie_ids = [movie["id"] for movie in data.get("results", [])]

            # 如果第一页不够，获取第二页
            if len(movie_ids) < limit and data.get("total_pages", 0) > 1:
                params["page"] = 2
                response = requests.get(
                    f"{cls.TMDB_BASE_URL}/discover/movie",
                    params=params,
                    headers=cls.TMDB_HEADERS,
                    timeout=10,
                )
                response.raise_for_status()
                data = response.json()
                movie_ids.extend([movie["id"] for movie in data.get("results", [])])

            return movie_ids[:limit]

        except Exception as e:
            print(f"Error fetching movies by genres: {e}")
            return cls._get_popular_movies(limit)

    @classmethod
    def _get_popular_movies(cls, limit=50):
        """
        获取热门电影作为后备方案
        """
        try:
            params = {"page": 1}

            response = requests.get(
                f"{cls.TMDB_BASE_URL}/movie/popular",
                params=params,
                headers=cls.TMDB_HEADERS,
                timeout=10,
            )
            response.raise_for_status()

            data = response.json()
            movie_ids = [movie["id"] for movie in data.get("results", [])]

            return movie_ids[:limit]

        except Exception as e:
            print(f"Error fetching popular movies: {e}")
            return []

    @classmethod
    def check_group_match(cls, group_session, tmdb_id):
        """
        检查是否所有活跃成员都喜欢这部电影

        Args:
            group_session: GroupSession 实例
            tmdb_id: 电影 ID

        Returns:
            bool: 是否匹配
        """
        # 获取活跃成员数量
        active_member_count = GroupMember.objects.filter(
            group_session=group_session, is_active=True
        ).count()

        # 获取喜欢这部电影的成员数量
        like_count = GroupSwipe.objects.filter(
            group_session=group_session, tmdb_id=tmdb_id, action=GroupSwipe.Action.LIKE
        ).count()

        print(
            f"[DEBUG check_group_match] active_members: {active_member_count}, likes: {like_count}, tmdb_id: {tmdb_id}"
        )

        # 检查是否所有人都喜欢
        is_match = like_count >= active_member_count and active_member_count > 0
        print(f"[DEBUG check_group_match] Result: {is_match}")
        return is_match

    @classmethod
    def get_movie_details(cls, tmdb_id):
        """
        从 TMDB 获取电影详情

        Args:
            tmdb_id: 电影 ID

        Returns:
            dict: 电影信息
        """
        cache_key = f"movie_details_{tmdb_id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        try:
            response = requests.get(
                f"{cls.TMDB_BASE_URL}/movie/{tmdb_id}",
                headers=cls.TMDB_HEADERS,
                timeout=10,
            )
            response.raise_for_status()

            data = response.json()

            # 格式化返回数据
            movie_info = {
                "tmdb_id": data["id"],
                "title": data.get("title", ""),
                "original_title": data.get("original_title", ""),
                "overview": data.get("overview", ""),
                "poster_path": data.get("poster_path", ""),
                "backdrop_path": data.get("backdrop_path", ""),
                "release_date": data.get("release_date", ""),
                "vote_average": data.get("vote_average", 0),
                "vote_count": data.get("vote_count", 0),
                "runtime": data.get("runtime", 0),
                "genres": [g["name"] for g in data.get("genres", [])],  # ← 类型名称列表
            }

            # 缓存 24 小时
            cache.set(cache_key, movie_info, 86400)

            return movie_info

        except Exception as e:
            print(f"Error fetching movie details: {e}")
            return None

    @classmethod
    def invalidate_deck_cache(cls, group_session):
        """
        清除群组推荐缓存（当有新的 swipe 或成员变化时调用）
        """
        cache_key = f"group_deck_{group_session.id}"
        cache.delete(cache_key)

    @classmethod
    def search_movies(cls, query, limit=10):
        """
        Search for movies by title using TMDb API

        Args:
            query: Movie title to search for
            limit: Maximum number of results to return

        Returns:
            list: List of movie dictionaries with id, title, year, poster_path
        """
        if not cls.TMDB_TOKEN:
            return []

        try:
            url = f"{cls.TMDB_BASE_URL}/search/movie"
            params = {
                "query": query,
                "language": "en-US",
                "page": 1,
                "include_adult": False,
            }

            response = requests.get(
                url, headers=cls.TMDB_HEADERS, params=params, timeout=10
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for movie in data.get("results", [])[:limit]:
                results.append(
                    {
                        "tmdb_id": movie.get("id"),
                        "title": movie.get("title"),
                        "year": (
                            movie.get("release_date", "")[:4]
                            if movie.get("release_date")
                            else ""
                        ),
                        "poster_path": movie.get("poster_path"),
                        "overview": movie.get("overview", ""),
                        "vote_average": movie.get("vote_average", 0),
                    }
                )

            return results

        except Exception as e:
            print(f"Error searching movies: {e}")
            return []

    @classmethod
    def get_similar_movies(cls, tmdb_id, limit=20):
        """
        Get similar movies using TMDb's similar movies endpoint

        Args:
            tmdb_id: TMDb movie ID
            limit: Maximum number of similar movies to return

        Returns:
            list: List of similar movie dictionaries
        """
        # Check cache first
        cache_key = f"similar_movies_{tmdb_id}"
        cached_similar = cache.get(cache_key)
        if cached_similar:
            return cached_similar[:limit]

        if not cls.TMDB_TOKEN:
            return []

        try:
            url = f"{cls.TMDB_BASE_URL}/movie/{tmdb_id}/similar"
            params = {"language": "en-US", "page": 1}

            response = requests.get(
                url, headers=cls.TMDB_HEADERS, params=params, timeout=10
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for movie in data.get("results", []):
                results.append(
                    {
                        "tmdb_id": movie.get("id"),
                        "title": movie.get("title"),
                        "year": (
                            movie.get("release_date", "")[:4]
                            if movie.get("release_date")
                            else ""
                        ),
                        "poster_path": movie.get("poster_path"),
                        "overview": movie.get("overview", ""),
                        "vote_average": movie.get("vote_average", 0),
                        "backdrop_path": movie.get("backdrop_path"),
                        "genre_ids": movie.get("genre_ids", []),
                    }
                )

            # Cache for 1 hour
            cache.set(cache_key, results, cls.CACHE_TIMEOUT)

            return results[:limit]

        except Exception as e:
            print(f"Error fetching similar movies: {e}")
            return []
