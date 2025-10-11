from django.contrib import admin
from .models import UserProfile, Interaction

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "sex", "country", "favourite_genre1", "favourite_genre2", "created_at")
    list_filter = ("sex", "country", "favourite_genre1", "favourite_genre2")
    search_fields = ("name", "user__username", "country", "liked_g1_title", "liked_g2_title")

@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    list_display = ("user", "tmdb_id", "status", "rating", "source", "updated_at")
    list_filter = ("status", "source", "updated_at")
    search_fields = ("tmdb_id", "user__username")

# Register your models here.
