"""
Test script to verify Supabase connection and basic operations.
"""
from dotenv import load_dotenv
import os
from pathlib import Path

# Explicitly load .env from current directory
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

# Now import supabase_client after env is loaded
from supabase_client import supabase

def test_connection():
    """Test basic Supabase connection."""
    print("=" * 60)
    print("Testing Supabase Connection")
    print("=" * 60)
    
    # Check environment variables
    print("\n1. Checking environment variables...")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if supabase_url:
        print(f"   ✓ SUPABASE_URL: {supabase_url}")
    else:
        print("   ✗ SUPABASE_URL not found")
        return False
    
    if supabase_key:
        print("   ✓ SUPABASE_KEY is set (hidden)")
    else:
        print("   ✗ SUPABASE_KEY not found")
        return False
    
    # Test client initialization
    print("\n2. Testing Supabase client initialization...")
    try:
        print(f"   ✓ Client initialized successfully")
        print(f"   ✓ Client URL: {supabase.supabase_url}")
    except Exception as e:
        print(f"   ✗ Client initialization failed: {e}")
        return False
    
    # Test database connection by listing tables
    print("\n3. Testing database access...")
    try:
        # Try to query a common table (users)
        response = supabase.table("users").select("*").limit(1).execute()
        print(f"   ✓ Successfully connected to database")
        print(f"   ✓ Users table exists")
        if response.data:
            print(f"   ✓ Found {len(response.data)} user(s) in sample query")
        else:
            print(f"   ℹ No users found (table may be empty)")
    except Exception as e:
        print(f"   ✗ Database access failed: {e}")
        print(f"   ℹ This might mean the 'users' table doesn't exist yet")
    
    # List all tables by trying common ones
    print("\n4. Checking for expected tables...")
    expected_tables = [
        "users",
        "shops", 
        "queues",
        "queue_items",
        "haircut_services",
        "user_favorites",
        "password_reset_tokens"
    ]
    
    for table_name in expected_tables:
        try:
            response = supabase.table(table_name).select("*").limit(0).execute()
            print(f"   ✓ Table '{table_name}' exists")
        except Exception as e:
            print(f"   ✗ Table '{table_name}' not found or inaccessible")
    
    # Test storage buckets
    print("\n5. Testing storage access...")
    try:
        buckets = supabase.storage.list_buckets()
        print(f"   ✓ Storage access successful")
        if buckets:
            print(f"   ✓ Found {len(buckets)} bucket(s)")
            for bucket in buckets:
                print(f"     - {bucket.name}")
        else:
            print(f"   ℹ No storage buckets found")
    except Exception as e:
        print(f"   ✗ Storage access failed: {e}")
    
    print("\n" + "=" * 60)
    print("Connection test completed!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        test_connection()
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
