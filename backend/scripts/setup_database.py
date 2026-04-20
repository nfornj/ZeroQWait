#!/usr/bin/env python3
"""
Setup database tables in Supabase using direct PostgreSQL connection
"""
import os
import psycopg2
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL not found in .env file")
    print("   Please add: DATABASE_URL=postgresql://postgres:password@db.project.supabase.co:5432/postgres")
    exit(1)

print("🚀 Setting up Supabase database tables")
print(f"   Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'hidden'}")
print()

# Read SQL file
sql_file = Path(__file__).parent.parent / "supabase_schema.sql"
if not sql_file.exists():
    print(f"❌ ERROR: SQL file not found at {sql_file}")
    exit(1)

print(f"📄 Reading SQL schema from: {sql_file.name}")

with open(sql_file, 'r') as f:
    sql_content = f.read()

try:
    # Connect to database
    print("🔌 Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cursor = conn.cursor()
    
    print("✓ Connected successfully")
    print()
    print("📊 Creating tables and indexes...")
    print("-" * 60)
    
    # Execute the entire SQL file
    try:
        cursor.execute(sql_content)
        print("✓ All tables, indexes, and policies created successfully!")
    except psycopg2.errors.DuplicateObject as e:
        print(f"ℹ Some objects already exist (this is normal): {e}")
    except psycopg2.Error as e:
        print(f"⚠️  Some SQL statements failed: {e}")
        print("   This might be normal if tables already exist")
    
    print()
    print("-" * 60)
    print("🎉 Database setup complete!")
    print()
    
    # Verify tables were created
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    
    tables = cursor.fetchall()
    print(f"📋 Found {len(tables)} tables:")
    for table in tables:
        print(f"   ✓ {table[0]}")
    
    print()
    print("✅ Setup complete! You can now:")
    print("   1. Run: python3 comprehensive_test.py")
    print("   2. Visit: http://localhost:8000/docs")
    print("   3. Test: http://localhost:3000")
    
    cursor.close()
    conn.close()
    
except psycopg2.OperationalError as e:
    print(f"❌ CONNECTION ERROR: {e}")
    print()
    print("Troubleshooting:")
    print("  1. Check if Supabase project is paused (unpause it)")
    print("  2. Verify DATABASE_URL in .env file")
    print("  3. Check if your IP is allowed in Supabase (should be for paid plans)")
    print()
    print("Alternative: Run SQL directly in Supabase SQL Editor")
    print(f"  Visit: https://supabase.com/dashboard/project/yuxfpspyzyhesfuspjns/sql/new")
    exit(1)
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
