from database import engine
from sqlalchemy import text

def sync_enums():
    with engine.connect() as conn:
        print("Checking userrole enum...")
        try:
            # Check if super_admin exists
            result = conn.execute(text("SELECT enum_range(NULL::userrole)"))
            roles = result.fetchone()[0]
            if 'super_admin' in roles:
                print("✅ super_admin already exists in userrole enum")
            else:
                conn.execute(text("ALTER TYPE userrole ADD VALUE 'super_admin'"))
                conn.commit()
                print("✅ Added super_admin to userrole enum")
        except Exception as e:
            print(f"❌ Error syncing enums: {e}")
            conn.rollback()

if __name__ == "__main__":
    sync_enums()
