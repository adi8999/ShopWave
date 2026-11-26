from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/api/wishlist", tags=["wishlist"])


@router.get("", response_model=List[schemas.WishlistItemOut])
def get_wishlist(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.WishlistItem)
        .join(models.Product, models.Product.id == models.WishlistItem.product_id)
        .filter(models.WishlistItem.user_id == current_user.id, models.Product.is_active == True)
        .order_by(models.WishlistItem.created_at.desc())
        .all()
    )


@router.post("/{product_id}", response_model=schemas.WishlistItemOut, status_code=201)
def add_to_wishlist(
    product_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = (
        db.query(models.Product)
        .filter(models.Product.id == product_id, models.Product.is_active == True)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = (
        db.query(models.WishlistItem)
        .filter(
            models.WishlistItem.user_id == current_user.id,
            models.WishlistItem.product_id == product_id,
        )
        .first()
    )
    if existing:
        return existing

    item = models.WishlistItem(user_id=current_user.id, product_id=product_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{product_id}", status_code=204)
def remove_from_wishlist(
    product_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(models.WishlistItem)
        .filter(
            models.WishlistItem.user_id == current_user.id,
            models.WishlistItem.product_id == product_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Wishlist item not found")
    db.delete(item)
    db.commit()
