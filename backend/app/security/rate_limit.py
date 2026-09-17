"""
app/security/rate_limit.py
──────────────────────────
Redis-backed sliding-window rate limiter for FastAPI routes.
Falls back to a thread-safe in-memory counter when Redis is unavailable
so the server never crashes due to a missing cache layer.

Usage
-----
from app.security.rate_limit import RateLimiter

limiter = RateLimiter(requests=20, window_seconds=60)

@router.post("/create-checkout-session")
def checkout(request: Request, _=Depends(limiter)):
    ...
"""
from __future__ import annotations

import os
import time
import threading
from collections import defaultdict, deque
from typing import Deque

import redis
from fastapi import Depends, HTTPException, Request, status


# ── Redis Connection ──────────────────────────────────────────────────────────

def _get_redis() -> redis.Redis | None:
    """
    Attempt to connect to Redis using REDIS_URL env var
    (e.g. redis://localhost:6379 or a Redis Cloud / Upstash URL).
    Returns None if the connection fails so callers can fall back gracefully.
    """
    url = os.getenv("REDIS_URL", "redis://localhost:6379")
    try:
        client = redis.from_url(url, socket_connect_timeout=1, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


_redis_client: redis.Redis | None = _get_redis()


# ── In-Memory Fallback ────────────────────────────────────────────────────────

_mem_lock = threading.Lock()
# key → deque of timestamps (float seconds)
_mem_store: dict[str, Deque[float]] = defaultdict(deque)


def _mem_is_allowed(key: str, max_requests: int, window: int) -> bool:
    """Sliding-window check using an in-memory deque (thread-safe)."""
    now = time.time()
    cutoff = now - window
    with _mem_lock:
        dq = _mem_store[key]
        # Evict expired timestamps
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
    """Lua-atomic sliding-window check in Redis (precise, race-condition free)."""
    try:
        result = r.eval(
            _RATE_LIMIT_SCRIPT,
            1,  # numkeys
            key,
            time.time(),
            window,
            max_requests,
        )
        return bool(result)
    except Exception:
        # If Redis errors during eval, fail open (allow request) to avoid outage
        return True


# ── Public Dependency ─────────────────────────────────────────────────────────


def _get_client_ip(request: Request) -> str:
    """Extract real client IP, respecting X-Forwarded-For set by a trusted proxy."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Use the first IP (original client) if the header contains a chain
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    """
    FastAPI dependency that enforces a sliding-window rate limit per client IP.

    Parameters
    ----------
    requests : int
        Maximum number of allowed requests within ``window_seconds``.
    window_seconds : int
        Duration of the sliding window in seconds.
    key_prefix : str
        Redis key prefix to namespace limits (e.g. ``"rl:checkout"``).

    Example
    -------
    checkout_limiter = RateLimiter(requests=10, window_seconds=60, key_prefix="rl:checkout")
    search_limiter   = RateLimiter(requests=30, window_seconds=60, key_prefix="rl:search")

    @router.post("/create-checkout-session")
    def checkout(request: Request, _=Depends(checkout_limiter)):
        ...
    """

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


# ── Pre-configured limiters (import and use directly) ────────────────────────

#: Strict limiter for checkout — 10 requests / 60 s per IP
checkout_limiter = RateLimiter(
    requests=10,
    window_seconds=60,
    key_prefix="rl:checkout",
)

#: Generous limiter for search — 60 requests / 60 s per IP
search_limiter = RateLimiter(
    requests=60,
    window_seconds=60,
    key_prefix="rl:search",
)

#: Chat / AI limiter — 20 requests / 60 s per IP
chat_limiter = RateLimiter(
    requests=20,
    window_seconds=60,
    key_prefix="rl:chat",
)
