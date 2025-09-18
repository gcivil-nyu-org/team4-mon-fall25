from django.contrib import admin
from .models import Movie

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ['title', 'release_date', 'vote_average', 'popularity', 'created_at']
    list_filter = ['release_date', 'created_at']
    search_fields = ['title', 'overview']
    readonly_fields = ['tmdb_id', 'created_at', 'updated_at']
    ordering = ['-popularity', '-vote_average']
