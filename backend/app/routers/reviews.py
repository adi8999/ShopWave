import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app import models, schemas
from app.auth import get_current_user
from app.database import get_db
from app.security.sanitize import sanitize_search_query

router = APIRouter(prefix="/api/products/{product_id}/reviews", tags=["reviews"])


@router.get("", response_model=schemas.ReviewList)
def get_product_reviews(
    product_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    total = db.query(func.count(models.Review.id)).filter(models.Review.product_id == product_id).scalar() or 0
    pages = max(1, math.ceil(total / limit)) if total > 0 else 1
    offset = (page - 1) * limit

    db_reviews = (
        db.query(models.Review)
        .filter(models.Review.product_id == product_id)
        .order_by(models.Review.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    review_items = []
    for r in db_reviews:
        user_name = r.user.name if r.user else "Anonymous Customer"
        review_items.append(
            schemas.ReviewOut(
                id=r.id,
                user_id=r.user_id,
                user_name=user_name,
                product_id=r.product_id,
                rating=r.rating,
                comment=r.comment,
                verified_purchase=r.verified_purchase,
                created_at=r.created_at,
            )
        )

    avg_rating = product.rating if total > 0 else 0.0

    return schemas.ReviewList(
        reviews=review_items,
        total=total,
        page=page,
        pages=pages,
        average_rating=avg_rating,
    )


@router.post("", response_model=schemas.ReviewOut, status_code=201)
def create_or_update_product_review(
    product_id: int,
    payload: schemas.ReviewCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.rating < 1 or payload.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5 stars")

    clean_comment = sanitize_search_query(payload.comment.strip())
    if len(clean_comment) < 3:
        raise HTTPException(status_code=400, detail="Review comment must be at least 3 characters")

    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Check for verified purchase (user has an order with this product that is not cancelled)
    verified_order = (
        db.query(models.Order)
        .join(models.OrderItem, models.Order.id == models.OrderItem.order_id)
        .filter(
            models.Order.user_id == current_user.id,
            models.OrderItem.product_id == product_id,
            models.Order.status != "cancelled",
        )
        .first()
    )
    is_verified = verified_order is not None

    # Check if user already reviewed this item
    existing_review = (
        db.query(models.Review)
        .filter(
            models.Review.user_id == current_user.id,
            models.Review.product_id == product_id,
        )
        .first()
    )

    if existing_review:
        existing_review.rating = payload.rating
        existing_review.comment = clean_comment
        existing_review.verified_purchase = is_verified
        review = existing_review
    else:
        review = models.Review(
            user_id=current_user.id,
            product_id=product_id,
            rating=payload.rating,
            comment=clean_comment,
            verified_purchase=is_verified,
        )
        db.add(review)

    db.commit()
    db.refresh(review)

    # Recalculate product rating and review count
    all_ratings = [
        r.rating
        for r in db.query(models.Review.rating).filter(models.Review.product_id == product_id).all()
    ]
    if all_ratings:
        product.rating = round(sum(all_ratings) / len(all_ratings), 1)
        product.review_count = len(all_ratings)
        db.commit()

    return schemas.ReviewOut(
        id=review.id,
        user_id=review.user_id,
        user_name=current_user.name,
        product_id=review.product_id,
        rating=review.rating,
        comment=review.comment,
        verified_purchase=review.verified_purchase,
        created_at=review.created_at,
    )
