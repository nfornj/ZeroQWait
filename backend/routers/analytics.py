from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from db_interface import db_interface
from shared.auth_utils import get_current_user
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
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    # Verify shop ownership
    shop = db_interface.get_shop_by_id(shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    if shop["owner_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to view analytics for this shop")

    # Calculate date range
    if start_date and end_date:
        current_end = datetime.fromisoformat(end_date.replace("Z", "+00:00")).replace(tzinfo=None) if "T" in end_date else datetime.strptime(end_date, "%Y-%m-%d")
        current_start = datetime.fromisoformat(start_date.replace("Z", "+00:00")).replace(tzinfo=None) if "T" in start_date else datetime.strptime(start_date, "%Y-%m-%d")
    else:
        current_end = datetime.utcnow()
        current_start = current_end - timedelta(days=days)

    # Calculate comparison range (previous period of same duration)
    duration = current_end - current_start
    previous_end = current_start
    previous_start = previous_end - duration

    # Helper to calculate stats for a period
    def calculate_period_stats(start, end):
        queues = db_interface.get_analytics_queues(shop_id)
        if not queues:
            return {"count": 0, "revenue": 0, "wait": 0, "service": 0}
        
        queue_ids = [q["id"] for q in queues]
        items = db_interface.get_analytics_items(queue_ids, start) # This gets everything >= start
        
        # Filter strictly within range [start, end)
        period_items = []
        for item in items:
            completed_str = item.get("completed_at")
            if completed_str:
                dt = datetime.fromisoformat(completed_str.replace("Z", "+00:00")).replace(tzinfo=None)
                if start <= dt < end + timedelta(days=1): # inclusive of end date (end of day)
                    period_items.append(item)
        
        total_customers = len(period_items)
        total_revenue = 0.0
        total_wait = 0
        wait_count = 0
        total_service = 0
        service_count = 0
        
        daily_data = {}

        for item in period_items:
            # Revenue
            total_revenue += float(item.get("service_cost") or 0.0)
            
            # Wait Time
            svc_start = item.get("service_started_at")
            check_in = item.get("checked_in_at")
            completed = item.get("completed_at")
            
            if svc_start and check_in:
                try:
                    s = datetime.fromisoformat(svc_start.replace("Z", "+00:00")).replace(tzinfo=None)
                    c = datetime.fromisoformat(check_in.replace("Z", "+00:00")).replace(tzinfo=None)
                    w = (s - c).total_seconds()
                    if w > 0:
                        total_wait += w
                        wait_count += 1
                except: pass
            
            if completed and svc_start:
                try:
                    cp = datetime.fromisoformat(completed.replace("Z", "+00:00")).replace(tzinfo=None)
                    s = datetime.fromisoformat(svc_start.replace("Z", "+00:00")).replace(tzinfo=None)
                    sv = (cp - s).total_seconds()
                    if sv > 0:
                        total_service += sv
                        service_count += 1
                except: pass

            # Daily Stats (only needed for current period)
            if completed:
                try:
                    d = datetime.fromisoformat(completed.replace("Z", "+00:00")).replace(tzinfo=None).strftime("%Y-%m-%d")
                    if d not in daily_data:
                        daily_data[d] = {"count": 0, "revenue": 0}
                    daily_data[d]["count"] += 1
                    daily_data[d]["revenue"] += float(item.get("service_cost") or 0.0)
                except: pass

        avg_wait = round(total_wait / wait_count / 60) if wait_count > 0 else 0
        avg_service = round(total_service / service_count / 60) if service_count > 0 else 0
        
        return {
            "total_customers": total_customers,
            "total_revenue": total_revenue,
            "avg_wait_minutes": avg_wait,
            "avg_service_minutes": avg_service,
            "daily_data": daily_data
        }

    # Calculate stats
    current_stats = calculate_period_stats(current_start, current_end)
    previous_stats = calculate_period_stats(previous_start, previous_end)

    # Format Chart Data
    chart_data = []
    curr = current_start
    while curr <= current_end:
        d_str = curr.strftime("%Y-%m-%d")
        data = current_stats["daily_data"].get(d_str, {"count": 0, "revenue": 0})
        chart_data.append({
            "date": d_str,
            "count": data["count"],
            "revenue": data["revenue"]
        })
        curr += timedelta(days=1)

    # Calculate Trends (%)
    def calc_trend(curr, prev):
        if prev == 0:
            return 100 if curr > 0 else 0
        return round(((curr - prev) / prev) * 100)

    visits_trend = calc_trend(current_stats["total_customers"], previous_stats["total_customers"])
    revenue_trend = calc_trend(current_stats["total_revenue"], previous_stats["total_revenue"])
    wait_trend = calc_trend(current_stats["avg_wait_minutes"], previous_stats["avg_wait_minutes"])
    service_trend = calc_trend(current_stats["avg_service_minutes"], previous_stats["avg_service_minutes"])

    return {
        "period_days": days if not (start_date and end_date) else (current_end - current_start).days,
        "total_customers": current_stats["total_customers"],
        "total_revenue": current_stats["total_revenue"],
        "avg_wait_minutes": current_stats["avg_wait_minutes"],
        "avg_service_minutes": current_stats["avg_service_minutes"],
        "daily_stats": chart_data,
        "trends": {
            "visits": visits_trend,
            "revenue": revenue_trend,
            "wait": wait_trend,
            "service": service_trend
        }
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
