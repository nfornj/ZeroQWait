import sys
import random
import time
import os
import json
from datetime import datetime, date, timedelta
from sqlalchemy import text, func
from sqlalchemy.orm import Session
from faker import Faker
from passlib.context import CryptContext

# Add project root to path
sys.path.append(os.getcwd())

from database import SessionLocal, engine
from modules.auth.models import User, UserRole, SubscriptionTier
from modules.shops.models import Shop, ShopService, DailyAnalytics
from modules.queues.models import Queue, QueueItem, QueueStatus
from modules.employees.models import ShopEmployee, EmployeeShift
from shared.auth_utils import get_password_hash

fake = Faker()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

STANDARD_PASSWORD = "Password123!"
HASHED_PASSWORD = get_password_hash(STANDARD_PASSWORD)

def reset_database(db: Session):
    print("🧹 Resetting database...")
    tables = [
        "queue_items", "queues", "employee_shifts", "shop_employees",
        "shop_services", "shop_customers", "shop_close_days", "daily_analytics",
        "shops", "users"
    ]
    for table in tables:
        db.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
    db.commit()
    print("✅ Database reset complete.")

def create_super_admin(db: Session):
    admin = User(
        email="admin@zeroqwait.com",
        username="admin",
        hashed_password=HASHED_PASSWORD,
        role=UserRole.SUPER_ADMIN,
        subscription_tier=SubscriptionTier.ENTERPRISE
    )
    db.add(admin)
    db.commit()
    return admin

def generate_simulation_data(db: Session, years=2):
    print(f"🏗️ Generating experimental data for {years} years...")
    
    # 1. Create Owners
    owners = []
    credentials = []

    # Free Owners (Single Shop)
    for i in range(20):
        owner = User(
            email=f"free_owner_{i}@example.com",
            username=f"free_owner_{i}",
            hashed_password=HASHED_PASSWORD,
            role=UserRole.SHOP_OWNER,
            subscription_tier=SubscriptionTier.FREE
        )
        db.add(owner)
        owners.append((owner, "FREE"))
        credentials.append({"username": owner.username, "password": STANDARD_PASSWORD, "tier": "FREE"})

    # Premium Owners (Multiple Shops)
    for i in range(15):
        owner = User(
            email=f"premium_owner_{i}@example.com",
            username=f"premium_owner_{i}",
            hashed_password=HASHED_PASSWORD,
            role=UserRole.SHOP_OWNER,
            subscription_tier=SubscriptionTier.PREMIUM
        )
        db.add(owner)
        owners.append((owner, "PREMIUM"))
        credentials.append({"username": owner.username, "password": STANDARD_PASSWORD, "tier": "PREMIUM"})

    # Enterprise Owner
    ent_owner = User(
        email="enterprise@example.com",
        username="enterprise_boss",
        hashed_password=HASHED_PASSWORD,
        role=UserRole.SHOP_OWNER,
        subscription_tier=SubscriptionTier.ENTERPRISE
    )
    db.add(ent_owner)
    owners.append((ent_owner, "ENTERPRISE"))
    credentials.append({"username": ent_owner.username, "password": STANDARD_PASSWORD, "tier": "ENTERPRISE"})
    
    db.commit()

    # 2. Create Shops & Services
    all_shops = []
    for owner, tier in owners:
        num_shops = 1
        if tier == "PREMIUM": num_shops = random.randint(1, 3)
        if tier == "ENTERPRISE": num_shops = 5
        
        for s_idx in range(num_shops):
            shop = Shop(
                owner_id=owner.id,
                name=f"{owner.username.title().replace('_', ' ')} Shop {s_idx+1}",
                shop_type=random.choice(["Barbershop", "Salon", "Spa", "Clinic", "Auto Repair"]),
                address=fake.address(),
                city=fake.city(),
                state=fake.state_abbr(),
                zip_code=fake.zipcode(),
                phone=fake.phone_number()[:15],
                slug=f"{owner.username}-shop-{s_idx+1}".replace("_", "-")
            )
            db.add(shop)
            db.flush()
            all_shops.append((shop, tier))

            # Add Services
            service_names = ["Standard", "Premium", "Express", "Executive", "Consultation"]
            for name in service_names:
                svc = ShopService(
                    shop_id=shop.id,
                    name=name,
                    duration_minutes=random.randint(20, 60),
                    cost=random.uniform(20.0, 150.0)
                )
                db.add(svc)
            
            # Add Queues
            num_queues = 1
            if tier in ["PREMIUM", "ENTERPRISE"]: num_queues = random.randint(1, 3)
            
            for q_idx in range(num_queues):
                q_name = "Main Queue" if q_idx == 0 else (f"Express Queue" if q_idx == 1 else "VIP Lounge")
                queue = Queue(shop_id=shop.id, name=q_name, is_active=True)
                db.add(queue)

    db.commit()

    # Save credentials
    with open("simulation_credentials.json", "w") as f:
        json.dump(credentials, f, indent=4)
    print("📁 Credentials exported to simulation_credentials.json")

    # 3. Historical Simulation
    print("🗓️ Simulating historical traffic (Accelerated)...")
    today = date.today()
    start_date = today - timedelta(days=years * 365)
    
    # We'll batch this for performance
    queues = db.query(Queue).all()
    queue_map = {}
    for q in queues:
        if q.shop_id not in queue_map: queue_map[q.shop_id] = []
        queue_map[q.shop_id].append(q)

    shop_services = {}
    for s_svc in db.query(ShopService).all():
        if s_svc.shop_id not in shop_services: shop_services[s_svc.shop_id] = []
        shop_services[s_svc.shop_id].append(s_svc)

    batch_size = 5000
    items_batch = []

    for d in range((today - start_date).days):
        curr_date = start_date + timedelta(days=d)
        is_weekend = curr_date.weekday() >= 4  # Thu-Sun are busy
        
        # Random Peak Days (seasonal)
        is_seasonal_peak = curr_date.month in [12, 7]
        
        for shop, tier in all_shops:
            # Multiplier logic
            multiplier = 1.0
            if is_weekend: multiplier *= 2.5
            if is_seasonal_peak: multiplier *= 1.8
            if random.random() < 0.05: multiplier *= 4.0 # Random Mega Peak
            
            # Throttle Day Logic (5% chance)
            is_throttle_day = random.random() < 0.05
            if is_throttle_day: multiplier *= 0.5
            
            # Traffic by tier
            base_traffic = 5
            if tier == "PREMIUM": base_traffic = 15
            if tier == "ENTERPRISE": base_traffic = 30
            
            daily_count = int(base_traffic * multiplier * random.uniform(0.5, 1.5))
            
            sh_queues = queue_map.get(shop.id, [])
            sh_services = shop_services.get(shop.id, [])
            if not sh_queues or not sh_services: continue

            for _ in range(daily_count):
                queue = random.choice(sh_queues)
                service = random.choice(sh_services)
                
                check_in_time = datetime.combine(curr_date, datetime.min.time()) + \
                                timedelta(hours=random.randint(8, 20), minutes=random.randint(0, 59))
                
                status = QueueStatus.COMPLETED if random.random() > 0.1 else QueueStatus.CANCELLED
                
                wait_time = random.randint(5, 60)
                if is_throttle_day: wait_time *= 3
                
                start_time = check_in_time + timedelta(minutes=wait_time)
                end_time = start_time + timedelta(minutes=service.duration_minutes + random.randint(-5, 15))
                
                item = QueueItem(
                    queue_id=queue.id,
                    customer_name=fake.name(),
                    position=0,
                    status=status,
                    service_id=service.id,
                    service_cost=service.cost,
                    checked_in_at=check_in_time,
                    service_started_at=start_time if status == QueueStatus.COMPLETED else None,
                    completed_at=end_time if status == QueueStatus.COMPLETED else None
                )
                items_batch.append(item)
                
                if len(items_batch) >= batch_size:
                    db.add_all(items_batch)
                    db.commit()
                    items_batch = []
                    sys.stdout.write('.')
                    sys.stdout.flush()

    if items_batch:
        db.add_all(items_batch)
        db.commit()
    print("\n✅ Historical simulation complete.")

def run_realtime_simulation(db_factory, duration_minutes=60):
    print(f"🕒 Starting REAL-TIME simulation for {duration_minutes} minutes...")
    end_time = datetime.now() + timedelta(minutes=duration_minutes)
    
    db = db_factory()
    shops = db.query(Shop).all()
    queues = db.query(Queue).all()
    queue_map = {q.id: q for q in queues}
    shop_queues = {}
    for q in queues:
        if q.shop_id not in shop_queues: shop_queues[q.shop_id] = []
        shop_queues[q.shop_id].append(q)
    
    shop_services = {}
    for s in db.query(ShopService).all():
        if s.shop_id not in shop_services: shop_services[s.shop_id] = []
        shop_services[s.shop_id].append(s)
    db.close()

    while datetime.now() < end_time:
        db = db_factory()
        try:
            # Pick a random shop
            shop = random.choice(shops)
            sh_queues = shop_queues.get(shop.id, [])
            sh_services = shop_services.get(shop.id, [])
            
            if not sh_queues: continue
            
            queue = random.choice(sh_queues)
            
            action = random.choice(["JOIN", "START", "COMPLETE", "CANCEL", "JOIN", "JOIN"]) # Weight JOIN
            
            if action == "JOIN":
                svc = random.choice(sh_services) if sh_services else None
                item = QueueItem(
                    queue_id=queue.id,
                    customer_name=fake.name(),
                    status=QueueStatus.WAITING,
                    service_id=svc.id if svc else None,
                    service_cost=svc.cost if svc else 0,
                    checked_in_at=datetime.utcnow(),
                    position=0
                )
                db.add(item)
                print(f"  [LIVE] ➕ {shop.name} ({queue.name}): {item.customer_name} joined.")
            
            elif action == "START":
                item = db.query(QueueItem).filter(
                    QueueItem.queue_id == queue.id,
                    QueueItem.status == QueueStatus.WAITING
                ).first()
                if item:
                    item.status = QueueStatus.BEING_SERVED
                    item.service_started_at = datetime.utcnow()
                    print(f"  [LIVE] ⏳ {shop.name} ({queue.name}): Service started for {item.customer_name}.")
            
            elif action == "COMPLETE":
                item = db.query(QueueItem).filter(
                    QueueItem.queue_id == queue.id,
                    QueueItem.status == QueueStatus.BEING_SERVED
                ).first()
                if item:
                    item.status = QueueStatus.COMPLETED
                    item.completed_at = datetime.utcnow()
                    print(f"  [LIVE] ✅ {shop.name} ({queue.name}): Service completed for {item.customer_name}.")
            
            elif action == "CANCEL":
                item = db.query(QueueItem).filter(
                    QueueItem.queue_id == queue.id,
                    QueueItem.status == QueueStatus.WAITING
                ).first()
                if item:
                    item.status = QueueStatus.CANCELLED
                    print(f"  [LIVE] ❌ {shop.name} ({queue.name}): {item.customer_name} cancelled.")

            db.commit()
        except Exception as e:
            print(f"  [LIVE ERR] {e}")
            db.rollback()
        finally:
            db.close()
            
        time.sleep(random.uniform(0.5, 3.0)) # Random interval between events

    print("🏁 Real-time simulation finished.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", action="store_true", help="Run with a small sample (1 month)")
    parser.add_argument("--years", type=int, default=2, help="Years of data to seed")
    parser.add_argument("--no-reset", action="store_true", help="Do not reset DB")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if not args.no_reset:
            reset_database(db)
            create_super_admin(db)
        
        years_to_seed = 0.1 if args.sample else args.years
        generate_simulation_data(db, years=years_to_seed)
        print(f"\n🚀 Data seeded ({years_to_seed} years). Moving to Real-time loop...")
    finally:
        db.close()
    
    run_realtime_simulation(SessionLocal, duration_minutes=60)
