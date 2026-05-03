from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timedelta, timezone
import re
import difflib
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from db_interface import db_interface
from integrations.finance_mcp_client import FinanceMCPClient


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

_SIMPLE_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}

_TENS_NUMBER_WORDS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

_NUMBER_WORD_PATTERN = r"\d{1,3}|[a-z]+(?:[ -][a-z]+){0,3}"

_TIME_WINDOW_KEYWORDS = [
    "today", "daily", "day", "trend", "yesterday",
    "this", "last", "previous", "past", "over", "in",
    "week", "weekly", "month", "monthly", "quarter", "quarterly",
    "year", "yearly", "annual", "months", "years",
]

_finance_mcp_client: Optional[FinanceMCPClient] = None
_DEFAULT_BUSINESS_TIMEZONE = (
    os.getenv("DEFAULT_BUSINESS_TIMEZONE")
    or os.getenv("TZ")
    or "UTC"
)


def _get_finance_client() -> FinanceMCPClient:
    global _finance_mcp_client
    if _finance_mcp_client is None:
        _finance_mcp_client = FinanceMCPClient()
    return _finance_mcp_client


def _get_zoneinfo(tz_name: Optional[str]) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or _DEFAULT_BUSINESS_TIMEZONE)
    except (ZoneInfoNotFoundError, Exception):
        return ZoneInfo("UTC")


def _resolve_shop_timezone_name(shop_id: int, session) -> str:
    try:
        from modules.shops.models import ShopOperatingHours

        tz_name = (
            session.query(ShopOperatingHours.timezone)
            .filter(ShopOperatingHours.shop_id == shop_id)
            .scalar()
        )
        return tz_name or _DEFAULT_BUSINESS_TIMEZONE
    except Exception:
        return _DEFAULT_BUSINESS_TIMEZONE


def _now_for_shop(shop_id: int, session) -> datetime:
    return datetime.now(_get_zoneinfo(_resolve_shop_timezone_name(shop_id, session)))


def _to_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _to_local_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.replace(tzinfo=None)


def _shop_local_day_bounds_utc(local_date, tz_name: str) -> Tuple[datetime, datetime]:
    tz = _get_zoneinfo(tz_name)
    start_local = datetime.combine(local_date, datetime.min.time(), tzinfo=tz)
    end_local = datetime.combine(local_date, datetime.max.time(), tzinfo=tz)
    return _to_utc_naive(start_local), _to_utc_naive(end_local)


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


def _parse_relative_window_count(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None

    token = str(value).strip().lower()
    if not token:
        return None
    if token.isdigit():
        return int(token)

    token = token.replace("-", " ")
    parts = [part for part in token.split() if part and part != "and"]
    if not parts:
        return None

    total = 0
    current = 0
    for part in parts:
        if part in _SIMPLE_NUMBER_WORDS:
            current += _SIMPLE_NUMBER_WORDS[part]
            continue
        if part in _TENS_NUMBER_WORDS:
            current += _TENS_NUMBER_WORDS[part]
            continue
        if part == "hundred":
            current = max(current, 1) * 100
            continue
        return None

    total += current
    return total if total > 0 else None


def _describe_time_window(label: str, start_dt: datetime, end_dt: datetime, granularity: str) -> str:
    month_match = re.fullmatch(r"month_(\d{4})_(\d{2})", str(label or ""))
    if month_match:
        year = int(month_match.group(1))
        month = int(month_match.group(2))
        return datetime(year, month, 1).strftime("%B %Y")

    if label == "specific_day":
        return start_dt.strftime("%b %-d, %Y")

    if label == "today":
        return "today"
    if label == "yesterday":
        return "yesterday"
    if label == "this_week":
        return "this week"
    if label == "last_week":
        return "last week"
    if label == "this_month":
        return "this month"
    if label == "last_month":
        return "last month"
    if label == "this_quarter":
        return "this quarter"
    if label == "this_year":
        return "this year"
    if label == "last_year":
        return "last year"
    if label == "past_year":
        return "past year"

    if str(label or "").startswith("last_"):
        return str(label).replace("_", " ")

    if granularity == "month":
        return f"{start_dt.strftime('%b %Y')} to {end_dt.strftime('%b %Y')}"
    return f"{start_dt.strftime('%b %-d, %Y')} to {end_dt.strftime('%b %-d, %Y')}"


def _local_daily_revenue(shop_id: int, date: Optional[str] = None) -> Dict[str, Any]:
    """Get daily revenue via db_interface.
    
    For today's date, queries queue_items in real-time (daily_analytics
    is batch-populated nightly and may not have today's row yet).
    """
    try:
        session = db_interface.get_session()
        from models import DailyAnalytics, QueueItem, Queue, QueueStatus
        from sqlalchemy import func
        tz_name = _resolve_shop_timezone_name(shop_id, session)
        shop_now = _now_for_shop(shop_id, session)
        
        if not date:
            date = shop_now.strftime("%Y-%m-%d")
        
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
        is_today = (target_date == shop_now.date())

        # Query batch analytics first
        analytics_list = session.query(DailyAnalytics).filter(
            DailyAnalytics.shop_id == shop_id,
            DailyAnalytics.date == date
        ).all()
        
        if analytics_list and not is_today:
            total_revenue = sum(getattr(a, 'total_revenue', 0.0) for a in analytics_list)
            total_completed = sum(getattr(a, 'completed_services', 0) for a in analytics_list)
            average_transaction = total_revenue / total_completed if total_completed > 0 else 0.0
            session.close()
            return {
                "total_revenue": total_revenue,
                "transaction_count": total_completed,
                "completed_services": total_completed,
                "average_transaction": average_transaction,
                "shop_id": shop_id,
                "date": date
            }
        
        day_start_utc, day_end_utc = _shop_local_day_bounds_utc(target_date, tz_name)

        # Real-time fallback: query queue_items directly
        completed_items = (
            session.query(QueueItem)
            .join(Queue)
            .filter(
                Queue.shop_id == shop_id,
                QueueItem.checked_in_at >= day_start_utc,
                QueueItem.checked_in_at <= day_end_utc,
                QueueItem.status == QueueStatus.COMPLETED,
            )
            .all()
        )
        total_completed = len(completed_items)
        total_revenue = sum(float(item.service_cost or 0.0) for item in completed_items)
        average_transaction = total_revenue / total_completed if total_completed > 0 else 0.0

        # Also count all customers (any status) for "total customers"
        all_count = (
            session.query(func.count(QueueItem.id))
            .join(Queue)
            .filter(
                Queue.shop_id == shop_id,
                QueueItem.checked_in_at >= day_start_utc,
                QueueItem.checked_in_at <= day_end_utc,
            )
            .scalar() or 0
        )

        session.close()
        return {
            "total_revenue": total_revenue,
            "transaction_count": total_completed,
            "completed_services": total_completed,
            "total_customers": all_count,
            "average_transaction": average_transaction,
            "shop_id": shop_id,
            "date": date
        }
    except Exception as e:
        return {"error": str(e)}


def _parse_time_window(query: str, now: Optional[datetime] = None) -> Tuple[datetime, datetime, str, str]:
    """Parse common NL time-window phrases to concrete range + grouping granularity."""
    now = now or datetime.now()
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

        start_dt = datetime(year, month, 1, 0, 0, 0, 0, tzinfo=now.tzinfo)
        if month == 12:
            next_month = datetime(year + 1, 1, 1, 0, 0, 0, 0, tzinfo=now.tzinfo)
        else:
            next_month = datetime(year, month + 1, 1, 0, 0, 0, 0, tzinfo=now.tzinfo)
        end_dt = next_month - timedelta(microseconds=1)
        granularity = "day"
        label = f"month_{start_dt.strftime('%Y_%m')}"
        return start_dt, end_dt, granularity, label

    relative_months_match = re.search(
        rf"\b(?:last|past|previous)\s+({_NUMBER_WORD_PATTERN})\s+months?\b",
        q,
    )
    if relative_months_match:
        months = _parse_relative_window_count(relative_months_match.group(1)) or 0
        if months > 0:
            anchor_month = now.month - (months - 1)
            anchor_year = now.year
            while anchor_month <= 0:
                anchor_month += 12
                anchor_year -= 1

            start_dt = datetime(anchor_year, anchor_month, 1, 0, 0, 0, 0, tzinfo=now.tzinfo)
            end_dt = now
            granularity = "month" if months >= 4 else "day"
            label = f"last_{months}_months"
            return start_dt, end_dt, granularity, label

    relative_days_match = re.search(
        rf"\b(?:last|past|previous)\s+({_NUMBER_WORD_PATTERN})\s+days?\b",
        q,
    )
    if not relative_days_match:
        relative_days_match = re.search(
            rf"\b({_NUMBER_WORD_PATTERN})\s+days?\b",
            q,
        )
    if relative_days_match:
        days = _parse_relative_window_count(relative_days_match.group(1)) or 0
        if days > 0:
            start_dt = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = now
            granularity = "day"
            label = f"last_{days}_days"
            return start_dt, end_dt, granularity, label

    relative_weeks_match = re.search(
        rf"\b(?:last|past|previous)\s+({_NUMBER_WORD_PATTERN})\s+weeks?\b",
        q,
    )
    if relative_weeks_match:
        weeks = _parse_relative_window_count(relative_weeks_match.group(1)) or 0
        if weeks > 0:
            start_dt = (now - timedelta(days=(weeks * 7) - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = now
            granularity = "day" if weeks <= 4 else "week"
            label = f"last_{weeks}_weeks"
            return start_dt, end_dt, granularity, label

    relative_years_match = re.search(
        rf"\b(?:last|past|previous)\s+({_NUMBER_WORD_PATTERN})\s+years?\b",
        q,
    )
    if relative_years_match:
        years = _parse_relative_window_count(relative_years_match.group(1)) or 0
        if years > 0:
            start_dt = now - timedelta(days=365 * years)
            end_dt = now
            granularity = "month"
            label = f"last_{years}_years"
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


def _local_trend_summary(shop_id: int, query: str) -> Dict[str, Any]:
    """Dynamic finance trend query backed by DailyAnalytics aggregation.
    
    For windows that include today, supplements batch daily_analytics
    with real-time queue_items data so recently-completed services are visible.
    """
    try:
        session = db_interface.get_session()
        from models import DailyAnalytics, QueueItem, Queue, QueueStatus
        tz_name = _resolve_shop_timezone_name(shop_id, session)
        shop_now = _now_for_shop(shop_id, session)

        start_dt, end_dt, granularity, window = _parse_time_window(query, now=shop_now)
        start_db = _to_local_naive(start_dt)
        end_db = _to_local_naive(end_dt)

        today = shop_now.date()
        window_includes_today = (start_dt.date() <= today <= end_dt.date())

        # Query daily_analytics (exclude today if window includes it — we'll add real-time below)
        if window_includes_today and start_dt.date() < today:
            hist_end = datetime.combine(today - timedelta(days=1), datetime.max.time())
            rows = session.query(DailyAnalytics).filter(
                DailyAnalytics.shop_id == shop_id,
                DailyAnalytics.date >= start_db,
                DailyAnalytics.date <= hist_end,
            ).all()
        elif not window_includes_today:
            rows = session.query(DailyAnalytics).filter(
                DailyAnalytics.shop_id == shop_id,
                DailyAnalytics.date >= start_db,
                DailyAnalytics.date <= end_db,
            ).all()
        else:
            # Window is today-only — no historical rows needed
            rows = []

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

        # Real-time today supplement from queue_items
        if window_includes_today:
            today_start_utc, today_end_utc = _shop_local_day_bounds_utc(today, tz_name)
            query_end_utc = min(_to_utc_naive(end_dt), today_end_utc)
            today_items = (
                session.query(QueueItem)
                .join(Queue)
                .filter(
                    Queue.shop_id == shop_id,
                    QueueItem.checked_in_at >= today_start_utc,
                    QueueItem.checked_in_at <= query_end_utc,
                )
                .all()
            )
            today_all = len(today_items)
            today_completed_items = [i for i in today_items if i.status == QueueStatus.COMPLETED]
            today_completed_count = len(today_completed_items)
            today_revenue = sum(float(i.service_cost or 0.0) for i in today_completed_items)

            key = _bucket_key(shop_now, granularity)
            if key not in buckets:
                buckets[key] = {"revenue": 0.0, "customers": 0, "completed": 0}
            buckets[key]["revenue"] += today_revenue
            buckets[key]["customers"] += today_all
            buckets[key]["completed"] += today_completed_count

            total_revenue += today_revenue
            total_customers += today_all
            total_completed += today_completed_count

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
            "window_display": _describe_time_window(window, start_dt, end_dt, granularity),
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


def _local_weekly_summary(shop_id: int, week_start: Optional[str] = None) -> Dict[str, Any]:
    """Get weekly revenue summary.
    
    Supplements batch daily_analytics with real-time queue_items
    for today's date so recently-completed services are included.
    """
    try:
        session = db_interface.get_session()
        from models import DailyAnalytics, QueueItem, Queue, QueueStatus
        tz_name = _resolve_shop_timezone_name(shop_id, session)
        shop_now = _now_for_shop(shop_id, session)
        
        if week_start:
            start_date = datetime.fromisoformat(week_start)
        else:
            today_dt = shop_now
            start_date = today_dt - timedelta(days=today_dt.weekday())
        
        today = shop_now.date()
        total_revenue = 0.0
        total_customers = 0
        total_completed = 0
        best_day = None
        best_day_revenue = 0.0
        points = []
        
        for i in range(7):
            loop_date = (start_date + timedelta(days=i)).date()
            date_str = loop_date.strftime("%Y-%m-%d")
            day_revenue = 0.0
            day_customers = 0
            day_completed_count = 0

            if loop_date == today:
                # Real-time from queue_items
                today_start_utc, _today_end_utc = _shop_local_day_bounds_utc(today, tz_name)
                today_items = (
                    session.query(QueueItem)
                    .join(Queue)
                    .filter(
                        Queue.shop_id == shop_id,
                        QueueItem.checked_in_at >= today_start_utc,
                    )
                    .all()
                )
                day_completed_items = [item for item in today_items if getattr(item, "status", None) == QueueStatus.COMPLETED]
                day_revenue = sum(float(getattr(item, "service_cost", 0.0) or 0.0) for item in day_completed_items)
                day_customers = len(today_items)
                day_completed_count = len(day_completed_items)
                total_revenue += day_revenue
                total_customers += day_customers
                total_completed += day_completed_count
            elif loop_date > today:
                continue  # Future dates — skip
            else:
                # Historical from daily_analytics
                day_records = session.query(DailyAnalytics).filter(
                    DailyAnalytics.shop_id == shop_id,
                    DailyAnalytics.date == date_str
                ).all()

                for record in day_records:
                    rev = getattr(record, 'total_revenue', 0.0)
                    day_revenue += rev
                    total_revenue += rev
                    customers = int(getattr(record, 'total_customers', 0) or 0)
                    completed = int(getattr(record, 'completed_services', 0) or 0)
                    day_customers += customers
                    day_completed_count += completed
                    total_customers += customers
                    total_completed += completed
            
            if day_revenue > best_day_revenue:
                best_day_revenue = day_revenue
                best_day = date_str

            points.append(
                {
                    "period": date_str,
                    "revenue": round(float(day_revenue), 2),
                    "customers": day_customers,
                    "completed_services": day_completed_count,
                }
            )
        
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
            "shop_id": shop_id,
            "window": f"week_of_{start_date.strftime('%Y-%m-%d')}",
            "granularity": "day",
            "range_start": start_date.strftime("%Y-%m-%d"),
            "range_end": min((start_date + timedelta(days=6)).date(), today).strftime("%Y-%m-%d"),
            "points": points,
        }
    except Exception as e:
        return {"error": str(e)}


def _local_top_services(shop_id: int, limit: int = 5) -> Dict[str, Any]:
    """Get top services by live completed-service revenue.

    Daily analytics and invoices can lag behind the simulator/local queue
    activity, so this reads completed queue visits directly for the recent
    live window and falls back to the service catalog only when no visits
    exist yet.
    """
    session = None
    try:
        session = db_interface.get_session()
        from modules.queues.models import Queue, QueueItem, QueueStatus
        from modules.shops.models import ShopService
        from sqlalchemy import func

        safe_limit = max(1, min(int(limit or 5), 50))
        shop_now = _now_for_shop(shop_id, session)
        start_dt, end_dt, _granularity, window = _parse_time_window("last 30 days", now=shop_now)
        start_utc = _to_utc_naive(start_dt)
        end_utc = _to_utc_naive(end_dt)

        rows = (
            session.query(
                ShopService.id.label("service_id"),
                func.coalesce(ShopService.name, QueueItem.notes, "Unknown service").label("name"),
                func.count(QueueItem.id).label("completed_services"),
                func.count(QueueItem.id).label("customer_count"),
                func.coalesce(func.sum(QueueItem.service_cost), 0.0).label("revenue"),
                func.coalesce(func.avg(QueueItem.service_cost), 0.0).label("average_ticket"),
            )
            .join(Queue, QueueItem.queue_id == Queue.id)
            .outerjoin(ShopService, QueueItem.service_id == ShopService.id)
            .filter(
                Queue.shop_id == shop_id,
                QueueItem.status == QueueStatus.COMPLETED,
                func.coalesce(QueueItem.completed_at, QueueItem.checked_in_at) >= start_utc,
                func.coalesce(QueueItem.completed_at, QueueItem.checked_in_at) <= end_utc,
            )
            .group_by(ShopService.id, func.coalesce(ShopService.name, QueueItem.notes, "Unknown service"))
            .order_by(func.coalesce(func.sum(QueueItem.service_cost), 0.0).desc(), func.count(QueueItem.id).desc())
            .limit(safe_limit)
            .all()
        )

        services = [
            {
                "id": row.service_id,
                "service_id": row.service_id,
                "name": row.name,
                "completed_services": int(row.completed_services or 0),
                "customer_count": int(row.customer_count or 0),
                "revenue": round(float(row.revenue or 0.0), 2),
                "average_ticket": round(float(row.average_ticket or 0.0), 2),
            }
            for row in rows
        ]

        if not services:
            catalog = db_interface.get_shop_services(shop_id, include_inactive=False)
            services = catalog[:safe_limit] if catalog else []

        return {
            "services": services,
            "shop_id": shop_id,
            "limit": safe_limit,
            "window": window,
            "window_display": _describe_time_window(window, start_dt, end_dt, "day"),
            "total_revenue": round(sum(float(item.get("revenue", 0.0) or 0.0) for item in services), 2),
            "completed_services": sum(int(item.get("completed_services", 0) or 0) for item in services),
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        if session is not None:
            session.close()


def _local_customer_metrics(shop_id: int, query: Optional[str] = None) -> Dict[str, Any]:
    """Get customer metrics for a parsed time window.
    
    Uses real-time queue_items data when the window includes today
    (daily_analytics is batch-populated nightly and may lag).
    Falls back to daily_analytics for historical ranges.
    """
    session = None
    try:
        session = db_interface.get_session()
        from models import DailyAnalytics, QueueItem, Queue, QueueStatus
        from modules.shops.models import ShopCustomer
        from sqlalchemy import func
        tz_name = _resolve_shop_timezone_name(shop_id, session)
        shop_now = _now_for_shop(shop_id, session)

        start_dt, end_dt, granularity, window = _parse_time_window(query or "", now=shop_now)
        start_db = _to_local_naive(start_dt)
        end_db = _to_local_naive(end_dt)
        start_utc = _to_utc_naive(start_dt)
        end_utc = _to_utc_naive(end_dt)

        today = shop_now.date()
        window_includes_today = (start_dt.date() <= today <= end_dt.date())

        # --- Historical portion from daily_analytics ---
        total_customers = 0
        completed_services = 0
        days_with_data = 0

        if start_dt.date() < today:
            # Query daily_analytics only for dates before today
            hist_end = min(
                end_dt,
                datetime.combine(
                    today - timedelta(days=1),
                    datetime.max.time(),
                    tzinfo=end_dt.tzinfo,
                ),
            )
            rows = session.query(DailyAnalytics).filter(
                DailyAnalytics.shop_id == shop_id,
                DailyAnalytics.date >= start_db,
                DailyAnalytics.date <= _to_local_naive(hist_end),
            ).all()
            total_customers += sum(int(getattr(row, "total_customers", 0) or 0) for row in rows)
            completed_services += sum(int(getattr(row, "completed_services", 0) or 0) for row in rows)
            days_with_data += len(rows)

        # --- Real-time portion from queue_items for today ---
        if window_includes_today:
            today_start_utc, today_end_utc = _shop_local_day_bounds_utc(today, tz_name)
            query_end_utc = min(_to_utc_naive(end_dt), today_end_utc)
            today_all = (
                session.query(func.count(QueueItem.id))
                .join(Queue)
                .filter(
                    Queue.shop_id == shop_id,
                    QueueItem.checked_in_at >= today_start_utc,
                    QueueItem.checked_in_at <= query_end_utc,
                )
                .scalar() or 0
            )
            today_completed = (
                session.query(func.count(QueueItem.id))
                .join(Queue)
                .filter(
                    Queue.shop_id == shop_id,
                    QueueItem.checked_in_at >= today_start_utc,
                    QueueItem.checked_in_at <= query_end_utc,
                    QueueItem.status == QueueStatus.COMPLETED,
                )
                .scalar() or 0
            )
            total_customers += today_all
            completed_services += today_completed
            if today_all > 0:
                days_with_data += 1

        new_customers = session.query(ShopCustomer).filter(
            ShopCustomer.shop_id == shop_id,
            ShopCustomer.created_at >= start_utc,
            ShopCustomer.created_at <= end_utc,
        ).count()

        repeat_customers = session.query(ShopCustomer).filter(
            ShopCustomer.shop_id == shop_id,
            ShopCustomer.visit_count > 1,
            ShopCustomer.last_visit >= start_utc,
            ShopCustomer.last_visit <= end_utc,
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


def _local_service_customer_counts(
    shop_id: int,
    query: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """Count completed customer visits grouped by service for a parsed time window."""
    session = None
    try:
        session = db_interface.get_session()
        from modules.queues.models import Queue, QueueItem, QueueStatus
        from modules.shops.models import ShopService
        from sqlalchemy import func

        shop_now = _now_for_shop(shop_id, session)
        tz_name = _resolve_shop_timezone_name(shop_id, session)
        start_dt, end_dt, _granularity, window = _parse_time_window(query or "", now=shop_now)
        start_utc = _to_utc_naive(start_dt)
        end_utc = _to_utc_naive(end_dt)

        # Completed visits are the safest definition of "attended/served".
        # Fall back to checked_in_at only when completed_at was not recorded.
        rows = (
            session.query(
                func.coalesce(ShopService.name, QueueItem.notes, "Unknown service").label("service_name"),
                func.count(QueueItem.id).label("customer_count"),
                func.coalesce(func.sum(QueueItem.service_cost), 0.0).label("revenue"),
            )
            .join(Queue, QueueItem.queue_id == Queue.id)
            .outerjoin(ShopService, QueueItem.service_id == ShopService.id)
            .filter(
                Queue.shop_id == shop_id,
                QueueItem.status == QueueStatus.COMPLETED,
                func.coalesce(QueueItem.completed_at, QueueItem.checked_in_at) >= start_utc,
                func.coalesce(QueueItem.completed_at, QueueItem.checked_in_at) <= end_utc,
            )
            .group_by(func.coalesce(ShopService.name, QueueItem.notes, "Unknown service"))
            .order_by(func.count(QueueItem.id).desc())
            .limit(max(1, min(int(limit or 20), 50)))
            .all()
        )

        services = [
            {
                "service_name": row.service_name,
                "customer_count": int(row.customer_count or 0),
                "revenue": round(float(row.revenue or 0.0), 2),
            }
            for row in rows
        ]

        return {
            "shop_id": shop_id,
            "query": query or "",
            "window": window,
            "window_display": _describe_time_window(window, start_dt, end_dt, "day"),
            "range_start": start_dt.strftime("%Y-%m-%d"),
            "range_end": end_dt.strftime("%Y-%m-%d"),
            "services": services,
            "total_customers": sum(item["customer_count"] for item in services),
            "total_revenue": round(sum(float(item["revenue"] or 0.0) for item in services), 2),
            "timezone": tz_name,
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        if session is not None:
            session.close()


def _local_export_report(shop_id: int, format: str = "csv") -> Dict[str, Any]:
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


def _local_create_invoice(
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


def _local_record_payment(
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


def _local_process_refund(
    shop_id: int,
    payment_id: int,
    refund_amount: Optional[float] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Refund a completed payment for a shop."""
    try:
        from agents.tools import payment_tools

        result = payment_tools.process_refund(
            shop_id=shop_id,
            payment_id=payment_id,
            refund_amount=refund_amount,
            reason=reason,
        )
        if result.get("error"):
            return result

        refunded_amount = result.get("refund_amount")
        if refunded_amount in (None, ""):
            refunded_amount = refund_amount

        if refunded_amount not in (None, ""):
            amount_text = f"${float(refunded_amount):.2f}"
        else:
            amount_text = "the requested amount"

        payment_status = str(result.get("status") or "refunded").replace("_", " ")
        return {
            **result,
            "message": f"Refunded payment {payment_id} for {amount_text}. Payment is now {payment_status}.",
        }
    except Exception as e:
        return {"error": str(e)}


def _local_list_invoices(
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


def _local_get_pos_summary(shop_id: int, date: Optional[str] = None) -> Dict[str, Any]:
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


def _local_answer_finance_question(
    shop_id: int,
    question: str,
    operation: Optional[str] = None,
    mode: str = "enabled",
) -> Dict[str, Any]:
    """Answer a finance read question through the guarded dynamic SQL engine."""
    try:
        from agents.tools import finance_query_engine

        result = finance_query_engine.answer_question(shop_id, question, mode=mode)
        if operation:
            result["operation"] = operation
        return result
    except Exception as e:
        return {
            "error": str(e),
            "error_class": type(e).__name__,
            "fallback_used": True,
            "shop_id": shop_id,
            "operation": operation,
        }


def daily_revenue(shop_id: int, date: Optional[str] = None) -> Dict[str, Any]:
    return _get_finance_client().daily_revenue(shop_id, date)


def weekly_summary(shop_id: int, week_start: Optional[str] = None) -> Dict[str, Any]:
    return _get_finance_client().weekly_summary(shop_id, week_start)


def trend_summary(shop_id: int, query: str) -> Dict[str, Any]:
    return _get_finance_client().trend_summary(shop_id, query)


def top_services(shop_id: int, limit: int = 5) -> Dict[str, Any]:
    return _get_finance_client().top_services(shop_id, limit)


def customer_metrics(shop_id: int, query: Optional[str] = None) -> Dict[str, Any]:
    return _get_finance_client().customer_metrics(shop_id, query=query)


def service_customer_counts(
    shop_id: int,
    query: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    return _get_finance_client().service_customer_counts(shop_id, query=query, limit=limit)


def export_report(shop_id: int, format: str = "csv") -> Dict[str, Any]:
    return _get_finance_client().export_report(shop_id, format)


def create_invoice(
    shop_id: int,
    service_name: str,
    unit_price: float,
    quantity: int = 1,
    customer_id: Optional[int] = None,
    tax_rate: float = 0.0,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    return _get_finance_client().create_invoice(
        shop_id,
        service_name,
        unit_price,
        quantity=quantity,
        customer_id=customer_id,
        tax_rate=tax_rate,
        notes=notes,
    )


def record_payment(
    shop_id: int,
    amount: float,
    method: str = "cash",
    invoice_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    return _get_finance_client().record_payment(
        shop_id,
        amount,
        method=method,
        invoice_id=invoice_id,
        notes=notes,
    )


def process_refund(
    shop_id: int,
    payment_id: int,
    refund_amount: Optional[float] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    return _get_finance_client().process_refund(
        shop_id,
        payment_id,
        refund_amount=refund_amount,
        reason=reason,
    )


def list_invoices(
    shop_id: int,
    status: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    return _get_finance_client().list_invoices(shop_id, status=status, limit=limit)


def get_pos_summary(shop_id: int, date: Optional[str] = None) -> Dict[str, Any]:
    return _get_finance_client().get_pos_summary(shop_id, date=date)


def answer_finance_question(
    shop_id: int,
    question: str,
    operation: Optional[str] = None,
    mode: str = "enabled",
) -> Dict[str, Any]:
    return _get_finance_client().answer_finance_question(
        shop_id,
        question,
        operation=operation,
        mode=mode,
    )


def get_inactive_clients(shop_id: int, days_threshold: int = 45) -> Dict[str, Any]:
    return _get_finance_client().get_inactive_clients(shop_id, days_threshold=days_threshold)


def get_top_clients(shop_id: int, limit: int = 10) -> Dict[str, Any]:
    return _get_finance_client().get_top_clients(shop_id, limit=limit)


def get_visit_frequency_summary(shop_id: int) -> Dict[str, Any]:
    return _get_finance_client().get_visit_frequency_summary(shop_id)


def get_client_profile(shop_id: int, client_id: int) -> Dict[str, Any]:
    return _get_finance_client().get_client_profile(shop_id, client_id)


def search_clients(shop_id: int, name: str) -> Dict[str, Any]:
    return _get_finance_client().search_clients(shop_id, name)
