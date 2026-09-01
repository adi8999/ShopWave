import os
import json
import redis as redis_lib
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./shopwave.db"  # SQLite for local dev; swap for RDS PostgreSQL URL on AWS
)

# SQLite needs check_same_thread=False
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Redis ───────────────────────────────────────────────────────────────────

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

try:
    _redis_client = redis_lib.from_url(REDIS_URL, decode_responses=True)
    _redis_client.ping()
    REDIS_AVAILABLE = True
except Exception:
    _redis_client = None
    REDIS_AVAILABLE = False


def get_redis():
    return _redis_client


def cache_get(key: str):
    """Return cached dict/list or None."""
    if not REDIS_AVAILABLE or _redis_client is None:
        return None
    try:
        val = _redis_client.get(key)
        return json.loads(val) if val else None
    except Exception:
        return None


def cache_set(key: str, value, ttl: int = 300):
    """Set a JSON-serialisable value with TTL seconds."""
    if not REDIS_AVAILABLE or _redis_client is None:
        return
    try:
        _redis_client.setex(key, ttl, json.dumps(value))
    except Exception:
        pass


def cache_invalidate_pattern(pattern: str):
    """Delete all keys matching pattern (e.g. 'products:*')."""
    if not REDIS_AVAILABLE or _redis_client is None:
        return
    try:
        keys = _redis_client.keys(pattern)
        if keys:
            _redis_client.delete(*keys)
    except Exception:
        pass
