from django.urls import path
from django.contrib.auth import views as auth_views
from .views import recommend_view, profile_view, set_interaction_view
from .views_auth import signup_view

urlpatterns = [
    path("signup/", signup_view, name="signup"),  # ✅ remove template_name here
    path("login/", auth_views.LoginView.as_view(
        template_name="recom_sys_app/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),

    path("profile/", profile_view, name="profile"),
    path("recommend/", recommend_view, name="recommend"),
    path("interact/<int:tmdb_id>/<str:status>/", set_interaction_view, name="set_interaction"),
]
