import random
from datetime import datetime, timedelta
import sys
from sqlalchemy import create_engine, text
from database import DATABASE_URL
from models import Base, ShopService, Shop, Queue, QueueItem

# Connect to database
engine = create_engine(DATABASE_URL)

def populate_revenue_data():
    print("Connecting to database...")
def populate_revenue_data():
    print("Connecting to database...")
    with engine.connect() as conn:
        # 1. Get ALL active shops
        shops_result = conn.execute(text("SELECT id, name FROM shops WHERE is_active = true")).fetchall()
        
        if not shops_result:
            print("No active shops found.")
            return

        for shop in shops_result:
            shop_id = shop.id
            print(f"Populating data for Shop: {shop.name} (ID: {shop_id})")

            # 2. Get services for this shop
            services_result = conn.execute(text("SELECT id, name, cost FROM shop_services WHERE shop_id = :shop_id"), {"shop_id": shop_id}).fetchall()
            
            if not services_result:
                print(f"  No services found for {shop.name}. Creating dummy services...")
                # If no services, let's create some
                dummy_services = [
                    {"name": "Haircut", "cost": 25.0},
                    {"name": "Shave", "cost": 15.0},
                    {"name": "Coloring", "cost": 60.0},
                    {"name": "Styling", "cost": 40.0}
                ]
                
                created_services = []
                for ds in dummy_services:
                    res = conn.execute(text("""
                        INSERT INTO shop_services (shop_id, name, description, duration_minutes, cost, is_active)
                        VALUES (:shop_id, :name, 'Dummy service', 30, :cost, true)
                        RETURNING id, name, cost
                    """), {"shop_id": shop_id, "name": ds["name"], "cost": ds["cost"]})
                    created_services.append(res.fetchone())
                conn.commit()
                services = created_services
            else:
                services = services_result

            # 3. Get the main queue
            queue_result = conn.execute(text("SELECT id FROM queues WHERE shop_id = :shop_id LIMIT 1"), {"shop_id": shop_id}).fetchone()
            if not queue_result:
                print(f"  Creating dummy queue for {shop.name}...")
                res = conn.execute(text("INSERT INTO queues (shop_id, name, is_active) VALUES (:shop_id, 'Main Queue', true) RETURNING id"), {"shop_id": shop_id})
                queue_id = res.scalar()
                conn.commit()
            else:
                queue_id = queue_result.id

            # 4. Generate Data for last 6 months
            print(f"  Generating transactions for {shop.name}...")
            end_date = datetime.now()
            start_date = end_date - timedelta(days=180)
            
            # We'll create about 50-100 random transactions per month
            records_created = 0
            
            current_date = start_date
            while current_date <= end_date:
                # Random number of bookings for this day (0 to 5)
                daily_count = random.randint(0, 5)
                
                for _ in range(daily_count):
                    service = random.choice(services)
                    
                    # Determine times
                    check_in_time = current_date.replace(hour=random.randint(9, 16), minute=random.randint(0, 59))
                    service_start_time = check_in_time + timedelta(minutes=random.randint(5, 30))
                    completed_time = service_start_time + timedelta(minutes=30) # approx duration
                    
                    conn.execute(text("""
                        INSERT INTO queue_items 
                        (queue_id, customer_name, customer_phone, status, position,
                         service_id, service_cost, 
                         checked_in_at, service_started_at, completed_at)
                        VALUES 
                        (:queue_id, :name, '555-0199', 'COMPLETED', 0,
                         :service_id, :cost, 
                         :checked_in, :started, :completed)
                    """), {
                        "queue_id": queue_id,
                        "name": f"Customer {random.randint(1000, 9999)}",
                        "service_id": service.id,
                        "cost": service.cost,
                        "checked_in": check_in_time,
                        "started": service_start_time,
                        "completed": completed_time
                    })
                    records_created += 1
                
                current_date += timedelta(days=1)
                
            conn.commit()
            print(f"  Successfully created {records_created} records for {shop.name}.")

if __name__ == "__main__":
    populate_revenue_data()
