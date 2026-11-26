import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.database import REDIS_AVAILABLE
from app.observability import (
    configure_logging,
    configure_sentry,
    MetricsMiddleware,
    get_metrics_snapshot,
)
from app.routers import auth, products, cart, orders, admin, payments, chat, coupons, wishlist
from app.security.rate_limit import is_production

configure_logging()
configure_sentry()
logger = logging.getLogger("shopwave")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate security-critical configuration on startup."""
    if is_production():
        missing = []
        if not os.getenv("STRIPE_WEBHOOK_SECRET"):
            missing.append("STRIPE_WEBHOOK_SECRET")
        if not REDIS_AVAILABLE:
            missing.append("REDIS_URL (Redis unreachable)")
        if missing:
            msg = f"CRITICAL SECURITY CONFIG MISSING IN PRODUCTION: {', '.join(missing)}"
            logger.critical(msg)
            if os.getenv("FAIL_CLOSED_ON_STARTUP", "true").lower() == "true":
                raise RuntimeError(msg)
    yield


app = FastAPI(
    title="ShopWave API",
    description="Full-stack e-commerce backend with JWT auth, cart, and orders",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Request Size Limit Middleware ─────────────────────────────────────────────
MAX_BODY_BYTES = int(os.getenv("MAX_REQUEST_BODY_BYTES", str(2 * 1024 * 1024)))  # 2 MB
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BODY_BYTES", str(10 * 1024 * 1024)))  # 10 MB


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        limit = (
            MAX_UPLOAD_BYTES
            if request.url.path.startswith("/api/admin/products/upload-image")
            else MAX_BODY_BYTES
        )
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > limit:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": f"Request body too large (max {limit} bytes)."},
                    )
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header."})
        return await call_next(request)


# ── Security Headers Middleware ───────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(MetricsMiddleware)

# ── CORS ──────────────────────────────────────────────────────────────────────
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
ALLOWED_ORIGINS: list[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Requested-With"],
)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(admin.router)
app.include_router(payments.router)
app.include_router(chat.router)
app.include_router(coupons.router)
app.include_router(wishlist.router)


@app.get("/")
@app.get("/api")
@app.get("/api/")
def root():
    return {
        "message": "ShopWave API is running 🛍️",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "products": "/api/products",
            "auth": "/api/auth",
            "cart": "/api/cart",
            "orders": "/api/orders",
            "coupons": "/api/coupons",
            "chat": "/api/chat",
        },
    }


@app.get("/health")
@app.get("/api/health")
def health():
    """Lightweight health check endpoint for monitoring without hitting the DB."""
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    """Lightweight JSON metrics endpoint."""
    return get_metrics_snapshot()


@app.get("/api/docs", include_in_schema=False)
def api_docs():
    return RedirectResponse(url="/docs")
