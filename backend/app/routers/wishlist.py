from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/api/wishlist", tags=["wishlist"])


@router.get("", response_model=List[schemas.ProductOut])
def get_wishlist(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch all products in the current user's wishlist."""
    items = (
        db.query(models.WishlistItem)
        .filter(models.WishlistItem.user_id == current_user.id)
        .order_by(models.WishlistItem.created_at.desc())
        .all()
    )
    return [item.product for item in items if item.product is not None]


@router.get("/ids", response_model=List[int])
def get_wishlist_ids(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fast lookup of all product IDs in user's wishlist."""
    items = (
        db.query(models.WishlistItem.product_id)
        .filter(models.WishlistItem.user_id == current_user.id)
        .all()
    )
    return [pid for (pid,) in items]


@router.post("/{product_id}")
def toggle_wishlist_item(
    product_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Toggle a product in/out of the user's wishlist."""
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
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
        db.delete(existing)
        db.commit()
        return {
            "in_wishlist": False,
            "message": f"Removed '{product.name}' from your wishlist",
            "product_id": product_id,
        }

    item = models.WishlistItem(user_id=current_user.id, product_id=product_id)
    db.add(item)
    db.commit()
    return {
        "in_wishlist": True,
        "message": f"Added '{product.name}' to your wishlist",
        "product_id": product_id,
    }


@router.delete("/{product_id}", status_code=200)
def remove_from_wishlist(
    product_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a product from the wishlist."""
    existing = (
        db.query(models.WishlistItem)
        .filter(
            models.WishlistItem.user_id == current_user.id,
            models.WishlistItem.product_id == product_id,
        )
        .first()
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Item not in wishlist")

    db.delete(existing)
    db.commit()
    return {"message": "Item removed from wishlist", "product_id": product_id}
