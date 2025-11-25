#!/usr/bin/env python3
"""
Script to create Supabase tables from local machine
Run this instead of copying SQL manually
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://yuxfpspyzyhesfuspjns.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_KEY:
    print("❌ Error: SUPABASE_KEY not found in environment variables")
    print("   Please set it in your .env file or export it:")
    print("   export SUPABASE_KEY='your_service_role_key'")
    sys.exit(1)

try:
    from supabase import create_client
except ImportError:
    print("❌ Error: supabase package not installed")
    print("   Run: pip install supabase==2.3.0")
    sys.exit(1)

print("🚀 Creating Supabase tables...")
print(f"   URL: {SUPABASE_URL}")
print()

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Read SQL file
sql_file = "supabase_schema.sql"
if not os.path.exists(sql_file):
    sql_file = "../supabase_schema.sql"
    if not os.path.exists(sql_file):
        print(f"❌ Error: supabase_schema.sql not found")
        sys.exit(1)

print(f"📄 Reading SQL from: {sql_file}")

with open(sql_file, 'r') as f:
    sql_content = f.read()

# Split into individual statements (simple approach)
# Remove comments and split by semicolon
statements = []
current_statement = []

for line in sql_content.split('\n'):
    # Skip comment-only lines
    if line.strip().startswith('--'):
        continue
    
    # Skip empty lines
    if not line.strip():
        continue
    
    # Add line to current statement
    current_statement.append(line)
    
    # If line ends with semicolon, we have a complete statement
    if line.strip().endswith(';'):
        statement = '\n'.join(current_statement)
        if statement.strip():
            statements.append(statement)
        current_statement = []

print(f"📊 Found {len(statements)} SQL statements to execute")
print()

# Execute each statement
success_count = 0
error_count = 0

for i, statement in enumerate(statements, 1):
    # Get first line for display
    first_line = statement.split('\n')[0][:60]
    print(f"[{i}/{len(statements)}] Executing: {first_line}...", end=" ")
    
    try:
        # Use rpc to execute raw SQL
        # Note: This requires a database function, so we'll use a different approach
        # We'll use the PostgREST API directly
        import requests
        
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"
            },
            json={"query": statement}
        )
        
        if response.status_code in [200, 201, 204]:
            print("✅")
            success_count += 1
        else:
            # Try alternative: some statements might not need rpc
            # For CREATE statements, they might already exist
            if "already exists" in response.text.lower():
                print("⚠️  (already exists)")
                success_count += 1
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"   Response: {response.text[:100]}")
                error_count += 1
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        error_count += 1

print()
print("=" * 60)
print(f"📊 Results:")
print(f"   ✅ Success: {success_count}")
print(f"   ❌ Errors: {error_count}")
print()

if error_count > 0:
    print("⚠️  Some statements failed. This might be normal if:")
    print("   - Tables/types already exist")
    print("   - RLS policies already exist")
    print()
    print("💡 Alternative: Run the SQL directly in Supabase SQL Editor")
    print("   1. Go to: https://supabase.com/dashboard/project/yuxfpspyzyhesfuspjns/sql/new")
    print("   2. Copy content from: supabase_schema.sql")
    print("   3. Paste and click RUN")
else:
    print("🎉 All tables created successfully!")
    print()
    print("Next steps:")
    print("1. Verify tables in Supabase Dashboard → Table Editor")
    print("2. Create storage bucket 'shop-logos' (in Storage section)")
    print("3. Start backend: uvicorn main:app --reload")
    print("4. Run tests: ./test_api.sh")
