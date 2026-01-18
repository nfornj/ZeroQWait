"""
Create sample data for testing the FastCuts application
Run this to populate the database with test users and shops
"""
import sys
from database import SessionLocal
from models import User, Shop, Queue, QueueItem, UserRole, QueueStatus, SubscriptionTier
from auth_utils import get_password_hash
from datetime import datetime

def create_sample_data():
    """Create sample users, shops, and queues"""
    db = SessionLocal()
    
    try:
        print("Creating sample data...")
        
        # Check if data already exists
        existing_users = db.query(User).count()
        if existing_users > 0:
            print(f"⚠ Database already has {existing_users} users. Skipping data creation.")
            return True
        
        # Create test users
        print("\n1. Creating users...")
        
        # Customer user
        customer = User(
            email="customer@test.com",
            username="testcustomer",
            hashed_password=get_password_hash("password123"),
            role=UserRole.CUSTOMER,
            is_active=True,
            subscription_tier=SubscriptionTier.FREE
        )
        db.add(customer)
        
        # Shop owner user
        owner = User(
            email="owner@test.com",
            username="testowner",
            hashed_password=get_password_hash("password123"),
            role=UserRole.SHOP_OWNER,
            is_active=True,
            subscription_tier=SubscriptionTier.PREMIUM
        )
        db.add(owner)
        
        # Employee user
        employee = User(
            email="employee@test.com",
            username="testemployee",
            hashed_password=get_password_hash("password123"),
            role=UserRole.EMPLOYEE,
            is_active=True,
            subscription_tier=SubscriptionTier.FREE
        )
        db.add(employee)
        
        db.commit()
        db.refresh(owner)
        
        print("   ✓ Created 3 test users")
        
        # Create test shops
        print("\n2. Creating shops...")
        
        shop1 = Shop(
            owner_id=owner.id,
            name="Downtown Barbershop",
            description="Professional haircuts and grooming services",
            shop_type="barbershop",
            address="123 Main Street",
            city="San Francisco",
            state="California",
            zip_code="94102",
            country="United States",
            phone="+1-415-555-0101",
            email="info@downtownbarber.com",
            website="https://downtownbarber.com",
            average_service_time=30,
            slug="downtown-barbershop",
            latitude=37.7749,
            longitude=-122.4194,
            is_active=True,
            primary_color="#1976d2",
            secondary_color="#424242"
        )
        db.add(shop1)
        
        shop2 = Shop(
            owner_id=owner.id,
            name="Elite Hair Salon",
            description="Modern salon with expert stylists",
            shop_type="salon",
            address="456 Oak Avenue",
            city="San Francisco",
            state="California",
            zip_code="94103",
            country="United States",
            phone="+1-415-555-0102",
            email="contact@elitehair.com",
            website="https://elitehair.com",
            average_service_time=45,
            slug="elite-hair-salon",
            latitude=37.7739,
            longitude=-122.4312,
            is_active=True,
            primary_color="#e91e63",
            secondary_color="#9c27b0"
        )
        db.add(shop2)
        
        db.commit()
        db.refresh(shop1)
        db.refresh(shop2)
        
        print("   ✓ Created 2 test shops")
        
        # Create queues
        print("\n3. Creating queues...")
        
        queue1 = Queue(
            shop_id=shop1.id,
            name="Main Queue",
            is_active=True,
            date=datetime.utcnow()
        )
        db.add(queue1)
        
        queue2 = Queue(
            shop_id=shop2.id,
            name="Main Queue",
            is_active=True,
            date=datetime.utcnow()
        )
        db.add(queue2)
        
        db.commit()
        db.refresh(queue1)
        
        print("   ✓ Created 2 queues")
        
        # Create queue items
        print("\n4. Creating queue items...")
        
        item1 = QueueItem(
            queue_id=queue1.id,
            user_id=customer.id,
            customer_name="John Doe",
            customer_phone="+1-415-555-1234",
            customer_email="john@example.com",
            position=1,
            status=QueueStatus.WAITING,
            notes="Regular haircut"
        )
        db.add(item1)
        
        item2 = QueueItem(
            queue_id=queue1.id,
            customer_name="Jane Smith",
            customer_phone="+1-415-555-5678",
            position=2,
            status=QueueStatus.WAITING,
            notes="Haircut and beard trim"
        )
        db.add(item2)
        
        db.commit()
        
        print("   ✓ Created 2 queue items")
        
        print("\n" + "="*60)
        print("✅ Sample data created successfully!")
        print("="*60)
        print("\n📋 Test Accounts:")
        print("\n1. Customer Account:")
        print("   Username: testcustomer")
        print("   Password: password123")
        print("   Email: customer@test.com")
        
        print("\n2. Shop Owner Account:")
        print("   Username: testowner")
        print("   Password: password123")
        print("   Email: owner@test.com")
        
        print("\n3. Employee Account:")
        print("   Username: testemployee")
        print("   Password: password123")
        print("   Email: employee@test.com")
        
        print("\n🏪 Test Shops:")
        print(f"   - Downtown Barbershop (ID: {shop1.id})")
        print(f"   - Elite Hair Salon (ID: {shop2.id})")
        
        print("\n🔗 API Endpoints to Test:")
        print("   - GET  /api/shops - List all shops")
        print("   - POST /api/token - Login")
        print("   - GET  /api/users/me - Get current user")
        print("   - GET  /docs - API documentation")
        print("\n")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error creating sample data: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = create_sample_data()
    sys.exit(0 if success else 1)
