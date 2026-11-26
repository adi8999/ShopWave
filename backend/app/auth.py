import base64
import hashlib
import hmac
import logging
import os
import re
import secrets
import struct
import time
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app import models

logger = logging.getLogger(__name__)

# ── Secret key enforcement ────────────────────────────────────────────────────
_SECRET_KEY = os.getenv("SECRET_KEY", "")
if not _SECRET_KEY or len(_SECRET_KEY) < 32:
    raise RuntimeError(
        "SECRET_KEY environment variable is missing or shorter than 32 characters. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )


SECRET_KEY: str = _SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "14"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login", auto_error=False
)


def validate_password_strength(password: str) -> None:
    """Enforce strong password policy (>= 8 chars, upper, lower, digit)."""
    if len(password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long.",
        )
    if not re.search(r"[A-Z]", password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one uppercase letter.",
        )
    if not re.search(r"[a-z]", password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one lowercase letter.",
        )
    if not re.search(r"\d", password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one digit.",
        )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:72],
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt(rounds=12)).decode("utf-8")


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    token_version: int = 0,
) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "ver": token_version, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token_record(user: models.User, db: Session) -> str:
    raw = secrets.token_urlsafe(48)
    record = models.RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw),
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        revoked=False,
    )
    db.add(record)
    db.commit()
    return raw


# ── TOTP MFA Helpers (RFC 6238, stdlib only) ──────────────────────────────────

def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii")


def _totp_code(secret_b32: str, counter: int) -> str:
    key = base64.b32decode(secret_b32, casefold=True)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{code_int % 1_000_000:06d}"


def verify_totp(secret_b32: str, code: str, window: int = 1) -> bool:
    if not secret_b32 or not code or not code.isdigit():
        return False
    now_counter = int(time.time() // 30)
    for delta in range(-window, window + 1):
        if hmac.compare_digest(_totp_code(secret_b32, now_counter + delta), code):
            return True
    return False


# ── User Dependencies ─────────────────────────────────────────────────────────

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_ver = payload.get("ver", 0)
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if user is None or user.token_version != token_ver:
        raise credentials_exception
    return user


def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> Optional[models.User]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            return None
        token_ver = payload.get("ver", 0)
        user = db.query(models.User).filter(models.User.id == int(user_id)).first()
        if user is None or user.token_version != token_ver:
            return None
        return user
    except Exception:
        return None


def get_admin_user(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ── Admin Audit Logger ────────────────────────────────────────────────────────

def log_admin_action(
    db: Session,
    admin_id: int,
    action: str,
    target_type: str,
    target_id: Optional[str] = None,
    details: Optional[str] = None,
    request: Optional[Request] = None,
) -> None:
    ip = None
    if request and request.client:
        ip = request.client.host
    entry = models.AuditLog(
        admin_id=admin_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        details=details,
        ip_address=ip,
    )
    db.add(entry)
    logger.info(
        "ADMIN_AUDIT admin_id=%s action=%s target=%s:%s",
        admin_id, action, target_type, target_id,
    )
