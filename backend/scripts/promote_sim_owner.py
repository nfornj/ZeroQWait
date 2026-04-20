from database import engine
from sqlalchemy import text

def promote():
    with engine.connect() as conn:
        print("Promoting simulation_owner to super_admin...")
        try:
            conn.execute(text("UPDATE users SET role = 'super_admin' WHERE username = 'simulation_owner'"))
            conn.commit()
            print("✅ Promotion successful")
            
            # Verify
            res = conn.execute(text("SELECT username, role FROM users WHERE username = 'simulation_owner'")).fetchone()
            print(f"Verification - User: {res[0]}, Role: {res[1]}")
        except Exception as e:
            print(f"❌ Error: {e}")
            conn.rollback()

if __name__ == "__main__":
    promote()
