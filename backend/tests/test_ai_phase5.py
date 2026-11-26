"""
test_ai_phase5.py – AI assistant security, guest isolation, tool allowlist,
history/message limits, and PII/ID stripping.
"""
from app import models
from tests.conftest import get_token, auth_headers


def _make_order(db_session, user_id: int, product: models.Product) -> models.Order:
    order = models.Order(
        user_id=user_id,
        total_amount=product.price,
        status="processing",
        payment_status="paid",
        shipping_name="Bob Secret",
        shipping_address="742 Evergreen Terrace",
        shipping_city="Springfield",
        shipping_zip="11111",
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


class TestAIChatSecurity:
    def test_guest_chat_cannot_access_order_details(self, client, db_session, user, product):
        order = _make_order(db_session, user.id, product)

        resp = client.post(
            "/api/chat",
            json={"message": f"track order #{order.id}"},
        )
        assert resp.status_code == 200
        text = resp.text
        assert "Evergreen Terrace" not in text
        assert "Bob Secret" not in text
        assert "Springfield" not in text
        reply_lower = resp.json()["reply"].lower()
        assert any(k in reply_lower for k in ("sign in", "authentication", "log in", "tracking token"))

    def test_authenticated_user_cannot_access_other_users_order_via_chat(
        self, client, db_session, user, other_user, product
    ):
        order = _make_order(db_session, user.id, product)
        other_tok = get_token(client, other_user.email, "Password123!")

        resp = client.post(
            "/api/chat",
            json={"message": f"track order #{order.id}"},
            headers=auth_headers(other_tok),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data["tool_calls"][0]["result"]
        assert "Evergreen Terrace" not in resp.text
        assert "Bob Secret" not in resp.text

    def test_authenticated_user_order_chat_omits_pii_and_internal_ids(
        self, client, db_session, user, product
    ):
        order = _make_order(db_session, user.id, product)
        tok = get_token(client, user.email, "Password123!")

        resp = client.post(
            "/api/chat",
            json={"message": f"track order #{order.id}"},
            headers=auth_headers(tok),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "processing" in data["reply"].lower()
        assert "Evergreen Terrace" not in resp.text
        assert "Bob Secret" not in resp.text
        tool_res = data["tool_calls"][0]["result"]
        assert "order_id" not in tool_res
        assert "shipping_address" not in tool_res

    def test_message_length_and_history_limits_enforced(self, client):
        too_long = client.post("/api/chat", json={"message": "a" * 501})
        assert too_long.status_code == 422

        too_much_history = client.post(
            "/api/chat",
            json={
                "message": "hello",
                "history": [{"role": "user", "content": "hi"} for _ in range(11)],
            },
        )
        assert too_much_history.status_code == 422

    def test_disallowed_tool_blocked(self, db_session):
        from app.routers.chat import dispatch_tool

        res = dispatch_tool("drop_database", {}, db_session)
        assert "not permitted" in res["error"].lower()
