"""
Script to delete manifest app migrations from the database
"""
import os
import sqlite3

# Connect to the SQLite database
conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

print("Connected to SQLite database")

# Check current migrations
cursor.execute("SELECT * FROM django_migrations WHERE app = 'manifest'")
migrations = cursor.fetchall()
print(f"Found {len(migrations)} migrations for 'manifest' app:")
for migration in migrations:
    print(f"  - ID: {migration[0]}, App: {migration[1]}, Name: {migration[2]}, Applied: {migration[3]}")

# Delete all migrations for the manifest app
cursor.execute("DELETE FROM django_migrations WHERE app = 'manifest'")
conn.commit()
print(f"Deleted {cursor.rowcount} migration records for 'manifest' app")

# Verify that migrations were deleted
cursor.execute("SELECT COUNT(*) FROM django_migrations WHERE app = 'manifest'")
count = cursor.fetchone()[0]
print(f"Remaining migration records for 'manifest' app: {count}")

# Close the connection
conn.close()
print("Database connection closed")
