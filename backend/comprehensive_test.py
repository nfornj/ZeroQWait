import asyncio
import httpx
import logging
import sys
import random
from datetime import datetime, timedelta
from database import SessionLocal
from models import QueueItem, Queue, Shop
from sqlalchemy.orm import Session

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000/api"

# Test Data
OWNER_EMAIL = f"owner_v2_{random.randint(1000,9999)}@test.com"
OWNER_PASS = "password123"
SHOP_NAME = f"Validation Barber {random.randint(100,999)}"

async def run_api_tests():
    async with httpx.AsyncClient(timeout=30.0) as client:
        logger.info("🚀 Starting Comprehensive API Test & Seeding...")

        # 1. Register Shop Owner
        logger.info(f"1. Registering Shop Owner: {OWNER_EMAIL}")
        # Note: Correct endpoint from users.py is /api/users
        res = await client.post(f"{BASE_URL}/users", json={
            "email": OWNER_EMAIL,
            "username": f"owner_v2_{random.randint(1000,9999)}",
            "password": OWNER_PASS,
            "role": "shop_owner"
        })
        if res.status_code != 200:
            logger.error(f"❌ Registration Failed: {res.text}")
            return
        
        # 2. Login
        logger.info("2. Logging in...")
        # Note: Correct endpoint from auth.py is /api/auth/token
        res = await client.post(f"{BASE_URL}/auth/token", data={
            "username": OWNER_EMAIL,
            "password": OWNER_PASS
        })
        if res.status_code != 200:
            logger.error(f"❌ Login Failed: {res.text}")
            return
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        logger.info("✅ Login Successful")

        # 3. Create Shop
        logger.info("3. Creating Shop...")
        res = await client.post(f"{BASE_URL}/shops/", json={
            "name": SHOP_NAME,
            "address": "123 Test St",
            "city": "Test City",
            "state": "TS",
            "zip_code": "12345",
            "phone": "555-0100",
            "shop_type": "Barbershop",
            "slug": f"test-shop-{random.randint(1000,9999)}",
            "country": "United States"
        }, headers=headers)
        
        if res.status_code != 200:
            logger.error(f"❌ Shop Creation Failed: {res.text}")
            return
        shop = res.json()
        shop_id = shop["id"]
        logger.info(f"✅ Shop Created: {shop['name']} (ID: {shop_id})")

        # 4. Create Employees
        logger.info("4. Creating Employees...")
        employees = ["John Barber", "Jane Stylist", "Mike Colorist"]
        for emp_name in employees:
            res = await client.post(f"{BASE_URL}/employees/", json={
                "username": emp_name.lower().replace(" ", ""),
                "email": f"{emp_name.lower().replace(' ', '')}@test.com",
                "password": "password123",
                "shop_id": shop_id
            }, headers=headers)
            if res.status_code == 200:
                logger.info(f"   ✓ Created employee: {emp_name}")
            else:
                logger.error(f"   ✗ Failed to create {emp_name}: {res.text}")

        # 5. Create Queues
        logger.info("5. Creating Queues...")
        res = await client.post(f"{BASE_URL}/queues/", json={
            "name": "Walk-ins",
            "shop_id": shop_id,
        }, headers=headers)
        if res.status_code != 200:
             # Try getting existing queues if creation fails (maybe auto-created)
             res = await client.get(f"{BASE_URL}/queues/{shop_id}", headers=headers)
        
        queues = res.json()
        if not queues:
             logger.error("❌ No queues found or created")
             return
        
        main_queue = queues[0] if isinstance(queues, list) else queues
        queue_id = main_queue["id"]
        logger.info(f"✅ Queue Validated: {main_queue['name']} (ID: {queue_id})")

        # 6. Simulate Active Usage (Join, Serve, Complete)
        logger.info("6. Simulating Live Queue Flow (Join -> Serve -> Complete)...")
        
        # Validating Create Queue Item (Join)
        res = await client.post(f"{BASE_URL}/queues/{queue_id}/join", json={
            "customer_name": "Test Customer Live",
            "customer_phone": "555-0000",
            "notes": "Live Test Haircut"
        })
        if res.status_code == 200:
            item = res.json()
            item_id = item["id"]
            logger.info("   ✓ Customer Joined Queue")
            
            # Serve
            res = await client.put(f"{BASE_URL}/queues/items/{item_id}/status", 
                json={"status": "being_served"}, 
                headers=headers
            )
            if res.status_code == 200:
                logger.info("   ✓ Serving Customer")
                
                # Complete
                res = await client.put(f"{BASE_URL}/queues/items/{item_id}/status", 
                    json={"status": "completed"}, 
                    headers=headers
                )
                if res.status_code == 200:
                    logger.info("   ✓ Service Completed")
                else:
                    logger.error("   ✗ Failed to complete service")
            else:
                logger.error("   ✗ Failed to start service")
        else:
             logger.error(f"   ✗ Join Failed: {res.text}")

        # 7. Seed Historical Data (Direct DB for Analytics)
        logger.info("7. Seeding Historical Data for Analytics...")
        spawn_historical_data(shop_id, queue_id)
        
        logger.info("\n" + "="*50)
        logger.info("🎉 TEST COMPLETE")
        logger.info("="*50)
        logger.info(f"Login Email: {OWNER_EMAIL}")
        logger.info(f"Login Pass : {OWNER_PASS}")
        logger.info(f"Shop Name  : {SHOP_NAME}")
        logger.info("LOG INTO THE DASHBOARD WITH THESE CREDENTIALS TO SEE DATA!")


def spawn_historical_data(shop_id, queue_id):
    """
    Directly inserts 30 days of data into the database using SQLAlchemy.
    This ensures the 'Analytics' page has something to show.
    """
    try:
        db = SessionLocal()
        from analytics_processor import AnalyticsProcessor
        processor = AnalyticsProcessor(db)

        services = ["Haircut", "Shave", "Beard Trim", "Coloring"]
        
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=30)
        current = start_date
        
        total_seeded = 0
        
        while current <= end_date:
            visits = random.randint(15, 45)
            day_start = datetime.combine(current, datetime.min.time()) + timedelta(hours=9)
            
            for i in range(visits):
                c_time = day_start + timedelta(minutes=random.randint(0, 480))
                s_start = c_time + timedelta(minutes=random.randint(5, 30))
                c_end = s_start + timedelta(minutes=random.randint(20, 45))
                
                item = QueueItem(
                    queue_id=queue_id,
                    customer_name=f"Historical User {random.randint(100,999)}",
                    position=i+1,
                    status="completed",
                    checked_in_at=c_time,
                    service_started_at=s_start,
                    completed_at=c_end,
                    notes=random.choice(services)
                )
                db.add(item)
                total_seeded += 1
            
            db.commit()
            # Run aggregation
            processor.aggregate_daily_analytics(current)
            current += timedelta(days=1)
            
        logger.info(f"✅ Seeded {total_seeded} historical records")
        db.close()
    except Exception as e:
        logger.error(f"❌ Historical Seeding Failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_api_tests())
