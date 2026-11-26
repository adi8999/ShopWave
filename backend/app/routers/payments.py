"""
payments.py – Stripe PaymentIntent creation and webhook handling.

Security guarantees
-------------------
1. STRIPE_WEBHOOK_SECRET is REQUIRED in production.  Requests without a valid
   signature are rejected with HTTP 400.
2. Each Stripe event is recorded in the stripe_events table; duplicates are
   skipped (idempotency).
3. Payment status is updated ONLY via signed webhook events, never from
   frontend-supplied data.
4. Stock is restored when a payment fails or is cancelled.
5. Coupon usage is incremented ONLY after payment_intent.succeeded.
"""
import logging
import os
from decimal import Decimal

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user
from app.database import get_db
from app.security.rate_limit import checkout_limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["payments"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")


# ─── Create PaymentIntent ─────────────────────────────────────────────────────

@router.post("/create-checkout-session", response_model=schemas.PaymentIntentResponse)
def create_checkout_session(
    payload: schemas.PaymentIntentCreate,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _rl: None = Depends(checkout_limiter),
):
    """
    Create a Stripe PaymentIntent for an existing awaiting_payment order.

    The order must belong to the current user and be in 'awaiting_payment'
    status.  Coupon validation happens here; usage is recorded only after
    webhook confirmation.
    """
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    order = (
        db.query(models.Order)
        .filter(
            models.Order.id == payload.order_id,
            models.Order.user_id == current_user.id,
        )
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Prevent creating a new PaymentIntent for already-paid orders
    if order.status not in ("awaiting_payment", "draft"):
        raise HTTPException(
            status_code=409,
            detail=f"Order is already in '{order.status}' status and cannot be paid again.",
        )

    # ── Coupon validation (preview only — usage recorded after webhook) ────────
    discount_amount = Decimal("0.00")
    applied_coupon: models.Coupon | None = None

    if payload.coupon_code:
        clean_code = payload.coupon_code.strip().upper()
        coupon = (
            db.query(models.Coupon)
            .filter(models.Coupon.code == clean_code, models.Coupon.is_active == True)
            .first()
        )
        if coupon:
            from datetime import datetime

            # Expiration check
            if coupon.expires_at and coupon.expires_at < datetime.utcnow():
                raise HTTPException(
                    status_code=400,
                    detail=f"Coupon '{clean_code}' has expired.",
                )
            # Max-uses check
            if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
                raise HTTPException(
                    status_code=400,
                    detail=f"Coupon '{clean_code}' has reached its maximum uses.",
                )
            # Minimum order amount check
            if coupon.min_order_amount and order.total_amount < coupon.min_order_amount:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Coupon '{clean_code}' requires a minimum order of "
                        f"${coupon.min_order_amount:.2f}."
                    ),
                )
            # One coupon per order
            if order.coupon_code and order.coupon_code != clean_code:
                raise HTTPException(
                    status_code=400,
                    detail="An order can only use one coupon.",
                )

            if coupon.percent_off:
                discount_amount = round(order.total_amount * (coupon.percent_off / 100), 2)
            elif coupon.amount_off:
                discount_amount = round(min(order.total_amount, coupon.amount_off), 2)

            applied_coupon = coupon
            order.coupon_code = clean_code
            order.discount_amount = discount_amount

    # ── Build Stripe amount in cents ──────────────────────────────────────────
    final_amount = max(Decimal("0.50"), order.total_amount - discount_amount)
    amount_cents = int(round(final_amount * 100))

    # ── Create / retrieve PaymentIntent ───────────────────────────────────────
    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency="usd",
        metadata={
            "order_id": str(order.id),
            "user_id": str(current_user.id),
            "coupon_code": order.coupon_code or "",
            "discount_amount": str(discount_amount),
        },
    )

    order.stripe_payment_intent_id = intent["id"]
    order.status = "awaiting_payment"
    db.commit()

    return schemas.PaymentIntentResponse(
        client_secret=intent["client_secret"],
        payment_intent_id=intent["id"],
        amount=amount_cents,
        discount_amount=discount_amount,
        publishable_key=STRIPE_PUBLISHABLE_KEY,
    )


# ─── Stripe Webhook ───────────────────────────────────────────────────────────

@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: Session = Depends(get_db),
):
    """
    Stripe webhook endpoint.

    • Signature verification is ALWAYS enforced (STRIPE_WEBHOOK_SECRET required).
    • Each event is recorded in stripe_events for idempotency.
    • Stock is restored on payment failure or cancellation.
    • Coupon usage is incremented only on payment success.
    """
    payload = await request.body()

    # ── Signature verification ─────────────────────────────────────────────────
    if not STRIPE_WEBHOOK_SECRET:
        # In production this should be a startup-time failure; here we surface it
        # as a 503 so operators are alerted immediately.
        logger.error("STRIPE_WEBHOOK_SECRET is not set – rejecting webhook")
        raise HTTPException(
            status_code=503,
            detail="Webhook secret is not configured. Contact the administrator.",
        )

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        logger.warning("Stripe webhook signature verification failed")
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    except Exception as exc:
        logger.error("Stripe webhook parse error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))

    # Stripe v9 returns StripeObjects; convert to plain dict for uniform access
    if hasattr(event, "to_dict"):
        event = event.to_dict()

    event_id: str = event["id"]
    event_type: str = event["type"]

    # ── Idempotency guard ──────────────────────────────────────────────────────
    already_processed = (
        db.query(models.StripeEvent)
        .filter(models.StripeEvent.event_id == event_id)
        .first()
    )
    if already_processed:
        logger.info("Stripe event %s already processed – skipping", event_id)
        return {"received": True, "skipped": True}

    # Record event before processing to prevent double-processing under load
    db.add(models.StripeEvent(event_id=event_id, event_type=event_type))
    db.flush()

    intent = event["data"]["object"]

    # ── payment_intent.succeeded ───────────────────────────────────────────────
    if event_type == "payment_intent.succeeded":
        _handle_payment_succeeded(intent, db)

    # ── payment_intent.payment_failed ─────────────────────────────────────────
    elif event_type == "payment_intent.payment_failed":
        _handle_payment_failed(intent, db)

    # ── payment_intent.canceled ───────────────────────────────────────────────
    elif event_type == "payment_intent.canceled":
        _handle_payment_canceled(intent, db)

    # ── charge.refunded ───────────────────────────────────────────────────────
    elif event_type == "charge.refunded":
        _handle_charge_refunded(event["data"]["object"], db)

    db.commit()
    return {"received": True}


# ─── Webhook sub-handlers ─────────────────────────────────────────────────────

def _get_order_by_intent(intent_id: str, db: Session) -> models.Order | None:
    return (
        db.query(models.Order)
        .filter(models.Order.stripe_payment_intent_id == intent_id)
        .first()
    )


def _handle_payment_succeeded(intent: dict, db: Session) -> None:
    """Mark order paid and increment coupon usage."""
    from app.routers.orders import manager, apply_transition
    import asyncio

    # Stripe v9+ returns a StripeObject, not a plain dict; convert to dict
    if hasattr(intent, "to_dict"):
        intent = intent.to_dict()

    order = _get_order_by_intent(intent["id"], db)
    if not order:
        logger.warning("payment_intent.succeeded: no order for intent %s", intent["id"])
        return

    # Validate metadata matches the order on record
    meta = intent.get("metadata", {})
    if str(order.id) != meta.get("order_id") or str(order.user_id) != meta.get("user_id"):
        logger.error(
            "Metadata mismatch for intent %s: expected order=%s user=%s, got %s",
            intent["id"], order.id, order.user_id, meta,
        )
        return

    if order.payment_status == "paid":
        logger.info("Order #%d already paid; skipping succeeded event", order.id)
        return

    apply_transition(order, "paid")
    order.payment_status = "paid"

    # Consume coupon atomically (runs inside the outer transaction)
    if order.coupon_code:
        from sqlalchemy import or_
        db.query(models.Coupon).filter(
            models.Coupon.code == order.coupon_code,
            models.Coupon.is_active == True,
            or_(
                models.Coupon.max_uses.is_(None),
                models.Coupon.used_count < models.Coupon.max_uses,
            ),
        ).update(
            {models.Coupon.used_count: models.Coupon.used_count + 1},
            synchronize_session="fetch",
        )

    # Then advance to processing
    apply_transition(order, "processing")

    logger.info("Order #%d marked paid + processing", order.id)

    # Broadcast via WebSocket (best-effort)
    try:
        asyncio.create_task(
            manager.broadcast(order.id, {"status": "processing", "payment_status": "paid"})
        )
    except RuntimeError:
        pass  # No running event loop in test environments


def _handle_payment_failed(intent: dict, db: Session) -> None:
    """Mark order payment failed and restore stock."""
    from app.routers.orders import restore_stock_for_order

    if hasattr(intent, "to_dict"):
        intent = intent.to_dict()

    order = _get_order_by_intent(intent["id"], db)
    if not order:
        logger.warning("payment_intent.payment_failed: no order for intent %s", intent["id"])
        return

    if order.payment_status == "failed":
        return  # Already handled

    order.payment_status = "failed"
    order.status = "cancelled"
    restore_stock_for_order(order, db)
    logger.info("Order #%d cancelled (payment failed); stock restored", order.id)


def _handle_payment_canceled(intent: dict, db: Session) -> None:
    """Mark order cancelled and restore stock."""
    from app.routers.orders import restore_stock_for_order

    if hasattr(intent, "to_dict"):
        intent = intent.to_dict()

    order = _get_order_by_intent(intent["id"], db)
    if not order:
        return

    if order.status in ("cancelled", "refunded"):
        return

    order.payment_status = "failed"
    order.status = "cancelled"
    restore_stock_for_order(order, db)
    logger.info("Order #%d cancelled (payment intent canceled); stock restored", order.id)


def _handle_charge_refunded(charge: dict, db: Session) -> None:
    """Mark order refunded when charge is fully refunded."""
    payment_intent_id = charge.get("payment_intent")
    if not payment_intent_id:
        return

    order = _get_order_by_intent(payment_intent_id, db)
    if not order:
        return

    if order.status == "refunded":
        return

    order.status = "refunded"
    order.payment_status = "refunded"
    logger.info("Order #%d marked refunded", order.id)
