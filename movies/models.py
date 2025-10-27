from django.db import models


class Movie(models.Model):
    tmdb_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=255)
    overview = models.TextField(blank=True)
    release_date = models.DateField(null=True, blank=True)
    runtime = models.IntegerField(null=True, blank=True)
    vote_average = models.FloatField(default=0.0)
    vote_count = models.IntegerField(default=0)
    popularity = models.FloatField(default=0.0)
    poster_path = models.CharField(max_length=255, blank=True)
    backdrop_path = models.CharField(max_length=255, blank=True)
    genres = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-popularity", "-vote_average"]

    def __str__(self):
        return f"{self.title} ({self.release_date.year if self.release_date else 'Unknown'})"

    @property
    def poster_url(self):
        if self.poster_path:
            from django.conf import settings

            return f"{settings.TMDB_IMAGE_BASE_URL}{self.poster_path}"
        return None

    @property
    def backdrop_url(self):
        if self.backdrop_path:
            from django.conf import settings

            return f"{settings.TMDB_IMAGE_BASE_URL}{self.backdrop_path}"
        return None
