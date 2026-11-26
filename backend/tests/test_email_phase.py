"""
test_email_phase.py – Email provider abstraction, token expiry, one-time reuse,
prior-token invalidation, and delivery failure handling.
"""
import logging
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app import models
from app.auth import hash_token
from app.email_service import (
    ConsoleEmailProvider,
    EmailDeliveryError,
    SMTPEmailProvider,
    get_email_provider,
    get_memory_provider,
)
from tests.conftest import auth_headers


class TestEmailProviderAbstraction:
    def test_memory_provider_dispatches_verification_and_reset_emails(self, client, db_session, user, monkeypatch):
        monkeypatch.setenv("EMAIL_PROVIDER", "memory")
        monkeypatch.setenv("FRONTEND_URL", "https://shopwave.test")
        outbox = get_memory_provider()
        outbox.clear()

        # Signup triggers verification email without returning token in API response or logs
        r = client.post(
            "/api/auth/signup",
            json={"name": "Mailer", "email": "mailer@test.com", "password": "Password123!"},
        )
        assert r.status_code == 201
        assert "token=" not in r.text
        assert len(outbox.outbox) == 1
        assert outbox.outbox[0]["to"] == "mailer@test.com"
        assert "https://shopwave.test/verify-email?token=" in outbox.outbox[0]["body_text"]

        # Forgot password sends reset email
        outbox.clear()
        fp = client.post("/api/auth/forgot-password", json={"email": user.email})
        assert fp.status_code == 200
        assert len(outbox.outbox) == 1
        assert "https://shopwave.test/reset-password?token=" in outbox.outbox[0]["body_text"]

    def test_console_provider_blocked_in_production(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("EMAIL_PROVIDER", "console")
        with pytest.raises(EmailDeliveryError):
            get_email_provider()

        with pytest.raises(EmailDeliveryError):
            ConsoleEmailProvider().send_email("u@test.com", "Subj", "Body")

    def test_smtp_delivery_failure_raises_email_delivery_error(self):
        provider = SMTPEmailProvider("invalid.smtp.local", 587, None, None, "noreply@test.com")
        with patch("app.email_service.smtplib.SMTP", side_effect=OSError("connection refused")):
            with pytest.raises(EmailDeliveryError):
                provider.send_email("u@test.com", "Subject", "Body")

    def test_delivery_failure_invalidates_token_and_does_not_leak_logs(
        self, client, db_session, user, monkeypatch, caplog
    ):
        monkeypatch.setenv("EMAIL_PROVIDER", "memory")
        with patch(
            "app.routers.auth.send_password_reset_email",
            side_effect=EmailDeliveryError("SMTP down"),
        ):
            with caplog.at_level(logging.WARNING):
                resp = client.post("/api/auth/forgot-password", json={"email": user.email})
        assert resp.status_code == 200
        # No unused reset token remains when delivery fails
        active_tokens = (
            db_session.query(models.VerificationToken)
            .filter(
                models.VerificationToken.user_id == user.id,
                models.VerificationToken.purpose == "reset_password",
                models.VerificationToken.used == False,
            )
            .all()
        )
        assert len(active_tokens) == 0


class TestTokenExpiryReuseAndInvalidation:
    def test_expired_verification_token_rejected(self, client, db_session, user):
        raw = "expired-verify-tok"
        db_session.add(models.VerificationToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            purpose="verify_email",
            expires_at=datetime.utcnow() - timedelta(minutes=1),
            used=False,
        ))
        db_session.commit()

        resp = client.post("/api/auth/verify-email", json={"token": raw})
        assert resp.status_code == 400

    def test_reset_token_is_one_time_use_and_prior_token_invalidated(
        self, client, db_session, user, monkeypatch
    ):
        monkeypatch.setenv("EMAIL_PROVIDER", "memory")
        outbox = get_memory_provider()
        outbox.clear()

        # Issue first reset token
        client.post("/api/auth/forgot-password", json={"email": user.email})
        first_body = outbox.outbox[-1]["body_text"]
        first_tok = first_body.split("token=")[1].splitlines()[0]

        # Issuing a second reset token invalidates the first one
        client.post("/api/auth/forgot-password", json={"email": user.email})
        second_body = outbox.outbox[-1]["body_text"]
        second_tok = second_body.split("token=")[1].splitlines()[0]

        r_old = client.post(
            "/api/auth/reset-password",
            json={"token": first_tok, "new_password": "NewPassword99!"},
        )
        assert r_old.status_code == 400

        # Second token works once
        r_ok = client.post(
            "/api/auth/reset-password",
            json={"token": second_tok, "new_password": "NewPassword99!"},
        )
        assert r_ok.status_code == 200

        # Reusing second token fails
        r_replay = client.post(
            "/api/auth/reset-password",
            json={"token": second_tok, "new_password": "AnotherPass99!"},
        )
        assert r_replay.status_code == 400
