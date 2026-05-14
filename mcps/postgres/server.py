"""Postgres MCP server — analytics and safe read queries over the ZeroQwait database."""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
import logging
import os
import sys

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import models  # noqa: F401
from database import SessionLocal  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("postgres-mcp")

app = FastAPI(title="ZeroQwait Postgres MCP", version="1.0.0")

# Only these tables may be read via the safe-query endpoint (allowlist).
ALLOWED_TABLES: frozenset = frozenset({
    "queues",
    "queue_items",
    "appointments",
    "shop_services",
    "shop_employees",
    "employee_shifts",
    "shops",
    "users",
    "shop_customers",
    "daily_analytics",
    "conversation_history",
    "inventory_items",
    "inventory_movements",
})


# ── Pydantic request models ────────────────────────────────────────────────────


class ShopRequest(BaseModel):
    shop_id: int


class DateRangeRequest(ShopRequest):
    days: int = 7


class CustomerHistoryRequest(ShopRequest):
    phone: str
    limit: int = 20


class SafeQueryRequest(ShopRequest):
    table: str
    filters: Optional[dict] = None
    limit: int = 50
    order_by: Optional[str] = None
    desc: bool = False


# ── Helper ─────────────────────────────────────────────────────────────────────


def _db():
    return SessionLocal()


# ── REST endpoints ─────────────────────────────────────────────────────────────


@app.post("/analytics/queue-volume")
async def rest_queue_volume(req: DateRangeRequest):
    """Daily queue volume (items completed) for the last N days."""
    since = date.today() - timedelta(days=req.days)
    db = _db()
    try:
        rows = db.execute(
            text(
                """
                SELECT
                    DATE(qi.checked_in_at) AS day,
                    COUNT(*) AS total,
                    SUM(CASE WHEN qi.status = 'COMPLETED' THEN 1 ELSE 0 END) AS served,
                    SUM(CASE WHEN qi.status = 'CANCELLED' THEN 1 ELSE 0 END) AS cancelled
                FROM queue_items qi
                JOIN queues q ON qi.queue_id = q.id
                WHERE q.shop_id = :shop_id
                  AND qi.checked_in_at >= :since
                  AND qi.status IN ('COMPLETED', 'CANCELLED')
                GROUP BY DATE(qi.checked_in_at)
                ORDER BY day ASC
                """
            ),
            {"shop_id": req.shop_id, "since": since},
        ).fetchall()
        return {
            "shop_id": req.shop_id,
            "days": req.days,
            "data": [dict(r._mapping) for r in rows],
        }
    finally:
        db.close()


@app.post("/analytics/peak-hours")
async def rest_peak_hours(req: DateRangeRequest):
    """Hourly check-in distribution for the last N days."""
    since = date.today() - timedelta(days=req.days)
    db = _db()
    try:
        rows = db.execute(
            text(
                """
                SELECT
                    EXTRACT(HOUR FROM qi.checked_in_at) AS hour,
                    COUNT(*) AS arrivals
                FROM queue_items qi
                JOIN queues q ON qi.queue_id = q.id
                WHERE q.shop_id = :shop_id
                  AND qi.checked_in_at >= :since
                GROUP BY hour
                ORDER BY hour ASC
                """
            ),
            {"shop_id": req.shop_id, "since": since},
        ).fetchall()
        return {
            "shop_id": req.shop_id,
            "days": req.days,
            "peak_hours": [dict(r._mapping) for r in rows],
        }
    finally:
        db.close()


@app.post("/analytics/wait-time-trend")
async def rest_wait_time_trend(req: DateRangeRequest):
    """Average wait time (minutes) per day for the last N days."""
    since = date.today() - timedelta(days=req.days)
    db = _db()
    try:
        rows = db.execute(
            text(
                """
                SELECT
                    DATE(qi.checked_in_at) AS day,
                    ROUND(
                        AVG(
                            EXTRACT(EPOCH FROM (qi.service_started_at - qi.checked_in_at)) / 60
                        )::numeric,
                        1
                    ) AS avg_wait_minutes
                FROM queue_items qi
                JOIN queues q ON qi.queue_id = q.id
                WHERE q.shop_id = :shop_id
                  AND qi.checked_in_at >= :since
                  AND qi.service_started_at IS NOT NULL
                  AND qi.status = 'COMPLETED'
                GROUP BY day
                ORDER BY day ASC
                """
            ),
            {"shop_id": req.shop_id, "since": since},
        ).fetchall()
        return {
            "shop_id": req.shop_id,
            "days": req.days,
            "data": [dict(r._mapping) for r in rows],
        }
    finally:
        db.close()


@app.post("/analytics/service-popularity")
async def rest_service_popularity(req: DateRangeRequest):
    """Most popular services by queue item count for the last N days."""
    since = date.today() - timedelta(days=req.days)
    db = _db()
    try:
        rows = db.execute(
            text(
                """
                SELECT
                    ss.name AS service_name,
                    COUNT(qi.id) AS total_served,
                    ROUND(AVG(qi.service_cost)::numeric, 2) AS avg_cost
                FROM queue_items qi
                JOIN queues q ON qi.queue_id = q.id
                JOIN shop_services ss ON qi.service_id = ss.id AND ss.shop_id = :shop_id
                WHERE q.shop_id = :shop_id
                  AND qi.checked_in_at >= :since
                  AND qi.status = 'COMPLETED'
                GROUP BY ss.name
                ORDER BY total_served DESC
                LIMIT 20
                """
            ),
            {"shop_id": req.shop_id, "since": since},
        ).fetchall()
        return {
            "shop_id": req.shop_id,
            "days": req.days,
            "services": [dict(r._mapping) for r in rows],
        }
    finally:
        db.close()


@app.post("/customers/history")
async def rest_customer_history(req: CustomerHistoryRequest):
    """Visit history for a customer phone number at a shop."""
    db = _db()
    try:
        rows = db.execute(
            text(
                """
                SELECT
                    qi.id,
                    qi.checked_in_at,
                    qi.completed_at,
                    qi.status,
                    qi.service_cost,
                    ss.name AS service_name
                FROM queue_items qi
                JOIN queues q ON qi.queue_id = q.id
                LEFT JOIN shop_services ss ON qi.service_id = ss.id
                WHERE q.shop_id = :shop_id
                  AND qi.customer_phone = :phone
                ORDER BY qi.checked_in_at DESC
                LIMIT :lim
                """
            ),
            {"shop_id": req.shop_id, "phone": req.phone, "lim": req.limit},
        ).fetchall()
        return {
            "shop_id": req.shop_id,
            "phone": req.phone,
            "visits": [dict(r._mapping) for r in rows],
        }
    finally:
        db.close()


@app.post("/query/safe")
async def rest_safe_query(req: SafeQueryRequest):
    """Read rows from an allowlisted table with optional equality filters."""
    table = req.table.lower().strip()
    if table not in ALLOWED_TABLES:
        raise HTTPException(
            status_code=400,
            detail=f"Table '{table}' is not in the allowed list. Allowed: {sorted(ALLOWED_TABLES)}",
        )
    if req.limit > 500:
        raise HTTPException(status_code=400, detail="limit cannot exceed 500")

    # Build WHERE clause from filters dict (equality only)
    where_parts = ["shop_id = :_shop_id"] if "shop_id" in _table_columns(table) else []
    params: dict = {"_shop_id": req.shop_id, "_limit": req.limit}

    if req.filters:
        for i, (col, val) in enumerate(req.filters.items()):
            # Only allow simple alphanumeric column names to prevent injection
            if not col.replace("_", "").isalnum():
                raise HTTPException(status_code=400, detail=f"Invalid column name: {col!r}")
            key = f"_f{i}"
            where_parts.append(f"{col} = :{key}")
            params[key] = val

    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    order_sql = ""
    if req.order_by:
        if not req.order_by.replace("_", "").isalnum():
            raise HTTPException(status_code=400, detail=f"Invalid order_by column: {req.order_by!r}")
        direction = "DESC" if req.desc else "ASC"
        order_sql = f"ORDER BY {req.order_by} {direction}"

    sql = f"SELECT * FROM {table} {where_sql} {order_sql} LIMIT :_limit"  # noqa: S608

    db = _db()
    try:
        rows = db.execute(text(sql), params).fetchall()
        return {
            "table": table,
            "count": len(rows),
            "rows": [dict(r._mapping) for r in rows],
        }
    except Exception as e:
        logger.error("safe_query error on table %s: %s", table, e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


def _table_columns(table: str) -> set:
    """Returns columns known to have shop_id for WHERE injection."""
    _shop_id_tables = {
        "queues", "appointments", "shop_services", "shop_employees",
        "shops", "shop_customers", "daily_analytics",
    }
    return {"shop_id"} if table in _shop_id_tables else set()


@app.get("/health")
async def health():
    db_ok = False
    try:
        db = _db()
        db.execute(text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception as e:
        logger.warning("DB health check failed: %s", e)
    return {"status": "ok" if db_ok else "degraded", "service": "postgres-mcp", "db_connected": db_ok}


# ── MCP tools ─────────────────────────────────────────────────────────────────


try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(
        name="zeroqwait-postgres",
        instructions="Direct PostgreSQL analytics and safe read-query tools for ZeroQwait.",
    )

    @mcp.tool(description="Get daily queue volume (completed items) for the last N days.")
    async def queue_volume(shop_id: int, days: int = 7) -> dict:
        return await rest_queue_volume(DateRangeRequest(shop_id=shop_id, days=days))

    @mcp.tool(description="Get hourly check-in distribution (peak hours) for the last N days.")
    async def peak_hours(shop_id: int, days: int = 7) -> dict:
        return await rest_peak_hours(DateRangeRequest(shop_id=shop_id, days=days))

    @mcp.tool(description="Get average wait time trend per day for the last N days.")
    async def wait_time_trend(shop_id: int, days: int = 7) -> dict:
        return await rest_wait_time_trend(DateRangeRequest(shop_id=shop_id, days=days))

    @mcp.tool(description="Get most popular services by completed visits for the last N days.")
    async def service_popularity(shop_id: int, days: int = 7) -> dict:
        return await rest_service_popularity(DateRangeRequest(shop_id=shop_id, days=days))

    @mcp.tool(description="Get visit history for a customer phone number at a shop.")
    async def customer_history(shop_id: int, phone: str, limit: int = 20) -> dict:
        return await rest_customer_history(CustomerHistoryRequest(shop_id=shop_id, phone=phone, limit=limit))

    @mcp.tool(
        description=(
            "Read rows from an allowlisted table with optional equality filters. "
            "Allowed tables: queues, queue_items, appointments, shop_services, "
            "shop_employees, employee_shifts, shops, users, shop_customers, "
            "daily_analytics, conversation_history."
        )
    )
    async def safe_query(
        shop_id: int,
        table: str,
        filters: Optional[dict] = None,
        limit: int = 50,
        order_by: Optional[str] = None,
        desc: bool = False,
    ) -> dict:
        return await rest_safe_query(
            SafeQueryRequest(
                shop_id=shop_id,
                table=table,
                filters=filters,
                limit=limit,
                order_by=order_by,
                desc=desc,
            )
        )

    try:
        app.mount("/mcp", mcp.sse_app())
    except AttributeError:
        logger.info("FastMCP SSE app not available; stdio MCP remains available.")
except ImportError:
    logger.warning("mcp package not installed — REST API remains available.")


if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8894")))
