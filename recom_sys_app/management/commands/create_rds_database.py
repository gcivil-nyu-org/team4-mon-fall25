"""
Django management command to create the RDS database if it doesn't exist.
Run this before migrations: python manage.py create_rds_database
"""

from django.core.management.base import BaseCommand
import os
import sys


class Command(BaseCommand):
    help = "Create the RDS database if it doesn't exist"

    def handle(self, *args, **options):
        postgres_host = os.getenv("POSTGRES_HOST")
        if not postgres_host:
            self.stdout.write(
                self.style.WARNING("POSTGRES_HOST not set, skipping database creation")
            )
            sys.exit(0)  # Exit cleanly if not configured

        db_name = os.getenv("POSTGRES_DB", "cinematch_production")
        self.stdout.write(
            f"Attempting to create database '{db_name}' on host '{postgres_host}'..."
        )

        try:
            # Try psycopg2 first (Django default)
            try:
                import psycopg2

                conn = psycopg2.connect(
                    host=postgres_host,
                    port=os.getenv("POSTGRES_PORT", "5432"),
                    user=os.getenv("POSTGRES_USER"),
                    password=os.getenv("POSTGRES_PASSWORD"),
                    database="postgres",
                    connect_timeout=10,
                    sslmode="require",
                )
            except ImportError:
                # Try installing psycopg2-binary
                import subprocess
                import sys

                try:
                    subprocess.check_call(
                        [
                            sys.executable,
                            "-m",
                            "pip",
                            "install",
                            "-q",
                            "psycopg2-binary",
                        ]
                    )
                    import psycopg2

                    conn = psycopg2.connect(
                        host=postgres_host,
                        port=os.getenv("POSTGRES_PORT", "5432"),
                        user=os.getenv("POSTGRES_USER"),
                        password=os.getenv("POSTGRES_PASSWORD"),
                        database="postgres",
                        connect_timeout=10,
                        sslmode="require",
                    )
                except Exception:
                    # Fallback to psycopg3
                    import psycopg

                    conn = psycopg.connect(
                        host=postgres_host,
                        port=os.getenv("POSTGRES_PORT", "5432"),
                        user=os.getenv("POSTGRES_USER"),
                        password=os.getenv("POSTGRES_PASSWORD"),
                        dbname="postgres",
                        connect_timeout=10,
                        sslmode="require",
                    )

            conn.autocommit = True
            cursor = conn.cursor()

            # Check if database exists
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            exists = cursor.fetchone()

            if exists:
                self.stdout.write(
                    self.style.SUCCESS(f"Database '{db_name}' already exists")
                )
            else:
                cursor.execute(f'CREATE DATABASE "{db_name}"')
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully created database '{db_name}'")
                )

            cursor.close()
            conn.close()

        except Exception as e:
            error_msg = f"Could not create database: {e}"
            self.stdout.write(self.style.ERROR(error_msg))
            # Print to stderr as well for better visibility in logs
            sys.stderr.write(f"ERROR: {error_msg}\n")
            # Don't fail the command - migrations will handle the error
            sys.exit(
                0
            )  # Exit with 0 to not fail deployment (ignoreErrors handles this)
