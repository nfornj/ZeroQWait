#!/usr/bin/env python3
"""
Script to reset all user passwords to 'password123' and verify login works
"""
import sys
sys.path.insert(0, '/Users/neekrish/zeroqwait/backend')

from passlib.context import CryptContext
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv('/Users/neekrish/zeroqwait/backend/.env')

# Database connection
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "zeroqwait")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")

# Use SSH tunnel to connect to remote database
# Instead, let's create a script that runs on the remote server

print("Creating password reset script to run on remote server...")
print("\nUsing database from environment or defaults:")
print(f"  DB_HOST: {DB_HOST}")
print(f"  DB_PORT: {DB_PORT}")
print(f"  DB_NAME: {DB_NAME}")
print(f"  DB_USER: {DB_USER}")

# Generate bcrypt hash for "password123"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
password_hash = pwd_context.hash("password123")

print(f"\nPassword hash to use: {password_hash}")

# Create SQL script to update all users
sql_script = f"""
-- Reset all user passwords to: password123
UPDATE users SET hashed_password = '{password_hash}';

-- Verify
SELECT email, hashed_password FROM users LIMIT 5;
"""

print("\nSQL script to execute:")
print(sql_script)

print("\n\nTo run this remotely, execute:")
print(f"ssh neekrishrichu@192.168.2.88 \"sudo kubectl exec postgres-0 -n zeroqwait -- psql -U fastcuts_user -d fastcuts_db << 'EOF'")
print(sql_script)
print("EOF\"")
