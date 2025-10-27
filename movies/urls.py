from django.urls import path
from . import views

app_name = "movies"

urlpatterns = [
    path("", views.movie_list, name="movie_list"),
    path("movie/<int:movie_id>/", views.movie_detail, name="movie_detail"),
]
