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
        if target_date is None:
            target_date = date.today() - timedelta(days=1)
        
        try:
            logger.info(f"Aggregating analytics for {target_date}")
            
            # Call PostgreSQL function to aggregate data
            result = self.db.execute(
                text("SELECT aggregate_daily_analytics(:target_date)"),
                {"target_date": target_date}
            )
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
                SUM(total_completed) as total_completed,
                SUM(total_cancelled) as total_cancelled,
                AVG(avg_wait_time_minutes) as avg_wait_time,
                AVG(avg_service_time_minutes) as avg_service_time,
                COUNT(*) as days_count
            FROM queue_analytics_daily
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
                "days_count": result[5] or 0
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
                peak_hour,
                customers_by_hour
            FROM queue_analytics_daily
            WHERE shop_id = :shop_id
              AND date >= :start_date
            ORDER BY date DESC
        """)
        
        start_date = date.today() - timedelta(days=days)
        results = db.execute(
            query,
            {"shop_id": shop_id, "start_date": start_date}
        ).fetchall()
        
        # Aggregate hourly data across all days
        hourly_totals = {}
        for row in results:
            customers_by_hour = row[2]  # JSONB field
            if customers_by_hour:
                for hour, count in customers_by_hour.items():
                    hourly_totals[int(hour)] = hourly_totals.get(int(hour), 0) + count
        
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
