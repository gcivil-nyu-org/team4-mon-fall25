"""
Management command to populate user preferences for existing users.

Usage:
    python manage.py populate_preferences
    python manage.py populate_preferences --force
    python manage.py populate_preferences --user-id 1
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from recom_sys_app.services import PreferenceService
from recom_sys_app.models import UserPreference

User = get_user_model()


class Command(BaseCommand):
    help = "Populate user preferences for existing users based on their interaction history"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force recalculation even if preferences were recently updated",
        )
        parser.add_argument(
            "--user-id",
            type=int,
            help="Populate preferences for a specific user ID only",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of users to process in each batch (default: 100)",
        )

    def handle(self, *args, **options):
        force = options["force"]
        user_id = options.get("user_id")
        batch_size = options["batch_size"]

        if user_id:
            # Process single user
            try:
                user = User.objects.get(id=user_id)
                self.stdout.write(f"Processing user: {user.username} (ID: {user_id})")
                preference = PreferenceService.update_user_preferences(
                    user, force_recalculate=force
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Updated preferences for {user.username}\n"
                        f"  - Total interactions: {preference.total_interactions}\n"
                        f"  - Likes: {preference.total_likes}\n"
                        f"  - Top genres: {len(preference.genre_preferences)}"
                    )
                )
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"User with ID {user_id} not found"))
        else:
            # Process all users
            users = User.objects.all()
            total_users = users.count()
            self.stdout.write(f"Processing {total_users} users...")

            processed = 0
            errors = 0

            for i in range(0, total_users, batch_size):
                batch = users[i : i + batch_size]  # noqa: E203
                self.stdout.write(
                    f"Processing batch {i // batch_size + 1} ({i + 1}-{min(i + batch_size, total_users)} of {total_users})..."
                )

                for user in batch:
                    try:
                        PreferenceService.update_user_preferences(
                            user, force_recalculate=force
                        )
                        processed += 1
                        if processed % 10 == 0:
                            self.stdout.write(f"  Processed {processed} users...")
                    except Exception as e:
                        errors += 1
                        self.stdout.write(
                            self.style.ERROR(
                                f"  Error processing user {user.username}: {e}"
                            )
                        )

            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ Completed!\n"
                    f"  - Processed: {processed} users\n"
                    f"  - Errors: {errors}\n"
                    f"  - Total preferences: {UserPreference.objects.count()}"
                )
            )
