from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user
from app.database import get_db
from app.security.rate_limit import checkout_limiter

router = APIRouter(prefix="/api/coupons", tags=["coupons"])


def calculate_discount(coupon: models.Coupon, subtotal: float) -> float:
    """Compute discount dollar amount based on percent_off or amount_off."""
    discount = 0.0
    if coupon.percent_off:
        discount = round(subtotal * (coupon.percent_off / 100.0), 2)
    elif coupon.amount_off:
        discount = round(min(subtotal, coupon.amount_off), 2)
    return max(0.0, discount)


@router.post("/validate", response_model=schemas.CouponValidateResponse)
def validate_coupon(
    payload: schemas.CouponValidateRequest,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _rl: None = Depends(checkout_limiter),
):
    """Validate a coupon code and calculate savings for checkout preview."""
    clean_code = payload.code.strip().upper()
    if not clean_code:
        raise HTTPException(status_code=400, detail="Please provide a coupon code")

    coupon = db.query(models.Coupon).filter(models.Coupon.code == clean_code).first()
    if not coupon or not coupon.is_active:
        return schemas.CouponValidateResponse(
            valid=False,
            message=f"Coupon code '{clean_code}' is invalid or no longer active.",
            discount_amount=0.0,
            final_total=payload.subtotal,
        )

    # Check expiration date
    if coupon.expires_at and coupon.expires_at < datetime.utcnow():
        return schemas.CouponValidateResponse(
            valid=False,
            message=f"Coupon code '{clean_code}' expired on {coupon.expires_at.strftime('%b %d, %Y')}.",
            discount_amount=0.0,
            final_total=payload.subtotal,
        )

    # Check maximum redemption count
    if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
        return schemas.CouponValidateResponse(
            valid=False,
            message=f"Coupon code '{clean_code}' has reached its maximum redemptions.",
            discount_amount=0.0,
            final_total=payload.subtotal,
        )

    discount = calculate_discount(coupon, payload.subtotal)
    final_total = max(0.0, round(payload.subtotal - discount, 2))

    detail_msg = f"{coupon.percent_off:.0f}% off" if coupon.percent_off else f"${coupon.amount_off:.2f} off"
    return schemas.CouponValidateResponse(
        valid=True,
        message=f"Promo code '{clean_code}' applied! Saving ${discount:.2f} ({detail_msg}).",
        code=clean_code,
        discount_amount=discount,
        final_total=final_total,
    )


# ── Admin CRUD Endpoints ──────────────────────────────────────────────────────

def require_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user


@router.get("", response_model=List[schemas.CouponOut])
def list_coupons(
    _admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin: List all coupons."""
    return db.query(models.Coupon).order_by(models.Coupon.created_at.desc()).all()


@router.post("", response_model=schemas.CouponOut, status_code=201)
def create_coupon(
    payload: schemas.CouponCreate,
    _admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin: Create a new promotional discount coupon."""
    clean_code = payload.code.strip().upper()
    if not clean_code or len(clean_code) < 3:
        raise HTTPException(status_code=400, detail="Coupon code must be at least 3 characters")

    existing = db.query(models.Coupon).filter(models.Coupon.code == clean_code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Coupon '{clean_code}' already exists")

    if not payload.percent_off and not payload.amount_off:
        raise HTTPException(status_code=400, detail="Coupon must specify either percent_off or amount_off")

    if payload.percent_off and (payload.percent_off <= 0 or payload.percent_off > 100):
        raise HTTPException(status_code=400, detail="Percent off must be between 1 and 100")

    if payload.amount_off and payload.amount_off <= 0:
        raise HTTPException(status_code=400, detail="Amount off must be greater than zero")

    coupon = models.Coupon(
        code=clean_code,
        percent_off=payload.percent_off,
        amount_off=payload.amount_off,
        expires_at=payload.expires_at,
        max_uses=payload.max_uses,
        is_active=payload.is_active,
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return coupon


@router.patch("/{coupon_id}/toggle", response_model=schemas.CouponOut)
def toggle_coupon_status(
    coupon_id: int,
    _admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin: Activate or deactivate a coupon."""
    coupon = db.query(models.Coupon).filter(models.Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    coupon.is_active = not coupon.is_active
    db.commit()
    db.refresh(coupon)
    return coupon


@router.delete("/{coupon_id}", status_code=200)
def delete_coupon(
    coupon_id: int,
    _admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin: Delete a coupon."""
    coupon = db.query(models.Coupon).filter(models.Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    db.delete(coupon)
    db.commit()
    return {"message": f"Coupon '{coupon.code}' successfully deleted", "id": coupon_id}
