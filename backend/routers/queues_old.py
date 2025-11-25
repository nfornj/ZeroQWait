from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from database import get_db
from models import (
    Queue as QueueModel, 
    QueueItem as QueueItemModel, 
    Shop as ShopModel,
    User as UserModel,
    QueueStatus
)
from schemas import Queue, QueueItem, QueueItemCreate, QueueCreate
from auth_utils import get_current_user
from datetime import datetime

router = APIRouter(prefix="/queues", tags=["queues"])

@router.get("/shop/{shop_id}/active", response_model=Queue)
def get_active_queue(shop_id: int, db: Session = Depends(get_db)):
    """Get the active queue for a shop"""
    queue = db.query(QueueModel).filter(
        QueueModel.shop_id == shop_id,
        QueueModel.is_active == True
    ).first()
    
    if not queue:
        # Create a new queue if none exists
        shop = db.query(ShopModel).filter(ShopModel.id == shop_id).first()
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        queue = QueueModel(shop_id=shop_id, date=datetime.utcnow(), is_active=True)
        db.add(queue)
        db.commit()
        db.refresh(queue)
    
    return queue

@router.get("/shop/{shop_id}/all", response_model=List[Queue])
def get_all_shop_queues(
    shop_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Get all queues for a shop (Shop Owner only)"""
    shop = db.query(ShopModel).filter(ShopModel.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    if shop.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only shop owner can view queues"
        )
    
    queues = db.query(QueueModel).filter(
        QueueModel.shop_id == shop_id
    ).order_by(QueueModel.date.desc()).all()
    
    return queues

@router.post("/shop/{shop_id}", response_model=Queue)
def create_queue(
    shop_id: int,
    queue_create: QueueCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Create a new queue for a shop (Shop Owner only)"""
    shop = db.query(ShopModel).filter(ShopModel.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    if shop.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only shop owner can create queues"
        )
    
    # Check queue limit based on subscription tier
    from tier_limits import TIER_LIMITS
    current_queue_count = db.query(QueueModel).filter(
        QueueModel.shop_id == shop_id,
        QueueModel.is_active == True
    ).count()
    
    tier_limit = TIER_LIMITS[current_user.subscription_tier]["max_queues_per_shop"]
    if current_queue_count >= tier_limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Queue limit reached for {current_user.subscription_tier.value} tier. Maximum: {tier_limit} active queue(s). Upgrade to Premium for up to 5 queues."
        )
        
    queue = QueueModel(
        shop_id=shop_id, 
        name=queue_create.name,
        date=datetime.utcnow(), 
        is_active=True
    )
    db.add(queue)
    db.commit()
    db.refresh(queue)
    return queue

@router.post("/shop/{shop_id}/join", response_model=QueueItem)
def join_queue(
    shop_id: int,
    queue_item: QueueItemCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(lambda: None)
):
    """Join a shop's queue (authenticated or guest)"""
    # Get shop and verify it exists
    shop = db.query(ShopModel).filter(ShopModel.id == shop_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    # Get shop owner to check their subscription tier
    owner = db.query(UserModel).filter(UserModel.id == shop.owner_id).first()
    
    # Get or create active queue
    queue = db.query(QueueModel).filter(
        QueueModel.shop_id == shop_id,
        QueueModel.is_active == True
    ).first()
    
    if not queue:
        queue = QueueModel(shop_id=shop_id, date=datetime.utcnow(), is_active=True)
        db.add(queue)
        db.commit()
        db.refresh(queue)
    
    # Check queue size limit based on shop owner's subscription tier
    from tier_limits import TIER_LIMITS
    current_queue_size = db.query(QueueItemModel).filter(
        QueueItemModel.queue_id == queue.id,
        QueueItemModel.status.in_([QueueStatus.WAITING, QueueStatus.BEING_SERVED])
    ).count()
    
    tier_limit = TIER_LIMITS[owner.subscription_tier]["max_queue_size"]
    if tier_limit is not None and current_queue_size >= tier_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Queue is full. Maximum capacity for {owner.subscription_tier.value} tier: {tier_limit} customers. Please try again later or contact the shop to upgrade their plan."
        )
    
    # Calculate position (last position + 1)
    max_position = db.query(func.max(QueueItemModel.position)).filter(
        QueueItemModel.queue_id == queue.id
    ).scalar()
    position = (max_position or 0) + 1
    
    # Create queue item
    user_id = current_user.id if current_user else None
    db_queue_item = QueueItemModel(
        **queue_item.dict(),
        queue_id=queue.id,
        user_id=user_id,
        position=position
    )
    db.add(db_queue_item)
    db.commit()
    db.refresh(db_queue_item)
    
    return db_queue_item

@router.get("/{queue_id}/items", response_model=List[QueueItem])
def get_queue_items(queue_id: int, db: Session = Depends(get_db)):
    """Get all items in a queue"""
    items = db.query(QueueItemModel).filter(
        QueueItemModel.queue_id == queue_id
    ).order_by(QueueItemModel.position).all()
    return items

@router.patch("/items/{item_id}/status")
def update_queue_item_status(
    item_id: int,
    new_status: QueueStatus,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Update queue item status (Shop Owner only)"""
    item = db.query(QueueItemModel).filter(QueueItemModel.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    
    # Verify user owns the shop
    queue = db.query(QueueModel).filter(QueueModel.id == item.queue_id).first()
    shop = db.query(ShopModel).filter(ShopModel.id == queue.shop_id).first()
    
    if shop.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this queue"
        )
    
    item.status = new_status
    if new_status == QueueStatus.BEING_SERVED:
        item.service_started_at = datetime.utcnow()
    elif new_status in [QueueStatus.COMPLETED, QueueStatus.CANCELLED]:
        item.completed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(item)
    return item

@router.post("/{queue_id}/call-next", response_model=QueueItem)
def call_next_customer(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Call the next customer in line (Shop Owner only)"""
    queue = db.query(QueueModel).filter(QueueModel.id == queue_id).first()
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")
    
    shop = db.query(ShopModel).filter(ShopModel.id == queue.shop_id).first()
    if shop.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage this queue"
        )
    
    # Find next waiting customer
    next_item = db.query(QueueItemModel).filter(
        QueueItemModel.queue_id == queue_id,
        QueueItemModel.status == QueueStatus.WAITING
    ).order_by(QueueItemModel.position).first()
    
    if not next_item:
        raise HTTPException(status_code=404, detail="No customers waiting")
    
    next_item.status = QueueStatus.BEING_SERVED
    next_item.service_started_at = datetime.utcnow()
    db.commit()
    db.refresh(next_item)
    
    return next_item

@router.get("/items/{item_id}/estimate")
def get_wait_estimate(item_id: int, db: Session = Depends(get_db)):
    """Get estimated wait time for a queue item"""
    item = db.query(QueueItemModel).filter(QueueItemModel.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    
    # Count how many people are ahead
    ahead = db.query(QueueItemModel).filter(
        QueueItemModel.queue_id == item.queue_id,
        QueueItemModel.position < item.position,
        QueueItemModel.status.in_([QueueStatus.WAITING, QueueStatus.BEING_SERVED])
    ).count()
    
    # Get shop's average service time
    queue = db.query(QueueModel).filter(QueueModel.id == item.queue_id).first()
    shop = db.query(ShopModel).filter(ShopModel.id == queue.shop_id).first()
    
    estimated_minutes = ahead * shop.average_service_time
    
    return {
        "item_id": item_id,
        "position": item.position,
        "people_ahead": ahead,
        "estimated_wait_minutes": estimated_minutes,
        "status": item.status
    }
