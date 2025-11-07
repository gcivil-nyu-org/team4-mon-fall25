from django.urls import path, include
from django.contrib.auth import views as auth_views
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from . import views_solo

# Import views
from .views import recommend_view, profile_view, edit_profile_view, set_interaction_view
from .views_auth import signup_view
from .views_group import (
    get_group_deck,
    swipe_like,
    group_room_view,
    group_deck_view,  # New: Swipe Card Page View
    get_group_matches,  # New: Retrieve matching records
    join_or_create_community_group,  # New: Community group creation
)
from . import views_group
from . import views  # For additional helper views

try:
    from . import api_views  # REST API views
except ImportError:
    api_views = None  # If not created yet

# Application Namespace
app_name = "recom_sys"

# ============================================
# REST API Router (if api_views exists)
# ============================================
router = DefaultRouter()
if api_views:
    router.register(r"profile", api_views.UserProfileViewSet, basename="api_profile")
    router.register(
        r"interactions", api_views.InteractionViewSet, basename="api_interaction"
    )

# ============================================
# URL Patterns
# ============================================
urlpatterns = [
    path(
        "api/groups/<str:group_code>/chat/history/",
        views_group.get_chat_history,
        name="get_chat_history",
    ),
    path(
        "api/groups/<str:group_code>/chat/send/",
        views_group.send_chat_message,
        name="send_chat_message",
    ),
    # ==================== AUTHENTICATION ====================
    path("signup/", signup_view, name="signup"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="recom_sys_app/login.html"),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="recom_sys:login"),
        name="logout",
    ),
    # ==================== PROFILE & RECOMMENDATIONS ====================
    path("profile/", profile_view, name="profile"),
    path("profile/edit/", edit_profile_view, name="edit_profile"),
    path("recommend/", recommend_view, name="recommend"),
    # ==================== INTERACTIONS ====================
    path(
        "interact/<int:tmdb_id>/<str:status>/",
        set_interaction_view,
        name="set_interaction",
    ),
    # ==================== GROUP MATCHING - PAGE VIEWS ====================
    # Group Lobby (Original)
    path("group/<uuid:group_id>/", views.group_lobby, name="group_lobby"),
    # Group Room (existing, using group_code)
    path("groups/<str:group_code>/room/", group_room_view, name="group_room"),
    # Group Swipe Card Page (New)
    path("groups/<str:group_code>/deck/", group_deck_view, name="group_deck_page"),
    path("solo/genres/", views_solo.solo_genre_selection, name="solo_genre_selection"),
    path("solo/deck/", views_solo.solo_deck_view, name="solo_deck"),
    # ==================== MOVIE SEARCH - FIND SIMILAR ====================
    path("search/", views.movie_search_view, name="movie_search"),
    path("api/search/movies/", views.search_movies_api, name="api_search_movies"),
    path("api/movies/<int:tmdb_id>/similar/", views.get_similar_movies_api, name="api_similar_movies"),
    # Solo Mode API Endpoints
    path("api/solo/set-genres/", views_solo.set_solo_genres, name="set_solo_genres"),
    path("api/solo/deck/", views_solo.get_solo_deck, name="get_solo_deck"),
    path("api/solo/swipe/", views_solo.solo_swipe, name="solo_swipe"),
    path("api/solo/likes/", views_solo.get_solo_likes, name="get_solo_likes"),
    # ==================== GROUP MATCHING - API ENDPOINTS ====================
    # Create and join groups (existing ones)
    path("api/groups", views.create_group, name="create_group"),
    path("api/groups/join", views.join_group, name="join_group"),
    path("api/groups/<uuid:group_id>", views.get_group_details, name="group_details"),
    # Group Recommendation API (New)
    path("api/groups/<str:group_code>/deck/", get_group_deck, name="api_group_deck"),
    path("api/groups/<str:group_code>/swipe/like/", swipe_like, name="api_swipe_like"),
    path(
        "api/groups/<str:group_code>/matches/",
        get_group_matches,
        name="api_group_matches",
    ),
    path(
        "api/groups/community/join/",
        join_or_create_community_group,
        name="api_community_join",
    ),
]

# ==================== OPTIONAL HELPER ROUTES ====================
# Uncomment if you have these views
try:
    urlpatterns += [
        path("", views.home_view, name="home"),
        path("stats/", views.user_stats_view, name="user_stats"),
        path("movie/<int:tmdb_id>/", views.movie_details_view, name="movie_details"),
        path("search/", views.search_movies_view, name="search_movies"),
    ]
except AttributeError:
    # Views don't exist yet
    pass

# ==================== REST API ROUTES ====================
if api_views:
    api_patterns = [
        # Health & Options
        path("health/", api_views.health_check, name="api_health"),
        path("options/", api_views.get_options, name="api_options"),
        # Authentication
        path("auth/register/", api_views.RegisterView.as_view(), name="api_register"),
        path("auth/login/", obtain_auth_token, name="api_token_auth"),
        # Recommendations
        path(
            "recommendations/",
            api_views.RecommendationsView.as_view(),
            name="api_recommendations",
        ),
        # Include router URLs (profile & interactions viewsets)
        path("", include(router.urls)),
    ]

    # Add API routes under /api/ prefix
    urlpatterns += [
        path("api/", include(api_patterns)),
    ]

# ============================================
# URL Reference Guide
# ============================================
"""
TEMPLATE-BASED PAGE ROUTES:
    /signup/                                    - User signup page
    /login/                                     - User login page
    /logout/                                    - User logout
    /profile/                                   - User profile page
    /recommend/                                 - Get recommendations page
    /interact/<tmdb_id>/<status>/               - Set movie interaction

    === GROUP MATCHING PAGES ===
    /group/<uuid:group_id>/                     - Group lobby (original)
    /groups/<group_code>/room/                  - Group room (original)
    /groups/<group_code>/deck/                  - Group movie deck (NEW) ⭐

GROUP MATCHING API ENDPOINTS:
    /api/groups                                 - Create group (POST)
    /api/groups/join                            - Join group (POST)
    /api/groups/<uuid:group_id>                 - Get group details (GET)

    === NEW GROUP RECOMMENDATION APIs ===
    /api/groups/<group_code>/deck/              - Get movie recommendations (GET) ⭐
    /api/groups/<group_code>/swipe/like/        - Record like action (POST) ⭐
    /api/groups/<group_code>/matches/           - Get all matches (GET) ⭐

REST API ROUTES (if api_views exists):
    /api/health/                                - Health check
    /api/options/                               - Get dropdown options
    /api/auth/register/                         - Register new user
    /api/auth/login/                            - Get auth token
    /api/profile/                               - Profile CRUD
    /api/interactions/                          - Interaction CRUD
    /api/recommendations/                       - AI recommendations

OPTIONAL HELPER ROUTES:
    /                                           - Home/Landing page
    /stats/                                     - User statistics
    /movie/<tmdb_id>/                           - Movie details
    /search/                                    - Search movies

USAGE EXAMPLES:
    1. User visits group deck page:
       → http://localhost:8000/groups/ABC123/deck/

    2. Frontend fetches movie recommendations:
       → GET /api/groups/ABC123/deck/?with_details=true&limit=20

    3. User swipes right (likes a movie):
       → POST /api/groups/ABC123/swipe/like/
       → Body: {"tmdb_id": 550, "movie_title": "Fight Club"}

    4. Check if there are any matches:
       → GET /api/groups/ABC123/matches/
"""
