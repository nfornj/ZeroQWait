from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from db_interface import db_interface
from auth_utils import get_current_user
from analytics_processor import get_analytics_summary, get_peak_hours_analysis, AnalyticsProcessor
from scheduler import trigger_maintenance_now
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, date
import logging

# Setup logger
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/{shop_id}")
def get_shop_analytics(
    shop_id: int,
    days: int = 30,
    current_user: dict = Depends(get_current_user)
):
    # Verify shop ownership
    shop = db_interface.get_shop_by_id(shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    if shop["owner_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to view analytics for this shop")

    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Get all queues for the shop
    queues = db_interface.get_analytics_queues(shop_id)
    if not queues:
        # No queues, return empty analytics
        return {
            "period_days": days,
            "total_customers": 0,
            "avg_wait_minutes": 0,
            "avg_service_minutes": 0,
            "daily_stats": []
        }
    
    queue_ids = [q["id"] for q in queues]
    
    # Get completed items in date range
    completed_items = db_interface.get_analytics_items(queue_ids, start_date)

    # 1. Total Customers Served
    total_customers = len(completed_items)

    # 2. Average Wait Time (Check-in to Service Start)
    total_wait_seconds = 0
    wait_count = 0
    
    # 3. Average Service Time (Service Start to Completion)
    total_service_seconds = 0
    service_count = 0

    # 4. Customers Per Day & Revenue
    daily_counts = {}
    daily_revenue = {}
    total_revenue = 0.0

    for item in completed_items:
        # Wait Time
        service_started = item.get("service_started_at")
        checked_in = item.get("checked_in_at")
        if service_started and checked_in:
            try:
                service_started_dt = datetime.fromisoformat(service_started.replace("Z", "+00:00"))
                checked_in_dt = datetime.fromisoformat(checked_in.replace("Z", "+00:00"))
                wait_time = (service_started_dt - checked_in_dt).total_seconds()
                if wait_time > 0:
                    total_wait_seconds += wait_time
                    wait_count += 1
            except Exception:
                pass
        
        # Service Time
        completed = item.get("completed_at")
        if completed and service_started:
            try:
                completed_dt = datetime.fromisoformat(completed.replace("Z", "+00:00"))
                service_started_dt = datetime.fromisoformat(service_started.replace("Z", "+00:00"))
                service_time = (completed_dt - service_started_dt).total_seconds()
                if service_time > 0:
                    total_service_seconds += service_time
                    service_count += 1
            except Exception:
                pass
        
        # Daily Counts
        if completed:
            try:
                completed_dt = datetime.fromisoformat(completed.replace("Z", "+00:00"))
                date_str = completed_dt.strftime("%Y-%m-%d")
                daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
                
                # Revenue
                cost = float(item.get("service_cost") or 0.0)
                total_revenue += cost
                daily_revenue[date_str] = daily_revenue.get(date_str, 0.0) + cost
            except Exception:
                pass

    avg_wait_minutes = round(total_wait_seconds / wait_count / 60) if wait_count > 0 else 0
    avg_service_minutes = round(total_service_seconds / service_count / 60) if service_count > 0 else 0

    # Format daily counts for frontend
    # Fill in missing days with 0
    chart_data = []
    current = start_date
    while current <= end_date:
        date_str = current.strftime("%Y-%m-%d")
        chart_data.append({
            "date": date_str,
            "count": daily_counts.get(date_str, 0),
            "revenue": daily_revenue.get(date_str, 0.0)
        })
        current += timedelta(days=1)

    return {
        "period_days": days,
        "total_customers": total_customers,
        "total_revenue": total_revenue,
        "avg_wait_minutes": avg_wait_minutes,
        "avg_service_minutes": avg_service_minutes,
        "daily_stats": chart_data
    }


@router.get("/daily/{shop_id}")
def get_daily_analytics(
    shop_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get aggregated daily analytics from queue_analytics_daily table
    Much faster than calculating from raw queue_items
    """
    # Verify shop ownership
    # Verify shop ownership
    try:
        shop = db_interface.get_shop_by_id(shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        if shop["owner_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not authorized to view analytics for this shop")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    # Parse dates
    if end_date:
        end = date.fromisoformat(end_date)
    else:
        end = date.today()
    
    if start_date:
        start = date.fromisoformat(start_date)
    else:
        start = end - timedelta(days=30)
    
    # Get summary from analytics processor
    try:
        summary = get_analytics_summary(db, shop_id, start, end)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching analytics: {str(e)}")


@router.get("/peak-hours/{shop_id}")
def get_peak_hours(
    shop_id: int,
    days: int = 7,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get peak hours analysis for a shop
    Shows which hours of the day are busiest
    """
    # Verify shop ownership
    # Verify shop ownership
    try:
        shop = db_interface.get_shop_by_id(shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        if shop["owner_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not authorized to view analytics for this shop")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    try:
        analysis = get_peak_hours_analysis(db, shop_id, days)
        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing peak hours: {str(e)}")


@router.post("/maintenance/run")
async def run_maintenance(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually trigger analytics aggregation and archival
    Admin/testing endpoint
    """
    # For now, allow any authenticated user to trigger
    # In production, you may want to restrict this to admins only
    
    try:
        await trigger_maintenance_now()
        return {"status": "success", "message": "Maintenance tasks triggered"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running maintenance: {str(e)}")


@router.get("/archive/stats/{shop_id}")
def get_archive_stats(
    shop_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get statistics about archived queue items
    Shows how many items are in archive vs active table
    """
    # Verify shop ownership
    # Verify shop ownership
    try:
        shop = db_interface.get_shop_by_id(shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        if shop["owner_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not authorized to view analytics for this shop")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    try:
        from sqlalchemy import text
        
        # Count active items
        active_query = text("""
            SELECT COUNT(*) FROM queue_items qi
            JOIN queues q ON qi.queue_id = q.id
            WHERE q.shop_id = :shop_id
        """)
        active_count = db.execute(active_query, {"shop_id": shop_id}).scalar()
        
        # Count archived items
        archive_query = text("""
            SELECT COUNT(*) FROM queue_items_archive
            WHERE shop_id = :shop_id
        """)
        archive_count = db.execute(archive_query, {"shop_id": shop_id}).scalar()
        
        # Get oldest archived item
        oldest_query = text("""
            SELECT MIN(completed_at) FROM queue_items_archive
            WHERE shop_id = :shop_id
        """)
        oldest_date = db.execute(oldest_query, {"shop_id": shop_id}).scalar()
        
        return {
            "shop_id": shop_id,
            "active_items_count": active_count or 0,
            "archived_items_count": archive_count or 0,
            "total_items_count": (active_count or 0) + (archive_count or 0),
            "oldest_archived_date": oldest_date.isoformat() if oldest_date else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching archive stats: {str(e)}")


@router.get("/services/{shop_id}")
def get_service_popularity(
    shop_id: int,
    days: int = 30,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get service popularity based on notes field
    """
    # Verify shop ownership
    try:
        shop = db_interface.get_shop_by_id(shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        if shop["owner_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not authorized to view analytics for this shop")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Shop not found")

    try:
        from sqlalchemy import text
        
        start_date = date.today() - timedelta(days=days)
        
        # Simple grouping by notes
        # In a real app, you'd likely normalize this or use a proper Service model
        query = text("""
            SELECT 
                qi.notes as service_name,
                COUNT(*) as count
            FROM queue_items qi
            JOIN queues q ON qi.queue_id = q.id
            WHERE q.shop_id = :shop_id
              AND qi.created_at >= :start_date
              AND qi.notes IS NOT NULL
            GROUP BY qi.notes
            ORDER BY count DESC
            LIMIT 10
        """) # Note: using created_at in query but python uses checked_in_at typically. 
             # QueueItem doesn't have created_at in models.py shown earlier, checking models.py...
             # QueueItem has checked_in_at. Let's use that.
        
        # Re-verify schema... QueueItem has checked_in_at.
        
        query = text("""
            SELECT 
                qi.notes as service_name,
                COUNT(*) as count
            FROM queue_items qi
            JOIN queues q ON qi.queue_id = q.id
            WHERE q.shop_id = :shop_id
              AND qi.checked_in_at >= :start_date
              AND qi.notes IS NOT NULL
            GROUP BY qi.notes
            ORDER BY count DESC
            LIMIT 10
        """)

        results = db.execute(query, {"shop_id": shop_id, "start_date": start_date}).fetchall()
        
        return [
            {"name": row[0], "value": row[1]} 
            for row in results
        ]
        
    except Exception as e:
        logger.error(f"Error analyzing services: {e}")
        # Return empty list on error to gracefully degrade
        return []

@router.get("/revenue/monthly-by-service/{shop_id}")
def get_monthly_revenue_by_service(
    shop_id: int,
    months: int = 6,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get monthly revenue broken down by service for stacked bar chart
    """
    # Verify shop ownership
    try:
        shop = db_interface.get_shop_by_id(shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        if shop["owner_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not authorized to view analytics for this shop")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Shop not found")

    try:
        from sqlalchemy import text
        from datetime import date
        from dateutil.relativedelta import relativedelta

        end_date = date.today()
        # Go back 'months' months, start from the 1st
        start_date = (end_date - relativedelta(months=months-1)).replace(day=1)
        
        # Query to get sum of cost grouped by month and service name
        # Using to_char for month formatting (Postgres specific)
        query = text("""
            SELECT 
                to_char(qi.completed_at, 'Mon') as month_name,
                EXTRACT(MONTH FROM qi.completed_at) as month_num,
                EXTRACT(YEAR FROM qi.completed_at) as year_num,
                COALESCE(s.name, 'Other') as service_name,
                SUM(qi.service_cost) as revenue
            FROM queue_items qi
            JOIN queues q ON qi.queue_id = q.id
            LEFT JOIN shop_services s ON qi.service_id = s.id
            WHERE q.shop_id = :shop_id
              AND qi.completed_at >= :start_date
              AND qi.status = 'COMPLETED'
            GROUP BY 1, 2, 3, 4
            ORDER BY year_num, month_num
        """)

        results = db.execute(query, {"shop_id": shop_id, "start_date": start_date}).fetchall()
        
        # Process results into chart format
        # structure: {month: "Jan", "Haircut": 100, "Shave": 50, ...}
        
        # Initialize map with all months in range to ensure continuity
        month_map = {}
        curr = start_date
        while curr <= end_date:
            key = curr.strftime("%b") # Jan, Feb...
            month_map[key] = {"month": key}
            # Increment month
            curr += relativedelta(months=1)
            
        # Fill data
        all_services = set()
        for row in results:
            month_name = row[0]
            service_name = row[3]
            revenue = float(row[4])
            
            if month_name in month_map:
                month_map[month_name][service_name] = revenue
                all_services.add(service_name)
                
        # Convert to list ensuring order based on original time range
        final_data = []
        curr = start_date
        while curr <= end_date:
            key = curr.strftime("%b")
            if key in month_map:
                # Ensure all services serve as keys (default 0) for stacked chart safety
                item = month_map[key]
                for s in all_services:
                    if s not in item:
                        item[s] = 0
                final_data.append(item)
            curr += relativedelta(months=1)
            
        return final_data

    except Exception as e:
        logger.error(f"Error fetching monthly revenue: {e}")
        return []
