"""
app/email_service.py – Email provider abstraction for verification & password reset.

Supported providers (configured via EMAIL_PROVIDER env var):
  • smtp    – Standard SMTP / TLS using SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
  • ses     – AWS SES via boto3 using AWS_SES_REGION (and standard AWS env/IAM creds)
  • memory  – In-memory outbox for automated unit/integration tests
  • console – Explicit development-only logger (never logs raw tokens; blocked in production)
"""
from __future__ import annotations

import logging
import os
import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage
from typing import List, Dict

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """Raised when sending an email fails or provider configuration is invalid."""


class EmailProvider(ABC):
    @abstractmethod
    def send_email(self, to_email: str, subject: str, body_text: str) -> None:
        """Send an email or raise EmailDeliveryError."""


class MemoryEmailProvider(EmailProvider):
    """Stores sent emails in memory for tests without logging tokens."""

    def __init__(self) -> None:
        self.outbox: List[Dict[str, str]] = []

    def send_email(self, to_email: str, subject: str, body_text: str) -> None:
        self.outbox.append({
            "to": to_email,
            "subject": subject,
            "body_text": body_text,
        })

    def clear(self) -> None:
        self.outbox.clear()


class ConsoleEmailProvider(EmailProvider):
    """
    Explicit non-production email provider.
    Logs only the recipient domain and subject — NEVER raw verification/reset tokens.
    """

    def send_email(self, to_email: str, subject: str, body_text: str) -> None:
        if os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower() == "production":
            raise EmailDeliveryError("ConsoleEmailProvider is disabled in production.")
        domain = to_email.split("@")[-1] if "@" in to_email else "unknown"
        logger.info("DEV_EMAIL_DISPATCH domain=%s subject=%r (body redacted)", domain, subject)


class SMTPEmailProvider(EmailProvider):
    def __init__(
        self,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        from_email: str,
        use_tls: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.use_tls = use_tls

    def send_email(self, to_email: str, subject: str, body_text: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.from_email
        msg["To"] = to_email
        msg.set_content(body_text)

        try:
            with smtplib.SMTP(self.host, self.port, timeout=10) as server:
                if self.use_tls:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.send_message(msg)
        except Exception as exc:
            logger.error("SMTP delivery failed: %s", type(exc).__name__)
            raise EmailDeliveryError("Failed to deliver email via SMTP.") from exc


class SESEmailProvider(EmailProvider):
    def __init__(self, region: str, from_email: str) -> None:
        self.region = region
        self.from_email = from_email

    def send_email(self, to_email: str, subject: str, body_text: str) -> None:
        try:
            import boto3
            client = boto3.client("ses", region_name=self.region)
            client.send_email(
                Source=self.from_email,
                Destination={"ToAddresses": [to_email]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": body_text, "Charset": "UTF-8"}},
                },
            )
        except Exception as exc:
            logger.error("SES delivery failed: %s", type(exc).__name__)
            raise EmailDeliveryError("Failed to deliver email via AWS SES.") from exc


_memory_provider = MemoryEmailProvider()


def get_memory_provider() -> MemoryEmailProvider:
    return _memory_provider


def get_email_provider() -> EmailProvider:
    is_prod = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower() == "production"
    provider_name = os.getenv("EMAIL_PROVIDER", "").strip().lower()
    from_email = os.getenv("EMAIL_FROM", "noreply@shopwave.local")

    if not provider_name:
        if is_prod:
            raise EmailDeliveryError("EMAIL_PROVIDER is not configured in production.")
        provider_name = "console"

    if provider_name == "memory":
        return _memory_provider

    if provider_name == "console":
        if is_prod:
            raise EmailDeliveryError("Console email provider cannot be used in production.")
        return ConsoleEmailProvider()

    if provider_name == "smtp":
        host = os.getenv("SMTP_HOST", "").strip()
        if not host:
            raise EmailDeliveryError("SMTP_HOST must be set when EMAIL_PROVIDER=smtp.")
        port = int(os.getenv("SMTP_PORT", "587"))
        username = os.getenv("SMTP_USER") or None
        password = os.getenv("SMTP_PASSWORD") or None
        use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        return SMTPEmailProvider(host, port, username, password, from_email, use_tls)

    if provider_name == "ses":
        region = os.getenv("AWS_SES_REGION", os.getenv("AWS_REGION", "")).strip()
        if not region:
            raise EmailDeliveryError("AWS_SES_REGION must be set when EMAIL_PROVIDER=ses.")
        return SESEmailProvider(region, from_email)

    raise EmailDeliveryError(f"Unsupported EMAIL_PROVIDER: {provider_name}")


def send_verification_email(to_email: str, token: str) -> None:
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    verify_link = f"{frontend_url}/verify-email?token={token}"
    subject = "Verify your ShopWave email address"
    body = (
        "Welcome to ShopWave!\n\n"
        f"Please verify your email address by visiting:\n{verify_link}\n\n"
        "This link expires in 24 hours and can only be used once."
    )
    get_email_provider().send_email(to_email, subject, body)


def send_password_reset_email(to_email: str, token: str) -> None:
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    reset_link = f"{frontend_url}/reset-password?token={token}"
    subject = "Reset your ShopWave password"
    body = (
        "We received a request to reset your ShopWave password.\n\n"
        f"Reset your password using this link:\n{reset_link}\n\n"
        "This link expires in 1 hour and can only be used once. "
        "If you did not request this, you can safely ignore this message."
    )
    get_email_provider().send_email(to_email, subject, body)
