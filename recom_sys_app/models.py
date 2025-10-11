from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import date

# ---- 1) User fundamentals ----
class Sex(models.TextChoices):
    FEMALE = "F", "Female"
    MALE = "M", "Male"
    OTHER = "O", "Other"
    UNSPECIFIED = "N", "Prefer not to say"

# Keep this list short for now; you can expand anytime.
class Genre(models.TextChoices):
    ACTION = "Action", "Action"
    ADVENTURE = "Adventure", "Adventure"
    ANIMATION = "Animation", "Animation"
    COMEDY = "Comedy", "Comedy"
    CRIME = "Crime", "Crime"
    DRAMA = "Drama", "Drama"
    FAMILY = "Family", "Family"
    FANTASY = "Fantasy", "Fantasy"
    HISTORY = "History", "History"
    HORROR = "Horror", "Horror"
    MUSIC = "Music", "Music"
    MYSTERY = "Mystery", "Mystery"
    ROMANCE = "Romance", "Romance"
    SCI_FI = "Science Fiction", "Science Fiction"
    THRILLER = "Thriller", "Thriller"
    WAR = "War", "War"
    WESTERN = "Western", "Western"

class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        db_index=True,
    )

    # requested fields
    name = models.CharField(max_length=120)                           # display name
    sex = models.CharField(max_length=1, choices=Sex.choices, default=Sex.UNSPECIFIED)
    age = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(120)],
        blank=True, null=True,
    )
    date_of_birth = models.DateField(blank=True, null=True)
    country = models.CharField(max_length=64)                         # keep simple (free text)
    favourite_genre1 = models.CharField(max_length=32, choices=Genre.choices, blank=True)
    favourite_genre2 = models.CharField(max_length=32, choices=Genre.choices, blank=True)

    # “movie liked in genre 1/2” – store TMDB id + optional title snapshot
    liked_g1_tmdb_id = models.IntegerField(blank=True, null=True, db_index=True)
    liked_g1_title = models.CharField(max_length=300, blank=True)
    liked_g2_tmdb_id = models.IntegerField(blank=True, null=True, db_index=True)
    liked_g2_title = models.CharField(max_length=300, blank=True)

    # tiny extras that help later
    language = models.CharField(max_length=16, blank=True, help_text="e.g., en, hi, kn")
    timezone = models.CharField(max_length=64, blank=True, help_text="e.g., America/New_York")
    onboarding_complete = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name or self.user.get_username()

    @property
    def computed_age(self):
        if not self.date_of_birth:
            return None
        today = date.today()
        years = today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )
        return max(0, years)

    def clean(self):
        # keep 'age' consistent if DOB present
        if self.date_of_birth and self.age is None:
            self.age = self.computed_age


# ---- 2) Interactions table (single source of truth per user x movie) ----
class Interaction(models.Model):
    class Status(models.TextChoices):
        LIKE = "LIKE", "Like"
        DISLIKE = "DISLIKE", "Dislike"
        WATCH_LATER = "WATCH_LATER", "Watch Later"
        WATCHED = "WATCHED", "Watched"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="interactions",
        db_index=True,
    )
    tmdb_id = models.IntegerField(db_index=True)
    status = models.CharField(max_length=12, choices=Status.choices, db_index=True)

    # helpful extras
    rating = models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1), MaxValueValidator(10)])
    source = models.CharField(max_length=64, blank=True)  # e.g., "solo", "group_room"

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "tmdb_id"], name="uniq_user_movie")
        ]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["tmdb_id", "status"]),
            models.Index(fields=["-updated_at"]),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.tmdb_id} -> {self.status}"

# Create your models here.
