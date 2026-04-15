import sys
import random
from datetime import datetime, timedelta
import logging
from sqlalchemy import text
from database import SessionLocal
from models import User, Shop, Queue, QueueItem, UserRole, QueueStatus, SubscriptionTier
from shared.auth_utils import get_password_hash
from analytics_processor import AnalyticsProcessor

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICES = [
    "Haircut", "Beard Trim", "Shave", "Hair Coloring", "Manicure", "Pedicure", "Facial"
]

def create_historical_data(shop_id, days=30):
    db = SessionLocal()
    processor = AnalyticsProcessor(db)
    
    try:
        shop = db.query(Shop).filter(Shop.id == shop_id).first()
        if not shop:
            logger.error(f"Shop {shop_id} not found")
            return

        logger.info(f"Generating data for shop: {shop.name} ({shop_id})")

        # Create a historical queue for data attachment (if not exists)
        queue = db.query(Queue).filter(Queue.shop_id == shop_id).first()
        if not queue:
            queue = Queue(shop_id=shop.id, name="Main Queue", date=datetime.utcnow())
            db.add(queue)
            db.commit()
            db.refresh(queue)

        # Generate data for past 'days'
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days)
        
        current_date = start_date
        total_items = 0

        while current_date <= end_date:
            # Random number of visitors (10 to 40)
            daily_visits = random.randint(10, 40)
            
            # Simulated updated_at timestamp base (9 AM)
            day_start = datetime.combine(current_date, datetime.min.time()) + timedelta(hours=9)

            for i in range(daily_visits):
                # Random service
                service = random.choice(SERVICES)
                
                # Random times
                check_in = day_start + timedelta(minutes=random.randint(0, 480)) # Spread over 8 hours
                wait_time = random.randint(5, 45)
                service_duration = random.randint(15, 60)
                
                service_start = check_in + timedelta(minutes=wait_time)
                completed_at = service_start + timedelta(minutes=service_duration)

                # 90% Completed, 10% Cancelled
                status = QueueStatus.COMPLETED if random.random() > 0.1 else QueueStatus.CANCELLED
                
                item = QueueItem(
                    queue_id=queue.id,
                    customer_name=f"Customer {random.randint(1000, 9999)}",
                    position=i+1,
                    status=status,
                    notes=service,
                    checked_in_at=check_in,
                    service_started_at=service_start if status == QueueStatus.COMPLETED else None,
                    completed_at=completed_at if status == QueueStatus.COMPLETED else None
                )
                db.add(item)
                total_items += 1

            db.commit()
            
            # Aggregate analytics for this day
            processor.aggregate_daily_analytics(current_date)
            logger.info(f"Processed {daily_visits} visits for {current_date}")
            
            current_date += timedelta(days=1)

        logger.info(f"Successfully generated {total_items} historical records for Shop {shop_id}")
        return True

    except Exception as e:
        logger.error(f"Error generating data: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    from create_sample_data import create_sample_data
    # Run sample data creation to ensure base users exist
    create_sample_data()
    
    db = SessionLocal()
    # Find any shop owned by a shop_owner
    shops = db.query(Shop).all()
    
    if not shops:
        logger.warning("No shops found. Creating a default shop...")
        # Create a shop manually if create_sample_data skipped it
        owner = db.query(User).filter(User.role == UserRole.SHOP_OWNER).first()
        if not owner:
            logger.error("No shop owner found. Please reset database or check create_sample_data.")
        else:
            shop1 = Shop(
                owner_id=owner.id,
                name="Downtown Barbershop",
                description="Professional haircuts",
                shop_type="barbershop",
                address="123 Main St",
                city="San Francisco",
                state="CA",
                zip_code="94103",
                country="US",
                phone="555-0101",
                slug="downtown-barbershop",
                is_active=True
            )
            db.add(shop1)
            db.commit()
            db.refresh(shop1)
            shops = [shop1]

    if shops:
        for shop in shops:
            logger.info(f"Populating data for shop: {shop.name} ({shop.id})")
            create_historical_data(shop.id, days=30)
    else:
        logger.error("Could not find or create any shops.")
        
    db.close()
