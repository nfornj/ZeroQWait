from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, case
from typing import List, Dict, Any
from datetime import datetime, timedelta
import logging

from database import get_db
from shared.auth_utils import get_current_user
from modules.auth.models import User, UserRole
from modules.shops.models import Shop, DailyAnalytics
from modules.queues.models import QueueItem, QueueStatus, Queue
from redis_client import redis_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

def check_super_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can access this resource"
        )
    return current_user

@router.get("/dashboard-stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(check_super_admin)
):
    """Aggregate stats for the master dashboard"""
    # 1. Try Cache
    cache_key = "admin:dashboard:stats"
    cached = redis_client.get(cache_key)
    if cached:
        return cached

    # 2. Query DB
    total_shops = db.query(Shop).count()
    active_shops = db.query(Shop).filter(Shop.is_active == True).count()
    total_users = db.query(User).count()
    
    # Real-time stats (last 24 hours)
    last_24h = datetime.utcnow() - timedelta(hours=24)
    active_customers = db.query(QueueItem).filter(
        QueueItem.status == QueueStatus.WAITING,
        QueueItem.checked_in_at >= last_24h
    ).count()
    
    completed_today = db.query(QueueItem).filter(
        QueueItem.status == QueueStatus.COMPLETED,
        QueueItem.completed_at >= last_24h
    ).count()

    stats = {
        "total_shops": total_shops,
        "active_shops": active_shops,
        "total_users": total_users,
        "real_time": {
            "active_customers": active_customers,
            "completed_today": completed_today
        }
    }
    
    # 3. Set Cache (5 seconds TTL for near real-time)
    redis_client.set(cache_key, stats, ttl=5)
    return stats

@router.get("/shops-status")
def get_shops_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(check_super_admin)
):
    """Live status of all shops"""
    # 1. Try Cache
    t0 = datetime.utcnow()
    cache_key = "admin:shops:status"
    cached = redis_client.get(cache_key)
    if cached:
        logger.info(f"Cache HIT for shops-status. Time: {(datetime.utcnow() - t0).total_seconds()}s")
        return cached

    # 2. Optimized Query (Avoid N+1)
    t1 = datetime.utcnow()
    shops = db.query(Shop).all()
    t2 = datetime.utcnow()
    logger.info(f"DB Fetch Shops: {(t2 - t1).total_seconds()}s")
    
    # Bulk fetch waiting counts
    waiting_counts = db.query(
        Queue.shop_id, 
        func.count(QueueItem.id)
    ).join(QueueItem).filter(
        QueueItem.status == QueueStatus.WAITING
    ).group_by(Queue.shop_id).all()
    
    waiting_map = {shop_id: count for shop_id, count in waiting_counts}
    t3 = datetime.utcnow()
    logger.info(f"DB Waiting Counts: {(t3 - t2).total_seconds()}s")

    # Bulk fetch last activity (optimized: limit to last 24 hours to use index)
    last_24h = datetime.utcnow() - timedelta(days=1)
    last_activities = db.query(
        Queue.shop_id, 
        func.max(QueueItem.checked_in_at)
    ).join(QueueItem).filter(
        QueueItem.checked_in_at >= last_24h
    ).group_by(Queue.shop_id).all()
    
    activity_map = {shop_id: dt.isoformat() if dt else None for shop_id, dt in last_activities}
    t4 = datetime.utcnow()
    logger.info(f"DB Last Activity: {(t4 - t3).total_seconds()}s")

    results = []
    
    for shop in shops:
        results.append({
            "id": shop.id,
            "name": shop.name,
            "slug": shop.slug,
            "is_active": shop.is_active,
            "waiting_count": waiting_map.get(shop.id, 0),
            "last_activity": activity_map.get(shop.id)
        })
        
    # 3. Set Cache
    redis_client.set(cache_key, results, ttl=5)
    t5 = datetime.utcnow()
    logger.info(f"Total Time: {(t5 - t0).total_seconds()}s")
    
    return results
