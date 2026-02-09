from database import SessionLocal
from modules.auth.models import User, UserRole
from modules.shops.models import Shop
from modules.queues.models import QueueItem
from modules.employees.models import ShopEmployee

def promote_user(username: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"❌ User {username} not found")
            return
        
        user.role = UserRole.SUPER_ADMIN
        db.commit()
        print(f"✅ User {username} promoted to SUPER_ADMIN")
    finally:
        db.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        promote_user(sys.argv[1])
    else:
        print("Usage: python3 create_super_admin.py <username>")
