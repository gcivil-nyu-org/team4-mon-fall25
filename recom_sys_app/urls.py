from django.urls import path, include
from django.contrib.auth import views as auth_views
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token

# Import existing views
from .views import recommend_view, profile_view, set_interaction_view
from .views_auth import signup_view

# Import new views (you'll need to add these)
from . import views  # For additional helper views
try:
    from . import api_views  # REST API views
except ImportError:
    api_views = None  # If not created yet

# ============================================
# REST API Router (if api_views exists)
# ============================================
router = DefaultRouter()
if api_views:
    router.register(r'profile', api_views.UserProfileViewSet, basename='api_profile')
    router.register(r'interactions', api_views.InteractionViewSet, basename='api_interaction')

# ============================================
# URL Patterns
# ============================================
urlpatterns = [
    # ==================== EXISTING ROUTES (Template Views) ====================
    # Authentication
    path("signup/", signup_view, name="signup"),
    path("login/", auth_views.LoginView.as_view(
        template_name="recom_sys_app/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
    
    # Profile & Recommendations
    path("profile/", profile_view, name="profile"),
    path("recommend/", recommend_view, name="recommend"),
    
    # Interactions
    path("interact/<int:tmdb_id>/<str:status>/", set_interaction_view, name="set_interaction"),
]

# ==================== NEW HELPER ROUTES (Optional - add if you created these views) ====================
# Uncomment these if you added the helper views to views.py
# urlpatterns += [
#     path("", views.home_view, name="home"),
#     path("stats/", views.user_stats_view, name="user_stats"),
#     path("movie/<int:tmdb_id>/", views.movie_details_view, name="movie_details"),
#     path("search/", views.search_movies_view, name="search_movies"),
# ]

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
        path("recommendations/", api_views.RecommendationsView.as_view(), name="api_recommendations"),
        
        # Include router URLs (profile & interactions viewsets)
        path("", include(router.urls)),
    ]
    
    # Add API routes under /api/ prefix
    urlpatterns += [
        path("api/", include(api_patterns)),
    ]

# ============================================
# URL Reference
# ============================================
"""
EXISTING TEMPLATE-BASED ROUTES:
    /signup/                                - User signup page
    /login/                                 - User login page
    /logout/                                - User logout
    /profile/                               - User profile page
    /recommend/                             - Get recommendations page
    /interact/<tmdb_id>/<status>/           - Set movie interaction

REST API ROUTES :
    /api/health/                            - Health check
    /api/options/                           - Get dropdown options
    
    /api/auth/register/                     - Register new user (REST)
    /api/auth/login/                        - Get auth token
    
    /api/profile/                           - List/Get profile
    /api/profile/<id>/                      - Update/Delete profile
    
    /api/interactions/                      - List/Create interactions
    /api/interactions/<id>/                 - Get/Update/Delete interaction
    /api/interactions/stats/                - Get interaction stats
    /api/interactions/set/<tmdb_id>/<status>/ - Quick set status
    
    /api/recommendations/                   - Get AI recommendations

OPTIONAL HELPER ROUTES (uncomment if needed):
    /                                       - Home/Landing page
    /stats/                                 - User statistics
    /movie/<tmdb_id>/                       - Movie details
    /search/                                - Search movies
"""