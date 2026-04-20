import sys
import random
from datetime import datetime, date, timedelta
from database import SessionLocal
from models import Shop, Queue, QueueItem, DailyAnalytics, QueueStatus, ShopService
from sqlalchemy import func

def simulate_historical_data(years=5, shops_prefix="test_bulk_"):
    db = SessionLocal()
    try:
        print(f"📈 Starting 5-year historical simulation for shops with prefix: '{shops_prefix}'")
        
        # 1. Target shops by owner's test username prefix
        from models import User
        shops = db.query(Shop).join(User, Shop.owner_id == User.id).filter(User.username.like(f"{shops_prefix}%")).all()
        if not shops:
            print("No shops found with the specified prefix.")
            return

        print(f"Found {len(shops)} shops to simulate data for.")
        
        end_date = date.today()
        start_date = end_date - timedelta(days=years * 365)
        
        # Boundary for raw vs aggregated
        raw_boundary_days = 90
        raw_boundary_date = end_date - timedelta(days=raw_boundary_days)

        for shop in shops:
            print(f"  🏢 Simulating: {shop.name} (Type: {shop.shop_type})")
            
            services = db.query(ShopService).filter(ShopService.shop_id == shop.id).all()
            if not services:
                print(f"    ⚠️ No services found for {shop.name}, skipping.")
                continue
            
            queue = db.query(Queue).filter(Queue.shop_id == shop.id).first()
            if not queue:
                queue = Queue(shop_id=shop.id, name="Main Queue")
                db.add(queue)
                db.flush()

            # Business Growth Factor: Starts at 40% of current capacity and grows to 100%
            growth_base = 0.4 
            
            current_date = start_date
            day_count = 0
            
            while current_date <= end_date:
                # Progress factor (0.0 at start, 1.0 at end)
                days_since_start = (current_date - start_date).days
                total_days = (end_date - start_date).days
                progress = days_since_start / total_days
                
                # Seasonality (Sin wave)
                # Max in summer (July) and Winter (Dec)
                seasonality = 1.0 + (0.2 * random.random()) # Random jitter
                month = current_date.month
                if month in [12, 7, 8]:
                    seasonality += 0.3
                
                # Weekend boost
                is_weekend = current_date.weekday() >= 5
                weekend_boost = 1.5 if is_weekend else 1.0
                
                # Daily volume (Randomized + Growth + Seasonality)
                current_growth = growth_base + (progress * (1.0 - growth_base))
                base_customers = random.randint(8, 25)
                daily_volume = int(base_customers * current_growth * seasonality * weekend_boost)
                
                if current_date > raw_boundary_date:
                    # GENERATE RAW RECORDS (Last 90 days)
                    for i in range(daily_volume):
                        status = QueueStatus.COMPLETED if random.random() > 0.05 else QueueStatus.CANCELLED
                        service = random.choice(services)
                        
                        # Timestamps
                        check_in = datetime.combine(current_date, datetime.min.time()) + \
                                   timedelta(hours=random.randint(9, 17), minutes=random.randint(0, 59))
                        
                        wait_min = random.randint(2, 45)
                        serv_min = random.randint(15, 60)
                        
                        item = QueueItem(
                            queue_id=queue.id,
                            customer_name=f"Sim Customer {random.randint(1000, 9999)}",
                            customer_phone=f"555-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
                            position=0,
                            status=status,
                            service_id=service.id,
                            service_cost=service.cost,
                            checked_in_at=check_in,
                            service_started_at=check_in + timedelta(minutes=wait_min) if status == QueueStatus.COMPLETED else None,
                            completed_at=check_in + timedelta(minutes=wait_min + serv_min) if status == QueueStatus.COMPLETED else None
                        )
                        db.add(item)
                
                # ALWAYS GENERATE AGGREGATED ANALYTICS (Full 5 years)
                # This ensures charts are fast
                rev = 0
                completed = int(daily_volume * 0.95)
                for _ in range(completed):
                    rev += random.choice(services).cost * (0.9 + (0.2 * random.random())) # Cost jitter
                
                daily_stat = DailyAnalytics(
                    shop_id=shop.id,
                    date=current_date,
                    total_customers=daily_volume,
                    completed_services=completed,
                    cancelled_services=daily_volume - completed,
                    total_revenue=round(rev, 2),
                    avg_wait_time_minutes=random.uniform(5, 35),
                    avg_service_time_minutes=random.uniform(20, 50),
                    peak_hour_start=random.randint(11, 15),
                    peak_hour_customers=int(daily_volume * 0.3)
                )
                db.add(daily_stat)
                
                day_count += 1
                current_date += timedelta(days=1)
                
                if day_count % 365 == 0:
                    print(f"      📅 Simulated year {day_count // 365} for {shop.name}...")
                    db.commit() # Commit yearly to avoid memory bloat
                    
            db.commit() # Final commit for shop
            print(f"    ✅ Completed {years} years for {shop.name}.")

        print(f"🎉 Historically simulated data for {len(shops)} shops successfully!")

    except Exception as e:
        print(f"❌ Simulation Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    simulate_historical_data()
