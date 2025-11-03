from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import date
import uuid
import random
import string

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

# ---- 3) Group Movie Matching (NEW) ----
class GroupSession(models.Model):
    """群组会话模型 - 用于多人协作选电影"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group_code = models.CharField(max_length=8, unique=True, db_index=True)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_groups'
    )
    
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'group_sessions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['group_code']),
            models.Index(fields=['creator', '-created_at']),
        ]
    
    def save(self, *args, **kwargs):
        """覆盖 save 方法，自动生成 group_code"""
        if not self.group_code:
            self.group_code = self.generate_unique_code()
        
        # 判断是否是新创建的群组
        is_new = self.pk is None
        
        super().save(*args, **kwargs)
        
        # 如果是新创建的群组，自动添加创建者为成员
        if is_new and self.creator:
            GroupMember.objects.get_or_create(
                group_session=self,
                user=self.creator,
                defaults={
                    'role': GroupMember.Role.CREATOR,
                    'is_active': True
                }
            )
    
    @staticmethod
    def generate_unique_code():
        """生成唯一的6位大写字母+数字群组代码"""
        import random
        import string
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not GroupSession.objects.filter(group_code=code).exists():
                return code


class GroupMember(models.Model):
    """群组成员模型"""
    
    class Role(models.TextChoices):
        CREATOR = "CREATOR", "Creator"
        MEMBER = "MEMBER", "Member"
    
    id = models.AutoField(primary_key=True)
    group_session = models.ForeignKey(
        GroupSession,
        on_delete=models.CASCADE,
        related_name='members'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='group_memberships'
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'group_members'
        constraints = [
            models.UniqueConstraint(
                fields=['group_session', 'user'], 
                name='uniq_group_user'
            )
        ]
        indexes = [
            models.Index(fields=['group_session', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]
        ordering = ['joined_at']
    
    def __str__(self):
        return f"{self.user.username} in {self.group_session.group_code}"
    

    # ---- 4) Group Swipe & Match (NEW.1) ----
class GroupSwipe(models.Model):
    """群组中的滑动记录"""
    
    class Action(models.TextChoices):
        LIKE = "LIKE", "Like"
        DISLIKE = "DISLIKE", "Dislike"
        SUPER_LIKE = "SUPER_LIKE", "Super Like"
    
    id = models.AutoField(primary_key=True)
    group_session = models.ForeignKey(
        GroupSession,
        on_delete=models.CASCADE,
        related_name='swipes'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='group_swipes'
    )
    tmdb_id = models.IntegerField(db_index=True)
    action = models.CharField(max_length=12, choices=Action.choices)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'group_swipes'
        constraints = [
            models.UniqueConstraint(
                fields=['group_session', 'user', 'tmdb_id'],
                name='uniq_group_user_movie_swipe'
            )
        ]
        indexes = [
            models.Index(fields=['group_session', 'tmdb_id']),
            models.Index(fields=['user', 'action']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} {self.action} movie {self.tmdb_id} in group {self.group_session.group_code}"


class GroupMatch(models.Model):
    """群组匹配成功的电影"""
    
    id = models.AutoField(primary_key=True)
    group_session = models.ForeignKey(
        GroupSession,
        on_delete=models.CASCADE,
        related_name='matches'
    )
    tmdb_id = models.IntegerField(db_index=True)
    
    # Optional: Save movie title snapshots
    movie_title = models.CharField(max_length=300, blank=True)
    
    matched_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'group_matches'
        constraints = [
            models.UniqueConstraint(
                fields=['group_session', 'tmdb_id'],
                name='uniq_group_match'
            )
        ]
        indexes = [
            models.Index(fields=['group_session', '-matched_at']),
            models.Index(fields=['tmdb_id']),
        ]
    
    def __str__(self):
        return f"Match: Movie {self.tmdb_id} in group {self.group_session.group_code}"
    
class GroupChatMessage(models.Model):
    """Group Chat Message Model"""
    
    id = models.AutoField(primary_key=True)
    group_session = models.ForeignKey(
        GroupSession,
        on_delete=models.CASCADE,
        related_name='chat_messages'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    content = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'group_chat_messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['group_session', 'created_at']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        preview = self.content[:50] + '...' if len(self.content) > 50 else self.content
        return f"{self.user.username}: {preview}"