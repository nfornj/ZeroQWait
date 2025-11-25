#!/usr/bin/env python3
"""
Check users in database
"""
from supabase_client import supabase

print("Checking users in database...")
print("=" * 60)

try:
    response = supabase.table("users").select("id, username, email, role, is_active").execute()
    
    if response.data:
        print(f"Found {len(response.data)} user(s):\n")
        for user in response.data:
            print(f"ID: {user['id']}")
            print(f"Username: {user['username']}")
            print(f"Email: {user['email']}")
            print(f"Role: {user['role']}")
            print(f"Active: {user['is_active']}")
            print("-" * 60)
    else:
        print("No users found in database")
        
except Exception as e:
    print(f"Error: {e}")
