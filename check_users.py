#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth.models import User

print("Existing users in database:")
users = User.objects.all()
if users:
    for user in users:
        print(f"- {user.username} ({user.email}) - Active: {user.is_active}")
else:
    print("No users found")

print(f"\nTotal users: {users.count()}")
