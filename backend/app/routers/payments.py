import os
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/api/payments", tags=["payments"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")


# ─── Create PaymentIntent ─────────────────────────────────────────────────────

@router.post("/create-checkout-session", response_model=schemas.PaymentIntentResponse)
def create_checkout_session(
    payload: schemas.PaymentIntentCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    order = (
        db.query(models.Order)
        .filter(models.Order.id == payload.order_id, models.Order.user_id == current_user.id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Amount in cents
    amount_cents = int(round(order.total_amount * 100))

    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency="usd",
        metadata={"order_id": order.id, "user_id": current_user.id},
    )

    # Save PaymentIntent ID on the order
    order.stripe_payment_intent_id = intent["id"]
    order.status = "pending_payment"
    db.commit()

    return schemas.PaymentIntentResponse(
        client_secret=intent["client_secret"],
        payment_intent_id=intent["id"],
        amount=amount_cents,
        publishable_key=STRIPE_PUBLISHABLE_KEY,
    )


# ─── Stripe Webhook ───────────────────────────────────────────────────────────

@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: Session = Depends(get_db),
):
    payload = await request.body()

    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(
                payload, stripe_signature, STRIPE_WEBHOOK_SECRET
            )
        else:
            import json
            event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    event_type = event["type"]
    intent = event["data"]["object"]

    if event_type == "payment_intent.succeeded":
        order = (
            db.query(models.Order)
            .filter(models.Order.stripe_payment_intent_id == intent["id"])
            .first()
        )
        if order:
            order.payment_status = "paid"
            order.status = "processing"
            db.commit()
            # Broadcast via WebSocket if connected
            try:
                from app.routers.orders import manager
                import asyncio
                asyncio.create_task(
                    manager.broadcast(order.id, {"status": "processing", "payment_status": "paid"})
                )
            except Exception:
                pass

    elif event_type == "payment_intent.payment_failed":
        order = (
            db.query(models.Order)
            .filter(models.Order.stripe_payment_intent_id == intent["id"])
            .first()
        )
        if order:
            order.payment_status = "failed"
            order.status = "cancelled"
            db.commit()

    return {"received": True}
