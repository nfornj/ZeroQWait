#!/usr/bin/env python3
"""List users from the current PostgreSQL database."""

from database import get_db_sync
from modules.auth.models import User


print("Checking users in database...")
print("=" * 60)

db = get_db_sync()

try:
    users = db.query(User).order_by(User.id.asc()).all()

    if users:
        print(f"Found {len(users)} user(s):\n")
        for user in users:
            role = user.role.value if hasattr(user.role, "value") else user.role
            print(f"ID: {user.id}")
            print(f"Username: {user.username}")
            print(f"Email: {user.email}")
            print(f"Role: {role}")
            print(f"Active: {user.is_active}")
            print("-" * 60)
    else:
        print("No users found in database")
except Exception as exc:
    print(f"Error: {exc}")
finally:
    db.close()
