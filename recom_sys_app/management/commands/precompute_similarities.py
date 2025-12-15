"""
Management command to precompute user similarities for collaborative filtering.

This command warms up the cache by computing similarity scores between users,
which improves recommendation performance.

Usage:
    python manage.py precompute_similarities
    python manage.py precompute_similarities --user-id 1
    python manage.py precompute_similarities --batch-size 50
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db.models import Count
from recom_sys_app.services import CollaborativeFilteringService

User = get_user_model()


class Command(BaseCommand):
    help = "Precompute user similarities for collaborative filtering (warm up cache)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user-id",
            type=int,
            help="Precompute similarities for a specific user ID only",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of users to process in each batch (default: 100)",
        )
        parser.add_argument(
            "--min-interactions",
            type=int,
            default=None,
            help=f"Minimum interactions required (default: {CollaborativeFilteringService.MIN_INTERACTIONS_FOR_CF})",
        )

    def handle(self, *args, **options):
        user_id = options.get("user_id")
        batch_size = options["batch_size"]
        min_interactions = (
            options.get("min_interactions")
            or CollaborativeFilteringService.MIN_INTERACTIONS_FOR_CF
        )

        if user_id:
            # Process single user
            try:
                user = User.objects.get(id=user_id)
                interaction_count = user.interactions.count()

                if interaction_count < min_interactions:
                    self.stdout.write(
                        self.style.WARNING(
                            f"User {user.username} has only {interaction_count} interactions. "
                            f"Need at least {min_interactions} for collaborative filtering."
                        )
                    )
                    return

                self.stdout.write(
                    f"Precomputing similarities for user: {user.username} (ID: {user_id})"
                )
                similar_users = CollaborativeFilteringService.find_similar_users(
                    user, limit=20
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Found {len(similar_users)} similar users\n"
                        f"  - Top similarity: {similar_users[0][1]:.3f}"
                        if similar_users
                        else "  - No similar users found"
                    )
                )
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"User with ID {user_id} not found"))
        else:
            # Process all users with sufficient interactions
            users = User.objects.annotate(
                interaction_count=Count("interactions")
            ).filter(interaction_count__gte=min_interactions)

            total_users = users.count()

            if total_users == 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"No users found with at least {min_interactions} interactions."
                    )
                )
                return

            self.stdout.write(
                f"Precomputing similarities for {total_users} users "
                f"(with at least {min_interactions} interactions)..."
            )

            processed = 0
            errors = 0
            total_similarities = 0

            for i in range(0, total_users, batch_size):
                batch = users[i : i + batch_size]  # noqa: E203
                self.stdout.write(
                    f"Processing batch {i // batch_size + 1} "
                    f"({i + 1}-{min(i + batch_size, total_users)} of {total_users})..."
                )

                for user in batch:
                    try:
                        similar_users = (
                            CollaborativeFilteringService.find_similar_users(
                                user, limit=20
                            )
                        )
                        processed += 1
                        total_similarities += len(similar_users)

                        if processed % 10 == 0:
                            self.stdout.write(
                                f"  Processed {processed} users... "
                                f"({total_similarities} similarities found so far)"
                            )
                    except Exception as e:
                        errors += 1
                        self.stdout.write(
                            self.style.ERROR(
                                f"  Error processing user {user.username}: {e}"
                            )
                        )

            avg_similarities = total_similarities / processed if processed > 0 else 0

            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ Completed!\n"
                    f"  - Processed: {processed} users\n"
                    f"  - Total similarities found: {total_similarities}\n"
                    f"  - Average similarities per user: {avg_similarities:.1f}\n"
                    f"  - Errors: {errors}"
                )
            )
