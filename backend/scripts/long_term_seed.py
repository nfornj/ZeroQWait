import sys
import random
import os
from faker import Faker
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from faker import Faker

fake = Faker()

def seed_long_term():
    from database import SessionLocal
    # Modular imports
    from modules.auth.models import User, UserRole
    from modules.shops.models import Shop, ShopService, DailyAnalytics
    from modules.queues.models import Queue, QueueItem, QueueStatus
    from modules.employees.models import ShopEmployee, EmployeeShift

    db = SessionLocal()
    try:
        print("🌱 Starting 2-year long-term data simulation...")
        
        shops = db.query(Shop).all()
        if not shops:
            print("❌ No shops found in database. Run basic seed first.")
            return

        print(f"  🏢 Found {len(shops)} shops. Simulating 730 days of data for each...")
        
        today = date.today()
        start_date = today - timedelta(days=730)
        
        for shop in shops:
            print(f"  📊 Seeding Shop: {shop.name} (Slug: {shop.slug})")
            
            # Get services for this shop
            services = db.query(ShopService).filter(ShopService.shop_id == shop.id).all()
            if not services:
                # Add default services if none exist
                s_services = ["Consultation", "Quick Service", "Standard Treatment"]
                db_services = []
                for s_name in s_services:
                    svc = ShopService(
                        shop_id=shop.id,
                        name=s_name,
                        duration_minutes=random.randint(15, 60),
                        cost=random.uniform(20.0, 100.0)
                    )
                    db.add(svc)
                    db_services.append(svc)
                db.flush()
                services = db_services

            # Get or create queue
            queue = db.query(Queue).filter(Queue.shop_id == shop.id).first()
            if not queue:
                queue = Queue(shop_id=shop.id, name="Main Queue", is_active=True)
                db.add(queue)
                db.flush()

            # Simulate 730 days
            items_to_add = []
            for d in range(730):
                sim_date = start_date + timedelta(days=d)
                
                # Weekend traffic boost
                is_weekend = sim_date.weekday() >= 5
                base_count = random.randint(3, 10)
                if is_weekend:
                    base_count = random.randint(10, 25)
                
                # Business growth over 2 years (more traffic as time goes on)
                growth_factor = 1.0 + (d / 365) * 0.5 # 50% growth per year
                daily_count = int(base_count * growth_factor)
                
                for _ in range(daily_count):
                    status = QueueStatus.COMPLETED if random.random() > 0.15 else QueueStatus.CANCELLED
                    service = random.choice(services)
                    
                    # Random time between 9 AM and 6 PM
                    check_in_time = datetime.combine(sim_date, datetime.min.time()) + \
                                    timedelta(hours=random.randint(9, 17), minutes=random.randint(0, 59))
                    
                    wait_time = random.randint(0, 45)
                    service_time = service.duration_minutes + random.randint(-5, 15)
                    
                    item = QueueItem(
                        queue_id=queue.id,
                        customer_name=fake.name(),
                        customer_phone=fake.phone_number()[:15],
                        position=0,
                        status=status,
                        service_id=service.id,
                        service_cost=service.cost,
                        checked_in_at=check_in_time,
                        service_started_at=check_in_time + timedelta(minutes=wait_time) if status == QueueStatus.COMPLETED else None,
                        completed_at=check_in_time + timedelta(minutes=wait_time + service_time) if status == QueueStatus.COMPLETED else None
                    )
                    items_to_add.append(item)
                
                # Batch add every 10 days to keep memory usage low
                if d % 10 == 0:
                    db.add_all(items_to_add)
                    db.commit()
                    items_to_add = []
            
            db.add_all(items_to_add)
            db.commit()
            print(f"    ✅ {shop.name} historical data complete.")

        print("🏁 2-year simulation complete!")

    except Exception as e:
        print(f"❌ Simulation Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    sys.path.append(os.getcwd())
    seed_long_term()
