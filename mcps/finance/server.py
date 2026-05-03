"""Finance MCP server for revenue, analytics, and finance operations."""

from pathlib import Path
from typing import Optional
import logging
import os
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from agents.tools import client_insights_tools, finance_tools


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


class TrendSummaryRequest(ShopRequest):
    query: str


class CustomerMetricsRequest(ShopRequest):
    query: Optional[str] = None


class CreateInvoiceRequest(ShopRequest):
    service_name: str
    unit_price: float
    quantity: int = 1
    customer_id: Optional[int] = None
    tax_rate: float = 0.0
    notes: Optional[str] = None


class RecordPaymentRequest(ShopRequest):
    amount: float
    method: str = "cash"
    invoice_id: Optional[int] = None
    notes: Optional[str] = None


class RefundPaymentRequest(ShopRequest):
    payment_id: int
    refund_amount: Optional[float] = None
    reason: Optional[str] = None


class ListInvoicesRequest(ShopRequest):
    status: Optional[str] = None
    limit: int = 20


class PosSummaryRequest(ShopRequest):
    date: Optional[str] = None


class QueryAnswerRequest(ShopRequest):
    question: str
    operation: Optional[str] = None
    mode: str = "enabled"


class InactiveClientsRequest(ShopRequest):
    days_threshold: int = 45


class TopClientsRequest(ShopRequest):
    limit: int = 10


class ClientProfileRequest(ShopRequest):
    client_id: int


class SearchClientsRequest(ShopRequest):
    name: str


@app.post("/revenue/daily")
async def rest_daily_revenue(req: DailyRevenueRequest):
    return finance_tools._local_daily_revenue(req.shop_id, req.date)


@app.post("/revenue/weekly")
async def rest_weekly_summary(req: WeeklySummaryRequest):
    return finance_tools._local_weekly_summary(req.shop_id, req.week_start)


@app.post("/revenue/trend")
async def rest_trend_summary(req: TrendSummaryRequest):
    return finance_tools._local_trend_summary(req.shop_id, req.query)


@app.post("/services/top")
async def rest_top_services(req: TopServicesRequest):
    return finance_tools._local_top_services(req.shop_id, req.limit)


@app.post("/customers/metrics")
async def rest_customer_metrics(req: CustomerMetricsRequest):
    return finance_tools._local_customer_metrics(req.shop_id, req.query)


@app.post("/reports/export")
async def rest_export_report(req: ExportReportRequest):
    return finance_tools._local_export_report(req.shop_id, req.format)


@app.post("/invoices/create")
async def rest_create_invoice(req: CreateInvoiceRequest):
    return finance_tools._local_create_invoice(
        req.shop_id,
        req.service_name,
        req.unit_price,
        quantity=req.quantity,
        customer_id=req.customer_id,
        tax_rate=req.tax_rate,
        notes=req.notes,
    )


@app.post("/payments/record")
async def rest_record_payment(req: RecordPaymentRequest):
    return finance_tools._local_record_payment(
        req.shop_id,
        req.amount,
        method=req.method,
        invoice_id=req.invoice_id,
        notes=req.notes,
    )


@app.post("/payments/refund")
async def rest_process_refund(req: RefundPaymentRequest):
    return finance_tools._local_process_refund(
        req.shop_id,
        req.payment_id,
        refund_amount=req.refund_amount,
        reason=req.reason,
    )


@app.post("/invoices/list")
async def rest_list_invoices(req: ListInvoicesRequest):
    return finance_tools._local_list_invoices(req.shop_id, status=req.status, limit=req.limit)


@app.post("/pos/summary")
async def rest_get_pos_summary(req: PosSummaryRequest):
    return finance_tools._local_get_pos_summary(req.shop_id, req.date)


@app.post("/query/answer")
async def rest_answer_finance_question(req: QueryAnswerRequest):
    return await run_in_threadpool(
        finance_tools._local_answer_finance_question,
        req.shop_id,
        req.question,
        req.operation,
        req.mode,
    )


@app.post("/clients/inactive")
async def rest_get_inactive_clients(req: InactiveClientsRequest):
    return {"clients": client_insights_tools.get_inactive_clients(req.shop_id, req.days_threshold), "shop_id": req.shop_id}


@app.post("/clients/top")
async def rest_get_top_clients(req: TopClientsRequest):
    return {"clients": client_insights_tools.get_top_clients(req.shop_id, req.limit), "shop_id": req.shop_id}


@app.post("/clients/visit-frequency")
async def rest_get_visit_frequency_summary(req: ShopRequest):
    return client_insights_tools.get_visit_frequency_summary(req.shop_id)


@app.post("/clients/profile")
async def rest_get_client_profile(req: ClientProfileRequest):
    return client_insights_tools.get_client_profile(req.shop_id, req.client_id)


@app.post("/clients/search")
async def rest_search_clients(req: SearchClientsRequest):
    return {"clients": client_insights_tools.get_client_search(req.shop_id, req.name), "shop_id": req.shop_id}


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

    @mcp.tool(description="Return a trend summary for a natural-language finance window.")
    async def trend_summary(shop_id: int, query: str) -> dict:
        return await rest_trend_summary(TrendSummaryRequest(shop_id=shop_id, query=query))

    @mcp.tool(description="Return the top services by revenue for a shop.")
    async def top_services(shop_id: int, limit: int = 5) -> dict:
        return await rest_top_services(TopServicesRequest(shop_id=shop_id, limit=limit))

    @mcp.tool(description="Return customer metrics for a shop.")
    async def customer_metrics(shop_id: int, query: Optional[str] = None) -> dict:
        return await rest_customer_metrics(CustomerMetricsRequest(shop_id=shop_id, query=query))

    @mcp.tool(description="Export a weekly finance report for a shop.")
    async def export_report(shop_id: int, format: str = "csv") -> dict:
        return await rest_export_report(ExportReportRequest(shop_id=shop_id, format=format))

    @mcp.tool(description="Create an invoice for a service.")
    async def create_invoice(
        shop_id: int,
        service_name: str,
        unit_price: float,
        quantity: int = 1,
        customer_id: Optional[int] = None,
        tax_rate: float = 0.0,
        notes: Optional[str] = None,
    ) -> dict:
        return await rest_create_invoice(
            CreateInvoiceRequest(
                shop_id=shop_id,
                service_name=service_name,
                unit_price=unit_price,
                quantity=quantity,
                customer_id=customer_id,
                tax_rate=tax_rate,
                notes=notes,
            )
        )

    @mcp.tool(description="Record a payment for a shop.")
    async def record_payment(
        shop_id: int,
        amount: float,
        method: str = "cash",
        invoice_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> dict:
        return await rest_record_payment(
            RecordPaymentRequest(
                shop_id=shop_id,
                amount=amount,
                method=method,
                invoice_id=invoice_id,
                notes=notes,
            )
        )

    @mcp.tool(description="Refund a completed payment for a shop.")
    async def process_refund(
        shop_id: int,
        payment_id: int,
        refund_amount: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> dict:
        return await rest_process_refund(
            RefundPaymentRequest(
                shop_id=shop_id,
                payment_id=payment_id,
                refund_amount=refund_amount,
                reason=reason,
            )
        )

    @mcp.tool(description="List invoices for a shop.")
    async def list_invoices(shop_id: int, status: Optional[str] = None, limit: int = 20) -> dict:
        return await rest_list_invoices(ListInvoicesRequest(shop_id=shop_id, status=status, limit=limit))

    @mcp.tool(description="Return POS summary for a shop and date.")
    async def get_pos_summary(shop_id: int, date: Optional[str] = None) -> dict:
        return await rest_get_pos_summary(PosSummaryRequest(shop_id=shop_id, date=date))

    @mcp.tool(description="Answer a finance read question with the guarded dynamic SQL query engine.")
    async def answer_finance_question(shop_id: int, question: str, operation: Optional[str] = None, mode: str = "enabled") -> dict:
        return await rest_answer_finance_question(
            QueryAnswerRequest(shop_id=shop_id, question=question, operation=operation, mode=mode)
        )

    @mcp.tool(description="Return inactive clients for a shop.")
    async def get_inactive_clients(shop_id: int, days_threshold: int = 45) -> dict:
        return await rest_get_inactive_clients(InactiveClientsRequest(shop_id=shop_id, days_threshold=days_threshold))

    @mcp.tool(description="Return top clients for a shop.")
    async def get_top_clients(shop_id: int, limit: int = 10) -> dict:
        return await rest_get_top_clients(TopClientsRequest(shop_id=shop_id, limit=limit))

    @mcp.tool(description="Return client visit frequency summary for a shop.")
    async def get_visit_frequency_summary(shop_id: int) -> dict:
        return await rest_get_visit_frequency_summary(ShopRequest(shop_id=shop_id))

    @mcp.tool(description="Return a specific client profile for a shop.")
    async def get_client_profile(shop_id: int, client_id: int) -> dict:
        return await rest_get_client_profile(ClientProfileRequest(shop_id=shop_id, client_id=client_id))

    @mcp.tool(description="Search clients for a shop by name.")
    async def search_clients(shop_id: int, name: str) -> dict:
        return await rest_search_clients(SearchClientsRequest(shop_id=shop_id, name=name))

    try:
        app.mount("/mcp", mcp.sse_app())
    except AttributeError:
        logger.info("FastMCP SSE app not available; stdio MCP remains available.")
except ImportError:
    logger.warning("mcp package not installed — REST API remains available.")


if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8891")))
