"""Stripe payment integration client."""

import os
import logging
from typing import Dict, Optional

import stripe

logger = logging.getLogger(__name__)

# Configure Stripe with secret key from environment
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

# Webhook signing secret
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")


def is_configured() -> bool:
    """Check if Stripe is properly configured."""
    return bool(stripe.api_key and stripe.api_key.startswith("sk_"))


def create_payment_intent(
    amount_cents: int,
    currency: str = "usd",
    description: str = "",
    metadata: Optional[Dict] = None,
) -> Dict:
    """
    Create a Stripe PaymentIntent.

    Args:
        amount_cents: Amount in cents (e.g. 5000 for $50.00)
        currency: Three-letter ISO currency code
        description: Human-readable description
        metadata: Arbitrary key-value pairs attached to the PaymentIntent

    Returns:
        Dict with id, client_secret, amount, currency, status
    """
    if not is_configured():
        raise RuntimeError("Stripe is not configured. Set STRIPE_SECRET_KEY env var.")

    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency=currency,
        description=description,
        metadata=metadata or {},
        automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
    )

    logger.info("Created PaymentIntent %s for %d %s", intent.id, amount_cents, currency)
    return {
        "id": intent.id,
        "client_secret": intent.client_secret,
        "amount": intent.amount,
        "currency": intent.currency,
        "status": intent.status,
    }


def retrieve_payment_intent(payment_intent_id: str) -> Dict:
    """Retrieve an existing PaymentIntent by ID."""
    if not is_configured():
        raise RuntimeError("Stripe is not configured.")
    intent = stripe.PaymentIntent.retrieve(payment_intent_id)
    return {
        "id": intent.id,
        "amount": intent.amount,
        "currency": intent.currency,
        "status": intent.status,
        "metadata": dict(intent.metadata) if intent.metadata else {},
    }


def create_checkout_session(
    line_items: list,
    success_url: str,
    cancel_url: str,
    mode: str = "payment",
    metadata: Optional[Dict] = None,
) -> Dict:
    """
    Create a Stripe Checkout Session for subscription or one-time payment.

    Args:
        line_items: List of dicts with price_data or price
        success_url: Redirect URL on success
        cancel_url: Redirect URL on cancel
        mode: "payment" or "subscription"
        metadata: Arbitrary key-value pairs

    Returns:
        Dict with id, url
    """
    if not is_configured():
        raise RuntimeError("Stripe is not configured.")

    session = stripe.checkout.Session.create(
        line_items=line_items,
        mode=mode,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata or {},
    )
    return {"id": session.id, "url": session.url}


def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    """Verify and construct a Stripe webhook event."""
    if not STRIPE_WEBHOOK_SECRET:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET not configured.")
    return stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
