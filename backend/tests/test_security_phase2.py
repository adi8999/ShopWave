"""
test_security_phase2.py – WebSocket ticket auth, public tracking token, CORS,
request size limit, and trusted proxy IP handling.
"""
import pytest
from decimal import Decimal
from starlette.websockets import WebSocketDisconnect

from app import models
from tests.conftest import get_token, auth_headers


def _make_order(db_session, user_id: int, product: models.Product) -> models.Order:
    order = models.Order(
        user_id=user_id,
        total_amount=product.price,
        status="awaiting_payment",
        payment_status="pending",
        shipping_name="Alice Private",
        shipping_address="999 Secret Lane",
        shipping_city="HiddenCity",
        shipping_zip="00000",
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(models.OrderItem(
        order_id=order.id,
        product_id=product.id,
        quantity=1,
        unit_price=product.price,
    ))
    db_session.commit()
    db_session.refresh(order)
    return order


class TestWebSocketTicketAuth:
    def test_ws_rejects_raw_jwt_in_query_param(self, client, db_session, user, product):
        order = _make_order(db_session, user.id, product)
        token = get_token(client, user.email, "Password123!")

        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(f"/api/orders/ws/{order.id}?token={token}"):
                pass
        assert exc.value.code == 4001

    def test_ws_accepts_valid_ticket_and_is_single_use(self, client, db_session, user, product):
        order = _make_order(db_session, user.id, product)
        token = get_token(client, user.email, "Password123!")

        t_resp = client.post(f"/api/orders/{order.id}/ws-ticket", headers=auth_headers(token))
        assert t_resp.status_code == 200
        ticket = t_resp.json()["ticket"]

        with client.websocket_connect(f"/api/orders/ws/{order.id}?ticket={ticket}") as ws:
            msg = ws.receive_json()
            assert msg["order_id"] == order.id
            assert msg["status"] == "awaiting_payment"

        # Second use of the same ticket must fail
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(f"/api/orders/ws/{order.id}?ticket={ticket}"):
                pass
        assert exc.value.code == 4001

    def test_ws_ticket_cannot_be_issued_for_other_user_order(self, client, db_session, user, other_user, product):
        order = _make_order(db_session, user.id, product)
        other_token = get_token(client, other_user.email, "Password123!")

        resp = client.post(f"/api/orders/{order.id}/ws-ticket", headers=auth_headers(other_token))
        assert resp.status_code == 404


class TestPublicOrderTrackingToken:
    def test_tracking_token_returns_status_without_pii(self, client, db_session, user, product):
        order = _make_order(db_session, user.id, product)
        token = get_token(client, user.email, "Password123!")

        tok_resp = client.post(f"/api/orders/{order.id}/tracking-token", headers=auth_headers(token))
        assert tok_resp.status_code == 200
        tracking_token = tok_resp.json()["tracking_token"]

        # Public endpoint (no auth header)
        pub_resp = client.get(f"/api/orders/track?token={tracking_token}")
        assert pub_resp.status_code == 200
        data = pub_resp.json()
        assert data["order_id"] == order.id
        assert data["status"] == "awaiting_payment"
        assert "shipping_address" not in data
        assert "shipping_name" not in data
        assert "Secret Lane" not in pub_resp.text
        assert "Alice Private" not in pub_resp.text

    def test_invalid_tracking_token_rejected(self, client):
        resp = client.get("/api/orders/track?token=invalid.jwt.token")
        assert resp.status_code == 401


class TestSecurityHeadersAndLimits:
    def test_security_headers_present(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_oversized_request_rejected_with_413(self, client):
        resp = client.post(
            "/api/auth/login",
            content=b"x",
            headers={"Content-Length": str(5 * 1024 * 1024), "Content-Type": "application/json"},
        )
        assert resp.status_code == 413


class TestRateLimitSecurityAndProxyTrust:
    def test_production_fails_closed_when_redis_unavailable(self, monkeypatch):
        from fastapi import HTTPException
        from starlette.requests import Request
        import app.security.rate_limit as rl

        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setattr(rl, "_redis_client", None)

        limiter = rl.RateLimiter(requests=5, window_seconds=60, key_prefix="rl:test")
        req = Request({
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
            "client": ("203.0.113.10", 12345),
        })
        with pytest.raises(HTTPException) as exc:
            limiter(req)
        assert exc.value.status_code == 503

    def test_x_forwarded_for_ignored_from_untrusted_client(self, monkeypatch):
        from starlette.requests import Request
        import app.security.rate_limit as rl

        monkeypatch.setenv("TRUSTED_PROXIES", "127.0.0.1")

        untrusted_req = Request({
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-forwarded-for", b"1.2.3.4")],
            "client": ("198.51.100.77", 5555),
        })
        assert rl._get_client_ip(untrusted_req) == "198.51.100.77"

        trusted_req = Request({
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-forwarded-for", b"203.0.113.9, 127.0.0.1")],
            "client": ("127.0.0.1", 5555),
        })
        assert rl._get_client_ip(trusted_req) == "203.0.113.9"
