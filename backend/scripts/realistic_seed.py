import sys
import random
import os
from faker import Faker
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from database import SessionLocal
# Modular imports
from modules.auth.models import User, UserRole
from modules.shops.models import Shop, ShopService as ShopServiceModel, DailyAnalytics
from modules.queues.models import Queue, QueueItem, QueueStatus
from modules.employees.models import ShopEmployee, EmployeeShift
from shared.auth_utils import get_password_hash
from slugify import slugify

fake = Faker()

def create_realistic_data():
    db = SessionLocal()
    try:
        print("🌱 Starting realistic data seeding and simulation (direct DB mode)...")
        
        # 1. Create a Master Owner for simulated shops
        sim_owner_username = "simulation_owner"
        sim_owner = db.query(User).filter(User.username == sim_owner_username).first()
        
        if not sim_owner:
            print(f"  👤 Creating simulation owner: {sim_owner_username}")
            hashed_pw = get_password_hash("password123")
            sim_owner = User(
                username=sim_owner_username,
                email="sim@zeroqwait.com",
                hashed_password=hashed_pw,
                role=UserRole.SHOP_OWNER
            )
            db.add(sim_owner)
            db.commit()
            db.refresh(sim_owner)
        
        # 2. Create Realistic Shops
        shop_types = [
            ("Barber Shop", ["Haircut", "Beard Trim", "Straight Razor Shave", "Hair Wash"]),
            ("Hair Salon", ["Balayage", "Trim", "Blowdry", "Bridal Styling", "Hair Color"]),
            ("Medical Clinic", ["General Consultation", "Flu Shot", "Physical Exam", "X-Ray"]),
            ("Spa & Wellness", ["Massage", "Facial", "Manicure", "Pedicure"]),
            ("Restaurant", ["Lunch Reservation", "Dinner Seat", "Takeaway Pickup"])
        ]
        
        for i in range(5):
            s_type, s_services = random.choice(shop_types)
            s_name = f"{fake.company()} {s_type}"
            
            print(f"  🏢 Creating Shop: {s_name} ({s_type})")
            
            # Generate slug
            base_slug = slugify(s_name)
            slug = base_slug
            counter = 1
            while db.query(Shop).filter(Shop.slug == slug).first():
                slug = f"{base_slug}-{counter}"
                counter += 1

            new_shop = Shop(
                owner_id=sim_owner.id,
                name=s_name,
                shop_type=s_type.lower(),
                description=fake.catch_phrase(),
                address=fake.street_address(),
                city=fake.city(),
                state=fake.state(),
                zip_code=fake.zipcode(),
                phone=fake.phone_number()[:20],
                email=fake.company_email(),
                average_service_time=random.randint(15, 60),
                latitude=float(fake.latitude()),
                longitude=float(fake.longitude()),
                slug=slug,
                is_active=True
            )
            db.add(new_shop)
            db.flush() # Get ID
            
            # Add services
            db_services = []
            for svc_name in s_services:
                svc = ShopServiceModel(
                    shop_id=new_shop.id,
                    name=svc_name,
                    description=fake.sentence(),
                    duration_minutes=random.randint(15, 60),
                    cost=random.uniform(20.0, 150.0)
                )
                db.add(svc)
                db_services.append(svc)
            
            db.flush()

            # Create a Main Queue
            main_queue = Queue(
                shop_id=new_shop.id,
                name="Primary Queue",
                is_active=True
            )
            db.add(main_queue)
            db.flush()
            
            # 3. Simulation: Historic items (last 30 days)
            print(f"    📡 Simulating 30 days of traffic for {s_name}...")
            
            for d in range(30):
                sim_date = date.today() - timedelta(days=d)
                daily_count = random.randint(5, 15)
                
                for _ in range(daily_count):
                    status = QueueStatus.COMPLETED if random.random() > 0.1 else QueueStatus.CANCELLED
                    service = random.choice(db_services)
                    
                    check_in_time = datetime.combine(sim_date, datetime.min.time()) + \
                                    timedelta(hours=random.randint(9, 18), minutes=random.randint(0, 59))
                    
                    wait_time = random.randint(5, 40)
                    service_time = service.duration_minutes + random.randint(-10, 10)
                    
                    item = QueueItem(
                        queue_id=main_queue.id,
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
                    db.add(item)
            
            db.commit()
            print(f"    ✅ Shop {s_name} seeded successfully.")

        print("🏁 All simulations and seeding complete!")

    except Exception as e:
        print(f"❌ Seeding Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    sys.path.append(os.getcwd())
    create_realistic_data()
