"""
Stripe payment endpoints — PaymentIntent creation, webhook handling, and status checks.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field

from integrations.stripe_client import (
    is_configured as stripe_configured,
    create_payment_intent,
    retrieve_payment_intent,
    construct_webhook_event,
)
from modules.payments.service import PaymentService
from modules.payments.models import PaymentMethod, PaymentStatus
from shared.auth_utils import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

_payment_service = PaymentService()


# ── Schemas ─────────────────────────────────────────────────────────

class CreatePaymentIntentRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Amount in dollars (e.g. 50.00)")
    currency: str = Field(default="usd", pattern=r"^[a-z]{3}$")
    description: str = Field(default="")
    shop_id: Optional[int] = None
    invoice_id: Optional[int] = None


class PaymentIntentResponse(BaseModel):
    payment_intent_id: str
    client_secret: str
    amount: float
    currency: str
    status: str


class PaymentStatusResponse(BaseModel):
    payment_intent_id: str
    status: str
    amount: float
    currency: str


# ── Endpoints ───────────────────────────────────────────────────────

@router.get("/config")
def get_stripe_config():
    """Return the Stripe publishable key for frontend initialization."""
    import os
    pub_key = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    return {
        "publishable_key": pub_key,
        "configured": stripe_configured() and bool(pub_key),
    }


@router.post("/create-payment-intent", response_model=PaymentIntentResponse)
def create_payment(req: CreatePaymentIntentRequest):
    """
    Create a Stripe PaymentIntent for a customer payment.
    Called by the AI agent or directly by the frontend.
    """
    if not stripe_configured():
        raise HTTPException(status_code=503, detail="Stripe payments are not configured")

    amount_cents = int(round(req.amount * 100))
    metadata = {}
    if req.shop_id:
        metadata["shop_id"] = str(req.shop_id)
    if req.invoice_id:
        metadata["invoice_id"] = str(req.invoice_id)

    try:
        intent = create_payment_intent(
            amount_cents=amount_cents,
            currency=req.currency,
            description=req.description or f"ZeroQwait payment - ${req.amount:.2f}",
            metadata=metadata,
        )
    except Exception as e:
        logger.error("Stripe PaymentIntent creation failed: %s", e)
        raise HTTPException(status_code=500, detail="Payment processing error")

    return PaymentIntentResponse(
        payment_intent_id=intent["id"],
        client_secret=intent["client_secret"],
        amount=req.amount,
        currency=req.currency,
        status=intent["status"],
    )


@router.get("/status/{payment_intent_id}", response_model=PaymentStatusResponse)
def check_payment_status(payment_intent_id: str):
    """Check the status of a PaymentIntent."""
    if not stripe_configured():
        raise HTTPException(status_code=503, detail="Stripe not configured")

    try:
        intent = retrieve_payment_intent(payment_intent_id)
    except Exception as e:
        logger.error("Failed to retrieve PaymentIntent %s: %s", payment_intent_id, e)
        raise HTTPException(status_code=404, detail="Payment not found")

    return PaymentStatusResponse(
        payment_intent_id=intent["id"],
        status=intent["status"],
        amount=intent["amount"] / 100.0,
        currency=intent["currency"],
    )


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events.
    Processes payment_intent.succeeded and payment_intent.payment_failed.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = construct_webhook_event(payload, sig_header)
    except ValueError:
        logger.warning("Invalid Stripe webhook payload")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except Exception as e:
        logger.warning("Stripe webhook signature verification failed: %s", e)
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    data_object = event["data"]["object"]
    logger.info("Stripe webhook received: %s for %s", event_type, data_object.get("id"))

    if event_type == "payment_intent.succeeded":
        _handle_payment_succeeded(data_object)
    elif event_type == "payment_intent.payment_failed":
        _handle_payment_failed(data_object)

    return {"status": "ok"}


# ── Webhook Handlers ────────────────────────────────────────────────

def _handle_payment_succeeded(intent_data: dict):
    """Record a successful Stripe payment in the local database."""
    metadata = intent_data.get("metadata", {})
    shop_id = metadata.get("shop_id")
    invoice_id = metadata.get("invoice_id")

    if not shop_id:
        logger.warning("Payment succeeded but no shop_id in metadata: %s", intent_data.get("id"))
        return

    shop_id = int(shop_id)
    amount = intent_data.get("amount", 0) / 100.0
    currency = intent_data.get("currency", "usd")

    try:
        _payment_service.record_payment(
            shop_id=shop_id,
            amount=amount,
            method="online",
            invoice_id=int(invoice_id) if invoice_id else None,
            external_ref=intent_data.get("id"),
            notes=f"Stripe payment - {currency.upper()} {amount:.2f}",
        )
        logger.info("Recorded Stripe payment for shop %d: $%.2f", shop_id, amount)
    except Exception as e:
        logger.error("Failed to record Stripe payment: %s", e)


def _handle_payment_failed(intent_data: dict):
    """Log failed Stripe payment for debugging."""
    last_error = intent_data.get("last_payment_error", {})
    logger.warning(
        "Stripe payment failed: %s - %s",
        intent_data.get("id"),
        last_error.get("message", "Unknown error"),
    )
