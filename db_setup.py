#!/usr/bin/env python
"""
Database setup utility for RePlugit Backend.
This script assists with initializing PostgreSQL database.
"""

import subprocess
import sys
import os
from django.core.management import execute_from_command_line

def check_postgresql():
    """Check if PostgreSQL is installed and running"""
    try:
        # Try to connect to PostgreSQL server
        import psycopg2
        from django.conf import settings
        
        # Parse connection string from DATABASE_URL
        db_url = settings.DATABASES['default']['NAME']
        db_user = settings.DATABASES['default']['USER']
        db_password = settings.DATABASES['default']['PASSWORD']
        db_host = settings.DATABASES['default']['HOST']
        
        # Attempt connection to PostgreSQL server
        conn = psycopg2.connect(
            dbname="postgres",  # Connect to default DB first
            user=db_user,
            password=db_password,
            host=db_host
        )
        conn.close()
        print("✅ PostgreSQL connection successful")
        return True
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        print("\nPlease ensure PostgreSQL is installed and running:")
        print("1. Install PostgreSQL: https://www.postgresql.org/download/")
        print("2. Start PostgreSQL service")
        print("3. Create database 'replugit'")
        print("4. Update .env with correct PostgreSQL credentials")
        return False

def create_database():
    """Create PostgreSQL database if it doesn't exist"""
    try:
        import psycopg2
        from django.conf import settings
        
        # Parse connection string
        db_name = settings.DATABASES['default']['NAME']
        db_user = settings.DATABASES['default']['USER']
        db_password = settings.DATABASES['default']['PASSWORD']
        db_host = settings.DATABASES['default']['HOST']
        
        # Connect to default PostgreSQL database
        conn = psycopg2.connect(
            dbname="postgres",
            user=db_user,
            password=db_password,
            host=db_host
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        # Check if database exists
        cur.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{db_name}'")
        exists = cur.fetchone()
        
        if not exists:
            print(f"Creating database '{db_name}'...")
            cur.execute(f"CREATE DATABASE {db_name}")
            print(f"✅ Database '{db_name}' created successfully")
        else:
            print(f"✅ Database '{db_name}' already exists")
            
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Database creation failed: {e}")
        return False

def run_migrations():
    """Run Django migrations"""
    try:
        print("Running database migrations...")
        execute_from_command_line(["manage.py", "migrate"])
        print("✅ Migrations completed successfully")
        return True
    except Exception as e:
        print(f"❌ Migrations failed: {e}")
        return False

def main():
    """Main function to setup database"""
    print("🔄 Setting up PostgreSQL database for RePlugit Backend...")
    
    if not check_postgresql():
        return False
    
    if not create_database():
        return False
    
    if not run_migrations():
        return False
    
    print("\n✅ Database setup completed successfully!")
    print("\nYou can now start the development server:")
    print("python manage.py runserver")
    
    return True

if __name__ == "__main__":
    # Setup Django environment
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "replugit.settings")
    import django
    django.setup()
    
    # Run setup
    success = main()
    sys.exit(0 if success else 1)
