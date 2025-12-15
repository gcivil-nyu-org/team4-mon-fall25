# recom_sys_app/services.py
from django.core.cache import cache
from django.db.models import Count
from django.contrib.auth import get_user_model

# Count imported locally where needed
from collections import Counter, defaultdict
import requests
import os
import math
from .models import GroupMember, GroupSwipe, Interaction, UserProfile

User = get_user_model()


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
    def get_group_deck(
        cls,
        group_session,
        user=None,
        limit=50,
        selected_genre_ids=None,
        use_collaborative_filtering=False,
    ):
        """
        为群组生成个性化电影推荐列表

        Args:
            group_session: GroupSession 实例
            user: User 实例（可选，用于过滤该用户已滑过的电影）
            limit: 返回电影数量
            selected_genre_ids: Optional list of genre IDs to filter by (default: None)

        Returns:
            list: 电影 tmdb_id 列表
        """
        # 检查缓存（如果提供了user，缓存key包含user_id）
        if user:
            cache_key = f"group_deck_{group_session.id}_user_{user.id}_cf_{use_collaborative_filtering}"
        else:
            cache_key = (
                f"group_deck_{group_session.id}_cf_{use_collaborative_filtering}"
            )

        cached_deck = cache.get(cache_key)
        if cached_deck:
            return cached_deck[:limit]

        # 获取活跃成员
        members = GroupMember.objects.filter(
            group_session=group_session, is_active=True
        ).select_related("user")

        # Combine group-based recommendations with collaborative filtering if enabled
        movie_ids = []

        # 1. Get group-based recommendations
        if members.count() < 2:
            # 人数不足，返回热门电影
            movie_ids = cls._get_popular_movies(limit * 2)
        else:
            # 基于群组历史 likes 生成推荐（传递 group_session）
            movie_ids = cls._generate_group_recommendations(
                group_session, members, limit * 2
            )

        # 2. Add collaborative filtering recommendations if enabled and user provided
        if use_collaborative_filtering and user:
            try:
                from .services import CollaborativeFilteringService
                from .models import Interaction

                interaction_count = Interaction.objects.filter(user=user).count()
                if (
                    interaction_count
                    >= CollaborativeFilteringService.MIN_INTERACTIONS_FOR_CF
                ):
                    # Get CF recommendations
                    cf_movies = (
                        CollaborativeFilteringService.get_collaborative_recommendations(
                            user, limit=limit
                        )
                    )
                    # Add CF movies to the list (prioritize them)
                    existing_ids = set(movie_ids)
                    cf_filtered = [mid for mid in cf_movies if mid not in existing_ids]
                    # Add CF movies at the beginning (higher priority)
                    movie_ids = cf_filtered[: limit // 2] + movie_ids
            except Exception as e:
                print(f"Collaborative filtering failed in group deck: {e}")
                # Continue with group-based recommendations only

        # 过滤已经滑过的电影（只过滤当前用户滑过的）
        if user:
            # 用户级别过滤：只排除该用户滑过的电影
            swiped_ids = set(
                GroupSwipe.objects.filter(
                    group_session=group_session, user=user  # ✅ 只过滤当前用户的swipes
                ).values_list("tmdb_id", flat=True)
            )
        else:
            # 群组级别过滤：排除所有人滑过的电影（向后兼容）
            swiped_ids = set(
                GroupSwipe.objects.filter(group_session=group_session).values_list(
                    "tmdb_id", flat=True
                )
            )

        # 移除已滑过的电影
        filtered_movies = [mid for mid in movie_ids if mid not in swiped_ids]

        # Filter by selected genres if provided
        if selected_genre_ids:
            # First, fetch movies directly from selected genres (most efficient)
            genre_based_movies = cls._get_movies_by_genres(
                selected_genre_ids, limit=limit * 3, randomize=True
            )
            # Remove already-swiped movies from genre-based results
            genre_based_movies = [
                mid for mid in genre_based_movies if mid not in swiped_ids
            ]

            # Also filter the group recommendations by genre
            # (to combine group-based recommendations with genre filtering)
            genre_filtered_group = []
            for tmdb_id in filtered_movies[
                : limit * 3
            ]:  # Check up to 3x limit for variety
                if tmdb_id in swiped_ids:
                    continue
                try:
                    movie_details = cls.get_movie_details(tmdb_id)
                    if movie_details:
                        # Get genre IDs from movie
                        movie_genres = movie_details.get("genres", [])
                        movie_genre_ids = []
                        for genre in movie_genres:
                            if isinstance(genre, dict) and "id" in genre:
                                movie_genre_ids.append(genre.get("id"))
                            elif isinstance(genre, int):
                                movie_genre_ids.append(genre)

                        # Check if movie matches any selected genre
                        if any(gid in selected_genre_ids for gid in movie_genre_ids):
                            genre_filtered_group.append(tmdb_id)

                        if len(genre_filtered_group) >= limit * 2:
                            break
                except Exception:
                    # If we can't fetch details, skip it (we have genre-based movies)
                    continue

            # Combine genre-based and filtered group recommendations
            # Prioritize genre-based (they're guaranteed to match), then supplement with group
            # Use dict.fromkeys to preserve order and remove duplicates
            combined_ids = list(
                dict.fromkeys(genre_based_movies + genre_filtered_group)
            )
            filtered_movies = [mid for mid in combined_ids if mid not in swiped_ids]

        # Add randomization for variety (shuffle to avoid same order every time)
        import random

        if len(filtered_movies) > limit:
            random.shuffle(filtered_movies)

        # 缓存结果
        cache.set(cache_key, filtered_movies, cls.CACHE_TIMEOUT)

        return filtered_movies[:limit]

    @classmethod
    def get_solo_deck(
        cls,
        user,
        limit=50,
        use_collaborative_filtering=True,
        offset=0,
        selected_genre_ids=None,
    ):
        """
        Generate personalized movie recommendations for solo mode.
        Uses hybrid approach: collaborative filtering + preference-based recommendations.
        Supports pagination via offset for variety.

        Args:
            user: User instance
            limit: Number of movies to return
            use_collaborative_filtering: Whether to use collaborative filtering (default: True)
            offset: Offset for pagination (default: 0)
            selected_genre_ids: Optional list of genre IDs to filter by (default: None)

        Returns:
            list: Movie tmdb_id list
        """
        # Check cache (but use offset to get different movies)
        cache_key = f"solo_deck_{user.id}_{use_collaborative_filtering}"
        cached_deck = cache.get(cache_key)
        if cached_deck and offset == 0:
            # Return from cache only if no offset (first page)
            return cached_deck[:limit]
        elif cached_deck and offset > 0:
            # Return next batch from cache if available
            if offset < len(cached_deck):
                return cached_deck[offset : offset + limit]  # noqa: E203
            # If cache exhausted, generate more (will be added to cache below)

        # SIMPLIFIED: When genres are selected, skip all preference/CF logic
        # Just use genre-based movies (handled in genre filtering section below)
        # Generate more movies for pagination (3x limit to support multiple pages)
        generation_limit = max(limit * 3, 150)  # At least 150 movies for variety

        # Initialize empty - will be populated by genre filtering if genres selected
        # Otherwise, use simple popular movies fallback
        movie_ids = []

        # Filter out already-swiped movies
        swiped_ids = set(
            Interaction.objects.filter(user=user).values_list("tmdb_id", flat=True)
        )

        # Filter by selected genres if provided
        preference_based_ids = set()  # Track which movies are preference-based
        if selected_genre_ids:
            # SIMPLIFIED: Prioritize genre-based movies, but add 1-2 preference-based
            # Fetch many movies from selected genres (simple and direct)
            min_movies_needed = max(limit, 50)  # At least 50 movies
            fetch_limit = max(
                generation_limit * 2, min_movies_needed * 3
            )  # Fetch 3x to account for swipes

            # Get genre-based movies directly (simple approach)
            genre_based_movies = cls._get_movies_by_genres(
                selected_genre_ids, limit=fetch_limit, randomize=True
            )
            # Remove already-swiped movies
            genre_filtered = [
                mid for mid in genre_based_movies if mid not in swiped_ids
            ]

            # Add 20-30% preference-based movies if user has preferences
            pref_movies_list = []
            try:
                from .models import UserPreference

                preference = UserPreference.objects.get(user=user)
                if preference.genre_preferences and preference.total_interactions > 0:
                    # Calculate target: 20-30% of the deck should be preference-based
                    target_pref_count = max(
                        int(limit * 0.25), 10
                    )  # At least 10, or 25% of limit
                    # Get more preference-based movies (we'll filter and mix them)
                    pref_movies = cls._generate_solo_recommendations_from_preferences(
                        user, preference, limit=target_pref_count * 2
                    )
                    # Filter out swiped and ensure they match selected genres
                    pref_filtered = []
                    for mid in pref_movies:
                        if mid not in swiped_ids and mid not in genre_filtered:
                            # Verify movie matches selected genres (use cached details if available)
                            movie_details = cls.get_movie_details(mid)
                            if movie_details:
                                movie_genres = movie_details.get("genres", [])
                                # Convert genre names to IDs for comparison
                                movie_genre_ids = cls._get_genre_ids_by_names(
                                    movie_genres
                                )
                                # Only include if matches at least one selected genre
                                if any(
                                    gid in selected_genre_ids for gid in movie_genre_ids
                                ):
                                    pref_filtered.append(mid)
                                    if len(pref_filtered) >= target_pref_count:
                                        break
                    # Track preference-based movie IDs
                    pref_movies_list = pref_filtered[:target_pref_count]
                    preference_based_ids = set(pref_movies_list)
            except UserPreference.DoesNotExist:
                pass  # No preferences, skip

            # Mix preference-based and genre-based movies throughout the deck
            # Strategy: Interleave them (every 3-4 genre movies, add 1 preference movie)
            filtered_movies = []
            pref_index = 0
            genre_index = 0
            pref_count = len(pref_movies_list)
            genre_count = len(genre_filtered)

            # Mix movies: for every 3 genre movies, add 1 preference movie
            while len(filtered_movies) < limit and (
                pref_index < pref_count or genre_index < genre_count
            ):
                # Add genre-based movies in batches of 3
                for _ in range(3):
                    if genre_index < genre_count:
                        filtered_movies.append(genre_filtered[genre_index])
                        genre_index += 1
                        if len(filtered_movies) >= limit:
                            break

                # Add 1 preference-based movie after every 3 genre movies
                if pref_index < pref_count and len(filtered_movies) < limit:
                    filtered_movies.append(pref_movies_list[pref_index])
                    pref_index += 1

                # If we run out of one type, fill with the other
                if pref_index >= pref_count and genre_index < genre_count:
                    remaining = limit - len(filtered_movies)
                    if remaining > 0:
                        filtered_movies.extend(
                            genre_filtered[genre_index : genre_index + remaining]
                        )
                    break
                elif genre_index >= genre_count and pref_index < pref_count:
                    remaining = limit - len(filtered_movies)
                    if remaining > 0:
                        filtered_movies.extend(
                            pref_movies_list[pref_index : pref_index + remaining]
                        )
                    break

            # Ensure we have at most the requested limit
            filtered_movies = filtered_movies[:limit]

            # Store preference-based IDs in cache for the view to retrieve
            if preference_based_ids:
                cache.set(
                    f"solo_pref_ids_{user.id}_{'_'.join(map(str, selected_genre_ids))}",
                    preference_based_ids,
                    cls.CACHE_TIMEOUT,
                )
        else:
            # No genre filtering - use simple approach: just remove swiped movies
            # If no genres selected, fall back to popular movies (simple)
            if not movie_ids or len(movie_ids) < limit:
                # Fallback to popular movies if we don't have enough
                popular_movies = cls._get_popular_movies(limit * 2)
                movie_ids = list(dict.fromkeys(list(movie_ids) + popular_movies))

            filtered_movies = [mid for mid in movie_ids if mid not in swiped_ids]

        # Add randomization for variety (shuffle only genre-based movies, keep preference-based at start)
        import random

        if len(filtered_movies) > limit and preference_based_ids:
            # Shuffle only the genre-based portion (after preference-based movies)
            pref_count = len([m for m in filtered_movies if m in preference_based_ids])
            if pref_count > 0:
                genre_portion = filtered_movies[pref_count:]
                random.shuffle(genre_portion)
                filtered_movies = filtered_movies[:pref_count] + genre_portion
            else:
                random.shuffle(filtered_movies)
        elif len(filtered_movies) > limit:
            random.shuffle(filtered_movies)

        # If we have cached deck, merge with new movies (for pagination)
        if cached_deck and offset > 0:
            # Merge cached and new movies, avoiding duplicates
            existing_ids = set(cached_deck)
            new_movies = [mid for mid in filtered_movies if mid not in existing_ids]
            filtered_movies = cached_deck + new_movies
            # Update cache with merged list
            cache.set(cache_key, filtered_movies, cls.CACHE_TIMEOUT)
            # Return the requested slice
            if offset < len(filtered_movies):
                return filtered_movies[offset : offset + limit]  # noqa: E203
            else:
                # Offset beyond available, return empty
                return []
        else:
            # Cache results (cache more than limit for pagination - store 3x limit)
            cache.set(cache_key, filtered_movies, cls.CACHE_TIMEOUT)
            # Ensure we return at least 50 movies if available, but respect the limit
            return filtered_movies[: max(limit, min(50, len(filtered_movies)))]

    @classmethod
    def _generate_solo_recommendations_from_preferences(
        cls, user, preference, limit=100
    ):
        """
        Generate recommendations using UserPreference genre scores.

        Args:
            user: User instance
            preference: UserPreference instance
            limit: Number of movies to fetch

        Returns:
            list: Movie tmdb_id list
        """
        # Get top genres from preferences
        top_genres = preference.get_top_genres(limit=5)
        if not top_genres:
            return cls._generate_solo_recommendations_from_history_or_profile(
                user, limit
            )

        # Get genre names and scores
        genre_names = [genre for genre, _ in top_genres]
        genre_scores = {genre: score for genre, score in top_genres}

        # Get movies for top genres
        genre_ids = cls._get_genre_ids_by_names(genre_names)
        if not genre_ids:
            return cls._generate_solo_recommendations_from_history_or_profile(
                user, limit
            )

        # Fetch movies and score them by genre preference
        all_movies = []
        for genre_id in genre_ids:
            movies = cls._get_movies_by_genres([genre_id], limit // len(genre_ids) + 10)
            all_movies.extend(movies)

        # Score movies based on genre preferences
        scored_movies = []
        for tmdb_id in all_movies:
            movie_details = cls.get_movie_details(tmdb_id)
            if not movie_details:
                continue

            # Calculate weighted score based on genre preferences
            movie_genres = movie_details.get("genres", [])
            score = 0.0
            for genre_name in movie_genres:
                score += genre_scores.get(genre_name, 0.0)

            # Average score across genres
            if movie_genres:
                score = score / len(movie_genres)

            scored_movies.append((tmdb_id, score))

        # Sort by score and return top movies
        scored_movies.sort(key=lambda x: x[1], reverse=True)
        return [tmdb_id for tmdb_id, _ in scored_movies[:limit]]

    @classmethod
    def _generate_solo_recommendations_from_history_or_profile(cls, user, limit=100):
        """
        Fallback method: use history or profile-based recommendations.

        Args:
            user: User instance
            limit: Number of movies to return

        Returns:
            list: Movie tmdb_id list
        """
        # Get user's interaction history
        liked_interactions = Interaction.objects.filter(
            user=user, status=Interaction.Status.LIKE
        ).values_list("tmdb_id", flat=True)

        has_history = liked_interactions.count() > 0

        if has_history:
            # Returning user: use swipe history
            return cls._generate_solo_recommendations_from_history(
                user, list(liked_interactions), limit
            )
        else:
            # New user: use onboarding preferences
            return cls._generate_solo_recommendations_from_profile(user, limit)

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
    def _get_movies_by_genres(cls, genre_ids, limit=100, randomize=True):
        """
        从 TMDB 获取指定类型的高评分电影
        Fetches from multiple pages and randomizes for variety
        添加随机性，避免每次返回相同电影
        Uses OR logic: movies matching ANY of the selected genres
        Handles niche genres (TV Movie, Music, Western, War, Family) with lower thresholds
        """
        import random

        try:
            # Niche genres that typically have fewer movies in TMDB
            # These need lower vote_count thresholds or no threshold at all
            niche_genre_ids = {
                10770,
                10402,
                37,
                10752,
                10751,
            }  # TV Movie, Music, Western, War, Family
            is_niche_genre = any(gid in niche_genre_ids for gid in genre_ids)

            # 构建类型筛选参数 - pipe-separated means OR logic (movies matching ANY genre)
            genre_str = "|".join(map(str, genre_ids))

            all_movie_ids = []
            # Fetch more pages to ensure we get enough movies, especially for genres with few movies
            # Calculate pages needed: at least enough for limit, plus extra for variety
            pages_per_sort = max(
                15, (limit // 20) + 10
            )  # Fetch at least 15 pages per sort order (increased for niche genres)

            # Try different sort orders for variety (includes vote_count.desc from develop)
            sort_options = [
                "popularity.desc",  # Most popular / 最受欢迎 (usually has most results)
                "vote_average.desc",  # Highest rated / 评分最高
                "release_date.desc",  # Newest / 最新上映
                "vote_count.desc",  # Most reviewed / 评论最多
            ]

            # Use all sort options to maximize variety and ensure we get enough movies
            for sort_by in sort_options:
                if len(all_movie_ids) >= limit * 3:
                    break  # Already have enough

                for page in range(1, pages_per_sort + 1):
                    # For niche genres, use much lower thresholds or remove entirely
                    if is_niche_genre:
                        # Start with lower threshold, remove it completely after page 5
                        if page <= 3:
                            vote_threshold = 10  # Very low threshold for niche genres
                        elif page <= 8:
                            vote_threshold = 5  # Even lower
                        else:
                            vote_threshold = None  # No threshold - get all movies
                    else:
                        # Regular genres: progressive lowering
                        vote_threshold = 100 if page <= 5 else 50 if page <= 10 else 20

                    params = {
                        "with_genres": genre_str,  # OR logic: movies matching ANY genre
                        "sort_by": sort_by,
                        "page": page,
                        "include_adult": "false",
                        "language": "en-US",
                    }

                    # Only add vote_count filter if threshold is set
                    if vote_threshold is not None:
                        params["vote_count.gte"] = vote_threshold

                    try:
                        response = requests.get(
                            f"{cls.TMDB_BASE_URL}/discover/movie",
                            params=params,
                            headers=cls.TMDB_HEADERS,
                            timeout=10,
                        )
                        response.raise_for_status()
                        data = response.json()
                        page_movies = [movie["id"] for movie in data.get("results", [])]

                        if not page_movies:
                            # No more movies on this page, try next sort order
                            break

                        all_movie_ids.extend(page_movies)

                        # Stop if we have enough or no more pages
                        total_pages = data.get("total_pages", 1)
                        if len(all_movie_ids) >= limit * 3 or page >= total_pages:
                            break
                    except Exception:
                        continue  # Skip failed pages

            # Remove duplicates while preserving order
            seen = set()
            unique_movies = []
            for movie_id in all_movie_ids:
                if movie_id not in seen:
                    seen.add(movie_id)
                    unique_movies.append(movie_id)

            # If we still don't have enough movies, fetch from each genre individually
            # This works for both single and multiple genres
            if len(unique_movies) < limit:
                # Fetch from each genre individually to ensure we get enough movies
                for genre_id in genre_ids:
                    if len(unique_movies) >= limit * 3:
                        break
                    try:
                        # For niche genres, use very low or no threshold
                        is_single_niche = genre_id in niche_genre_ids
                        single_genre_params = {
                            "with_genres": str(genre_id),
                            "sort_by": "popularity.desc",
                            "include_adult": "false",
                            "language": "en-US",
                        }

                        # Only add vote_count for non-niche genres or early pages
                        if not is_single_niche:
                            single_genre_params["vote_count.gte"] = 20

                        # Fetch more pages for niche genres
                        max_pages = 20 if is_single_niche else 15

                        # Fetch multiple pages from this genre
                        for page in range(1, max_pages + 1):
                            if len(unique_movies) >= limit * 3:
                                break

                            # For niche genres, remove threshold after a few pages
                            if is_single_niche and page > 5:
                                single_genre_params.pop("vote_count.gte", None)

                            single_genre_params["page"] = page
                            response = requests.get(
                                f"{cls.TMDB_BASE_URL}/discover/movie",
                                params=single_genre_params,
                                headers=cls.TMDB_HEADERS,
                                timeout=10,
                            )
                            response.raise_for_status()
                            data = response.json()
                            page_movies = [
                                movie["id"] for movie in data.get("results", [])
                            ]

                            if not page_movies:
                                break

                            for movie_id in page_movies:
                                if movie_id not in seen:
                                    seen.add(movie_id)
                                    unique_movies.append(movie_id)
                                    if len(unique_movies) >= limit * 3:
                                        break

                            if page >= data.get("total_pages", 1):
                                break
                    except Exception:
                        continue  # Skip failed genres

            # Randomize for variety if requested
            if randomize and len(unique_movies) > limit:
                random.shuffle(unique_movies)

            return unique_movies[:limit]

        except Exception as e:
            print(f"Error fetching movies by genres: {e}")
            return cls._get_popular_movies(limit, randomize=randomize)

    @classmethod
    def _get_popular_movies(cls, limit=50, randomize=True):
        """
        获取热门电影作为后备方案
        Fetches from multiple pages and randomizes for variety
        添加随机页码，避免每次返回相同电影
        """
        import random

        try:
            all_movie_ids = []
            pages_to_fetch = min(5, (limit // 20) + 2)  # Fetch more pages for variety

            for page in range(1, pages_to_fetch + 1):
                params = {"page": page}

                try:
                    response = requests.get(
                        f"{cls.TMDB_BASE_URL}/movie/popular",
                        params=params,
                        headers=cls.TMDB_HEADERS,
                        timeout=10,
                    )
                    response.raise_for_status()
                    data = response.json()
                    page_movies = [movie["id"] for movie in data.get("results", [])]
                    all_movie_ids.extend(page_movies)

                    # Stop if we have enough or no more pages
                    if len(all_movie_ids) >= limit * 2 or page >= data.get(
                        "total_pages", 1
                    ):
                        break
                except Exception:
                    continue  # Skip failed pages

            # Remove duplicates
            seen = set()
            unique_movies = []
            for movie_id in all_movie_ids:
                if movie_id not in seen:
                    seen.add(movie_id)
                    unique_movies.append(movie_id)

            # Randomize for variety if requested
            if randomize and len(unique_movies) > limit:
                random.shuffle(unique_movies)

            return unique_movies[:limit]

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
        现在需要清除所有用户的个性化缓存，包括所有 CF 变体
        """
        # 清除旧的群组级别缓存（向后兼容）
        cache_key = f"group_deck_{group_session.id}"
        cache.delete(cache_key)

        # 清除所有活跃成员的用户级别缓存（包括所有 CF 变体）
        active_members = GroupMember.objects.filter(
            group_session=group_session, is_active=True
        ).select_related("user")

        for member in active_members:
            # Clear cache for both CF=True and CF=False variants
            for use_cf in [True, False]:
                user_cache_key = (
                    f"group_deck_{group_session.id}_user_{member.user.id}_cf_{use_cf}"
                )
                cache.delete(user_cache_key)
            # Also clear old format (without _cf_ suffix) for backward compatibility
            user_cache_key_old = f"group_deck_{group_session.id}_user_{member.user.id}"
            cache.delete(user_cache_key_old)
            print(
                f"[DEBUG] Cleared cache for user {member.user.username} (all variants)"
            )

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
        Get similar movies using TMDb's recommendations endpoint with filtering
        for more relevant results. Returns movies that share at least one genre
        with the original movie and meet quality thresholds.

        Args:
            tmdb_id: TMDb movie ID
            limit: Maximum number of similar movies to return (default: 20)

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
            # First, get the original movie's genres
            movie_url = f"{cls.TMDB_BASE_URL}/movie/{tmdb_id}"
            movie_response = requests.get(
                movie_url, headers=cls.TMDB_HEADERS, timeout=10
            )
            movie_response.raise_for_status()
            original_movie = movie_response.json()
            original_genres = set(
                genre["id"] for genre in original_movie.get("genres", [])
            )

            # Fetch from multiple pages to get more results
            all_results = []
            max_pages = 5  # Fetch up to 5 pages for more variety
            target_results = max(limit * 2, 50)  # Get more than needed for filtering

            for page in range(1, max_pages + 1):
                # Use recommendations endpoint for better matches
                url = f"{cls.TMDB_BASE_URL}/movie/{tmdb_id}/recommendations"
                params = {"language": "en-US", "page": page}

                response = requests.get(
                    url, headers=cls.TMDB_HEADERS, params=params, timeout=10
                )
                response.raise_for_status()
                data = response.json()

                page_results = data.get("results", [])
                if not page_results:
                    break  # No more results

                for movie in page_results:
                    # Get movie year
                    release_date = movie.get("release_date", "")
                    year = release_date[:4] if release_date else ""

                    # Get movie genres
                    movie_genre_ids = set(movie.get("genre_ids", []))

                    # Filter criteria (relaxed for more results):
                    # 1. Must have a release year
                    # 2. Movie must be from 1990 or newer (relaxed from 2000)
                    # 3. Must have at least 20 votes (lowered from 100)
                    # 4. Must have rating of 4.0 or higher (lowered from 5.0)
                    # 5. Must share at least 1 genre with the original movie (relaxed from 2)
                    if not year:
                        continue
                    try:
                        if int(year) < 1990:
                            continue
                    except ValueError:
                        continue
                    if movie.get("vote_count", 0) < 20:
                        continue
                    if movie.get("vote_average", 0) < 4.0:
                        continue
                    # Check genre overlap - must share at least 1 genre for similarity
                    genre_overlap = original_genres.intersection(movie_genre_ids)
                    if len(genre_overlap) < 1:
                        continue

                    # Calculate similarity score:
                    # - Genre match score (more shared genres = higher score)
                    # - Rating score (higher rating = higher score)
                    # - Vote count score (more votes = more popular/trusted)
                    genre_match_score = len(genre_overlap)
                    rating_score = (
                        movie.get("vote_average", 0) / 10.0
                    )  # Normalize to 0-1
                    vote_score = min(
                        movie.get("vote_count", 0) / 1000.0, 1.0
                    )  # Cap at 1000 votes
                    similarity_score = (
                        genre_match_score * 0.5 + rating_score * 0.3 + vote_score * 0.2
                    )

                    # Avoid duplicates
                    movie_id = movie.get("id")
                    if any(r["tmdb_id"] == movie_id for r in all_results):
                        continue

                    all_results.append(
                        {
                            "tmdb_id": movie_id,
                            "title": movie.get("title"),
                            "year": year,
                            "poster_path": movie.get("poster_path"),
                            "overview": movie.get("overview", ""),
                            "vote_average": movie.get("vote_average", 0),
                            "backdrop_path": movie.get("backdrop_path"),
                            "genre_ids": movie.get("genre_ids", []),
                            "vote_count": movie.get("vote_count", 0),
                            "genre_match_score": genre_match_score,
                            "similarity_score": similarity_score,
                        }
                    )

                    # Stop if we have enough results
                    if len(all_results) >= target_results:
                        break

                # Stop if we have enough results
                if len(all_results) >= target_results:
                    break

            # If we don't have enough results from recommendations, try the "similar" endpoint
            if len(all_results) < limit:
                print(
                    f"[DEBUG] Only found {len(all_results)} from recommendations, trying similar endpoint..."
                )
                for page in range(1, 3):  # Try 2 pages from similar endpoint
                    similar_url = f"{cls.TMDB_BASE_URL}/movie/{tmdb_id}/similar"
                    similar_params = {"language": "en-US", "page": page}

                    similar_response = requests.get(
                        similar_url,
                        headers=cls.TMDB_HEADERS,
                        params=similar_params,
                        timeout=10,
                    )
                    similar_response.raise_for_status()
                    similar_data = similar_response.json()

                    similar_page_results = similar_data.get("results", [])
                    if not similar_page_results:
                        break

                    for movie in similar_page_results:
                        # Get movie year
                        release_date = movie.get("release_date", "")
                        year = release_date[:4] if release_date else ""

                        # Get movie genres
                        movie_genre_ids = set(movie.get("genre_ids", []))

                        # Apply same filtering criteria
                        if not year:
                            continue
                        try:
                            if int(year) < 1990:
                                continue
                        except ValueError:
                            continue
                        if movie.get("vote_count", 0) < 20:
                            continue
                        if movie.get("vote_average", 0) < 4.0:
                            continue
                        # Check genre overlap
                        genre_overlap = original_genres.intersection(movie_genre_ids)
                        if len(genre_overlap) < 1:
                            continue

                        # Calculate similarity score
                        genre_match_score = len(genre_overlap)
                        rating_score = movie.get("vote_average", 0) / 10.0
                        vote_score = min(movie.get("vote_count", 0) / 1000.0, 1.0)
                        similarity_score = (
                            genre_match_score * 0.5
                            + rating_score * 0.3
                            + vote_score * 0.2
                        )

                        # Avoid duplicates
                        movie_id = movie.get("id")
                        if any(r["tmdb_id"] == movie_id for r in all_results):
                            continue

                        all_results.append(
                            {
                                "tmdb_id": movie_id,
                                "title": movie.get("title"),
                                "year": year,
                                "poster_path": movie.get("poster_path"),
                                "overview": movie.get("overview", ""),
                                "vote_average": movie.get("vote_average", 0),
                                "backdrop_path": movie.get("backdrop_path"),
                                "genre_ids": movie.get("genre_ids", []),
                                "vote_count": movie.get("vote_count", 0),
                                "genre_match_score": genre_match_score,
                                "similarity_score": similarity_score,
                            }
                        )

                        if len(all_results) >= target_results:
                            break

                    if len(all_results) >= target_results:
                        break

            # Sort by similarity score (descending) for best matches first
            all_results.sort(key=lambda x: x["similarity_score"], reverse=True)

            # Cache for 1 hour
            cache.set(cache_key, all_results, cls.CACHE_TIMEOUT)

            return all_results[:limit]

        except Exception as e:
            print(f"Error fetching similar movies: {e}")
            import traceback

            traceback.print_exc()
            return []

    @classmethod
    def check_all_members_finished(cls, group_session):
        """检查是否所有成员都滑完了"""
        active_members = GroupMember.objects.filter(
            group_session=group_session, is_active=True
        ).select_related("user")

        total_members = active_members.count()

        print(f"[DEBUG check_finished] Group: {group_session.group_code}")
        print(f"[DEBUG check_finished] Total active members: {total_members}")

        if total_members == 0:
            return {
                "all_finished": False,
                "total_members": 0,
                "finished_members": 0,
                "total_movies": 20,
            }

        # 固定每轮 20 部电影
        MOVIES_PER_ROUND = 20
        total_movies = MOVIES_PER_ROUND

        print(f"[DEBUG check_finished] Movies per round: {total_movies}")

        finished_members = 0

        # 检查每个成员（包括当前用户）
        for member in active_members:
            # 统计该成员的滑动次数（包括 LIKE 和 DISLIKE）
            swipe_count = GroupSwipe.objects.filter(
                group_session=group_session, user=member.user
            ).count()

            print(
                f"[DEBUG check_finished] User: {member.user.username} (ID: {member.user.id})"
            )
            print(f"[DEBUG check_finished]   - Total swipes: {swipe_count}")

            # 滑动次数 >= 20 = 完成
            if swipe_count >= MOVIES_PER_ROUND:
                print("[DEBUG check_finished]   - ✅ User FINISHED!")
                finished_members += 1
            else:
                print(
                    f"[DEBUG check_finished]   - ❌ NOT finished ({swipe_count}/{MOVIES_PER_ROUND})"
                )

        all_finished = (finished_members == total_members) and total_members > 0

        print(
            f"[DEBUG check_finished] Result: {finished_members}/{total_members} finished"
        )
        print(f"[DEBUG check_finished] All finished: {all_finished}")
        print(
            f"[DEBUG check_finished] Active members list: {[m.user.username for m in active_members]}"
        )

        return {
            "all_finished": all_finished,
            "total_members": total_members,
            "finished_members": finished_members,
            "total_movies": total_movies,
        }

    @classmethod
    def get_all_common_matches(cls, group_session):
        """
        获取所有成员都喜欢的电影列表

        Args:
            group_session: GroupSession 实例

        Returns:
            list: 所有人都喜欢的电影列表
            [
                {
                    'tmdb_id': 550,
                    'movie_title': 'Fight Club',
                    'movie_info': {...},
                    'poster_url': '...',
                    'year': '1999',
                    'genres': ['Drama', 'Thriller'],
                    'overview': '...',
                    'vote_average': 8.4
                },
                ...
            ]
        """
        print(f"[DEBUG get_all_common_matches] Group: {group_session.group_code}")

        # 获取活跃成员数量
        active_members = GroupMember.objects.filter(
            group_session=group_session, is_active=True
        )
        total_members = active_members.count()

        print(f"[DEBUG get_all_common_matches] Total active members: {total_members}")

        if total_members == 0:
            return []

        # 查询所有 LIKE 的电影，按 tmdb_id 分组，统计每部电影的点赞数
        from django.db.models import Count

        common_movies = (
            GroupSwipe.objects.filter(
                group_session=group_session, action=GroupSwipe.Action.LIKE
            )
            .values("tmdb_id")
            .annotate(like_count=Count("id"))
            .filter(like_count=total_members)  # 所有人都喜欢
            .values_list("tmdb_id", flat=True)
        )

        common_movie_ids = list(common_movies)
        print(
            f"[DEBUG get_all_common_matches] Found {len(common_movie_ids)} common matches"
        )
        print(f"[DEBUG get_all_common_matches] Movie IDs: {common_movie_ids}")

        # 获取每部电影的详细信息
        result = []
        for tmdb_id in common_movie_ids:
            # 从缓存或 TMDB API 获取电影详情
            movie_info = cls.get_movie_details(tmdb_id)

            if movie_info:
                # 构建海报 URL
                poster_url = None
                if movie_info.get("poster_path"):
                    poster_url = (
                        f"https://image.tmdb.org/t/p/w500{movie_info['poster_path']}"
                    )

                # 处理类型
                genres_list = []
                if movie_info.get("genres"):
                    genres = movie_info["genres"]
                    if isinstance(genres, list) and len(genres) > 0:
                        if isinstance(genres[0], dict):
                            genres_list = [g.get("name", str(g)) for g in genres]
                        elif isinstance(genres[0], str):
                            genres_list = genres

                # 获取电影标题
                movie_title = movie_info.get("title", f"Movie {tmdb_id}")

                result.append(
                    {
                        "tmdb_id": tmdb_id,
                        "movie_title": movie_title,
                        "movie_info": movie_info,
                        "poster_url": poster_url,
                        "year": (
                            movie_info.get("release_date", "")[:4]
                            if movie_info.get("release_date")
                            else None
                        ),
                        "genres": genres_list,
                        "overview": movie_info.get("overview", ""),
                        "vote_average": movie_info.get("vote_average"),
                    }
                )

                print(f"[DEBUG get_all_common_matches] Added movie: {movie_title}")

        print(f"[DEBUG get_all_common_matches] Returning {len(result)} movies")
        return result

    @classmethod
    def clear_group_swipes(cls, group_session):
        """清空群组的所有滑动记录，开始新一轮"""
        deleted_count = GroupSwipe.objects.filter(group_session=group_session).delete()[
            0
        ]

        print(
            f"[DEBUG clear_swipes] Cleared {deleted_count} swipe records for group {group_session.group_code}"
        )

        # delete all swipe record in the group 删除该群组的所有swipe记录
        deleted_count, _ = GroupSwipe.objects.filter(
            group_session=group_session
        ).delete()

        print(f"[DEBUG clear_group_swipes] Deleted {deleted_count} swipe records")

        # clear recommendation cache
        cls.invalidate_deck_cache(group_session)

        return deleted_count


class PreferenceService:
    """
    Service for calculating and updating user preferences based on interaction history.
    Automatically learns from user likes/dislikes to improve recommendations.
    """

    @classmethod
    def update_user_preferences(cls, user, force_recalculate=False):
        """
        Calculate and update user preferences based on interaction history.

        Args:
            user: User instance
            force_recalculate: If True, recalculate even if recently updated

        Returns:
            UserPreference: The updated preference object
        """
        from .models import UserPreference, Interaction
        from django.db import transaction
        from django.utils import timezone
        from datetime import timedelta

        # Get or create preference object
        preference, created = UserPreference.objects.get_or_create(user=user)

        # Skip if recently updated (unless force_recalculate)
        if not force_recalculate and not created:
            recent_threshold = timezone.now() - timedelta(minutes=5)
            if preference.last_updated > recent_threshold:
                return preference

        # Get all user interactions
        interactions = Interaction.objects.filter(user=user).select_related()

        # Calculate statistics
        total_interactions = interactions.count()
        total_likes = interactions.filter(
            status__in=[
                Interaction.Status.LIKE,
                Interaction.Status.WATCHED_LIKED,
            ]
        ).count()
        total_dislikes = interactions.filter(
            status__in=[
                Interaction.Status.DISLIKE,
                Interaction.Status.WATCHED_DISLIKED,
            ]
        ).count()

        # Calculate average rating
        ratings = interactions.exclude(rating__isnull=True).values_list(
            "rating", flat=True
        )
        average_rating = sum(ratings) / len(ratings) if ratings else None

        # Calculate genre preferences
        genre_weights = {}
        liked_movies = interactions.filter(
            status__in=[Interaction.Status.LIKE, Interaction.Status.WATCHED_LIKED]
        ).values_list("tmdb_id", flat=True)
        disliked_movies = interactions.filter(
            status__in=[Interaction.Status.DISLIKE, Interaction.Status.WATCHED_DISLIKED]
        ).values_list("tmdb_id", flat=True)

        # Process liked movies: +2 weight per genre
        for tmdb_id in liked_movies[:50]:  # Limit to avoid too many API calls
            movie_details = RecommendationService.get_movie_details(tmdb_id)
            if movie_details and movie_details.get("genres"):
                for genre_name in movie_details["genres"]:
                    genre_weights[genre_name] = genre_weights.get(genre_name, 0) + 2

        # Process disliked movies: -1 weight per genre
        for tmdb_id in disliked_movies[:20]:  # Limit to avoid too many API calls
            movie_details = RecommendationService.get_movie_details(tmdb_id)
            if movie_details and movie_details.get("genres"):
                for genre_name in movie_details["genres"]:
                    genre_weights[genre_name] = genre_weights.get(genre_name, 0) - 1

        # Normalize genre scores to 0.0-1.0 range
        genre_preferences = {}
        if genre_weights:
            min_weight = min(genre_weights.values())
            max_weight = max(genre_weights.values())
            weight_range = max_weight - min_weight if max_weight != min_weight else 1

            for genre, weight in genre_weights.items():
                # Normalize: (weight - min) / range
                normalized = (
                    (weight - min_weight) / weight_range if weight_range > 0 else 0.5
                )
                # Ensure it's between 0.0 and 1.0
                genre_preferences[genre] = max(0.0, min(1.0, normalized))

        # Extract preferred actors/directors from liked movies
        # Note: This requires additional API calls to get credits
        # For now, we'll skip this to avoid too many API calls
        # Can be enhanced later with a separate endpoint or background job
        preferred_actors = []
        preferred_directors = []

        # Optional: Fetch credits for top liked movies (can be expensive)
        # Uncomment if you want to track actors/directors
        # for tmdb_id in liked_movies[:10]:  # Limit to avoid API rate limits
        #     try:
        #         credits_url = f"{RecommendationService.TMDB_BASE_URL}/movie/{tmdb_id}/credits"
        #         response = requests.get(
        #             credits_url,
        #             headers=RecommendationService.TMDB_HEADERS,
        #             timeout=10,
        #         )
        #         if response.status_code == 200:
        #             credits = response.json()
        #             # Extract top 3 cast members
        #             cast = credits.get("cast", [])[:3]
        #             for actor in cast:
        #                 actor_id = actor.get("id")
        #                 if actor_id and actor_id not in preferred_actors:
        #                     preferred_actors.append(actor_id)
        #             # Extract directors
        #             crew = credits.get("crew", [])
        #             for person in crew:
        #                 if person.get("job") == "Director":
        #                     director_id = person.get("id")
        #                     if director_id and director_id not in preferred_directors:
        #                         preferred_directors.append(director_id)
        #     except Exception:
        #         pass  # Skip if API call fails

        # Update preference object
        with transaction.atomic():
            preference.genre_preferences = genre_preferences
            preference.preferred_actors = preferred_actors[:20]  # Limit to top 20
            preference.preferred_directors = preferred_directors[:10]  # Limit to top 10
            preference.average_rating_given = average_rating
            preference.total_interactions = total_interactions
            preference.total_likes = total_likes
            preference.total_dislikes = total_dislikes
            preference.save()

        return preference

    @classmethod
    def get_user_genre_scores(cls, user):
        """
        Get genre preference scores for a user.

        Args:
            user: User instance

        Returns:
            dict: Genre name -> score (0.0-1.0)
        """
        from .models import UserPreference

        try:
            preference = UserPreference.objects.get(user=user)
            return preference.genre_preferences or {}
        except UserPreference.DoesNotExist:
            return {}


class CollaborativeFilteringService:
    """
    Collaborative Filtering Service for movie recommendations.

    Uses user-based collaborative filtering to find similar users and recommend
    movies based on what similar users liked.

    Features:
    - User similarity calculation using cosine similarity
    - Cached similarity matrices for performance
    - Integration with preference-based recommendations
    - Hybrid recommendation approach
    """

    # Cache timeouts
    SIMILARITY_CACHE_TIMEOUT = 86400  # 24 hours (user similarities don't change often)
    RECOMMENDATION_CACHE_TIMEOUT = 3600  # 1 hour (recommendations per user)
    MIN_INTERACTIONS_FOR_CF = 3  # Minimum interactions needed for CF to work
    MIN_SIMILAR_USERS = 3  # Minimum similar users needed for recommendations
    SIMILARITY_THRESHOLD = 0.1  # Minimum similarity score (0.0-1.0)

    @classmethod
    def get_user_interaction_vector(cls, user):
        """
        Build interaction vector for a user.

        Returns a dict mapping tmdb_id -> interaction score:
        - LIKE: 2.0
        - WATCHED_LIKED: 2.0
        - DISLIKE: -1.0
        - WATCHED_DISLIKED: -1.0
        - WATCH_LATER: 0.5
        - WATCHED: 0.0 (neutral)

        Args:
            user: User instance

        Returns:
            dict: {tmdb_id: score, ...}
        """
        interactions = Interaction.objects.filter(user=user).select_related()

        vector = {}
        for interaction in interactions:
            tmdb_id = interaction.tmdb_id
            status = interaction.status

            # Map status to score
            if status in [Interaction.Status.LIKE, Interaction.Status.WATCHED_LIKED]:
                score = 2.0
            elif status in [
                Interaction.Status.DISLIKE,
                Interaction.Status.WATCHED_DISLIKED,
            ]:
                score = -1.0
            elif status == Interaction.Status.WATCH_LATER:
                score = 0.5
            else:  # WATCHED (neutral)
                score = 0.0

            # If user has a rating, incorporate it
            if interaction.rating:
                # Normalize rating (1-10) to (-1, 1) range
                normalized_rating = (interaction.rating - 5.5) / 4.5
                score = score + normalized_rating * 0.5

            # Accumulate scores if user has multiple interactions with same movie
            vector[tmdb_id] = vector.get(tmdb_id, 0.0) + score

        return vector

    @classmethod
    def cosine_similarity(cls, vector1, vector2):
        """
        Calculate cosine similarity between two interaction vectors.

        Args:
            vector1: dict of {tmdb_id: score, ...}
            vector2: dict of {tmdb_id: score, ...}

        Returns:
            float: Similarity score between 0.0 and 1.0
        """
        # Get intersection of movies both users interacted with
        common_movies = set(vector1.keys()) & set(vector2.keys())

        if not common_movies:
            return 0.0

        # Calculate dot product and magnitudes
        dot_product = sum(vector1[movie] * vector2[movie] for movie in common_movies)

        magnitude1 = math.sqrt(sum(score**2 for score in vector1.values()))
        magnitude2 = math.sqrt(sum(score**2 for score in vector2.values()))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        # Cosine similarity: dot product / (magnitude1 * magnitude2)
        similarity = dot_product / (magnitude1 * magnitude2)

        # Normalize to 0.0-1.0 range (cosine similarity is -1 to 1, but with our scoring it's usually 0-1)
        return max(0.0, min(1.0, similarity))

    @classmethod
    def find_similar_users(cls, user, limit=20, min_similarity=None):
        """
        Find users similar to the given user based on interaction patterns.

        Args:
            user: User instance
            limit: Maximum number of similar users to return
            min_similarity: Minimum similarity threshold (default: SIMILARITY_THRESHOLD)

        Returns:
            list: List of tuples (similar_user, similarity_score) sorted by score descending
        """
        if min_similarity is None:
            min_similarity = cls.SIMILARITY_THRESHOLD

        # Check cache
        cache_key = f"similar_users_{user.id}"
        cached_similar = cache.get(cache_key)
        if cached_similar:
            return cached_similar[:limit]

        # Get user's interaction vector
        user_vector = cls.get_user_interaction_vector(user)

        if len(user_vector) < cls.MIN_INTERACTIONS_FOR_CF:
            # User doesn't have enough interactions for CF
            return []

        # Get all other users with interactions
        other_users = (
            User.objects.exclude(id=user.id)
            .filter(interactions__isnull=False)
            .distinct()
        )

        similar_users = []
        for other_user in other_users:
            other_vector = cls.get_user_interaction_vector(other_user)

            if len(other_vector) < cls.MIN_INTERACTIONS_FOR_CF:
                continue

            similarity = cls.cosine_similarity(user_vector, other_vector)

            if similarity >= min_similarity:
                similar_users.append((other_user, similarity))

        # Sort by similarity (descending)
        similar_users.sort(key=lambda x: x[1], reverse=True)

        # Cache results
        cache.set(cache_key, similar_users, cls.SIMILARITY_CACHE_TIMEOUT)

        return similar_users[:limit]

    @classmethod
    def get_collaborative_recommendations(cls, user, limit=50, min_similar_users=None):
        """
        Get movie recommendations using collaborative filtering.

        Strategy:
        1. Find similar users
        2. Get movies they liked (that current user hasn't seen)
        3. Score movies by weighted similarity (more similar users = higher score)
        4. Return top recommendations

        Args:
            user: User instance
            limit: Maximum number of recommendations
            min_similar_users: Minimum number of similar users needed (default: MIN_SIMILAR_USERS)

        Returns:
            list: List of tmdb_id recommendations sorted by score
        """
        if min_similar_users is None:
            min_similar_users = cls.MIN_SIMILAR_USERS

        # Check cache
        cache_key = f"cf_recommendations_{user.id}"
        cached_recs = cache.get(cache_key)
        if cached_recs:
            return cached_recs[:limit]

        # Find similar users
        similar_users = cls.find_similar_users(user, limit=50)

        if len(similar_users) < min_similar_users:
            # Not enough similar users for reliable recommendations
            return []

        # Get movies current user has already interacted with
        user_interactions = set(
            Interaction.objects.filter(user=user).values_list("tmdb_id", flat=True)
        )

        # Score movies based on similar users' preferences
        movie_scores = defaultdict(float)
        movie_counts = defaultdict(int)

        for similar_user, similarity_score in similar_users:
            # Get movies similar user liked
            liked_movies = Interaction.objects.filter(
                user=similar_user,
                status__in=[Interaction.Status.LIKE, Interaction.Status.WATCHED_LIKED],
            ).values_list("tmdb_id", flat=True)

            # Score each movie by similarity weight
            for tmdb_id in liked_movies:
                if tmdb_id not in user_interactions:
                    # Weight by similarity: more similar users = higher score
                    movie_scores[tmdb_id] += similarity_score
                    movie_counts[tmdb_id] += 1

        if not movie_scores:
            return []

        # Normalize scores by number of similar users who liked it
        # Movies liked by more similar users get higher scores
        for tmdb_id in movie_scores:
            # Average similarity score * log(count) to favor movies liked by multiple similar users
            count = movie_counts[tmdb_id]
            movie_scores[tmdb_id] = movie_scores[tmdb_id] * (1 + math.log(count + 1))

        # Sort by score and return top movies
        sorted_movies = sorted(movie_scores.items(), key=lambda x: x[1], reverse=True)
        recommendations = [tmdb_id for tmdb_id, _ in sorted_movies]

        # Cache results
        cache.set(cache_key, recommendations, cls.RECOMMENDATION_CACHE_TIMEOUT)

        return recommendations[:limit]

    @classmethod
    def get_hybrid_recommendations(
        cls, user, limit=50, cf_weight=0.4, preference_weight=0.4, popular_weight=0.2
    ):
        """
        Get hybrid recommendations combining collaborative filtering and preference-based approaches.

        Args:
            user: User instance
            limit: Maximum number of recommendations
            cf_weight: Weight for collaborative filtering (0.0-1.0)
            preference_weight: Weight for preference-based (0.0-1.0)
            popular_weight: Weight for popular movies fallback (0.0-1.0)

        Returns:
            list: List of tmdb_id recommendations
        """
        # Normalize weights
        total_weight = cf_weight + preference_weight + popular_weight
        if total_weight > 0:
            cf_weight /= total_weight
            preference_weight /= total_weight
            popular_weight /= total_weight

        # Check cache
        cache_key = f"hybrid_recommendations_{user.id}_{cf_weight}_{preference_weight}"
        cached_recs = cache.get(cache_key)
        if cached_recs:
            return cached_recs[:limit]

        all_movies = {}

        # 1. Get collaborative filtering recommendations
        cf_movies = cls.get_collaborative_recommendations(user, limit=limit * 2)
        for idx, tmdb_id in enumerate(cf_movies):
            score = (len(cf_movies) - idx) * cf_weight  # Higher rank = higher score
            all_movies[tmdb_id] = all_movies.get(tmdb_id, 0.0) + score

        # 2. Get preference-based recommendations
        try:
            from .models import UserPreference

            preference = UserPreference.objects.get(user=user)
            if preference.genre_preferences and preference.total_interactions > 0:
                pref_movies = RecommendationService._generate_solo_recommendations_from_preferences(
                    user, preference, limit * 2
                )
                for idx, tmdb_id in enumerate(pref_movies):
                    score = (len(pref_movies) - idx) * preference_weight
                    all_movies[tmdb_id] = all_movies.get(tmdb_id, 0.0) + score
        except Exception:
            pass  # Fallback if preferences don't exist

        # 3. Add popular movies as fallback (lower weight)
        if popular_weight > 0:
            popular_movies = RecommendationService._get_popular_movies(limit=limit)
            for idx, tmdb_id in enumerate(popular_movies):
                score = (
                    (len(popular_movies) - idx) * popular_weight * 0.5
                )  # Lower weight for popular
                all_movies[tmdb_id] = all_movies.get(tmdb_id, 0.0) + score

        # Sort by combined score
        sorted_movies = sorted(all_movies.items(), key=lambda x: x[1], reverse=True)
        recommendations = [tmdb_id for tmdb_id, _ in sorted_movies]

        # Cache results
        cache.set(cache_key, recommendations, cls.RECOMMENDATION_CACHE_TIMEOUT)

        return recommendations[:limit]

    @classmethod
    def invalidate_user_cache(cls, user):
        """
        Invalidate all cached data for a user (call when user interactions change).

        Args:
            user: User instance
        """
        cache_keys = [
            f"similar_users_{user.id}",
            f"cf_recommendations_{user.id}",
        ]

        # Also invalidate hybrid recommendations (pattern matching)
        # Note: Django cache doesn't support pattern deletion, so we'll clear common patterns
        for key in cache_keys:
            cache.delete(key)

        # Invalidate hybrid cache (approximate - clear all hybrid for this user)
        # In production, consider using cache versioning or Redis with pattern deletion
        for weight_cf in [0.3, 0.4, 0.5]:
            for weight_pref in [0.3, 0.4, 0.5]:
                cache.delete(
                    f"hybrid_recommendations_{user.id}_{weight_cf}_{weight_pref}"
                )

    @classmethod
    def precompute_similarities(cls, user_ids=None, batch_size=100):
        """
        Precompute user similarities for better performance.
        Useful for background jobs to warm up the cache.

        Args:
            user_ids: List of user IDs to precompute (None = all active users)
            batch_size: Number of users to process at a time
        """
        if user_ids is None:
            # Get all users with at least MIN_INTERACTIONS_FOR_CF interactions
            user_ids = list(
                User.objects.annotate(interaction_count=Count("interactions"))
                .filter(interaction_count__gte=cls.MIN_INTERACTIONS_FOR_CF)
                .values_list("id", flat=True)
            )

        processed = 0
        for user_id in user_ids:
            try:
                user = User.objects.get(id=user_id)
                # This will compute and cache similarities
                cls.find_similar_users(user, limit=20)
                processed += 1

                if processed % batch_size == 0:
                    print(f"Processed {processed} users...")
            except User.DoesNotExist:
                continue

        return processed
