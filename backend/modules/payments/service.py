"""Payment service — invoice and payment CRUD + POS logic."""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from database import SessionLocal
from .models import (
    Invoice, InvoiceLineItem, InvoiceStatus,
    Payment, PaymentMethod, PaymentStatus,
)


class PaymentService:
    """Tenant-scoped invoice and payment operations."""

    def get_session(self) -> Session:
        return SessionLocal()

    def _invoice_to_dict(self, inv: Invoice) -> Dict:
        return {
            "id": inv.id,
            "shop_id": inv.shop_id,
            "customer_id": inv.customer_id,
            "invoice_number": inv.invoice_number,
            "status": inv.status.value if inv.status else None,
            "subtotal": inv.subtotal,
            "tax_amount": inv.tax_amount,
            "tax_rate": inv.tax_rate,
            "discount_amount": inv.discount_amount,
            "tip_amount": inv.tip_amount,
            "total": inv.total,
            "currency": inv.currency,
            "notes": inv.notes,
            "due_date": str(inv.due_date) if inv.due_date else None,
            "paid_at": str(inv.paid_at) if inv.paid_at else None,
            "created_at": str(inv.created_at) if inv.created_at else None,
            "line_items": [
                {
                    "id": li.id,
                    "description": li.description,
                    "quantity": li.quantity,
                    "unit_price": li.unit_price,
                    "total": li.total,
                }
                for li in (inv.line_items or [])
            ],
        }

    def _payment_to_dict(self, pmt: Payment) -> Dict:
        return {
            "id": pmt.id,
            "shop_id": pmt.shop_id,
            "invoice_id": pmt.invoice_id,
            "customer_id": pmt.customer_id,
            "amount": pmt.amount,
            "tip_amount": pmt.tip_amount,
            "currency": pmt.currency,
            "method": pmt.method.value if pmt.method else None,
            "status": pmt.status.value if pmt.status else None,
            "external_ref": pmt.external_ref,
            "processed_at": str(pmt.processed_at) if pmt.processed_at else None,
            "refunded_at": str(pmt.refunded_at) if pmt.refunded_at else None,
            "refund_amount": pmt.refund_amount,
            "notes": pmt.notes,
            "created_at": str(pmt.created_at) if pmt.created_at else None,
        }

    # ── Invoice CRUD ──────────────────────────────────────────────

    def _generate_invoice_number(self, shop_id: int) -> str:
        """Generate a sequential invoice number: INV-{shop_id}-{uuid_short}."""
        short = uuid.uuid4().hex[:8].upper()
        return f"INV-{shop_id}-{short}"

    def create_invoice(
        self,
        shop_id: int,
        line_items: List[Dict],
        customer_id: Optional[int] = None,
        tax_rate: float = 0.0,
        discount_amount: float = 0.0,
        tip_amount: float = 0.0,
        notes: Optional[str] = None,
        due_date: Optional[datetime] = None,
    ) -> Dict:
        session = self.get_session()
        try:
            inv = Invoice(
                shop_id=shop_id,
                customer_id=customer_id,
                invoice_number=self._generate_invoice_number(shop_id),
                tax_rate=tax_rate,
                discount_amount=discount_amount,
                tip_amount=tip_amount,
                notes=notes,
                due_date=due_date,
            )

            subtotal = 0.0
            for item in line_items:
                qty = item.get("quantity", 1)
                price = item.get("unit_price", 0.0)
                line_total = qty * price
                li = InvoiceLineItem(
                    description=item.get("description", "Service"),
                    service_id=item.get("service_id"),
                    queue_item_id=item.get("queue_item_id"),
                    appointment_id=item.get("appointment_id"),
                    quantity=qty,
                    unit_price=price,
                    total=line_total,
                )
                inv.line_items.append(li)
                subtotal += line_total

            inv.subtotal = subtotal
            inv.tax_amount = round(subtotal * tax_rate, 2)
            inv.total = round(subtotal + inv.tax_amount - discount_amount + tip_amount, 2)

            session.add(inv)
            session.commit()
            session.refresh(inv)
            return self._invoice_to_dict(inv)
        except Exception as e:
            session.rollback()
            return {"error": str(e)}
        finally:
            session.close()

    def get_invoice(self, shop_id: int, invoice_id: int) -> Optional[Dict]:
        session = self.get_session()
        try:
            inv = session.query(Invoice).filter(
                Invoice.id == invoice_id, Invoice.shop_id == shop_id,
            ).first()
            return self._invoice_to_dict(inv) if inv else None
        finally:
            session.close()

    def list_invoices(
        self,
        shop_id: int,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        session = self.get_session()
        try:
            q = session.query(Invoice).filter(Invoice.shop_id == shop_id)
            if status:
                try:
                    q = q.filter(Invoice.status == InvoiceStatus(status))
                except ValueError:
                    pass
            return [self._invoice_to_dict(i) for i in q.order_by(Invoice.created_at.desc()).limit(limit).all()]
        finally:
            session.close()

    # ── Payment CRUD ──────────────────────────────────────────────

    def record_payment(
        self,
        shop_id: int,
        amount: float,
        method: str = "cash",
        invoice_id: Optional[int] = None,
        customer_id: Optional[int] = None,
        tip_amount: float = 0.0,
        processed_by: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Dict:
        session = self.get_session()
        try:
            try:
                method_enum = PaymentMethod(method)
            except ValueError:
                method_enum = PaymentMethod.OTHER

            pmt = Payment(
                shop_id=shop_id,
                invoice_id=invoice_id,
                customer_id=customer_id,
                amount=amount,
                tip_amount=tip_amount,
                currency="USD",
                method=method_enum,
                status=PaymentStatus.COMPLETED,
                processed_by=processed_by,
                processed_at=datetime.utcnow(),
                notes=notes,
            )
            session.add(pmt)

            # Mark invoice as paid when fully covered
            if invoice_id:
                inv = session.query(Invoice).filter(Invoice.id == invoice_id).first()
                if inv:
                    total_paid = (
                        session.query(func.coalesce(func.sum(Payment.amount), 0.0))
                        .filter(
                            Payment.invoice_id == invoice_id,
                            Payment.status == PaymentStatus.COMPLETED,
                        )
                        .scalar()
                    ) + amount
                    if total_paid >= inv.total:
                        inv.status = InvoiceStatus.PAID
                        inv.paid_at = datetime.utcnow()

            session.commit()
            session.refresh(pmt)
            return self._payment_to_dict(pmt)
        except Exception as e:
            session.rollback()
            return {"error": str(e)}
        finally:
            session.close()

    def refund_payment(
        self,
        shop_id: int,
        payment_id: int,
        refund_amount: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> Dict:
        session = self.get_session()
        try:
            pmt = session.query(Payment).filter(
                Payment.id == payment_id, Payment.shop_id == shop_id,
            ).first()
            if not pmt:
                return {"error": "Payment not found"}
            if pmt.status not in (PaymentStatus.COMPLETED,):
                return {"error": f"Cannot refund a {pmt.status.value} payment"}

            amount = refund_amount if refund_amount is not None else pmt.amount
            if amount > pmt.amount:
                return {"error": "Refund amount exceeds original payment"}

            pmt.refund_amount = amount
            pmt.refunded_at = datetime.utcnow()
            pmt.status = (
                PaymentStatus.REFUNDED if amount >= pmt.amount
                else PaymentStatus.PARTIALLY_REFUNDED
            )
            pmt.notes = (pmt.notes or "") + f"\nRefund: {reason or 'No reason given'}"

            session.commit()
            session.refresh(pmt)
            return self._payment_to_dict(pmt)
        except Exception as e:
            session.rollback()
            return {"error": str(e)}
        finally:
            session.close()

    def list_payments(
        self,
        shop_id: int,
        status: Optional[str] = None,
        method: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        session = self.get_session()
        try:
            q = session.query(Payment).filter(Payment.shop_id == shop_id)
            if status:
                try:
                    q = q.filter(Payment.status == PaymentStatus(status))
                except ValueError:
                    pass
            if method:
                try:
                    q = q.filter(Payment.method == PaymentMethod(method))
                except ValueError:
                    pass
            return [self._payment_to_dict(p) for p in q.order_by(Payment.created_at.desc()).limit(limit).all()]
        finally:
            session.close()

    # ── POS Helpers ───────────────────────────────────────────────

    def daily_pos_summary(self, shop_id: int, date: Optional[datetime] = None) -> Dict:
        """Get POS summary for a specific day."""
        session = self.get_session()
        try:
            target = date or datetime.utcnow()
            day_start = target.replace(hour=0, minute=0, second=0, microsecond=0)
            from datetime import timedelta
            day_end = day_start + timedelta(days=1)

            payments = session.query(Payment).filter(
                Payment.shop_id == shop_id,
                Payment.status == PaymentStatus.COMPLETED,
                Payment.processed_at >= day_start,
                Payment.processed_at < day_end,
            ).all()

            total_revenue = sum(p.amount for p in payments)
            total_tips = sum(p.tip_amount or 0 for p in payments)
            total_refunds = sum(
                p.refund_amount or 0 for p in payments
                if p.status in (PaymentStatus.REFUNDED, PaymentStatus.PARTIALLY_REFUNDED)
            )

            by_method = {}
            for p in payments:
                m = p.method.value if p.method else "other"
                by_method[m] = by_method.get(m, 0.0) + p.amount

            return {
                "shop_id": shop_id,
                "date": str(day_start.date()),
                "total_transactions": len(payments),
                "total_revenue": round(total_revenue, 2),
                "total_tips": round(total_tips, 2),
                "total_refunds": round(total_refunds, 2),
                "net_revenue": round(total_revenue - total_refunds, 2),
                "by_method": by_method,
            }
        finally:
            session.close()


payment_service = PaymentService()
