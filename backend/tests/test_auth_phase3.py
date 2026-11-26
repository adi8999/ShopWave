"""
test_auth_phase3.py – Refresh token rotation, logout-all, password strength,
email verification, forgot/reset password, MFA, and account deletion.
"""
from datetime import datetime, timedelta
from app import models
from app.auth import hash_token, _totp_code
from tests.conftest import auth_headers
import time


class TestPasswordStrengthAndEnumeration:
    def test_weak_password_rejected_on_signup(self, client):
        resp = client.post(
            "/api/auth/signup",
            json={"name": "Weak", "email": "weak@test.com", "password": "abc"},
        )
        assert resp.status_code == 400

    def test_forgot_password_generic_response_prevents_enumeration(self, client, user):
        r1 = client.post("/api/auth/forgot-password", json={"email": user.email})
        r2 = client.post("/api/auth/forgot-password", json={"email": "nonexistent@test.com"})
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json() == r2.json()


class TestRefreshAndLogoutAll:
    def test_refresh_token_rotates_and_old_is_revoked(self, client, user):
        login_resp = client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "Password123!"},
        )
        assert login_resp.status_code == 200
        rt1 = login_resp.json()["refresh_token"]
        assert rt1

        ref_resp = client.post("/api/auth/refresh", json={"refresh_token": rt1})
        assert ref_resp.status_code == 200
        rt2 = ref_resp.json()["refresh_token"]
        assert rt2 != rt1

        # Old refresh token must now be rejected
        replay = client.post("/api/auth/refresh", json={"refresh_token": rt1})
        assert replay.status_code == 401

    def test_logout_all_invalidates_existing_access_token(self, client, user):
        login_resp = client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "Password123!"},
        )
        at = login_resp.json()["access_token"]
        rt = login_resp.json()["refresh_token"]

        out = client.post("/api/auth/logout-all", headers=auth_headers(at))
        assert out.status_code == 200

        # Old access token must now be rejected
        me_resp = client.get("/api/auth/me", headers=auth_headers(at))
        assert me_resp.status_code == 401

        # Old refresh token must also be revoked
        ref_resp = client.post("/api/auth/refresh", json={"refresh_token": rt})
        assert ref_resp.status_code == 401


class TestEmailVerificationAndPasswordReset:
    def test_verify_email_flow(self, client, db_session, user):
        raw = "verify-raw-token-123"
        db_session.add(models.VerificationToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            purpose="verify_email",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            used=False,
        ))
        db_session.commit()

        resp = client.post("/api/auth/verify-email", json={"token": raw})
        assert resp.status_code == 200
        db_session.refresh(user)
        assert user.is_verified is True

    def test_reset_password_flow(self, client, db_session, user):
        raw = "reset-raw-token-123"
        db_session.add(models.VerificationToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            purpose="reset_password",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            used=False,
        ))
        db_session.commit()

        resp = client.post(
            "/api/auth/reset-password",
            json={"token": raw, "new_password": "NewStrongPass99!"},
        )
        assert resp.status_code == 200

        login = client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "NewStrongPass99!"},
        )
        assert login.status_code == 200


class TestMFAAndAccountDeletion:
    def test_mfa_setup_enable_and_login(self, client, admin):
        login_resp = client.post(
            "/api/auth/login",
            json={"email": admin.email, "password": "AdminPass123!"},
        )
        at = login_resp.json()["access_token"]

        setup = client.post("/api/auth/mfa/setup", headers=auth_headers(at))
        assert setup.status_code == 200
        secret = setup.json()["secret"]

        code = _totp_code(secret, int(time.time() // 30))
        enable = client.post("/api/auth/mfa/enable", json={"code": code}, headers=auth_headers(at))
        assert enable.status_code == 200

        # Login without MFA code must fail
        fail_login = client.post(
            "/api/auth/login",
            json={"email": admin.email, "password": "AdminPass123!"},
        )
        assert fail_login.status_code == 401

        # Login with MFA code succeeds
        ok_login = client.post(
            "/api/auth/login",
            json={"email": admin.email, "password": "AdminPass123!", "mfa_code": code},
        )
        assert ok_login.status_code == 200

    def test_delete_account(self, client, user):
        login_resp = client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "Password123!"},
        )
        at = login_resp.json()["access_token"]
        del_resp = client.delete("/api/auth/me", headers=auth_headers(at))
        assert del_resp.status_code == 200

        # Cannot log in anymore
        relogin = client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "Password123!"},
        )
        assert relogin.status_code == 401
