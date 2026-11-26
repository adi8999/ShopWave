"""
test_catalog_analytics_phase4.py – Soft delete, reviews, variants, wishlist,
low-stock alerts, paid-only analytics, and admin audit logs.
"""
from decimal import Decimal
from app import models
from tests.conftest import get_token, auth_headers


class TestSoftDeleteAndCatalog:
    def test_soft_delete_hides_product_from_catalog(self, client, admin, product, db_session):
        admin_tok = get_token(client, admin.email, "AdminPass123!")
        del_resp = client.delete(f"/api/admin/products/{product.id}", headers=auth_headers(admin_tok))
        assert del_resp.status_code == 204

        # Public listing and detail no longer show soft-deleted product
        detail = client.get(f"/api/products/{product.id}")
        assert detail.status_code == 404

        listing = client.get("/api/products")
        assert listing.status_code == 200
        assert all(p["id"] != product.id for p in listing.json()["items"])

        # Audit log recorded
        logs = client.get("/api/admin/audit-logs", headers=auth_headers(admin_tok))
        assert logs.status_code == 200
        assert any(l["action"] == "soft_delete_product" for l in logs.json())

    def test_min_greater_than_max_price_returns_400(self, client):
        resp = client.get("/api/products?min_price=100&max_price=10")
        assert resp.status_code == 400


class TestWishlistVariantsAndReviews:
    def test_wishlist_add_list_remove(self, client, user, product):
        tok = get_token(client, user.email, "Password123!")
        add = client.post(f"/api/wishlist/{product.id}", headers=auth_headers(tok))
        assert add.status_code == 201

        lst = client.get("/api/wishlist", headers=auth_headers(tok))
        assert lst.status_code == 200
        assert len(lst.json()) == 1

        rem = client.delete(f"/api/wishlist/{product.id}", headers=auth_headers(tok))
        assert rem.status_code == 204

    def test_review_updates_product_rating(self, client, user, product, db_session):
        tok = get_token(client, user.email, "Password123!")
        resp = client.post(
            f"/api/products/{product.id}/reviews",
            json={"rating": 5, "comment": "Excellent!"},
            headers=auth_headers(tok),
        )
        assert resp.status_code == 201
        db_session.refresh(product)
        assert product.review_count == 1
        assert product.rating == Decimal("5.00")

    def test_admin_creates_variant(self, client, admin, product):
        admin_tok = get_token(client, admin.email, "AdminPass123!")
        resp = client.post(
            f"/api/admin/products/{product.id}/variants",
            json={"name": "Black / L", "sku": "WDG-BLK-L", "price_delta": "5.00", "stock": 4},
            headers=auth_headers(admin_tok),
        )
        assert resp.status_code == 201
        v_list = client.get(f"/api/products/{product.id}/variants")
        assert v_list.status_code == 200
        assert len(v_list.json()) == 1


class TestAnalyticsAndLowStock:
    def test_sales_excludes_unpaid_and_cancelled_orders(self, client, admin, user, product, db_session):
        # Paid processing order ($50)
        db_session.add(models.Order(
            user_id=user.id, total_amount=Decimal("50.00"),
            status="processing", payment_status="paid",
        ))
        # Unpaid pending order ($100) — must be excluded
        db_session.add(models.Order(
            user_id=user.id, total_amount=Decimal("100.00"),
            status="awaiting_payment", payment_status="pending",
        ))
        # Cancelled/refunded order ($200) — must be excluded
        db_session.add(models.Order(
            user_id=user.id, total_amount=Decimal("200.00"),
            status="cancelled", payment_status="paid",
        ))
        db_session.commit()

        admin_tok = get_token(client, admin.email, "AdminPass123!")
        resp = client.get("/api/admin/sales?range=7d", headers=auth_headers(admin_tok))
        assert resp.status_code == 200
        data = resp.json()
        assert Decimal(data["total_revenue"]) == Decimal("50.00")
        assert data["paid_orders_count"] == 1
        assert Decimal(data["average_order_value"]) == Decimal("50.00")

    def test_low_stock_endpoint(self, client, admin, low_stock_product):
        admin_tok = get_token(client, admin.email, "AdminPass123!")
        resp = client.get("/api/admin/low-stock", headers=auth_headers(admin_tok))
        assert resp.status_code == 200
        assert any(p["id"] == low_stock_product.id for p in resp.json())

    def test_non_admin_rejected_from_admin_routes(self, client, user):
        tok = get_token(client, user.email, "Password123!")
        assert client.get("/api/admin/sales", headers=auth_headers(tok)).status_code == 403
        assert client.get("/api/admin/low-stock", headers=auth_headers(tok)).status_code == 403
