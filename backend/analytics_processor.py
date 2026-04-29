"""
Analytics Processor
Handles daily analytics aggregation and queue item archival
"""
from datetime import date, datetime, timedelta
from typing import Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


class AnalyticsProcessor:
    """Process queue analytics and archival tasks"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def aggregate_daily_analytics(self, target_date: Optional[date] = None) -> bool:
        """
        Aggregate daily analytics for a specific date
        Default: yesterday's data
        
        Returns: True if successful, False otherwise
        """
        from models import QueueItem, DailyAnalytics, Queue, QueueStatus, Shop
        from sqlalchemy import func, extract
        
        if target_date is None:
            target_date = date.today() - timedelta(days=1)
        
        try:
            logger.info(f"Aggregating analytics for {target_date}")
            
            # Find all shops
            shops = self.db.query(Shop.id).all()
            
            for (shop_id,) in shops:
                # Get items for this shop on this date
                # Note: We need to filter by checked_in_at date
                items = self.db.query(QueueItem).join(Queue).filter(
                    Queue.shop_id == shop_id,
                    func.date(QueueItem.checked_in_at) == target_date
                ).all()
                
                if not items:
                    continue
                    
                total_customers = len(items)
                completed_items = [i for i in items if i.status == QueueStatus.COMPLETED and i.service_started_at and i.completed_at]
                completed_count = len(completed_items)
                cancelled_count = len([i for i in items if i.status == QueueStatus.CANCELLED])
                
                # Calculate times & revenue
                total_wait_sec = 0
                total_service_sec = 0
                total_revenue = sum(item.service_cost or 0.0 for item in completed_items)
                
                req_hours = {} # For peak hour
                
                for item in completed_items:
                    # Wait time
                    if item.checked_in_at and item.service_started_at:
                        wait = (item.service_started_at - item.checked_in_at).total_seconds()
                        total_wait_sec += max(0, wait)
                    
                    # Service time
                    if item.service_started_at and item.completed_at:
                        service = (item.completed_at - item.service_started_at).total_seconds()
                        total_service_sec += max(0, service)
                        
                    # Peak hour tracking (based on check-in)
                    hour = item.checked_in_at.hour
                    req_hours[hour] = req_hours.get(hour, 0) + 1

                avg_wait_min = (total_wait_sec / completed_count / 60) if completed_count > 0 else 0
                avg_service_min = (total_service_sec / completed_count / 60) if completed_count > 0 else 0
                
                peak_hour = max(req_hours, key=req_hours.get) if req_hours else None
                peak_count = req_hours[peak_hour] if peak_hour is not None else 0
                
                # Upsert DailyAnalytics
                existing = self.db.query(DailyAnalytics).filter(
                    DailyAnalytics.shop_id == shop_id,
                    func.date(DailyAnalytics.date) == target_date
                ).first()
                
                if existing:
                    existing.total_customers = total_customers
                    existing.completed_services = completed_count
                    existing.cancelled_services = cancelled_count
                    existing.avg_wait_time_minutes = avg_wait_min
                    existing.avg_service_time_minutes = avg_service_min
                    existing.peak_hour_start = peak_hour
                    existing.peak_hour_customers = peak_count
                    existing.total_revenue = total_revenue
                else:
                    daily = DailyAnalytics(
                        shop_id=shop_id,
                        date=target_date,
                        total_customers=total_customers,
                        completed_services=completed_count,
                        cancelled_services=cancelled_count,
                        avg_wait_time_minutes=avg_wait_min,
                        avg_service_time_minutes=avg_service_min,
                        peak_hour_start=peak_hour,
                        peak_hour_customers=peak_count,
                        total_revenue=total_revenue
                    )
                    self.db.add(daily)
            
            self.db.commit()
            logger.info(f"Successfully aggregated analytics for {target_date}")
            return True
            
        except Exception as e:
            logger.error(f"Error aggregating analytics for {target_date}: {e}")
            self.db.rollback()
            return False
    
    def archive_old_queue_items(self, days_old: int = 7) -> int:
        """
        Archive queue items older than specified days
        
        Args:
            days_old: Number of days to keep in main queue_items table
            
        Returns: Number of items archived
        """
        try:
            logger.info(f"Archiving queue items older than {days_old} days")
            
            # Call PostgreSQL function to archive old items
            result = self.db.execute(
                text("SELECT archive_old_queue_items(:days_old)"),
                {"days_old": days_old}
            )
            archived_count = result.scalar()
            self.db.commit()
            
            logger.info(f"Successfully archived {archived_count} queue items")
            return archived_count
            
        except Exception as e:
            logger.error(f"Error archiving queue items: {e}")
            self.db.rollback()
            return 0
    
    def run_daily_maintenance(self) -> Dict[str, any]:
        """
        Run all daily maintenance tasks
        Should be scheduled to run once daily (e.g., at midnight)
        
        Returns: Status dictionary with results
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "analytics_success": False,
            "archive_success": False,
            "archived_count": 0
        }
        
        try:
            # 1. Aggregate yesterday's analytics
            results["analytics_success"] = self.aggregate_daily_analytics()
            
            # 2. Archive old queue items (7 days old)
            archived_count = self.archive_old_queue_items(days_old=7)
            results["archive_success"] = archived_count >= 0
            results["archived_count"] = archived_count
            
            logger.info(f"Daily maintenance completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error during daily maintenance: {e}")
            return results


def get_analytics_summary(db: Session, shop_id: int, start_date: date, end_date: date) -> Dict:
    """
    Get analytics summary for a shop within date range
    
    Args:
        db: Database session
        shop_id: Shop ID
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        
    Returns: Analytics summary dictionary
    """
    try:
        query = text("""
            SELECT 
                SUM(total_customers) as total_customers,
                SUM(completed_services) as total_completed,
                SUM(cancelled_services) as total_cancelled,
                AVG(avg_wait_time_minutes) as avg_wait_time,
                AVG(avg_service_time_minutes) as avg_service_time,
                SUM(total_revenue) as total_revenue,
                COUNT(*) as days_count
            FROM daily_analytics
            WHERE shop_id = :shop_id
              AND date >= :start_date
              AND date <= :end_date
        """)
        
        result = db.execute(
            query,
            {"shop_id": shop_id, "start_date": start_date, "end_date": end_date}
        ).fetchone()
        
        if result:
            return {
                "shop_id": shop_id,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_customers": result[0] or 0,
                "total_completed": result[1] or 0,
                "total_cancelled": result[2] or 0,
                "avg_wait_time_minutes": round(result[3] or 0, 2),
                "avg_service_time_minutes": round(result[4] or 0, 2),
                "total_revenue": round(result[5] or 0.0, 2),
                "days_count": result[6] or 0
            }
        
        return {
            "shop_id": shop_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_customers": 0,
            "total_completed": 0,
            "total_cancelled": 0,
            "avg_wait_time_minutes": 0,
            "avg_service_time_minutes": 0,
            "days_count": 0
        }
        
    except Exception as e:
        logger.error(f"Error getting analytics summary: {e}")
        raise


def get_peak_hours_analysis(db: Session, shop_id: int, days: int = 7) -> Dict:
    """
    Analyze peak hours for a shop over the last N days
    
    Args:
        db: Database session
        shop_id: Shop ID
        days: Number of days to analyze (default: 7)
        
    Returns: Peak hours analysis
    """
    try:
        query = text("""
            SELECT 
                date,
                peak_hour_start,
                peak_hour_customers
            FROM daily_analytics
            WHERE shop_id = :shop_id
              AND date >= :start_date
            ORDER BY date DESC
        """)
        
        start_date = date.today() - timedelta(days=days)
        results = db.execute(
            query,
            {"shop_id": shop_id, "start_date": start_date}
        ).fetchall()
        
        # Aggregate peak hour data across all days
        hourly_totals = {}
        for row in results:
            peak_hour_start = row[1]
            peak_customers = row[2] or 0
            if peak_hour_start is not None:
                hourly_totals[int(peak_hour_start)] = hourly_totals.get(int(peak_hour_start), 0) + peak_customers
        
        # Find overall peak hour
        peak_hour = max(hourly_totals, key=hourly_totals.get) if hourly_totals else None
        
        return {
            "shop_id": shop_id,
            "period_days": days,
            "peak_hour": peak_hour,
            "hourly_distribution": {str(h): hourly_totals.get(h, 0) for h in range(24)},
            "total_customers": sum(hourly_totals.values())
        }
        
    except Exception as e:
        logger.error(f"Error analyzing peak hours: {e}")
        raise
