import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine
from app import models
from app.routers import auth, products, cart, orders, admin, payments, chat, coupons

# Create all tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ShopWave API",
    description="Full-stack e-commerce backend with JWT auth, cart, and orders",
    version="1.0.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Read ALLOWED_ORIGINS from env (comma-separated). In production, set this
# to your real domain(s), e.g.: https://shopwave.example.com
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
ALLOWED_ORIGINS: list[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(admin.router)
app.include_router(payments.router)
app.include_router(chat.router)
app.include_router(coupons.router)


@app.get("/")
def root():
    return {
        "message": "ShopWave API is running 🛍️",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    """Lightweight health check endpoint for monitoring (Render, UptimeRobot, etc.) without hitting the DB."""
    return {"status": "ok"}


# NOTE: seed() is intentionally NOT called on startup.
# Gunicorn starts 2 workers simultaneously — running seed on startup creates
# a race condition. Run seeding manually once before starting gunicorn:
#   python -m app.seed
