from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from sqlalchemy import desc, func, or_

from db_interface import db_interface


def _now() -> datetime:
    return datetime.now()


def _days_since(value: Optional[datetime]) -> Optional[int]:
    if not value:
        return None
    return max(0, (_now() - value).days)


def _as_date_string(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    return value.strftime("%Y-%m-%d")


def _contact_value(client: Any) -> Optional[str]:
    return getattr(client, "email", None) or getattr(client, "phone", None)


def _client_match_filters(client: Any) -> List[Any]:
    from models import QueueItem

    filters = []
    if getattr(client, "phone", None):
        filters.append(QueueItem.customer_phone == client.phone)
    if getattr(client, "email", None):
        filters.append(QueueItem.customer_email == client.email)
    if getattr(client, "name", None):
        filters.append(QueueItem.customer_name == client.name)
    return filters


def _get_client_service_history(session: Any, shop_id: int, client: Any) -> List[Dict[str, Any]]:
    from models import Queue, QueueItem, QueueStatus, ShopService

    filters = _client_match_filters(client)
    if not filters:
        return []

    rows = (
        session.query(QueueItem, ShopService)
        .join(Queue, QueueItem.queue_id == Queue.id)
        .outerjoin(ShopService, QueueItem.service_id == ShopService.id)
        .filter(
            Queue.shop_id == shop_id,
            QueueItem.status == QueueStatus.COMPLETED,
            or_(*filters),
        )
        .order_by(QueueItem.completed_at.asc(), QueueItem.checked_in_at.asc())
        .all()
    )

    history: List[Dict[str, Any]] = []
    for queue_item, service in rows:
        service_name = getattr(service, "name", None)
        completed_at = getattr(queue_item, "completed_at", None) or getattr(queue_item, "checked_in_at", None)
        history.append(
            {
                "service_name": service_name,
                "completed_at": completed_at,
                "price": getattr(queue_item, "service_cost", None),
            }
        )
    return history


def _most_booked_service(history: List[Dict[str, Any]]) -> Optional[str]:
    counts: Dict[str, int] = {}
    for entry in history:
        service_name = entry.get("service_name")
        if not service_name:
            continue
        counts[service_name] = counts.get(service_name, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


def _avg_days_between_visits(history: List[Dict[str, Any]]) -> Optional[float]:
    visit_dates = []
    seen = set()
    for entry in history:
        completed_at = entry.get("completed_at")
        if not completed_at:
            continue
        visit_day = completed_at.date()
        if visit_day in seen:
            continue
        seen.add(visit_day)
        visit_dates.append(completed_at)

    visit_dates.sort()
    if len(visit_dates) < 2:
        return None

    gaps = []
    for index in range(1, len(visit_dates)):
        gaps.append((visit_dates[index] - visit_dates[index - 1]).days)
    if not gaps:
        return None
    return round(sum(gaps) / len(gaps), 1)


def _last_service(history: List[Dict[str, Any]]) -> Optional[str]:
    for entry in reversed(history):
        if entry.get("service_name"):
            return entry["service_name"]
    return None


def get_inactive_clients(shop_id: int, days_threshold: int = 45) -> List[Dict[str, Any]]:
    session = None
    try:
        from models import ShopCustomer

        session = db_interface.get_session()
        cutoff = _now() - timedelta(days=days_threshold)
        clients = (
            session.query(ShopCustomer)
            .filter(
                ShopCustomer.shop_id == shop_id,
                ShopCustomer.last_visit < cutoff,
            )
            .order_by(ShopCustomer.last_visit.asc())
            .all()
        )

        result = []
        for client in clients:
            days_inactive = _days_since(getattr(client, "last_visit", None))
            result.append(
                {
                    "id": client.id,
                    "name": client.name,
                    "contact": _contact_value(client),
                    "last_visit": _as_date_string(client.last_visit),
                    "days_inactive": days_inactive,
                    "visit_count": int(getattr(client, "visit_count", 0) or 0),
                }
            )

        result.sort(key=lambda item: item.get("days_inactive") or 0, reverse=True)
        return result
    except Exception:
        raise
    finally:
        if session is not None:
            session.close()


def get_top_clients(shop_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    session = None
    try:
        from models import ShopCustomer

        session = db_interface.get_session()
        clients = (
            session.query(ShopCustomer)
            .filter(ShopCustomer.shop_id == shop_id)
            .order_by(desc(ShopCustomer.visit_count), desc(ShopCustomer.last_visit))
            .limit(limit)
            .all()
        )

        return [
            {
                "id": client.id,
                "name": client.name,
                "visit_count": int(getattr(client, "visit_count", 0) or 0),
                "last_visit": _as_date_string(client.last_visit),
                "days_since_last_visit": _days_since(getattr(client, "last_visit", None)),
            }
            for client in clients
        ]
    except Exception:
        raise
    finally:
        if session is not None:
            session.close()


def get_client_profile(shop_id: int, client_id: int) -> Dict[str, Any]:
    session = None
    try:
        from models import ShopCustomer

        session = db_interface.get_session()
        client = (
            session.query(ShopCustomer)
            .filter(
                ShopCustomer.shop_id == shop_id,
                ShopCustomer.id == client_id,
            )
            .first()
        )
        if not client:
            return {"error": "Client not found", "shop_id": shop_id, "client_id": client_id}

        history = _get_client_service_history(session, shop_id, client)
        most_booked_service = _most_booked_service(history)
        avg_visit_gap = _avg_days_between_visits(history)
        days_since_last_visit = _days_since(getattr(client, "last_visit", None))
        summary_parts = []
        if avg_visit_gap is not None:
            summary_parts.append(f"{client.name} visits every ~{round(avg_visit_gap)} days.")
        else:
            summary_parts.append(f"{client.name} has limited repeat-visit history recorded.")
        summary_parts.append(
            f"Most popular service: {most_booked_service or 'Unknown'}."
        )
        summary_parts.append(
            f"Last visit: {_as_date_string(client.last_visit) or 'Unknown'} ({days_since_last_visit if days_since_last_visit is not None else 'unknown'} days ago)."
        )

        return {
            "id": client.id,
            "shop_id": shop_id,
            "name": client.name,
            "phone": client.phone,
            "email": client.email,
            "created_at": _as_date_string(client.created_at),
            "visit_count": int(getattr(client, "visit_count", 0) or 0),
            "last_visit": _as_date_string(client.last_visit),
            "days_since_last_visit": days_since_last_visit,
            "most_booked_service": most_booked_service,
            "avg_days_between_visits": avg_visit_gap,
            "appointment_history_count": len(history),
            "summary": " ".join(summary_parts),
        }
    except Exception:
        raise
    finally:
        if session is not None:
            session.close()


def get_visit_frequency_summary(shop_id: int) -> Dict[str, Any]:
    session = None
    try:
        from models import ShopCustomer

        session = db_interface.get_session()
        clients = session.query(ShopCustomer).filter(ShopCustomer.shop_id == shop_id).all()
        total = len(clients)
        now = _now()

        regulars = 0
        at_risk = 0
        lapsed = 0
        new = 0

        for client in clients:
            last_visit = getattr(client, "last_visit", None)
            created_at = getattr(client, "created_at", None)
            visit_count = int(getattr(client, "visit_count", 0) or 0)
            days_since_last = (now - last_visit).days if last_visit else None
            days_since_created = (now - created_at).days if created_at else None

            if days_since_created is not None and days_since_created <= 30 and visit_count == 1:
                new += 1
            if days_since_last is None:
                continue
            if days_since_last <= 30:
                regulars += 1
            elif days_since_last <= 60:
                at_risk += 1
            else:
                lapsed += 1

        def _pct(count: int) -> float:
            return round((count / total) * 100, 1) if total else 0.0

        return {
            "shop_id": shop_id,
            "total_clients": total,
            "regulars": {"count": regulars, "percentage": _pct(regulars)},
            "at_risk": {"count": at_risk, "percentage": _pct(at_risk)},
            "lapsed": {"count": lapsed, "percentage": _pct(lapsed)},
            "new": {"count": new, "percentage": _pct(new)},
        }
    except Exception:
        raise
    finally:
        if session is not None:
            session.close()


def get_client_search(shop_id: int, name: str) -> List[Dict[str, Any]]:
    session = None
    try:
        from models import ShopCustomer

        session = db_interface.get_session()
        clients = (
            session.query(ShopCustomer)
            .filter(
                ShopCustomer.shop_id == shop_id,
                ShopCustomer.name.ilike(f"%{name}%"),
            )
            .order_by(desc(ShopCustomer.visit_count), desc(ShopCustomer.last_visit))
            .all()
        )

        results = []
        for client in clients:
            history = _get_client_service_history(session, shop_id, client)
            results.append(
                {
                    "id": client.id,
                    "name": client.name,
                    "visit_count": int(getattr(client, "visit_count", 0) or 0),
                    "last_visit": _as_date_string(client.last_visit),
                    "days_since_last_visit": _days_since(getattr(client, "last_visit", None)),
                    "last_service": _last_service(history),
                }
            )
        return results
    except Exception:
        raise
    finally:
        if session is not None:
            session.close()