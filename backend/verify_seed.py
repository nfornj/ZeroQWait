from database import SessionLocal
from modules.shops.models import Shop
from modules.queues.models import QueueItem
from modules.auth.models import User
from modules.employees.models import ShopEmployee

def verify():
    db = SessionLocal()
    try:
        shops = db.query(Shop).all()
        print(f"Total Shops in DB: {len(shops)}")
        for s in shops:
            if s.slug and "simulation" in (s.owner.username if s.owner else ""):
                print(f" - [SIM] {s.name} | Slug: {s.slug} | Owner: {s.owner.username}")
                from modules.queues.models import Queue
                items_count = db.query(QueueItem).join(Queue).filter(Queue.shop_id == s.id).count()
                print(f"   ㄴ Queue Items: {items_count}")
    finally:
        db.close()

if __name__ == "__main__":
    verify()
