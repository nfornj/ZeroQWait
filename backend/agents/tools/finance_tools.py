from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timedelta
from db_interface import db_interface


def daily_revenue(shop_id: int, date: Optional[str] = None) -> Dict[str, Any]:
    """Get daily revenue via db_interface."""
    try:
        session = db_interface.get_session()
        from models import DailyAnalytics
        
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        
        # Query ALL DailyAnalytics for this date (sum if multiple records)
        analytics_list = session.query(DailyAnalytics).filter(
            DailyAnalytics.shop_id == shop_id,
            DailyAnalytics.date == date
        ).all()
        session.close()
        
        if analytics_list:
            total_revenue = sum(getattr(a, 'total_revenue', 0.0) for a in analytics_list)
            total_completed = sum(getattr(a, 'completed_services', 0) for a in analytics_list)
            average_transaction = total_revenue / total_completed if total_completed > 0 else 0.0
            
            return {
                "total_revenue": total_revenue,
                "transaction_count": total_completed,
                "completed_services": total_completed,
                "average_transaction": average_transaction,
                "shop_id": shop_id,
                "date": date
            }
        
        return {
            "total_revenue": 0.0,
            "transaction_count": 0,
            "completed_services": 0,
            "average_transaction": 0.0,
            "shop_id": shop_id,
            "date": date
        }
    except Exception as e:
        return {"error": str(e)}


def _parse_time_window(query: str) -> Tuple[datetime, datetime, str, str]:
    """Parse common NL time-window phrases to concrete range + grouping granularity."""
    now = datetime.now()
    q = (query or "").lower()

    # Default: recent 30-day daily trend
    start_dt = now - timedelta(days=30)
    end_dt = now
    granularity = "day"
    label = "last_30_days"

    if any(token in q for token in ["today", "daily", "day trend"]):
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = now
        granularity = "hour"
        label = "today"
    elif any(token in q for token in ["yesterday"]):
        y = now - timedelta(days=1)
        start_dt = y.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = y.replace(hour=23, minute=59, second=59, microsecond=999999)
        granularity = "hour"
        label = "yesterday"
    elif any(token in q for token in ["this week", "weekly", "week trend"]):
        start_dt = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = now
        granularity = "day"
        label = "this_week"
    elif any(token in q for token in ["last week", "previous week"]):
        this_week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        start_dt = this_week_start - timedelta(days=7)
        end_dt = this_week_start - timedelta(microseconds=1)
        granularity = "day"
        label = "last_week"
    elif any(token in q for token in ["this month", "monthly", "month trend", "monthly trend"]):
        start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_dt = now
        granularity = "day"
        label = "this_month"
    elif any(token in q for token in ["last month", "previous month"]):
        first_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_prev_month = first_this_month - timedelta(microseconds=1)
        start_dt = last_prev_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_dt = last_prev_month
        granularity = "day"
        label = "last_month"
    elif any(token in q for token in ["quarter", "quarterly"]):
        quarter = (now.month - 1) // 3 + 1
        q_start_month = (quarter - 1) * 3 + 1
        start_dt = now.replace(month=q_start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_dt = now
        granularity = "week"
        label = "this_quarter"
    elif any(token in q for token in ["this year", "yearly", "annual", "year trend"]):
        start_dt = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_dt = now
        granularity = "month"
        label = "this_year"
    elif any(token in q for token in ["last year", "previous year"]):
        y = now.year - 1
        start_dt = datetime(y, 1, 1)
        end_dt = datetime(y, 12, 31, 23, 59, 59, 999999)
        granularity = "month"
        label = "last_year"
    elif "3 year" in q or "three year" in q:
        start_dt = now - timedelta(days=365 * 3)
        end_dt = now
        granularity = "month"
        label = "last_3_years"

    return start_dt, end_dt, granularity, label


def _bucket_key(dt_value: datetime, granularity: str) -> str:
    """Return stable bucket key for a datetime at requested granularity."""
    if granularity == "hour":
        return dt_value.strftime("%Y-%m-%d %H:00")
    if granularity == "week":
        monday = dt_value - timedelta(days=dt_value.weekday())
        return monday.strftime("%Y-%m-%d")
    if granularity == "month":
        return dt_value.strftime("%Y-%m")
    return dt_value.strftime("%Y-%m-%d")


def trend_summary(shop_id: int, query: str) -> Dict[str, Any]:
    """Dynamic finance trend query backed by DailyAnalytics aggregation."""
    try:
        session = db_interface.get_session()
        from models import DailyAnalytics

        start_dt, end_dt, granularity, window = _parse_time_window(query)

        rows = session.query(DailyAnalytics).filter(
            DailyAnalytics.shop_id == shop_id,
            DailyAnalytics.date >= start_dt,
            DailyAnalytics.date <= end_dt,
        ).all()

        buckets: Dict[str, Dict[str, float]] = {}
        total_revenue = 0.0
        total_customers = 0
        total_completed = 0

        for row in rows:
            dt = getattr(row, "date", None)
            if not dt:
                continue
            key = _bucket_key(dt, granularity)
            if key not in buckets:
                buckets[key] = {
                    "revenue": 0.0,
                    "customers": 0,
                    "completed": 0,
                }

            revenue = float(getattr(row, "total_revenue", 0.0) or 0.0)
            customers = int(getattr(row, "total_customers", 0) or 0)
            completed = int(getattr(row, "completed_services", 0) or 0)

            buckets[key]["revenue"] += revenue
            buckets[key]["customers"] += customers
            buckets[key]["completed"] += completed

            total_revenue += revenue
            total_customers += customers
            total_completed += completed

        points = []
        best_period = None
        best_revenue = -1.0
        for key in sorted(buckets.keys()):
            r = round(float(buckets[key]["revenue"]), 2)
            c = int(buckets[key]["customers"])
            k = int(buckets[key]["completed"])
            points.append({
                "period": key,
                "revenue": r,
                "customers": c,
                "completed_services": k,
            })
            if r > best_revenue:
                best_revenue = r
                best_period = key

        avg_transaction = (total_revenue / total_completed) if total_completed > 0 else 0.0

        session.close()
        return {
            "shop_id": shop_id,
            "window": window,
            "granularity": granularity,
            "query": query,
            "range_start": start_dt.strftime("%Y-%m-%d"),
            "range_end": end_dt.strftime("%Y-%m-%d"),
            "total_revenue": round(total_revenue, 2),
            "total_customers": total_customers,
            "completed_services": total_completed,
            "average_transaction": round(avg_transaction, 2),
            "best_period": best_period,
            "points": points,
        }
    except Exception as e:
        return {"error": str(e)}


def weekly_summary(shop_id: int, week_start: Optional[str] = None) -> Dict[str, Any]:
    """Get weekly revenue summary."""
    try:
        session = db_interface.get_session()
        from models import DailyAnalytics
        
        if week_start:
            start_date = datetime.fromisoformat(week_start)
        else:
            today = datetime.now()
            start_date = today - timedelta(days=today.weekday())
        
        total_revenue = 0.0
        total_customers = 0
        total_completed = 0
        best_day = None
        best_day_revenue = 0.0
        
        # Sum ALL records per date (use .all() not .first())
        for i in range(7):
            date_str = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
            day_records = session.query(DailyAnalytics).filter(
                DailyAnalytics.shop_id == shop_id,
                DailyAnalytics.date == date_str
            ).all()
            
            day_revenue = 0.0
            for record in day_records:
                rev = getattr(record, 'total_revenue', 0.0)
                day_revenue += rev
                total_revenue += rev
                total_customers += getattr(record, 'total_customers', 0)
                total_completed += getattr(record, 'completed_services', 0)
            
            if day_revenue > best_day_revenue:
                best_day_revenue = day_revenue
                best_day = date_str
        
        session.close()
        
        avg_trans = total_revenue / total_completed if total_completed > 0 else 0.0
        return {
            "total_revenue": total_revenue,
            "transaction_count": total_completed,
            "completed_services": total_completed,
            "average_transaction": avg_trans,
            "best_day": best_day,
            "total_customers": total_customers,
            "week_start": start_date.strftime("%Y-%m-%d"),
            "shop_id": shop_id
        }
    except Exception as e:
        return {"error": str(e)}


def top_services(shop_id: int, limit: int = 5) -> Dict[str, Any]:
    """Get top services by revenue."""
    try:
        services = db_interface.get_shop_services(shop_id, include_inactive=False)
        top = services[:limit] if services else []
        return {
            "services": top,
            "shop_id": shop_id,
            "limit": limit
        }
    except Exception as e:
        return {"error": str(e)}


def customer_metrics(shop_id: int) -> Dict[str, Any]:
    """Get customer metrics."""
    try:
        return {
            "total_customers": 0,
            "repeat_customers": 0,
            "new_customers": 0,
            "shop_id": shop_id
        }
    except Exception as e:
        return {"error": str(e)}


def export_report(shop_id: int, format: str = "csv") -> Dict[str, Any]:
    """Export analytics report."""
    try:
        return {
            "format": format,
            "filename": f"report_{shop_id}_{datetime.now().strftime('%Y%m%d')}.{format}",
            "row_count": 0,
            "shop_id": shop_id
        }
    except Exception as e:
        return {"error": str(e)}
