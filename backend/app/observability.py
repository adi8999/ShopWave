"""
app/observability.py – Structured JSON logging, lightweight request metrics,
and optional Sentry integration.
"""
import json
import logging
import os
import time
from collections import Counter
from datetime import datetime
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    if os.getenv("LOG_FORMAT", "json").lower() == "json":
        handler = logging.StreamHandler()
        handler.setFormatter(JsonLogFormatter())
        root = logging.getLogger()
        root.handlers = [handler]
        root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())


def configure_sentry() -> None:
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if dsn:
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=dsn,
                traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
                environment=os.getenv("ENVIRONMENT", "development"),
            )
        except ImportError:
            logging.getLogger(__name__).warning("SENTRY_DSN set but sentry-sdk is not installed")


_metrics_counter: Counter = Counter()


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _metrics_counter["http_requests_total"] += 1
        _metrics_counter[f"http_status_{response.status_code}"] += 1
        response.headers.setdefault("X-Response-Time-Ms", str(elapsed_ms))
        return response


def get_metrics_snapshot() -> dict:
    return dict(_metrics_counter)
