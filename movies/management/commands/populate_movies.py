from django.core.management.base import BaseCommand
from movies.services import TMDbService

class Command(BaseCommand):
    help = 'Populate database with movies from TMDb API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--pages',
            type=int,
            default=5,
            help='Number of pages to fetch from TMDb (default: 5)'
        )

    def handle(self, *args, **options):
        pages = options['pages']
        self.stdout.write(
            self.style.SUCCESS(f'Starting to populate movies from TMDb API ({pages} pages)...')
        )

        try:
            tmdb_service = TMDbService()
            movies_added, movies_updated = tmdb_service.populate_popular_movies(pages)

            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully completed! Added {movies_added} new movies, '
                    f'updated {movies_updated} existing movies.'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error populating movies: {str(e)}')
            )