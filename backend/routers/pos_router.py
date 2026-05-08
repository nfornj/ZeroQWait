"""pos_router.py — REST endpoints for POS management."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from database import SessionLocal
from shared.auth_utils import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pos", tags=["pos"])


def _assert_owner(shop_id: int, current_user: dict) -> None:
    with SessionLocal() as session:
        row = session.execute(
            text("SELECT owner_id FROM shops WHERE id = :shop_id"),
            {"shop_id": shop_id},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Shop not found")
    if row[0] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not your shop")


# ── Request models ─────────────────────────────────────────────────────────────

class StartSessionRequest(BaseModel):
    customer_name: Optional[str] = None
    employee_id: Optional[int] = None


class AddLineRequest(BaseModel):
    session_id: str
    service_id: Optional[int] = None
    item_id: Optional[int] = None
    description: Optional[str] = None
    quantity: float = 1.0
    unit_price_cents: Optional[int] = None
    hst_applicable: bool = True


class TipRequest(BaseModel):
    session_id: str
    tip_cents: int = Field(..., ge=0)


class DiscountRequest(BaseModel):
    session_id: str
    discount_pct: Optional[float] = Field(None, ge=0, le=100)
    discount_cents: Optional[int] = Field(None, ge=0)


class CompleteCheckoutRequest(BaseModel):
    session_id: str
    payment_method: str = "cash"
    send_receipt: bool = False


class RefundRequest(BaseModel):
    transaction_id: int
    reason: Optional[str] = None
    amount_cents: Optional[int] = None


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/shop/{shop_id}/session", status_code=201)
def start_session(
    shop_id: int,
    body: StartSessionRequest,
    current_user: dict = Depends(get_current_user),
):
    """Start a new POS checkout session."""
    _assert_owner(shop_id, current_user)
    from agents.pos_agent import _new_session, _calculate_totals
    sid, data = _new_session(shop_id, customer_name=body.customer_name, employee_id=body.employee_id)
    return {"session_id": sid, "status": "open", "totals": _calculate_totals(data)}


@router.post("/shop/{shop_id}/session/line")
def add_line(
    shop_id: int,
    body: AddLineRequest,
    current_user: dict = Depends(get_current_user),
):
    _assert_owner(shop_id, current_user)
    from agents.pos_agent import _build_pos_executor
    result = _build_pos_executor(shop_id)("add_line_item", body.model_dump())
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.delete("/shop/{shop_id}/session/line/{line_index}")
def remove_line(
    shop_id: int,
    line_index: int,
    session_id: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    _assert_owner(shop_id, current_user)
    from agents.pos_agent import _build_pos_executor
    result = _build_pos_executor(shop_id)("remove_line_item", {"session_id": session_id, "line_index": line_index})
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.patch("/shop/{shop_id}/session/tip")
def set_tip(
    shop_id: int,
    body: TipRequest,
    current_user: dict = Depends(get_current_user),
):
    _assert_owner(shop_id, current_user)
    from agents.pos_agent import _build_pos_executor
    result = _build_pos_executor(shop_id)("add_tip", body.model_dump())
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.patch("/shop/{shop_id}/session/discount")
def apply_discount(
    shop_id: int,
    body: DiscountRequest,
    current_user: dict = Depends(get_current_user),
):
    _assert_owner(shop_id, current_user)
    from agents.pos_agent import _build_pos_executor
    result = _build_pos_executor(shop_id)("apply_discount", body.model_dump())
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/shop/{shop_id}/session/{session_id}/totals")
def get_totals(
    shop_id: int,
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    _assert_owner(shop_id, current_user)
    from agents.pos_agent import _build_pos_executor
    result = _build_pos_executor(shop_id)("calculate_totals", {"session_id": session_id})
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/shop/{shop_id}/session/complete")
def complete_checkout(
    shop_id: int,
    body: CompleteCheckoutRequest,
    current_user: dict = Depends(get_current_user),
):
    _assert_owner(shop_id, current_user)
    from agents.pos_agent import _build_pos_executor
    args = body.model_dump()
    args["payment_method"] = body.payment_method.lower()
    result = _build_pos_executor(shop_id)("complete_checkout", args)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/shop/{shop_id}/refund")
def process_refund(
    shop_id: int,
    body: RefundRequest,
    current_user: dict = Depends(get_current_user),
):
    _assert_owner(shop_id, current_user)
    from agents.pos_agent import _build_pos_executor
    result = _build_pos_executor(shop_id)("process_refund", body.model_dump())
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/shop/{shop_id}/eod")
def end_of_day_summary(
    shop_id: int,
    current_user: dict = Depends(get_current_user),
):
    _assert_owner(shop_id, current_user)
    from agents.pos_agent import _build_pos_executor
    return _build_pos_executor(shop_id)("end_of_day_summary", {})


@router.get("/shop/{shop_id}/transactions")
def list_transactions(
    shop_id: int,
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    """List recent POS transactions for a shop."""
    _assert_owner(shop_id, current_user)
    with SessionLocal() as session:
        rows = session.execute(
            text("""
                SELECT id, subtotal_cents, hst_cents, tip_cents, discount_cents,
                       total_cents, payment_method, status, completed_at, created_at
                FROM pos_transactions
                WHERE shop_id = :shop_id
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"shop_id": shop_id, "limit": limit},
        ).fetchall()
    return [
        {
            "id": r[0],
            "subtotal_display": f"${(r[1] or 0)/100:.2f}",
            "hst_display": f"${(r[2] or 0)/100:.2f}",
            "tip_display": f"${(r[3] or 0)/100:.2f}",
            "discount_display": f"${(r[4] or 0)/100:.2f}",
            "total_display": f"${(r[5] or 0)/100:.2f}",
            "total_cents": r[5],
            "payment_method": r[6],
            "status": r[7],
            "completed_at": r[8].isoformat() if r[8] else None,
            "created_at": r[9].isoformat() if r[9] else None,
        }
        for r in rows
    ]


@router.get("/shop/{shop_id}/transactions/{txn_id}")
def get_transaction(
    shop_id: int,
    txn_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Get a single POS transaction with line items."""
    _assert_owner(shop_id, current_user)
    with SessionLocal() as session:
        txn = session.execute(
            text("""
                SELECT id, subtotal_cents, hst_cents, tip_cents, discount_cents,
                       total_cents, payment_method, status, completed_at, receipt_sent, notes
                FROM pos_transactions
                WHERE id = :txn_id AND shop_id = :shop_id
            """),
            {"txn_id": txn_id, "shop_id": shop_id},
        ).fetchone()
        if not txn:
            raise HTTPException(status_code=404, detail="Transaction not found")

        lines = session.execute(
            text("""
                SELECT description, quantity, unit_price_cents, hst_applicable, line_total_cents
                FROM pos_transaction_lines
                WHERE transaction_id = :txn_id
                ORDER BY id
            """),
            {"txn_id": txn_id},
        ).fetchall()

    return {
        "id": txn[0],
        "subtotal_cents": txn[1], "hst_cents": txn[2], "tip_cents": txn[3],
        "discount_cents": txn[4], "total_cents": txn[5],
        "total_display": f"${(txn[5] or 0)/100:.2f}",
        "payment_method": txn[6], "status": txn[7],
        "completed_at": txn[8].isoformat() if txn[8] else None,
        "receipt_sent": txn[9], "notes": txn[10],
        "lines": [
            {
                "description": r[0], "quantity": float(r[1]),
                "unit_price_cents": r[2], "hst_applicable": r[3],
                "line_total_cents": r[4],
                "line_total_display": f"${(r[4] or 0)/100:.2f}",
            }
            for r in lines
        ],
    }
