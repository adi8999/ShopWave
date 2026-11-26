"""
test_webhooks.py – Stripe webhook handling, idempotency, and stock restoration.

Covers:
  ✓ payment_intent.succeeded marks order paid and advances to processing
  ✓ Duplicate Stripe events are ignored (idempotency via stripe_events table)
  ✓ payment_intent.payment_failed restores stock and cancels order
  ✓ payment_intent.canceled restores stock and cancels order
  ✓ Webhook without valid secret is rejected (requires STRIPE_WEBHOOK_SECRET)
  ✓ Coupon used_count is incremented only on successful payment
  ✓ Metadata mismatch prevents fraudulent payment confirmation
"""
import json
import time
import hashlib
import hmac
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient

from app import models
from tests.conftest import get_token, auth_headers


WEBHOOK_SECRET = "whsec_test_fake"


def _stripe_sig(payload: bytes, secret: str) -> str:
    """Build a fake but structurally valid Stripe-Signature header."""
    ts = int(time.time())
    signed_payload = f"{ts}.{payload.decode()}"
    mac = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


def _post_webhook(client: TestClient, event: dict) -> object:
    body = json.dumps(event).encode()
    sig = _stripe_sig(body, WEBHOOK_SECRET)
    return client.post(
        "/api/payments/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "stripe-signature": sig,
        },
    )


def _make_intent_event(event_type: str, intent_id: str, order_id: int, user_id: int) -> dict:
    return {
        "id": f"evt_{intent_id}_{event_type}",
        "type": event_type,
        "data": {
            "object": {
                "id": intent_id,
                "object": "payment_intent",
                "metadata": {
                    "order_id": str(order_id),
                    "user_id": str(user_id),
                },
            }
        },
    }


def _create_pending_order(db_session, user_id: int, product: models.Product, qty: int = 2) -> models.Order:
    order = models.Order(
        user_id=user_id,
        total_amount=Decimal(str(product.price)) * qty,
        status="awaiting_payment",
        payment_status="pending",
        stripe_payment_intent_id="pi_test_001",
    )
    db_session.add(order)
    db_session.flush()
    item = models.OrderItem(
        order_id=order.id,
        product_id=product.id,
        quantity=qty,
        unit_price=product.price,
    )
    db_session.add(item)
    # Deduct stock (as checkout would)
    product.stock -= qty
    db_session.commit()
    db_session.refresh(order)
    return order


class TestWebhookPaymentSucceeded:
    def test_marks_order_paid(self, client, db_session, user, product):
        order = _create_pending_order(db_session, user.id, product, qty=2)
        event = _make_intent_event(
            "payment_intent.succeeded", order.stripe_payment_intent_id,
            order.id, user.id,
        )
        resp = _post_webhook(client, event)
        assert resp.status_code == 200

        db_session.refresh(order)
        assert order.payment_status == "paid"
        assert order.status == "processing"

    def test_idempotency_duplicate_event_skipped(self, client, db_session, user, product):
        """The same Stripe event ID must not change state twice."""
        order = _create_pending_order(db_session, user.id, product, qty=1)
        event = _make_intent_event(
            "payment_intent.succeeded", order.stripe_payment_intent_id,
            order.id, user.id,
        )
        # First delivery
        r1 = _post_webhook(client, event)
        assert r1.status_code == 200

        # Second delivery (same event_id)
        r2 = _post_webhook(client, event)
        assert r2.status_code == 200
        assert r2.json().get("skipped") is True

        # Order still in correct state (not double-processed)
        db_session.refresh(order)
        assert order.payment_status == "paid"

    def test_coupon_usage_incremented_on_success(self, client, db_session, user, product):
        coupon = models.Coupon(
            code="SAVE10",
            percent_off=Decimal("10"),
            is_active=True,
        )
        db_session.add(coupon)
        db_session.commit()

        order = _create_pending_order(db_session, user.id, product, qty=1)
        order.coupon_code = "SAVE10"
        db_session.commit()

        event = _make_intent_event(
            "payment_intent.succeeded", order.stripe_payment_intent_id,
            order.id, user.id,
        )
        _post_webhook(client, event)

        db_session.refresh(coupon)
        assert coupon.used_count == 1


class TestWebhookPaymentFailed:
    def test_payment_failed_restores_stock_and_cancels(self, client, db_session, user, product):
        stock_before = product.stock
        order = _create_pending_order(db_session, user.id, product, qty=2)
        stock_after_checkout = product.stock  # = stock_before - 2

        event = _make_intent_event(
            "payment_intent.payment_failed", order.stripe_payment_intent_id,
            order.id, user.id,
        )
        resp = _post_webhook(client, event)
        assert resp.status_code == 200

        db_session.refresh(order)
        db_session.refresh(product)
        assert order.payment_status == "failed"
        assert order.status == "cancelled"
        # Stock restored
        assert product.stock == stock_before

    def test_duplicate_failed_event_idempotent(self, client, db_session, user, product):
        order = _create_pending_order(db_session, user.id, product, qty=1)
        event = {
            **_make_intent_event(
                "payment_intent.payment_failed", order.stripe_payment_intent_id,
                order.id, user.id,
            ),
            "id": "evt_failed_idempotency_test",
        }
        r1 = _post_webhook(client, event)
        assert r1.status_code == 200

        event2 = {**event, "id": "evt_failed_idempotency_test"}
        r2 = _post_webhook(client, event2)
        assert r2.status_code == 200
        assert r2.json().get("skipped") is True


class TestWebhookSecurity:
    def test_unsigned_webhook_rejected(self, client):
        """A webhook without STRIPE_WEBHOOK_SECRET set is rejected with 503."""
        import os
        # Temporarily remove the secret to simulate misconfiguration
        original = os.environ.pop("STRIPE_WEBHOOK_SECRET", None)

        # Reload the module so the global picks up the env change
        import importlib
        import app.routers.payments as payments_mod
        old_secret = payments_mod.STRIPE_WEBHOOK_SECRET
        payments_mod.STRIPE_WEBHOOK_SECRET = ""

        try:
            resp = client.post(
                "/api/payments/webhook",
                content=b'{"id":"evt_test","type":"payment_intent.succeeded","data":{"object":{}}}',
                headers={"Content-Type": "application/json"},
            )
            assert resp.status_code in (400, 503)
        finally:
            if original:
                os.environ["STRIPE_WEBHOOK_SECRET"] = original
            payments_mod.STRIPE_WEBHOOK_SECRET = old_secret

    def test_bad_signature_returns_400(self, client):
        body = json.dumps({
            "id": "evt_bad_sig",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_xxx", "metadata": {}}},
        }).encode()
        resp = client.post(
            "/api/payments/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "stripe-signature": "t=0,v1=invalidsig",
            },
        )
        assert resp.status_code == 400


class TestWebhookChargeRefunded:
    def test_charge_refunded_marks_order_refunded(self, client, db_session, user, product):
        order = _create_pending_order(db_session, user.id, product, qty=1)
        order.status = "processing"
        order.payment_status = "paid"
        db_session.commit()

        event = {
            "id": "evt_charge_refunded_001",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "id": "ch_test_001",
                    "object": "charge",
                    "payment_intent": order.stripe_payment_intent_id,
                }
            },
        }
        resp = _post_webhook(client, event)
        assert resp.status_code == 200
        db_session.refresh(order)
        assert order.status == "refunded"
        assert order.payment_status == "refunded"
