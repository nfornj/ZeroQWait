import random
import sys
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import SessionLocal
from models import (
    User, UserRole, SubscriptionTier, 
    Shop, ShopService, 
    Queue, QueueItem, QueueStatus
)
from shared.auth_utils import get_password_hash

# --- Configuration ---
NUM_CUSTOMERS = 20
NUM_FREE_OWNERS = 3
NUM_PREMIUM_OWNERS = 2
SHOPS_PER_OWNER = 2
SERVICES_PER_SHOP = 4
QUEUE_ITEMS_PER_SHOP = 10

# --- Lists for Random Generation ---
FIRST_NAMES = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda", "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]
SHOP_TYPES = ["Barbershop", "Salon", "Dentist", "Spa", "Tattoo Parlor", "Auto Repair", "Clinic"]
CITIES = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose"]
SERVICE_NAMES = {
    "Barbershop": ["Haircut", "Beard Trim", "Shave", "Buzz Cut"],
    "Salon": ["Hair Coloring", "Blowout", "Styling", "Deep Conditioning"],
    "Dentist": ["Cleaning", "X-Ray", "Consultation", "Filling"],
    "Spa": ["Massage", "Facial", "Manicure", "Pedicure"],
    "Tattoo Parlor": ["Small Tattoo", "Consultation", "Touch Up", "Piercing"]
}

def get_random_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def get_random_email(name):
    clean_name = name.lower().replace(' ', '.').replace("'", "")
    return f"{clean_name}{random.randint(100, 999)}@example.com"

def seed_data():
    db = SessionLocal()
    try:
        print("🚀 Starting Rigorous Data Seeding...")
        
        # 1. Clear existing data (Optional but recommended for a clean test state)
        # Note: Be careful with deletions if existing data is precious.
        # For this exhaustive test, we'll just add to it unless specified otherwise.
        # print("🧹 Cleaning up existing test data...")
        # db.query(QueueItem).delete()
        # db.query(Queue).delete()
        # db.query(ShopService).delete()
        # db.query(Shop).delete()
        # db.query(User).filter(User.email.like('%@example.com')).delete(synchronize_session=False)
        # db.commit()

        # 2. Create Customers
        print(f"👤 Creating {NUM_CUSTOMERS} customers...")
        customers = []
        for i in range(NUM_CUSTOMERS):
            name = get_random_name()
            username = name.lower().replace(" ", "_") + str(i)
            email = get_random_email(name)
            user = User(
                email=email,
                username=username,
                hashed_password=get_password_hash("password123"),
                role=UserRole.CUSTOMER,
                is_active=True,
                subscription_tier=SubscriptionTier.FREE
            )
            db.add(user)
            customers.append(user)
        db.commit()

        # 3. Create Shop Owners (Free)
        print(f"🏢 Creating {NUM_FREE_OWNERS} Free Shop Owners...")
        free_owners = []
        for i in range(NUM_FREE_OWNERS):
            name = get_random_name()
            username = f"free_owner_{i}_{uuid.uuid4().hex[:4]}"
            email = f"free_{i}_{uuid.uuid4().hex[:4]}@example.com"
            owner = User(
                email=email,
                username=username,
                hashed_password=get_password_hash("password123"),
                role=UserRole.SHOP_OWNER,
                is_active=True,
                subscription_tier=SubscriptionTier.FREE
            )
            db.add(owner)
            free_owners.append(owner)
        db.commit()

        # 4. Create Shop Owners (Premium)
        print(f"💎 Creating {NUM_PREMIUM_OWNERS} Premium Shop Owners...")
        premium_owners = []
        for i in range(NUM_PREMIUM_OWNERS):
            name = get_random_name()
            username = f"prem_owner_{i}_{uuid.uuid4().hex[:4]}"
            email = f"prem_{i}_{uuid.uuid4().hex[:4]}@example.com"
            owner = User(
                email=email,
                username=username,
                hashed_password=get_password_hash("password123"),
                role=UserRole.SHOP_OWNER,
                is_active=True,
                subscription_tier=SubscriptionTier.PREMIUM
            )
            db.add(owner)
            premium_owners.append(owner)
        db.commit()

        # 5. Create Shops & Services
        all_shops = []
        all_owners = free_owners + premium_owners
        print(f"🏪 Creating Shops and Services for {len(all_owners)} owners...")
        
        for owner in all_owners:
            # Free owners restricted to 1 shop (policy simulation), Premium can have many
            limit = 1 if owner.subscription_tier == SubscriptionTier.FREE else SHOPS_PER_OWNER
            
            for j in range(limit):
                shop_type = random.choice(list(SERVICE_NAMES.keys()))
                shop_name = f"{random.choice(FIRST_NAMES)}'s {shop_type}"
                city = random.choice(CITIES)
                
                clean_shop_name = shop_name.lower().replace(' ', '-').replace("'", "")
                shop = Shop(
                    owner_id=owner.id,
                    name=shop_name,
                    description=f"Welcome to {shop_name}, the best {shop_type.lower()} in {city}!",
                    shop_type=shop_type.lower(),
                    address=f"{random.randint(100, 9999)} Main St",
                    city=city,
                    state="CA",
                    zip_code=str(random.randint(10000, 99999)),
                    phone=f"+1-{random.randint(200, 999)}-555-{random.randint(1000, 9999)}",
                    average_service_time=random.choice([15, 30, 45, 60]),
                    slug=f"{clean_shop_name}-{uuid.uuid4().hex[:4]}",
                    is_active=True
                )
                db.add(shop)
                all_shops.append(shop)
                db.flush() # Get shop ID

                # Add Services
                services = SERVICE_NAMES.get(shop_type, ["General Service"])
                for s_name in services:
                    service = ShopService(
                        shop_id=shop.id,
                        name=s_name,
                        duration_minutes=random.choice([15, 30, 45, 60]),
                        cost=float(random.randint(10, 100)),
                        is_active=True
                    )
                    db.add(service)
        db.commit()

        # 6. Create Queues and Queue Items
        print(f"📅 Creating Queues and {len(all_shops) * QUEUE_ITEMS_PER_SHOP} Queue Entries...")
        for shop in all_shops:
            queue = Queue(
                shop_id=shop.id,
                name="Day Queue",
                is_active=True,
                date=datetime.utcnow()
            )
            db.add(queue)
            db.flush()

            services = db.query(ShopService).filter(ShopService.shop_id == shop.id).all()
            
            for k in range(QUEUE_ITEMS_PER_SHOP):
                service = random.choice(services)
                # Mixture of registered users and guests
                is_registered = random.random() > 0.3
                user_id = random.choice(customers).id if is_registered else None
                
                name = get_random_name()
                
                # Mixture of statuses
                status_roll = random.random()
                if status_roll < 0.2:
                    status = QueueStatus.COMPLETED
                elif status_roll < 0.3:
                    status = QueueStatus.CANCELLED
                elif status_roll < 0.4:
                    status = QueueStatus.BEING_SERVED
                else:
                    status = QueueStatus.WAITING

                item = QueueItem(
                    queue_id=queue.id,
                    user_id=user_id,
                    customer_name=name,
                    customer_phone=f"+1-{random.randint(200, 999)}-555-{random.randint(1000, 9999)}",
                    position=k + 1,
                    status=status,
                    service_id=service.id,
                    service_cost=service.cost,
                    checked_in_at=datetime.utcnow() - timedelta(minutes=random.randint(10, 200))
                )
                db.add(item)
        
        db.commit()
        print("✅ Data Seeding Completed Successfully!")
        print(f"📊 Summary:")
        print(f"   - Customers: {NUM_CUSTOMERS}")
        print(f"   - Shop Owners: {NUM_FREE_OWNERS + NUM_PREMIUM_OWNERS}")
        print(f"   - Shops Created: {len(all_shops)}")
        print(f"   - Queue Entries: {len(all_shops) * QUEUE_ITEMS_PER_SHOP}")

    except Exception as e:
        print(f"❌ Error during seeding: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
