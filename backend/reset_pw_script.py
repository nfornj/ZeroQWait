#!/usr/bin/env python3
"""
Reset all user passwords to 'password123'
Run this on the backend container
"""
import sys
import os

# Add backend to path
sys.path.insert(0, '/app')

from database import SessionLocal
from shared.auth_utils import get_password_hash
from sqlalchemy import text

def reset_all_passwords():
    db = SessionLocal()
    try:
        # Hash the password
        password_hash = get_password_hash("password123")
        print(f"Generated hash: {password_hash}")
        
        # Update all users using raw SQL to avoid ORM issues
        result = db.execute(
            text("UPDATE users SET hashed_password = :hash"),
            {"hash": password_hash}
        )
        db.commit()
        print(f"Updated {result.rowcount} users with password hash")
        
        # Verify with raw SQL
        verify_result = db.execute(
            text("SELECT email, hashed_password FROM users LIMIT 1")
        ).fetchone()
        if verify_result:
            print(f"\nSample user: {verify_result[0]}")
            print(f"Hash from DB: {verify_result[1]}")
            print(f"Hashes match: {verify_result[1] == password_hash}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    reset_all_passwords()
