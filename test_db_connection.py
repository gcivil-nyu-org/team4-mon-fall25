#!/usr/bin/env python3
"""Test script to verify database connection on EB instance"""
import os
import psycopg

# Database connection parameters
db_params = {
    "dbname": os.getenv("POSTGRES_DB", "cinematch-db"),
    "user": os.getenv("POSTGRES_USER", "cinematch"),
    "password": os.getenv("POSTGRES_PASSWORD", "Cinematch303"),
    "host": os.getenv(
        "POSTGRES_HOST", "cinematch-db.cwdagky2eta9.us-east-1.rds.amazonaws.com"
    ),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "sslmode": "require",
    "connect_timeout": 10,
}

print("Testing PostgreSQL connection with parameters:")
print(f"  Host: {db_params['host']}")
print(f"  Port: {db_params['port']}")
print(f"  Database: {db_params['dbname']}")
print(f"  User: {db_params['user']}")
print(f"  SSL Mode: {db_params['sslmode']}")
print()

try:
    print("Attempting to connect...")
    conn = psycopg.connect(**db_params)
    print("✓ Connection successful!")

    # Test a simple query
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    version = cursor.fetchone()
    print(f"✓ PostgreSQL version: {version[0]}")

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
        for table in tables:
            print(f"  - {table[0]}")
    else:
        print("⚠ No tables found in database (migrations haven't run yet)")

    cursor.close()
    conn.close()
    print("\n✓ Database connection test passed!")

except Exception as e:
    print("\n✗ Connection failed!")
    print(f"Error: {type(e).__name__}: {e}")
    print("\nPossible issues:")
    print("  1. Database name might be incorrect")
    print("  2. Security group not allowing connections from EB")
    print("  3. Wrong credentials")
    print("  4. RDS endpoint is incorrect")
    exit(1)
