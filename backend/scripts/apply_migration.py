"""Apply a SQL migration file to the current PostgreSQL database."""
import sys
from pathlib import Path
from sqlalchemy import text
from database import get_db_sync

def apply_migration(migration_file: str):
    """Apply a SQL migration file"""
    # Read migration file
    migration_path = Path(__file__).parent / migration_file
    
    if not migration_path.exists():
        print(f"Error: Migration file not found: {migration_path}")
        sys.exit(1)
    
    with open(migration_path, 'r') as f:
        migration_sql = f.read()
    
    # Get database session
    db = get_db_sync()
    
    try:
        print(f"Applying migration: {migration_file}")
        print("-" * 60)
        
        # Split into statements (simple split by semicolon)
        # Note: This won't work perfectly for complex SQL with functions
        # For functions, we need to execute the entire function as one statement
        
        # Execute the entire migration as one block (works better for functions)
        db.execute(text(migration_sql))
        db.commit()
        
        print("Migration applied successfully!")
        print("-" * 60)
        
        # Verify tables were created
        print("\nVerifying tables...")
        result = db.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('queue_analytics_daily', 'queue_items_archive')
        """))
        
        tables = [row[0] for row in result]
        
        if 'queue_analytics_daily' in tables:
            print("✓ queue_analytics_daily table created")
        else:
            print("✗ queue_analytics_daily table NOT found")
        
        if 'queue_items_archive' in tables:
            print("✓ queue_items_archive table created")
        else:
            print("✗ queue_items_archive table NOT found")
        
        # Verify functions
        print("\nVerifying functions...")
        result = db.execute(text("""
            SELECT routine_name 
            FROM information_schema.routines 
            WHERE routine_schema = 'public' 
            AND routine_name IN ('aggregate_daily_analytics', 'archive_old_queue_items')
        """))
        
        functions = [row[0] for row in result]
        
        if 'aggregate_daily_analytics' in functions:
            print("✓ aggregate_daily_analytics function created")
        else:
            print("✗ aggregate_daily_analytics function NOT found")
        
        if 'archive_old_queue_items' in functions:
            print("✓ archive_old_queue_items function created")
        else:
            print("✗ archive_old_queue_items function NOT found")
        
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"Error applying migration: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        migration_file = sys.argv[1]
    else:
        migration_file = "migrations/001_analytics_and_archival.sql"
    
    print("=" * 60)
    print("ZeroQwait Database Migration Tool")
    print("=" * 60)
    
    apply_migration(migration_file)
