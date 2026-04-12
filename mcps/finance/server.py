"""Finance MCP server for revenue and analytics operations."""

from csv import DictWriter
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import Optional
import logging
import os
import sys

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import func


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal
import models  # noqa: F401
from modules.queues.models import Queue, QueueItem
from modules.shops.models import DailyAnalytics, ShopCustomer, ShopService


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("finance-mcp")

app = FastAPI(title="ZeroQwait Finance MCP", version="1.0.0")


class ShopRequest(BaseModel):
    shop_id: int


class DailyRevenueRequest(ShopRequest):
    date: Optional[str] = None


class WeeklySummaryRequest(ShopRequest):
    week_start: Optional[str] = None


class TopServicesRequest(ShopRequest):
    limit: int = 5


class ExportReportRequest(ShopRequest):
    format: str = "csv"


def _coerce_date(raw_date: Optional[str]) -> datetime:
    if raw_date:
        return datetime.fromisoformat(raw_date)
    return datetime.now(timezone.utc)


def _daily_revenue_payload(shop_id: int, target_date: datetime) -> dict:
    db = SessionLocal()
    try:
        day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        analytics = db.query(DailyAnalytics).filter(
            DailyAnalytics.shop_id == shop_id,
            DailyAnalytics.date >= day_start,
            DailyAnalytics.date < day_end,
        ).first()
        if analytics:
            revenue = float(analytics.total_revenue or 0.0)
            customers = int(analytics.total_customers or 0)
            services_completed = int(analytics.completed_services or 0)
        else:
            rows = db.query(QueueItem).join(Queue, Queue.id == QueueItem.queue_id).filter(
                Queue.shop_id == shop_id,
                QueueItem.status == "completed",
                QueueItem.completed_at >= day_start,
                QueueItem.completed_at < day_end,
            ).all()
            revenue = float(sum(float(row.service_cost or 0.0) for row in rows))
            customers = len(rows)
            services_completed = len(rows)
        average = revenue / customers if customers else 0.0
        return {
            "shop_id": shop_id,
            "date": day_start.date().isoformat(),
            "total_revenue": round(revenue, 2),
            "transaction_count": customers,
            "completed_services": services_completed,
            "average_transaction": round(average, 2),
        }
    finally:
        db.close()


@app.post("/revenue/daily")
async def rest_daily_revenue(req: DailyRevenueRequest):
    return _daily_revenue_payload(req.shop_id, _coerce_date(req.date))


@app.post("/revenue/weekly")
async def rest_weekly_summary(req: WeeklySummaryRequest):
    start = _coerce_date(req.week_start).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    db = SessionLocal()
    try:
        analytics_rows = db.query(DailyAnalytics).filter(
            DailyAnalytics.shop_id == req.shop_id,
            DailyAnalytics.date >= start,
            DailyAnalytics.date < end,
        ).all()
        total_revenue = round(sum(float(row.total_revenue or 0.0) for row in analytics_rows), 2)
        total_customers = int(sum(int(row.total_customers or 0) for row in analytics_rows))
        completed_services = int(sum(int(row.completed_services or 0) for row in analytics_rows))
        best_day = None
        if analytics_rows:
            best = max(analytics_rows, key=lambda row: float(row.total_revenue or 0.0))
            best_day = best.date.date().isoformat()
        avg_transaction = round(total_revenue / total_customers, 2) if total_customers else 0.0
        return {
            "shop_id": req.shop_id,
            "week_start": start.date().isoformat(),
            "week_end": (end - timedelta(days=1)).date().isoformat(),
            "total_revenue": total_revenue,
            "transaction_count": total_customers,
            "completed_services": completed_services,
            "average_transaction": avg_transaction,
            "best_day": best_day,
        }
    finally:
        db.close()


@app.post("/services/top")
async def rest_top_services(req: TopServicesRequest):
    db = SessionLocal()
    try:
        rows = (
            db.query(
                ShopService.id,
                ShopService.name,
                func.count(QueueItem.id).label("service_count"),
                func.coalesce(func.sum(QueueItem.service_cost), 0.0).label("revenue"),
            )
            .outerjoin(QueueItem, QueueItem.service_id == ShopService.id)
            .filter(ShopService.shop_id == req.shop_id)
            .group_by(ShopService.id, ShopService.name)
            .order_by(func.coalesce(func.sum(QueueItem.service_cost), 0.0).desc())
            .limit(req.limit)
            .all()
        )
        services = [
            {
                "service_id": row.id,
                "name": row.name,
                "count": int(row.service_count or 0),
                "revenue": round(float(row.revenue or 0.0), 2),
            }
            for row in rows
        ]
        return {"shop_id": req.shop_id, "services": services}
    finally:
        db.close()


@app.post("/customers/metrics")
async def rest_customer_metrics(req: ShopRequest):
    db = SessionLocal()
    try:
        customers = db.query(ShopCustomer).filter(ShopCustomer.shop_id == req.shop_id).all()
        total_customers = len(customers)
        repeat_customers = len([customer for customer in customers if int(customer.visit_count or 0) > 1])
        revenue_rows = (
            db.query(QueueItem.customer_phone, func.coalesce(func.sum(QueueItem.service_cost), 0.0).label("revenue"))
            .join(Queue, Queue.id == QueueItem.queue_id)
            .filter(Queue.shop_id == req.shop_id, QueueItem.status == "completed")
            .group_by(QueueItem.customer_phone)
            .all()
        )
        avg_ltv = round(
            sum(float(row.revenue or 0.0) for row in revenue_rows) / len(revenue_rows),
            2,
        ) if revenue_rows else 0.0
        return {
            "shop_id": req.shop_id,
            "total_customers": total_customers,
            "repeat_customers": repeat_customers,
            "repeat_rate": round(repeat_customers / total_customers, 2) if total_customers else 0.0,
            "average_ltv": avg_ltv,
        }
    finally:
        db.close()


@app.post("/reports/export")
async def rest_export_report(req: ExportReportRequest):
    if req.format.lower() != "csv":
        return {"error": "Only csv export is supported in Phase 3"}
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)
    db = SessionLocal()
    try:
        rows = (
            db.query(QueueItem)
            .join(Queue, Queue.id == QueueItem.queue_id)
            .filter(Queue.shop_id == req.shop_id, QueueItem.completed_at >= start)
            .order_by(QueueItem.completed_at.desc())
            .limit(500)
            .all()
        )
        buffer = StringIO()
        fieldnames = ["completed_at", "customer_name", "service_id", "service_cost", "status"]
        writer = DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "completed_at": row.completed_at.isoformat() if row.completed_at else "",
                    "customer_name": row.customer_name,
                    "service_id": row.service_id,
                    "service_cost": float(row.service_cost or 0.0),
                    "status": row.status.value if hasattr(row.status, "value") else row.status,
                }
            )
        return {
            "shop_id": req.shop_id,
            "format": "csv",
            "filename": f"shop_{req.shop_id}_weekly_report.csv",
            "row_count": len(rows),
            "content": buffer.getvalue(),
        }
    finally:
        db.close()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "finance-mcp"}


try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(
        name="zeroqwait-finance",
        instructions="Revenue and analytics tools for ZeroQwait.",
    )

    @mcp.tool(description="Return daily revenue metrics for a shop.")
    async def daily_revenue(shop_id: int, date: Optional[str] = None) -> dict:
        return await rest_daily_revenue(DailyRevenueRequest(shop_id=shop_id, date=date))

    @mcp.tool(description="Return weekly revenue summary for a shop.")
    async def weekly_summary(shop_id: int, week_start: Optional[str] = None) -> dict:
        return await rest_weekly_summary(WeeklySummaryRequest(shop_id=shop_id, week_start=week_start))

    @mcp.tool(description="Return the top services by revenue for a shop.")
    async def top_services(shop_id: int, limit: int = 5) -> dict:
        return await rest_top_services(TopServicesRequest(shop_id=shop_id, limit=limit))

    @mcp.tool(description="Return customer metrics for a shop.")
    async def customer_metrics(shop_id: int) -> dict:
        return await rest_customer_metrics(ShopRequest(shop_id=shop_id))

    @mcp.tool(description="Export a weekly finance report for a shop.")
    async def export_report(shop_id: int, format: str = "csv") -> dict:
        return await rest_export_report(ExportReportRequest(shop_id=shop_id, format=format))

    try:
        app.mount("/mcp", mcp.sse_app())
    except AttributeError:
        logger.info("FastMCP SSE app not available; stdio MCP remains available.")
except ImportError:
    logger.warning("mcp package not installed — REST API remains available.")


if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8891")))
