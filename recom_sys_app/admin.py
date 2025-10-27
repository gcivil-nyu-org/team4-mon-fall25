from django.contrib import admin
from .models import UserProfile, Interaction, GroupSession, GroupMember
from .models import GroupChatMessage

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

@admin.register(GroupSession)
class GroupSessionAdmin(admin.ModelAdmin):
    list_display = ('group_code', 'creator', 'member_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('group_code', 'creator__username')
    readonly_fields = ('id', 'group_code', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    
    def member_count(self, obj):
        return obj.members.filter(is_active=True).count()
    member_count.short_description = 'Members'


@admin.register(GroupMember)
class GroupMemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'group_code', 'role', 'is_active', 'joined_at')
    list_filter = ('role', 'is_active', 'joined_at')
    search_fields = ('user__username', 'group_session__group_code')
    readonly_fields = ('joined_at',)
    
    def group_code(self, obj):
        return obj.group_session.group_code
    group_code.short_description = 'Group Code'

@admin.register(GroupChatMessage)
class GroupChatMessageAdmin(admin.ModelAdmin):
    list_display = ['user', 'group_session', 'content_preview', 'created_at']
    list_filter = ['created_at', 'group_session']
    search_fields = ['content', 'user__username', 'group_session__group_code']
    readonly_fields = ['created_at']
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'