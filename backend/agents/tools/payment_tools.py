"""Payment/POS agent tools — plain functions called by Finance sub-agent."""

from typing import Any, Dict, List, Optional

from modules.payments.service import payment_service


def create_invoice(
    shop_id: int,
    line_items: List[Dict[str, Any]],
    customer_id: Optional[int] = None,
    tax_rate: float = 0.0,
    discount_amount: float = 0.0,
    tip_amount: float = 0.0,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new invoice for a shop.

    Args:
        shop_id: The shop ID.
        line_items: List of dicts with keys: description, quantity, unit_price,
                    and optional service_id, queue_item_id, appointment_id.
        customer_id: Optional customer ID.
        tax_rate: Tax rate as decimal (e.g. 0.13 for 13%).
        discount_amount: Flat discount amount.
        tip_amount: Tip amount.
        notes: Optional invoice notes.
    """
    try:
        return payment_service.create_invoice(
            shop_id=shop_id,
            line_items=line_items,
            customer_id=customer_id,
            tax_rate=tax_rate,
            discount_amount=discount_amount,
            tip_amount=tip_amount,
            notes=notes,
        )
    except Exception as e:
        return {"error": str(e)}


def record_payment(
    shop_id: int,
    amount: float,
    method: str = "cash",
    invoice_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    tip_amount: float = 0.0,
    processed_by: Optional[int] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Record a payment for a shop.

    Args:
        shop_id: The shop ID.
        amount: Payment amount.
        method: Payment method — cash, card, online, other.
        invoice_id: Optional linked invoice.
        customer_id: Optional customer.
        tip_amount: Tip amount.
        processed_by: Employee/user who processed payment.
        notes: Optional notes.
    """
    try:
        return payment_service.record_payment(
            shop_id=shop_id,
            amount=amount,
            method=method,
            invoice_id=invoice_id,
            customer_id=customer_id,
            tip_amount=tip_amount,
            processed_by=processed_by,
            notes=notes,
        )
    except Exception as e:
        return {"error": str(e)}


def process_refund(
    shop_id: int,
    payment_id: int,
    refund_amount: Optional[float] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Refund a payment (full or partial).

    Args:
        shop_id: The shop ID.
        payment_id: The payment to refund.
        refund_amount: Amount to refund (None = full refund).
        reason: Reason for refund.
    """
    try:
        return payment_service.refund_payment(
            shop_id=shop_id,
            payment_id=payment_id,
            refund_amount=refund_amount,
            reason=reason,
        )
    except Exception as e:
        return {"error": str(e)}


def list_invoices(
    shop_id: int,
    status: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """List invoices for a shop.

    Args:
        shop_id: The shop ID.
        status: Optional status filter (draft, sent, paid, overdue, cancelled).
        limit: Maximum number of results.
    """
    try:
        invoices = payment_service.list_invoices(shop_id=shop_id, status=status, limit=limit)
        return {"invoices": invoices, "shop_id": shop_id, "count": len(invoices)}
    except Exception as e:
        return {"error": str(e)}


def list_payments(
    shop_id: int,
    status: Optional[str] = None,
    method: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """List payments for a shop.

    Args:
        shop_id: The shop ID.
        status: Optional status filter.
        method: Optional method filter (cash, card, online).
        limit: Maximum number of results.
    """
    try:
        payments = payment_service.list_payments(
            shop_id=shop_id, status=status, method=method, limit=limit,
        )
        return {"payments": payments, "shop_id": shop_id, "count": len(payments)}
    except Exception as e:
        return {"error": str(e)}


def daily_pos_summary(shop_id: int, date: Optional[str] = None) -> Dict[str, Any]:
    """Get POS/payment summary for a specific day.

    Args:
        shop_id: The shop ID.
        date: Optional ISO date string. Defaults to today.
    """
    try:
        from datetime import datetime
        target = datetime.fromisoformat(date) if date else None
        return payment_service.daily_pos_summary(shop_id=shop_id, date=target)
    except Exception as e:
        return {"error": str(e)}
