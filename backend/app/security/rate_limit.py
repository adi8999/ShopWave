"""
app/security/rate_limit.py
──────────────────────────
Redis-backed sliding-window rate limiter for FastAPI routes.
In development, falls back to a thread-safe in-memory counter when Redis is
unavailable.
In production (ENVIRONMENT=production), fails closed with HTTP 503 if Redis is
unavailable so rate limits cannot be bypassed across Gunicorn workers.
"""
import logging
import os
import threading
import time
from collections import defaultdict, deque
from typing import Deque

import redis
from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


def is_production() -> bool:
    return os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower() == "production"


def _get_trusted_proxies() -> set[str]:
    raw = os.getenv("TRUSTED_PROXIES", "127.0.0.1,::1")
    return {p.strip() for p in raw.split(",") if p.strip()}


# ── Redis Connection ──────────────────────────────────────────────────────────

def _get_redis() -> redis.Redis | None:
    url = os.getenv("REDIS_URL", "redis://localhost:6379")
    try:
        client = redis.from_url(url, socket_connect_timeout=1, decode_responses=True)
        client.ping()
        return client
    except Exception as exc:
        if is_production():
            logger.critical("CRITICAL: Redis unavailable in production: %s", exc)
        return None


_redis_client: redis.Redis | None = _get_redis()


# ── In-Memory Fallback (dev/test only) ────────────────────────────────────────

_mem_lock = threading.Lock()
_mem_store: dict[str, Deque[float]] = defaultdict(deque)


def _mem_is_allowed(key: str, max_requests: int, window: int) -> bool:
    now = time.time()
    cutoff = now - window
    with _mem_lock:
        dq = _mem_store[key]
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= max_requests:
            return False
        dq.append(now)
        return True


# ── Redis Sliding-Window Implementation ───────────────────────────────────────

_RATE_LIMIT_SCRIPT = """
local key    = KEYS[1]
local now    = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit  = tonumber(ARGV[3])
local cutoff = now - window

redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, now, now .. math.random())
    redis.call('EXPIRE', key, window)
    return 1
else
    return 0
end
"""


def _redis_is_allowed(
    r: redis.Redis, key: str, max_requests: int, window: int
) -> bool:
    try:
        result = r.eval(
            _RATE_LIMIT_SCRIPT,
            1,
            key,
            time.time(),
            window,
            max_requests,
        )
        return bool(result)
    except Exception as exc:
        logger.error("Redis rate-limit eval error: %s", exc)
        if is_production():
            # Fail closed in production
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiting service unavailable.",
            )
        return True


# ── Public Dependency ─────────────────────────────────────────────────────────

def _get_client_ip(request: Request) -> str:
    """
    Extract real client IP.
    Trust X-Forwarded-For ONLY when the immediate peer is a known trusted proxy
    (e.g. local Nginx on 127.0.0.1 / ::1).
    """
    peer_ip = request.client.host if request.client else "unknown"
    trusted = _get_trusted_proxies()
    if peer_ip in trusted:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Right-most untrusted IP or first client IP from trusted proxy
            return forwarded_for.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
    return peer_ip


class RateLimiter:
    def __init__(
        self,
        requests: int = 20,
        window_seconds: int = 60,
        key_prefix: str = "rl:default",
    ) -> None:
        self.max_requests = requests
        self.window = window_seconds
        self.prefix = key_prefix

    def __call__(self, request: Request) -> None:
        ip = _get_client_ip(request)
        redis_key = f"{self.prefix}:{ip}"

        if _redis_client is not None:
            allowed = _redis_is_allowed(
                _redis_client, redis_key, self.max_requests, self.window
            )
        else:
            if is_production():
                logger.critical(
                    "CRITICAL: Blocking request in production because Redis rate-limiter is unavailable"
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Security rate-limiting service unavailable.",
                )
            allowed = _mem_is_allowed(redis_key, self.max_requests, self.window)

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Rate limit exceeded: max {self.max_requests} requests "
                    f"per {self.window}s. Please slow down."
                ),
                headers={"Retry-After": str(self.window)},
            )


checkout_limiter = RateLimiter(
    requests=10,
    window_seconds=60,
    key_prefix="rl:checkout",
)

search_limiter = RateLimiter(
    requests=60,
    window_seconds=60,
    key_prefix="rl:search",
)

chat_limiter = RateLimiter(
    requests=20,
    window_seconds=60,
    key_prefix="rl:chat",
)

auth_limiter = RateLimiter(
    requests=15,
    window_seconds=60,
    key_prefix="rl:auth",
)
