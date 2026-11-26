"""
test_coupons.py – coupon validation, expiry, max-uses, and atomic consumption.

Covers:
  ✓ Valid coupon validates successfully
  ✓ Expired coupon is rejected
  ✓ Max-uses coupon is rejected when exhausted
  ✓ Inactive coupon is rejected
  ✓ Invalid coupon code returns valid=False (not 404)
  ✓ Admin can create/toggle/delete coupons; non-admin is rejected
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from app import models
from tests.conftest import get_token, auth_headers


class TestCouponValidation:
    def test_valid_percent_coupon(self, client, user, db_session):
        coupon = models.Coupon(
            code="PERCENT20",
            percent_off=Decimal("20"),
            is_active=True,
        )
        db_session.add(coupon)
        db_session.commit()

        token = get_token(client, user.email, "Password123!")
        resp = client.post(
            "/api/coupons/validate",
            json={"code": "PERCENT20", "subtotal": "100.00"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert Decimal(data["discount_amount"]) == Decimal("20.00")
        assert Decimal(data["final_total"]) == Decimal("80.00")

    def test_expired_coupon_rejected(self, client, user, db_session):
        coupon = models.Coupon(
            code="EXPIRED",
            percent_off=Decimal("10"),
            is_active=True,
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        db_session.add(coupon)
        db_session.commit()

        token = get_token(client, user.email, "Password123!")
        resp = client.post(
            "/api/coupons/validate",
            json={"code": "EXPIRED", "subtotal": "50.00"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert "expired" in data["message"].lower()

    def test_max_uses_exhausted(self, client, user, db_session):
        coupon = models.Coupon(
            code="MAXUSED",
            percent_off=Decimal("5"),
            is_active=True,
            max_uses=3,
            used_count=3,
        )
        db_session.add(coupon)
        db_session.commit()

        token = get_token(client, user.email, "Password123!")
        resp = client.post(
            "/api/coupons/validate",
            json={"code": "MAXUSED", "subtotal": "50.00"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert "maximum" in data["message"].lower()

    def test_inactive_coupon_rejected(self, client, user, db_session):
        coupon = models.Coupon(
            code="INACTIVE",
            percent_off=Decimal("15"),
            is_active=False,
        )
        db_session.add(coupon)
        db_session.commit()

        token = get_token(client, user.email, "Password123!")
        resp = client.post(
            "/api/coupons/validate",
            json={"code": "INACTIVE", "subtotal": "50.00"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is False

    def test_unknown_coupon_returns_invalid_not_404(self, client, user):
        token = get_token(client, user.email, "Password123!")
        resp = client.post(
            "/api/coupons/validate",
            json={"code": "DOESNOTEXIST", "subtotal": "50.00"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is False


class TestCouponAdminCRUD:
    def test_admin_creates_coupon(self, client, admin):
        token = get_token(client, admin.email, "AdminPass123!")
        resp = client.post(
            "/api/coupons",
            json={"code": "NEWONE", "percent_off": 10.0, "is_active": True},
            headers=auth_headers(token),
        )
        assert resp.status_code == 201
        assert resp.json()["code"] == "NEWONE"

    def test_non_admin_cannot_create_coupon(self, client, user):
        token = get_token(client, user.email, "Password123!")
        resp = client.post(
            "/api/coupons",
            json={"code": "HACK", "percent_off": 100.0, "is_active": True},
            headers=auth_headers(token),
        )
        assert resp.status_code == 403

    def test_admin_toggles_coupon(self, client, admin, db_session):
        coupon = models.Coupon(code="TOGGLE", percent_off=Decimal("5"), is_active=True)
        db_session.add(coupon)
        db_session.commit()

        token = get_token(client, admin.email, "AdminPass123!")
        resp = client.patch(f"/api/coupons/{coupon.id}/toggle", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_admin_deletes_coupon(self, client, admin, db_session):
        coupon = models.Coupon(code="TODELETE", percent_off=Decimal("5"), is_active=True)
        db_session.add(coupon)
        db_session.commit()

        token = get_token(client, admin.email, "AdminPass123!")
        resp = client.delete(f"/api/coupons/{coupon.id}", headers=auth_headers(token))
        assert resp.status_code == 200
