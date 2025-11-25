#!/usr/bin/env python3
"""
Direct PostgreSQL connection to create Supabase tables
Requires: pip install psycopg2-binary
"""

import os
import sys

# Check if psycopg2 is installed
try:
    import psycopg2
except ImportError:
    print("❌ psycopg2 not installed")
    print("   Run: pip install psycopg2-binary")
    sys.exit(1)

# You need to get this from Supabase Dashboard -> Settings -> Database -> Connection String
print("📋 To get your database connection info:")
print("   1. Go to: https://supabase.com/dashboard/project/yuxfpspyzyhesfuspjns/settings/database")
print("   2. Copy 'Connection string' under 'Connection parameters'")
print("   3. Note your database password")
print()

# Connection parameters
DB_HOST = "db.yuxfpspyzyhesfuspjns.supabase.co"
DB_PORT = "5432"
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASSWORD = input("Enter your Supabase database password: ").strip()

if not DB_PASSWORD:
    print("❌ Password is required")
    sys.exit(1)

print()
print("🔌 Connecting to Supabase database...")

try:
    # Connect to database
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    conn.autocommit = True
    cursor = conn.cursor()
    
    print("✅ Connected successfully!")
    print()
    
    # Read SQL file
    sql_file = "supabase_schema.sql"
    print(f"📄 Reading SQL from: {sql_file}")
    
    with open(sql_file, 'r') as f:
        sql_content = f.read()
    
    print(f"📊 Executing schema creation...")
    print()
    
    # Execute the entire SQL file
    try:
        cursor.execute(sql_content)
        print("✅ Schema created successfully!")
        print()
        print("🎉 All tables have been created!")
        print()
        print("Next steps:")
        print("1. Verify tables at: https://supabase.com/dashboard/project/yuxfpspyzyhesfuspjns/editor")
        print("2. Create storage bucket 'shop-logos' (Storage section)")
        print("3. Set SUPABASE_KEY in .env file")
        print("4. Test API: cd backend && uvicorn main:app --reload")
        
    except psycopg2.Error as e:
        print(f"⚠️  Some errors occurred (might be normal if things already exist):")
        print(f"   {str(e)}")
        print()
        print("💡 Check Supabase Dashboard to see if tables were created")
    
    cursor.close()
    conn.close()
    
except psycopg2.OperationalError as e:
    print(f"❌ Connection failed: {str(e)}")
    print()
    print("💡 Alternative: Use Supabase SQL Editor (much easier)")
    print("   1. Go to: https://supabase.com/dashboard/project/yuxfpspyzyhesfuspjns/sql/new")
    print("   2. Copy content from: supabase_schema.sql")
    print("   3. Paste and click RUN")
    sys.exit(1)

except Exception as e:
    print(f"❌ Error: {str(e)}")
    sys.exit(1)
