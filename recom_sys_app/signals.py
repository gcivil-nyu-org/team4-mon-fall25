"""
Django signals for automatically updating user preferences when interactions change.
Also invalidates collaborative filtering cache when interactions change.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from .models import Interaction

# Import services lazily to avoid circular imports during app startup
try:
    from .services import PreferenceService, CollaborativeFilteringService
except ImportError:
    # During migrations or if services aren't available yet
    PreferenceService = None
    CollaborativeFilteringService = None


@receiver(post_save, sender=Interaction)
def update_preferences_on_interaction_save(sender, instance, created, **kwargs):
    """
    Update user preferences when an interaction is created or updated.
    Also invalidate collaborative filtering cache.
    Uses transaction.on_commit to avoid blocking the request.
    """
    if PreferenceService is None or CollaborativeFilteringService is None:
        return  # Services not available yet (e.g., during migrations)

    if created or kwargs.get("update_fields"):
        # Schedule preference update after transaction commits
        transaction.on_commit(
            lambda: PreferenceService.update_user_preferences(instance.user)
        )
        # Invalidate collaborative filtering cache
        transaction.on_commit(
            lambda: CollaborativeFilteringService.invalidate_user_cache(instance.user)
        )


@receiver(post_delete, sender=Interaction)
def update_preferences_on_interaction_delete(sender, instance, **kwargs):
    """
    Update user preferences when an interaction is deleted.
    Also invalidate collaborative filtering cache.
    """
    if PreferenceService is None or CollaborativeFilteringService is None:
        return  # Services not available yet (e.g., during migrations)

    transaction.on_commit(
        lambda: PreferenceService.update_user_preferences(instance.user)
    )
    # Invalidate collaborative filtering cache
    transaction.on_commit(
        lambda: CollaborativeFilteringService.invalidate_user_cache(instance.user)
    )
