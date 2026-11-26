import logging
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import (
    hash_password,
    verify_password,
    validate_password_strength,
    create_access_token,
    create_refresh_token_record,
    hash_token,
    get_current_user,
    generate_totp_secret,
    verify_totp,
)
from app.database import get_db
from app.email_service import (
    EmailDeliveryError,
    send_password_reset_email,
    send_verification_email,
)
from app.security.rate_limit import auth_limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _issue_verification_token(user_id: int, purpose: str, db: Session, hours: int = 24) -> tuple[str, models.VerificationToken]:
    """Invalidate any prior unused tokens for the same user/purpose and issue a fresh one."""
    db.query(models.VerificationToken).filter(
        models.VerificationToken.user_id == user_id,
        models.VerificationToken.purpose == purpose,
        models.VerificationToken.used == False,
    ).update({"used": True})

    raw = secrets.token_urlsafe(32)
    record = models.VerificationToken(
        user_id=user_id,
        token_hash=hash_token(raw),
        purpose=purpose,
        expires_at=datetime.utcnow() + timedelta(hours=hours),
        used=False,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return raw, record


@router.post("/signup", response_model=schemas.Token, status_code=201)
def signup(
    user_data: schemas.UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    _rl: None = Depends(auth_limiter),
):
    validate_password_strength(user_data.password)

    existing = db.query(models.User).filter(models.User.email == user_data.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Unable to complete registration with that email")

    user = models.User(
        name=user_data.name.strip(),
        email=user_data.email.lower(),
        hashed_password=hash_password(user_data.password),
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    verify_tok, record = _issue_verification_token(user.id, "verify_email", db, hours=24)
    try:
        send_verification_email(user.email, verify_tok)
    except EmailDeliveryError:
        # Invalidate undelivered token rather than leaving a dangling token or failing signup
        record.used = True
        db.commit()
        logger.warning("Verification email delivery failed for user_id=%s", user.id)

    access_token = create_access_token({"sub": str(user.id)}, token_version=user.token_version)
    refresh_token = create_refresh_token_record(user, db)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }


@router.post("/login", response_model=schemas.Token)
def login(
    credentials: schemas.UserLogin,
    request: Request,
    db: Session = Depends(get_db),
    _rl: None = Depends(auth_limiter),
):
    user = db.query(models.User).filter(models.User.email == credentials.email.lower()).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if user.mfa_enabled:
        if not credentials.mfa_code or not verify_totp(user.mfa_secret or "", credentials.mfa_code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="MFA code required or invalid",
            )

    access_token = create_access_token({"sub": str(user.id)}, token_version=user.token_version)
    refresh_token = create_refresh_token_record(user, db)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }


@router.post("/refresh", response_model=schemas.Token)
def refresh_access_token(
    payload: schemas.RefreshRequest,
    db: Session = Depends(get_db),
):
    """Rotate refresh token and issue a fresh short-lived access token."""
    tok_hash = hash_token(payload.refresh_token)
    record = (
        db.query(models.RefreshToken)
        .filter(
            models.RefreshToken.token_hash == tok_hash,
            models.RefreshToken.revoked == False,
        )
        .first()
    )
    if not record or record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = db.query(models.User).filter(models.User.id == record.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    record.revoked = True
    db.commit()

    new_access = create_access_token({"sub": str(user.id)}, token_version=user.token_version)
    new_refresh = create_refresh_token_record(user, db)
    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "user": user,
    }


@router.post("/logout")
def logout(payload: schemas.RefreshRequest, db: Session = Depends(get_db)):
    tok_hash = hash_token(payload.refresh_token)
    record = db.query(models.RefreshToken).filter(models.RefreshToken.token_hash == tok_hash).first()
    if record:
        record.revoked = True
        db.commit()
    return {"message": "Logged out"}


@router.post("/logout-all")
def logout_all_sessions(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Invalidate all access and refresh tokens for the current user."""
    current_user.token_version += 1
    db.query(models.RefreshToken).filter(
        models.RefreshToken.user_id == current_user.id,
        models.RefreshToken.revoked == False,
    ).update({"revoked": True})
    db.commit()
    return {"message": "All sessions invalidated"}


@router.post("/verify-email")
def verify_email(payload: schemas.VerifyEmailRequest, db: Session = Depends(get_db)):
    tok_hash = hash_token(payload.token)
    record = (
        db.query(models.VerificationToken)
        .filter(
            models.VerificationToken.token_hash == tok_hash,
            models.VerificationToken.purpose == "verify_email",
            models.VerificationToken.used == False,
        )
        .first()
    )
    if not record or record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    user = db.query(models.User).filter(models.User.id == record.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid verification token")

    user.is_verified = True
    record.used = True
    db.commit()
    return {"message": "Email verified successfully"}


@router.post("/resend-verification")
def resend_verification(
    payload: schemas.ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    _rl: None = Depends(auth_limiter),
):
    """Re-send email verification link without leaking whether the email exists."""
    user = db.query(models.User).filter(models.User.email == payload.email.lower()).first()
    if user and not user.is_verified:
        raw, record = _issue_verification_token(user.id, "verify_email", db, hours=24)
        try:
            send_verification_email(user.email, raw)
        except EmailDeliveryError:
            record.used = True
            db.commit()
            logger.warning("Resend verification email failed for user_id=%s", user.id)
    return {"message": "If an unverified account with that email exists, a verification link has been sent."}


@router.post("/forgot-password")
def forgot_password(
    payload: schemas.ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    _rl: None = Depends(auth_limiter),
):
    """Always returns 200 with a generic message to prevent account enumeration."""
    user = db.query(models.User).filter(models.User.email == payload.email.lower()).first()
    if user:
        raw, record = _issue_verification_token(user.id, "reset_password", db, hours=1)
        try:
            send_password_reset_email(user.email, raw)
        except EmailDeliveryError:
            record.used = True
            db.commit()
            logger.warning("Password reset email delivery failed for user_id=%s", user.id)
    return {"message": "If an account with that email exists, a password reset link has been sent."}


@router.post("/reset-password")
def reset_password(payload: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    validate_password_strength(payload.new_password)
    tok_hash = hash_token(payload.token)
    record = (
        db.query(models.VerificationToken)
        .filter(
            models.VerificationToken.token_hash == tok_hash,
            models.VerificationToken.purpose == "reset_password",
            models.VerificationToken.used == False,
        )
        .first()
    )
    if not record or record.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user = db.query(models.User).filter(models.User.id == record.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    user.hashed_password = hash_password(payload.new_password)
    user.token_version += 1  # Invalidate all existing sessions
    record.used = True
    db.query(models.RefreshToken).filter(
        models.RefreshToken.user_id == user.id,
        models.RefreshToken.revoked == False,
    ).update({"revoked": True})
    db.commit()
    return {"message": "Password reset successfully"}


@router.post("/mfa/setup")
def mfa_setup(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    secret = generate_totp_secret()
    current_user.mfa_secret = secret
    db.commit()
    otpauth_uri = f"otpauth://totp/ShopWave:{current_user.email}?secret={secret}&issuer=ShopWave"
    return {"secret": secret, "otpauth_uri": otpauth_uri}


@router.post("/mfa/enable")
def mfa_enable(
    payload: schemas.MfaVerifyRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.mfa_secret or not verify_totp(current_user.mfa_secret, payload.code):
        raise HTTPException(status_code=400, detail="Invalid MFA code")
    current_user.mfa_enabled = True
    db.commit()
    return {"message": "MFA enabled"}


@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.delete("/me")
def delete_my_account(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete user account (or anonymize if orders exist to preserve financial records)."""
    has_orders = db.query(models.Order).filter(models.Order.user_id == current_user.id).first() is not None
    db.query(models.CartItem).filter(models.CartItem.user_id == current_user.id).delete()
    db.query(models.RefreshToken).filter(models.RefreshToken.user_id == current_user.id).delete()
    if has_orders:
        current_user.name = f"Deleted User #{current_user.id}"
        current_user.email = f"deleted_{current_user.id}_{secrets.token_hex(4)}@deleted.local"
        current_user.hashed_password = hash_password(secrets.token_urlsafe(32))
        current_user.token_version += 1
    else:
        db.delete(current_user)
    db.commit()
    return {"message": "Account deleted"}
