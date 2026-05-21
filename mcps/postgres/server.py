"""Postgres MCP server — analytics and safe read queries over the ZeroQwait database."""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
import logging
import os
import re
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

# ── raw_read security ─────────────────────────────────────────────────────────
# Maximum rows returned by a single raw_read call.
_RAW_READ_MAX_ROWS = 500

# DML / DDL keywords that must not appear (word-boundary matched) in a read query.
_WRITE_KEYWORDS: frozenset[str] = frozenset({
    "insert", "update", "delete", "drop", "truncate",
    "alter", "create", "grant", "revoke",
})

# Dangerous sub-sequences blocked by substring match (no word boundary needed).
_BLOCKED_SEQUENCES: tuple[str, ...] = ("--", "/*", "*/", ";--", "xp_", "0x")

# SELECT INTO creates a new table — block it as a phrase.
_SELECT_INTO_RE = re.compile(r"\bselect\b.+\binto\b", re.IGNORECASE | re.DOTALL)


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


class RawReadRequest(ShopRequest):
    sql: str
    params: Optional[dict] = None
    limit: int = 100


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


@app.post("/query/raw_read")
async def rest_raw_read(req: RawReadRequest):
    """
    Execute any read-only SELECT query with shop_id tenant enforcement.

    Security rules (all enforced server-side, cannot be bypassed by the caller):
    - Query MUST start with SELECT
    - No write / DDL keywords (INSERT, UPDATE, DELETE, DROP, TRUNCATE, ALTER, CREATE, GRANT, REVOKE)
    - No comment sequences (-- /* */ ;-- xp_ 0x)
    - No SELECT INTO (table-creation via SELECT)
    - No semicolons (blocks multi-statement injection)
    - shop_id injected as :_shop_id — the AI's SQL should reference it so
      one shop never accidentally reads another shop's rows
    - Row count hard-capped at min(req.limit, 500)
    """
    if req.limit > _RAW_READ_MAX_ROWS:
        raise HTTPException(status_code=400, detail=f"limit cannot exceed {_RAW_READ_MAX_ROWS}")

    sql = req.sql.strip()
    sql_lower = sql.lower()

    # 1. Must start with SELECT or WITH (CTEs start with WITH ... SELECT)
    if not (sql_lower.startswith("select") or sql_lower.startswith("with")):
        raise HTTPException(status_code=400, detail="Only SELECT queries are allowed (may start with WITH for CTEs)")

    # 2. No semicolons (multi-statement injection)
    if ";" in sql:
        raise HTTPException(status_code=400, detail="Multiple statements are not allowed (semicolon detected)")

    # 3. Block dangerous sub-sequences
    for seq in _BLOCKED_SEQUENCES:
        if seq in sql_lower:
            raise HTTPException(status_code=400, detail=f"Blocked sequence: {seq!r}")

    # 4. Block write / DDL keywords (word-boundary match avoids false positives
    #    e.g. 'created_at' does not match 'create', 'deleted_at' does not match 'delete')
    for kw in _WRITE_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", sql_lower):
            raise HTTPException(status_code=400, detail=f"Blocked keyword: {kw!r}")

    # 5. Block SELECT INTO (writes data to a new table)
    if _SELECT_INTO_RE.search(sql_lower):
        raise HTTPException(status_code=400, detail="SELECT INTO is not allowed")

    # 6. Require :_shop_id placeholder — ensures tenant scoping is explicit in SQL
    if ":_shop_id" not in sql:
        raise HTTPException(
            status_code=400,
            detail="SQL must reference :_shop_id for tenant scoping (e.g. WHERE shop_id = :_shop_id)"
        )

    # 7. Merge caller params and inject shop_id (caller cannot override _shop_id)
    merged_params: dict = {k: v for k, v in (req.params or {}).items()}
    merged_params["_shop_id"] = req.shop_id  # always overwritten — tenant isolation

    db = _db()
    try:
        rows = db.execute(text(sql), merged_params).fetchmany(req.limit)
        return {
            "shop_id": req.shop_id,
            "count": len(rows),
            "rows": [dict(r._mapping) for r in rows],
        }
    except Exception as e:
        logger.error("raw_read error shop_id=%s: %s", req.shop_id, e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


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

    @mcp.tool(
        description=(
            "Run any complex read-only SELECT for a specific shop. "
            "Use this for multi-table JOINs, GROUP BY aggregations, window functions, "
            "subqueries, CTEs, BETWEEN/LIKE/IN filters — anything the named tools can't express. "
            "shop_id is automatically injected as :_shop_id in every query for tenant isolation. "
            "Your SQL MUST reference :_shop_id to scope results to the correct shop. "
            "No writes allowed: INSERT/UPDATE/DELETE/DROP/ALTER are blocked server-side. "
            "Example: SELECT ss.name, COUNT(*) FROM queue_items qi "
            "JOIN queues q ON qi.queue_id = q.id "
            "JOIN shop_services ss ON qi.service_id = ss.id "
            "WHERE q.shop_id = :_shop_id GROUP BY ss.name ORDER BY 2 DESC"
        )
    )
    async def raw_read(
        shop_id: int,
        sql: str,
        params: Optional[dict] = None,
        limit: int = 100,
    ) -> dict:
        return await rest_raw_read(
            RawReadRequest(shop_id=shop_id, sql=sql, params=params, limit=limit)
        )

    try:
        app.mount("/mcp", mcp.sse_app())
    except AttributeError:
        logger.info("FastMCP SSE app not available; stdio MCP remains available.")
except ImportError:
    logger.warning("mcp package not installed — REST API remains available.")


if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8894")))
