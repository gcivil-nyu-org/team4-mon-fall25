#!/usr/bin/env python3
"""
Standalone script to create RDS database without Django initialization.
This avoids the chicken-and-egg problem where Django tries to connect
to a database that doesn't exist yet.
"""
import os
import sys


def create_database():
    postgres_host = os.getenv("POSTGRES_HOST")
    if not postgres_host:
        print("WARNING: POSTGRES_HOST not set, skipping database creation")
        return 0

    db_name = os.getenv("POSTGRES_DB", "cinematch_production")
    print(f"Attempting to create database '{db_name}' on host '{postgres_host}'...")

    try:
        # Try psycopg2 first
        try:
            import psycopg2

            # Use sslmode='require' for RDS connections
            conn = psycopg2.connect(
                host=postgres_host,
                port=os.getenv("POSTGRES_PORT", "5432"),
                user=os.getenv("POSTGRES_USER"),
                password=os.getenv("POSTGRES_PASSWORD"),
                database="postgres",  # Connect to default postgres database
                connect_timeout=10,
                sslmode="require" if "rds.amazonaws.com" in postgres_host else "prefer",
            )
        except ImportError:
            # Fallback to psycopg3
            import psycopg

            conn = psycopg.connect(
                host=postgres_host,
                port=os.getenv("POSTGRES_PORT", "5432"),
                user=os.getenv("POSTGRES_USER"),
                password=os.getenv("POSTGRES_PASSWORD"),
                dbname="postgres",
                connect_timeout=10,
                sslmode="require" if "rds.amazonaws.com" in postgres_host else "prefer",
            )

        conn.autocommit = True
        cursor = conn.cursor()

        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        exists = cursor.fetchone()

        if exists:
            print(f"SUCCESS: Database '{db_name}' already exists")
        else:
            cursor.execute(f'CREATE DATABASE "{db_name}"')
            print(f"SUCCESS: Successfully created database '{db_name}'")

        cursor.close()
        conn.close()
        return 0

    except Exception as e:
        error_msg = f"ERROR: Could not create database: {e}"
        print(
            error_msg, file=sys.stderr
        )  # Print to stderr for better visibility in logs
        print(error_msg)  # Also print to stdout
        import traceback

        traceback.print_exc()  # Print full traceback for debugging
        return 0  # Don't fail deployment (ignoreErrors handles this)


if __name__ == "__main__":
    sys.exit(create_database())
