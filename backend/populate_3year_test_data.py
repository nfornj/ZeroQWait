#!/usr/bin/env python3
"""
Populate 3 years of realistic historical data for shop 41 (test account).
Includes:
- Daily analytics with seasonality, growth patterns, and weekend boosts
- Raw queue items for last 90 days
- Realistic customer data and service distributions
"""

import random
from datetime import datetime, date, timedelta
from database import SessionLocal
from models import Shop, Queue, QueueItem, DailyAnalytics, QueueStatus, ShopService

def populate_shop_41_data(shop_id=41, years=3):
    """Generate 3 years of realistic historical data for shop 41"""
    db = SessionLocal()
    try:
        # Verify shop exists
        shop = db.query(Shop).filter(Shop.id == shop_id).first()
        if not shop:
            print(f"❌ Shop {shop_id} not found")
            return

        print(f"🚀 Generating {years} years of realistic data for: {shop.name} (ID: {shop_id})")
        
        # Get or create main queue
        queue = db.query(Queue).filter(Queue.shop_id == shop_id).first()
        if not queue:
            queue = Queue(shop_id=shop_id, name="Main Queue")
            db.add(queue)
            db.flush()
            print(f"   📋 Created main queue for shop")
        
        # Get services for this shop
        services = db.query(ShopService).filter(ShopService.shop_id == shop_id).all()
        if not services:
            print(f"   ⚠️  No services found for shop {shop_id}, creating defaults...")
            # Create default services
            default_services = [
                ShopService(shop_id=shop_id, name="Basic Service", cost=25.00, duration_minutes=30),
                ShopService(shop_id=shop_id, name="Premium Service", cost=50.00, duration_minutes=60),
                ShopService(shop_id=shop_id, name="Express Service", cost=15.00, duration_minutes=15),
            ]
            db.add_all(default_services)
            db.flush()
            services = default_services
            print(f"   ✅ Created 3 default services")

        # Date boundaries
        end_date = date.today()
        start_date = end_date - timedelta(days=years * 365)
        raw_boundary_date = end_date - timedelta(days=90)  # Last 90 days get raw items
        
        print(f"   📅 Date range: {start_date} to {end_date}")
        print(f"   🎯 Raw queue items: {raw_boundary_date} to {end_date}")
        
        # Track progress
        day_count = 0
        total_customers = 0
        total_revenue = 0.0
        
        current_date = start_date
        
        while current_date <= end_date:
            # Calculate growth factor: starts at 40% grows to 100%
            days_since_start = (current_date - start_date).days
            total_days = (end_date - start_date).days
            progress = days_since_start / total_days if total_days > 0 else 1.0
            growth_factor = 0.4 + (progress * 0.6)  # 40% → 100%
            
            # Seasonality (peaks in summer and winter)
            month = current_date.month
            seasonality = 1.0
            if month in [7, 8]:  # July, August (summer)
                seasonality = 1.35
            elif month == 12:  # December (holidays)
                seasonality = 1.25
            elif month in [1, 6]:  # January, June (modest boost)
                seasonality = 1.1
            else:
                seasonality = 0.95
            
            # Weekend boost
            is_weekend = current_date.weekday() >= 5
            weekend_factor = 1.5 if is_weekend else 1.0
            
            # Calculate daily volume
            base_customers = random.randint(8, 20)
            daily_volume = int(base_customers * growth_factor * seasonality * weekend_factor)
            daily_volume = max(5, daily_volume)  # At least 5 customers
            
            if current_date > raw_boundary_date:
                # ========== GENERATE RAW QUEUE ITEMS (Last 90 days) ==========
                for i in range(daily_volume):
                    status = QueueStatus.COMPLETED if random.random() > 0.08 else QueueStatus.CANCELLED
                    service = random.choice(services)
                    
                    # Timestamps spread over business hours (9 AM - 6 PM)
                    check_in = datetime.combine(current_date, datetime.min.time()) + \
                               timedelta(hours=random.randint(9, 17), minutes=random.randint(0, 59))
                    
                    wait_minutes = random.randint(2, 40)
                    service_minutes = random.randint(15, 60)
                    
                    item = QueueItem(
                        queue_id=queue.id,
                        customer_name=f"Customer-{random.randint(1000, 9999)}",
                        customer_phone=f"555-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
                        position=i + 1,
                        status=status,
                        service_id=service.id,
                        service_cost=service.cost,
                        checked_in_at=check_in,
                        service_started_at=check_in + timedelta(minutes=wait_minutes) if status == QueueStatus.COMPLETED else None,
                        completed_at=check_in + timedelta(minutes=wait_minutes + service_minutes) if status == QueueStatus.COMPLETED else None,
                        notes=service.name
                    )
                    db.add(item)
            
            # ========== ALWAYS GENERATE DAILY ANALYTICS (Full 3 years) ==========
            # This ensures dashboards/reports are fast and complete
            completed_count = int(daily_volume * (0.92 if is_weekend else 0.95))
            cancelled_count = daily_volume - completed_count
            
            # Calculate realistic revenue
            daily_revenue = 0.0
            for _ in range(completed_count):
                service = random.choice(services)
                # Add 10-20% cost jitter
                cost_with_jitter = service.cost * (0.9 + (0.2 * random.random()))
                daily_revenue += cost_with_jitter
            
            daily_revenue = round(daily_revenue, 2)
            
            analytics = DailyAnalytics(
                shop_id=shop_id,
                date=current_date,
                total_customers=daily_volume,
                completed_services=completed_count,
                cancelled_services=cancelled_count,
                total_revenue=daily_revenue,
                avg_wait_time_minutes=round(random.uniform(5, 35), 1),
                avg_service_time_minutes=round(random.uniform(20, 50), 1),
                peak_hour_start=random.randint(11, 15),
                peak_hour_customers=int(daily_volume * (0.35 if is_weekend else 0.25))
            )
            db.add(analytics)
            
            total_customers += daily_volume
            total_revenue += daily_revenue
            day_count += 1
            
            # Progress indicator
            if day_count % 365 == 0:
                years_completed = day_count // 365
                print(f"   📊 Year {years_completed}: {daily_volume} customers, ${total_revenue:,.2f} revenue")
                db.commit()  # Commit yearly to manage memory
            
            current_date += timedelta(days=1)
        
        # Final commit
        db.commit()
        
        # Summary statistics
        print(f"\n✅ Data generation complete!")
        print(f"   📈 Total days: {day_count}")
        print(f"   👥 Total customers: {total_customers:,}")
        print(f"   💰 Total revenue: ${total_revenue:,.2f}")
        print(f"   📊 Avg daily customers: {total_customers // day_count}")
        print(f"   📊 Avg daily revenue: ${total_revenue / day_count:,.2f}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    populate_shop_41_data()
