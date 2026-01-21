from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import Shop, Queue, QueueItem, QueueStatus, User, UserRole
from analytics_processor import AnalyticsProcessor
from datetime import datetime, timedelta
import random
import logging
from auth_utils import get_current_user
from permissions import check_shop_access

router = APIRouter()
logger = logging.getLogger(__name__)

SERVICES = [
    "Haircut", "Beard Trim", "Shave", "Hair Coloring", "Manicure", "Pedicure", "Facial"
]

@router.post("/shops/{shop_id}/generate-sample-data")
def generate_shop_sample_data(
    shop_id: int,
    days: int = 30,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate sample historical data for a shop (Owner only)"""
    try:
        # Verify access (Owner only)
        check_shop_access(shop_id, current_user, require_owner=True)
        
        shop = db.query(Shop).filter(Shop.id == shop_id).first()
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
            
        logger.info(f"Generating data for shop: {shop.name} ({shop_id})")
        processor = AnalyticsProcessor(db)

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
                    created_at=check_in, # Using created_at as check-in approximation if needed, or rely on timestamps
                    # models.py QueueItem has created_at default=now. We need to override it if we want distinct history.
                    # Since sqlalchemy defaults, we check if we can set them.
                    service_started_at=service_start if status == QueueStatus.COMPLETED else None,
                    completed_at=completed_at if status == QueueStatus.COMPLETED else None
                )
                # Hack to force created_at (if model allows) - usually SQLAlchemy allows overriding
                item.created_at = check_in 
                
                db.add(item)
                total_items += 1

            db.commit()
            
            # Aggregate analytics for this day
            processor.aggregate_daily_analytics(current_date)
            
            current_date += timedelta(days=1)
            
        return {"message": f"Successfully generated {total_items} historical records", "days": days}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating data: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to generate data: {str(e)}")
