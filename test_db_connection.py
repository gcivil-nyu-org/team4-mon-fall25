#!/usr/bin/env python3
"""
Test script to verify database connection on EB instance.
Uses Django's database connection for compatibility.
"""
import os
import sys
import django

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recommendation_sys.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    django.setup()
except Exception as e:
    print(f"⚠ Warning: Could not setup Django: {e}")
    print("Attempting direct connection...")
    django.setup = lambda: None

from django.db import connection  # noqa: E402
from django.conf import settings  # noqa: E402

print("=" * 60)
print("Database Connection Test")
print("=" * 60)
print()

# Display connection parameters (mask password)
db_config = settings.DATABASES["default"]
print("Connection parameters:")
print(f"  Engine: {db_config.get('ENGINE', 'N/A')}")
print(f"  Host: {db_config.get('HOST', 'localhost (default)')}")
print(f"  Port: {db_config.get('PORT', '5432 (default)')}")
print(f"  Database: {db_config.get('NAME', 'N/A')}")
print(f"  User: {db_config.get('USER', 'N/A')}")
print(f"  Password: {'*' * 8 if db_config.get('PASSWORD') else 'Not set'}")
print()

try:
    print("Attempting to connect...")
    with connection.cursor() as cursor:
        # Test connection with a simple query
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✓ Connection successful!")
        print(f"✓ PostgreSQL version: {version[0]}")
        print()

        # Check if we can list tables
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """
        )
        tables = cursor.fetchall()

        if tables:
            print(f"✓ Found {len(tables)} tables in database:")
            for table in tables[:20]:  # Show first 20 tables
                print(f"  - {table[0]}")
            if len(tables) > 20:
                print(f"  ... and {len(tables) - 20} more tables")
        else:
            print("⚠ No tables found in database")
            print("  This is normal if migrations haven't run yet")
        print()

        # Check Django migrations status
        try:
            from django.db.migrations.recorder import MigrationRecorder

            recorder = MigrationRecorder(connection)
            applied = recorder.applied_migrations()
            if applied:
                print(f"✓ Found {len(applied)} applied migrations")
            else:
                print("⚠ No migrations have been applied yet")
                print("  Run: python manage.py migrate")
        except Exception as e:
            print(f"⚠ Could not check migration status: {e}")

    print()
    print("=" * 60)
    print("✓ Database connection test PASSED!")
    print("=" * 60)

except Exception as e:
    print()
    print("=" * 60)
    print("✗ Connection FAILED!")
    print("=" * 60)
    print(f"Error: {type(e).__name__}: {e}")
    print()
    print("Troubleshooting:")
    print("  1. Verify RDS instance is running and accessible")
    print("  2. Check security groups allow traffic from EB to RDS")
    print("  3. Verify environment variables are set correctly:")
    print("     - POSTGRES_HOST")
    print("     - POSTGRES_DB")
    print("     - POSTGRES_USER")
    print("     - POSTGRES_PASSWORD")
    print("     - POSTGRES_PORT (optional, defaults to 5432)")
    print("  4. Check RDS endpoint is correct")
    print("  5. Verify database credentials")
    print("  6. Ensure RDS and EB are in the same VPC")
    print()
    sys.exit(1)
