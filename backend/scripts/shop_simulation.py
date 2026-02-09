import sys
import random
import time
import os
from datetime import datetime, timedelta
from faker import Faker

fake = Faker()

def run_multi_shop_simulation(iterations=50):
    from database import SessionLocal
    # Modular imports
    from modules.auth.models import User
    from modules.shops.models import Shop, ShopService, DailyAnalytics
    from modules.queues.models import Queue, QueueItem, QueueStatus
    from modules.employees.models import ShopEmployee, EmployeeShift
    from modules.shops.service import shop_service
    
    db = SessionLocal()
    try:
        print(f"🚀 Starting live multi-shop simulation for {iterations} events...")
        
        shops = db.query(Shop).filter(Shop.is_active == True).all()
        if not shops:
            print("❌ No active shops found.")
            return

        print(f"  🏢 Simulating activity for {len(shops)} shops...")

        for i in range(iterations):
            shop = random.choice(shops)
            queue = db.query(Queue).filter(Queue.shop_id == shop.id).first()
            if not queue: continue

            action = random.choice(["JOIN", "START", "COMPLETE", "CANCEL", "IDLE"])
            
            if action == "JOIN":
                service = random.choice(db.query(ShopService).filter(ShopService.shop_id == shop.id).all() or [None])
                new_item = QueueItem(
                    queue_id=queue.id,
                    customer_name=fake.name(),
                    customer_phone=fake.phone_number()[:15],
                    position=0,
                    status=QueueStatus.WAITING,
                    service_id=service.id if service else None,
                    service_cost=service.cost if service else 0,
                    checked_in_at=datetime.utcnow()
                )
                db.add(new_item)
                print(f"  [{i}] ➕ {shop.name}: Customer JOINED ({new_item.customer_name})")
            
            elif action == "START":
                item = db.query(QueueItem).filter(
                    QueueItem.queue_id == queue.id, 
                    QueueItem.status == QueueStatus.WAITING
                ).first()
                if item:
                    item.status = QueueStatus.BEING_SERVED
                    item.service_started_at = datetime.utcnow()
                    print(f"  [{i}] ⏳ {shop.name}: Service STARTED for {item.customer_name}")
            
            elif action == "COMPLETE":
                item = db.query(QueueItem).filter(
                    QueueItem.queue_id == queue.id, 
                    QueueItem.status == QueueStatus.BEING_SERVED
                ).first()
                if item:
                    item.status = QueueStatus.COMPLETED
                    item.completed_at = datetime.utcnow()
                    print(f"  [{i}] ✅ {shop.name}: Service COMPLETED for {item.customer_name}")
            
            elif action == "CANCEL":
                item = db.query(QueueItem).filter(
                    QueueItem.queue_id == queue.id, 
                    QueueItem.status == QueueStatus.WAITING
                ).first()
                if item:
                    item.status = QueueStatus.CANCELLED
                    print(f"  [{i}] ❌ {shop.name}: Service CANCELLED for {item.customer_name}")
            
            else:
                print(f"  [{i}] 😴 {shop.name}: Idle iteration")

            db.commit()
            time.sleep(1) # Wait 1 second between events for real-time feel

        print("🏁 Multi-shop simulation finished.")

    except Exception as e:
        print(f"❌ Simulation Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    sys.path.append(os.getcwd())
    # Optional: read iterations from sys.argv
    iters = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    run_multi_shop_simulation(iters)
