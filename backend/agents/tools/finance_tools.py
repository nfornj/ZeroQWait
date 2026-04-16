from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timedelta
import re
import difflib
from db_interface import db_interface


_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_TIME_WINDOW_KEYWORDS = [
    "today", "daily", "day", "trend", "yesterday",
    "this", "last", "previous", "past", "over", "in",
    "week", "weekly", "month", "monthly", "quarter", "quarterly",
    "year", "yearly", "annual", "months", "years",
]


def _normalize_window_query(query: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", (query or "").lower())
    normalized_tokens = []
    for token in tokens:
        if token in _TIME_WINDOW_KEYWORDS:
            normalized_tokens.append(token)
            continue

        best = token
        best_ratio = 0.0
        for kw in _TIME_WINDOW_KEYWORDS:
            if abs(len(token) - len(kw)) > 2:
                continue
            ratio = difflib.SequenceMatcher(a=token, b=kw).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best = kw

        if best_ratio >= 0.82:
            normalized_tokens.append(best)
        else:
            normalized_tokens.append(token)

    return " ".join(normalized_tokens)


def extract_requested_date(query: str, now: Optional[datetime] = None) -> Optional[str]:
    """Extract a specific calendar day from user text in YYYY-MM-DD format."""
    q = (query or "").lower().strip()
    if not q:
        return None

    now = now or datetime.now()

    # ISO date: 2026-04-01
    iso_match = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", q)
    if iso_match:
        y, m, d = map(int, iso_match.groups())
        try:
            return datetime(y, m, d).strftime("%Y-%m-%d")
        except ValueError:
            return None

    # Slash date: 4/1 or 4/1/2026 (US-style month/day)
    slash_match = re.search(r"\b(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?\b", q)
    if slash_match:
        month = int(slash_match.group(1))
        day = int(slash_match.group(2))
        year_group = slash_match.group(3)
        year = now.year
        if year_group:
            year = int(year_group)
            if year < 100:
                year += 2000
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None

    # Month-name formats: april 1, apr 1st, april 1 2026
    month_name_pattern = (
        r"\b(" + "|".join(sorted(_MONTHS.keys(), key=len, reverse=True)) + r")\s+"
        r"(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b"
    )
    month_name_match = re.search(month_name_pattern, q)
    if month_name_match:
        month = _MONTHS[month_name_match.group(1)]
        day = int(month_name_match.group(2))
        year = int(month_name_match.group(3)) if month_name_match.group(3) else now.year
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None

    # Day-first month-name: 1 april 2026
    day_first_pattern = (
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+"
        r"(" + "|".join(sorted(_MONTHS.keys(), key=len, reverse=True)) + r")"
        r"(?:,?\s+(\d{4}))?\b"
    )
    day_first_match = re.search(day_first_pattern, q)
    if day_first_match:
        day = int(day_first_match.group(1))
        month = _MONTHS[day_first_match.group(2)]
        year = int(day_first_match.group(3)) if day_first_match.group(3) else now.year
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None

    return None


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
    q = _normalize_window_query((query or "").lower())

    # Default: recent 30-day daily trend
    start_dt = now - timedelta(days=30)
    end_dt = now
    granularity = "day"
    label = "last_30_days"

    # Use the original query for date extraction — normalization strips hyphens
    # from ISO dates like "2026-04-14" making them unrecognizable.
    requested_date = extract_requested_date(query or "", now)
    if requested_date:
        dt = datetime.strptime(requested_date, "%Y-%m-%d")
        start_dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        granularity = "day"
        label = "specific_day"
        return start_dt, end_dt, granularity, label

    # Month-name window: "in february", "what about march", optionally with year.
    # Resolve to full month range. If year is omitted and month is in the future,
    # interpret as previous year to avoid future-empty ranges.
    month_name_pattern = r"\b(?:in\s+)?(" + "|".join(sorted(_MONTHS.keys(), key=len, reverse=True)) + r")(?:\s+(\d{4}))?\b"
    month_name_match = re.search(month_name_pattern, q)
    if month_name_match:
        month = _MONTHS[month_name_match.group(1)]
        year_group = month_name_match.group(2)
        year = int(year_group) if year_group else now.year
        if not year_group and month > now.month:
            year -= 1

        start_dt = datetime(year, month, 1, 0, 0, 0, 0)
        if month == 12:
            next_month = datetime(year + 1, 1, 1, 0, 0, 0, 0)
        else:
            next_month = datetime(year, month + 1, 1, 0, 0, 0, 0)
        end_dt = next_month - timedelta(microseconds=1)
        granularity = "day"
        label = f"month_{start_dt.strftime('%Y_%m')}"
        return start_dt, end_dt, granularity, label

    relative_months_match = re.search(
        r"\b(?:last|past|previous)\s+(\d{1,2})\s+months?\b",
        q,
    )
    if relative_months_match:
        months = int(relative_months_match.group(1))
        if months > 0:
            anchor_month = now.month - (months - 1)
            anchor_year = now.year
            while anchor_month <= 0:
                anchor_month += 12
                anchor_year -= 1

            start_dt = datetime(anchor_year, anchor_month, 1, 0, 0, 0, 0)
            end_dt = now
            granularity = "month" if months >= 4 else "day"
            label = f"last_{months}_months"
            return start_dt, end_dt, granularity, label

    relative_days_match = re.search(
        r"\b(?:last|past|previous)\s+(\d{1,3})\s+days?\b",
        q,
    )
    if relative_days_match:
        days = int(relative_days_match.group(1))
        if days > 0:
            start_dt = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = now
            granularity = "day"
            label = f"last_{days}_days"
            return start_dt, end_dt, granularity, label

    relative_weeks_match = re.search(
        r"\b(?:last|past|previous)\s+(\d{1,2})\s+weeks?\b",
        q,
    )
    if relative_weeks_match:
        weeks = int(relative_weeks_match.group(1))
        if weeks > 0:
            start_dt = (now - timedelta(days=(weeks * 7) - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = now
            granularity = "day" if weeks <= 4 else "week"
            label = f"last_{weeks}_weeks"
            return start_dt, end_dt, granularity, label

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
    elif any(token in q for token in ["past year", "over past year", "in past year", "last 12 months", "past 12 months", "previous 12 months"]):
        start_dt = now - timedelta(days=365)
        end_dt = now
        granularity = "month"
        label = "past_year"
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
            "best_period_revenue": round(best_revenue, 2) if best_period else 0.0,
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


def customer_metrics(shop_id: int, query: Optional[str] = None) -> Dict[str, Any]:
    """Get customer metrics for a parsed time window from daily analytics + customer profiles."""
    session = None
    try:
        session = db_interface.get_session()
        from models import DailyAnalytics
        from modules.shops.models import ShopCustomer

        start_dt, end_dt, granularity, window = _parse_time_window(query or "")

        rows = session.query(DailyAnalytics).filter(
            DailyAnalytics.shop_id == shop_id,
            DailyAnalytics.date >= start_dt,
            DailyAnalytics.date <= end_dt,
        ).all()

        total_customers = sum(int(getattr(row, "total_customers", 0) or 0) for row in rows)
        completed_services = sum(int(getattr(row, "completed_services", 0) or 0) for row in rows)
        days_with_data = len(rows)

        new_customers = session.query(ShopCustomer).filter(
            ShopCustomer.shop_id == shop_id,
            ShopCustomer.created_at >= start_dt,
            ShopCustomer.created_at <= end_dt,
        ).count()

        repeat_customers = session.query(ShopCustomer).filter(
            ShopCustomer.shop_id == shop_id,
            ShopCustomer.visit_count > 1,
            ShopCustomer.last_visit >= start_dt,
            ShopCustomer.last_visit <= end_dt,
        ).count()

        known_customer_pool = int(new_customers) + int(repeat_customers)
        repeat_rate = (repeat_customers / known_customer_pool) if known_customer_pool > 0 else 0.0
        profile_signal_limited = bool(total_customers > 0 and known_customer_pool == 0)

        return {
            "shop_id": shop_id,
            "query": query or "",
            "window": window,
            "granularity": granularity,
            "range_start": start_dt.strftime("%Y-%m-%d"),
            "range_end": end_dt.strftime("%Y-%m-%d"),
            "total_customers": int(total_customers),
            "completed_services": int(completed_services),
            "days_with_data": days_with_data,
            "average_daily_customers": round((total_customers / days_with_data), 2) if days_with_data > 0 else 0.0,
            "new_customers": int(new_customers),
            "repeat_customers": int(repeat_customers),
            "repeat_rate": round(float(repeat_rate), 4),
            "profile_signal_limited": profile_signal_limited,
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        if session is not None:
            session.close()


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


def create_invoice(
    shop_id: int,
    service_name: str,
    unit_price: float,
    quantity: int = 1,
    customer_id: Optional[int] = None,
    tax_rate: float = 0.0,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Create an invoice for a service rendered at the shop."""
    try:
        from modules.payments.service import PaymentService

        svc = PaymentService()
        line_items = [{"description": service_name, "unit_price": unit_price, "quantity": quantity}]
        result = svc.create_invoice(
            shop_id=shop_id,
            line_items=line_items,
            customer_id=customer_id,
            tax_rate=tax_rate,
            notes=notes,
        )
        return result
    except Exception as e:
        return {"error": str(e)}


def record_payment(
    shop_id: int,
    amount: float,
    method: str = "cash",
    invoice_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Record a payment against an invoice or as a standalone transaction."""
    try:
        from modules.payments.service import PaymentService

        svc = PaymentService()
        # If no invoice_id provided, try to find the latest draft/sent invoice
        if invoice_id is None:
            from modules.payments.models import Invoice
            session = db_interface.get_session()
            try:
                latest = session.query(Invoice).filter(
                    Invoice.shop_id == shop_id,
                    Invoice.status.in_(["DRAFT", "SENT"]),
                ).order_by(Invoice.created_at.desc()).first()
                if latest:
                    invoice_id = latest.id
            finally:
                session.close()

        result = svc.record_payment(
            shop_id=shop_id,
            amount=amount,
            method=method,
            invoice_id=invoice_id,
            notes=notes,
        )
        return result
    except Exception as e:
        return {"error": str(e)}


def list_invoices(
    shop_id: int,
    status: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """List invoices for a shop."""
    try:
        from modules.payments.service import PaymentService

        svc = PaymentService()
        result = svc.list_invoices(shop_id=shop_id, status=status, limit=limit)
        return {"invoices": result, "count": len(result), "shop_id": shop_id}
    except Exception as e:
        return {"error": str(e)}


def get_pos_summary(shop_id: int, date: Optional[str] = None) -> Dict[str, Any]:
    """Get POS (point of sale) summary for a given day."""
    try:
        from modules.payments.models import Payment, PaymentStatus
        from sqlalchemy import func

        target_date = date or datetime.now().strftime("%Y-%m-%d")
        session = db_interface.get_session()
        try:
            from sqlalchemy import cast, Date
            rows = session.query(
                func.count(Payment.id).label("count"),
                func.coalesce(func.sum(Payment.amount), 0.0).label("total"),
                Payment.method,
            ).filter(
                Payment.shop_id == shop_id,
                Payment.status == PaymentStatus.COMPLETED,
                cast(Payment.processed_at, Date) == target_date,
            ).group_by(Payment.method).all()

            methods = {}
            total_count = 0
            total_amount = 0.0
            for row in rows:
                m = str(row.method.value) if hasattr(row.method, 'value') else str(row.method)
                methods[m] = {"count": int(row.count), "total": float(row.total)}
                total_count += int(row.count)
                total_amount += float(row.total)

            return {
                "shop_id": shop_id,
                "date": target_date,
                "total_transactions": total_count,
                "total_amount": total_amount,
                "by_method": methods,
            }
        finally:
            session.close()
    except Exception as e:
        return {"error": str(e)}
