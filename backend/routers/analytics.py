from fastapi import APIRouter, Depends, HTTPException
from supabase_client import supabase
from auth_utils import get_current_user
from typing import List, Dict, Any
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/{shop_id}")
def get_shop_analytics(
    shop_id: int,
    days: int = 30,
    current_user: dict = Depends(get_current_user)
):
    # Verify shop ownership
    try:
        shop_response = supabase.table("shops").select("*").eq("id", shop_id).execute()
        if not shop_response.data:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        shop = shop_response.data[0]
        if shop["owner_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not authorized to view analytics for this shop")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Shop not found")

    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Get all queues for the shop
    queues_response = supabase.table("queues").select("id").eq("shop_id", shop_id).execute()
    if not queues_response.data:
        # No queues, return empty analytics
        return {
            "period_days": days,
            "total_customers": 0,
            "avg_wait_minutes": 0,
            "avg_service_minutes": 0,
            "daily_stats": []
        }
    
    queue_ids = [q["id"] for q in queues_response.data]
    
    # Get completed items in date range
    items_response = supabase.table("queue_items").select("*").in_(
        "queue_id", queue_ids
    ).eq("status", "completed").gte(
        "completed_at", start_date.isoformat()
    ).execute()
    
    completed_items = items_response.data if items_response.data else []

    # 1. Total Customers Served
    total_customers = len(completed_items)

    # 2. Average Wait Time (Check-in to Service Start)
    total_wait_seconds = 0
    wait_count = 0
    
    # 3. Average Service Time (Service Start to Completion)
    total_service_seconds = 0
    service_count = 0

    # 4. Customers Per Day
    daily_counts = {}

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
            "count": daily_counts.get(date_str, 0)
        })
        current += timedelta(days=1)

    return {
        "period_days": days,
        "total_customers": total_customers,
        "avg_wait_minutes": avg_wait_minutes,
        "avg_service_minutes": avg_service_minutes,
        "daily_stats": chart_data
    }
