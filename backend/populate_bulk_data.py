import sys
import random
import argparse
from datetime import datetime, timedelta
from database import SessionLocal
from models import User, Shop, Queue, QueueItem, UserRole, QueueStatus, SubscriptionTier, ShopService, ShopEmployee
from auth_utils import get_password_hash
from sqlalchemy import text, or_

# Geographic Data
US_CITIES = [
    {"city": "New York", "state": "NY", "lat": 40.7128, "lng": -74.0060},
    {"city": "Los Angeles", "state": "CA", "lat": 34.0522, "lng": -118.2437},
    {"city": "Chicago", "state": "IL", "lat": 41.8781, "lng": -87.6298},
    {"city": "Houston", "state": "TX", "lat": 29.7604, "lng": -95.3698},
    {"city": "Phoenix", "state": "AZ", "lat": 33.4484, "lng": -112.0740},
    {"city": "Philadelphia", "state": "PA", "lat": 39.9526, "lng": -75.1652},
    {"city": "San Antonio", "state": "TX", "lat": 29.4241, "lng": -98.4936},
    {"city": "San Diego", "state": "CA", "lat": 32.7157, "lng": -117.1611},
    {"city": "Dallas", "state": "TX", "lat": 32.7767, "lng": -96.7970},
    {"city": "San Francisco", "state": "CA", "lat": 37.7749, "lng": -122.4194},
]

CA_CITIES = [
    {"city": "Toronto", "state": "ON", "lat": 43.6532, "lng": -79.3832},
    {"city": "Montreal", "state": "QC", "lat": 45.5017, "lng": -73.5673},
    {"city": "Vancouver", "state": "BC", "lat": 49.2827, "lng": -123.1207},
    {"city": "Calgary", "state": "AB", "lat": 51.0447, "lng": -114.0719},
    {"city": "Ottawa", "state": "ON", "lat": 45.4215, "lng": -75.6972},
    {"city": "Edmonton", "state": "AB", "lat": 53.5461, "lng": -113.4938},
    {"city": "Winnipeg", "state": "MB", "lat": 49.8951, "lng": -97.1384},
    {"city": "Quebec City", "state": "QC", "lat": 46.8139, "lng": -71.2080},
    {"city": "Hamilton", "state": "ON", "lat": 43.2557, "lng": -79.8711},
    {"city": "Kitchener", "state": "ON", "lat": 43.4516, "lng": -80.4925},
]

SHOP_TYPES = [
    {"type": "Barber", "services": ["Haircut", "Beard Trim", "Shave"]},
    {"type": "Salon", "services": ["Haircut", "Color", "Style", "Wash"]},
    {"type": "Nail Spa", "services": ["Manicure", "Pedicure", "Gel Nails"]},
    {"type": "Auto Repair", "services": ["Oil Change", "Tire Rotation", "Brake Check"]},
    {"type": "Clinic", "services": ["Consultation", "Checkup", "Vaccination"]},
    {"type": "Restaurant", "services": ["Table for 2", "Table for 4", "Bar Seating"]},
    {"type": "Vet", "services": ["Pet Exam", "Grooming", "Vaccination"]},
]

ADJECTIVES = ["Elite", "Modern", "Downtown", "Crystal", "Urban", "Royal", "Prime", "Swift", "Golden", "Classic"]

def generate_random_name():
    first_names = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda", "William", "Elizabeth"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
    return f"{random.choice(first_names)} {random.choice(last_names)}"

def create_bulk_data(count=100):
    db = SessionLocal()
    accounts = []
    
    try:
        print(f"🚀 Starting bulk creation of {count} shops...")
        
        for i in range(count):
            # 1. Create Owner
            name = generate_random_name()
            username = f"test_bulk_owner_{i}_{random.randint(1000, 9999)}"
            email = f"{username}@zeroqwait.com"
            password = "password123"
            
            owner = User(
                email=email,
                username=username,
                hashed_password=get_password_hash(password),
                role=UserRole.SHOP_OWNER,
                subscription_tier=SubscriptionTier.PREMIUM
            )
            db.add(owner)
            db.flush()
            
            accounts.append(f"OWNER: {username} | {password} | {email}")
            
            # 2. Create Shop
            is_ca = random.choice([True, False])
            city_data = random.choice(CA_CITIES if is_ca else US_CITIES)
            shop_info = random.choice(SHOP_TYPES)
            shop_name = f"{random.choice(ADJECTIVES)} {shop_info['type']}"
            
            shop = Shop(
                owner_id=owner.id,
                name=shop_name,
                shop_type=shop_info['type'].lower().replace(" ", "_"),
                address=f"{random.randint(10, 999)} {random.choice(['Main', 'Oak', 'Maple', 'Pine'])} St",
                city=city_data['city'],
                state=city_data['state'],
                zip_code=str(random.randint(10000, 99999)),
                country="Canada" if is_ca else "United States",
                phone=f"555-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
                slug=f"{shop_name.lower().replace(' ', '-')}-{i}-{random.randint(100, 999)}",
                latitude=city_data['lat'] + random.uniform(-0.05, 0.05),
                longitude=city_data['lng'] + random.uniform(-0.05, 0.05),
                average_service_time=random.randint(15, 60)
            )
            db.add(shop)
            db.flush()
            
            # 3. Create Services
            services = []
            for s_name in shop_info['services']:
                service = ShopService(
                    shop_id=shop.id,
                    name=s_name,
                    cost=random.randint(20, 100),
                    duration_minutes=random.randint(15, 60)
                )
                db.add(service)
                services.append(service)
            db.flush()
            
            # 4. Create Main Queue
            queue = Queue(shop_id=shop.id, name="Main Queue")
            db.add(queue)
            db.flush()
            
            # 5. Create Employees
            for e_idx in range(random.randint(1, 3)):
                e_name = generate_random_name()
                e_username = f"test_bulk_emp_{i}_{e_idx}_{random.randint(1000, 9999)}"
                e_email = f"{e_username}@zeroqwait.com"
                
                emp_user = User(
                    email=e_email,
                    username=e_username,
                    hashed_password=get_password_hash(password),
                    role=UserRole.EMPLOYEE
                )
                db.add(emp_user)
                db.flush()
                
                shop_emp = ShopEmployee(shop_id=shop.id, user_id=emp_user.id)
                db.add(shop_emp)
                
                accounts.append(f"EMPLOYEE: {e_username} | {password} | {e_email} (Shop: {shop.name})")
            
            # 6. Create Queue Items (Customers)
            num_items = random.randint(5, 15)
            for q_idx in range(num_items):
                status = QueueStatus.COMPLETED if q_idx < num_items - 3 else QueueStatus.WAITING
                service = random.choice(services)
                
                q_item = QueueItem(
                    queue_id=queue.id,
                    customer_name=generate_random_name(),
                    customer_phone=f"555-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
                    position=q_idx + 1 if status == QueueStatus.WAITING else 0,
                    status=status,
                    service_id=service.id,
                    service_cost=service.cost,
                    checked_in_at=datetime.utcnow() - timedelta(hours=random.randint(1, 24))
                )
                db.add(q_item)
            
            if i % 10 == 0:
                print(f"  Processed {i}/{count} shops...")
                db.commit()

        db.commit()
        
        # Write accounts to file
        with open("test_accounts.txt", "w") as f:
            f.write("\n".join(accounts))
            
        print(f"✅ Created {count} shops and logged credentials to test_accounts.txt")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

def destroy_bulk_data():
    db = SessionLocal()
    try:
        print("🧨 Destroying bulk test data...")
        
        prefix = "test_bulk_"
        
        # Find all users with the prefix
        users_to_delete = db.query(User).filter(or_(User.username.like(f"{prefix}%"), User.email.like(f"{prefix}%"))).all()
        user_ids = [u.id for u in users_to_delete]
        
        if not user_ids:
            print("No bulk test data found.")
            return

        print(f"Found {len(user_ids)} test users. Cleaning up shops, employees, and queues...")
        
        # Delete Shops owned by these users (this will cascade to queues, services, items)
        db.query(Shop).filter(Shop.owner_id.in_(user_ids)).delete(synchronize_session=False)
        
        # Delete ShopEmployee records where these users are the employees
        db.query(ShopEmployee).filter(ShopEmployee.user_id.in_(user_ids)).delete(synchronize_session=False)
        
        # Finally delete the users
        db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        
        db.commit()
        print(f"✅ Successfully purged all data starting with '{prefix}'")
        
    except Exception as e:
        print(f"❌ Error during destruction: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk Data Generator")
    parser.add_argument("--mode", choices=["create", "destroy"], required=True)
    parser.add_argument("--count", type=int, default=100)
    args = parser.parse_args()
    
    if args.mode == "create":
        create_bulk_data(args.count)
    else:
        destroy_bulk_data()
