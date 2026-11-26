import hashlib
import json
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user
from app.database import get_db, cache_get, cache_set, cache_invalidate_pattern
from app.security.rate_limit import search_limiter
from app.security.sanitize import sanitize_search_query

router = APIRouter(prefix="/api/products", tags=["products"])


def _make_cache_key(**kwargs) -> str:
    raw = json.dumps(kwargs, sort_keys=True, default=str)
    digest = hashlib.md5(raw.encode()).hexdigest()
    return f"products:{digest}"


@router.get("", response_model=schemas.ProductPage)
def list_products(
    request: Request,
    q: Optional[str] = Query(None, description="Search by name/description"),
    category: Optional[str] = Query(None),
    min_price: Optional[Decimal] = Query(None, ge=0),
    max_price: Optional[Decimal] = Query(None, ge=0),
    in_stock: Optional[bool] = Query(None),
    sort_by: Optional[str] = Query(
        "newest",
        description="price_asc | price_desc | rating_desc | newest",
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _rl: None = Depends(search_limiter),
):
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status_code=400, detail="min_price cannot be greater than max_price")

    cache_key = _make_cache_key(
        q=q, category=category, min_price=min_price,
        max_price=max_price, in_stock=in_stock, sort_by=sort_by, page=page, limit=limit,
    )
    cached = cache_get(cache_key)
    if cached:
        return cached

    query = db.query(models.Product).filter(models.Product.is_active == True)

    if q:
        try:
            q = sanitize_search_query(q)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid search query.")
        pattern = f"%{q}%"
        query = query.filter(
            models.Product.name.ilike(pattern) |
            models.Product.description.ilike(pattern)
        )
    if category:
        query = query.filter(models.Product.category == category)
    if min_price is not None:
        query = query.filter(models.Product.price >= min_price)
    if max_price is not None:
        query = query.filter(models.Product.price <= max_price)
    if in_stock is True:
        query = query.filter(models.Product.stock > 0)
    elif in_stock is False:
        query = query.filter(models.Product.stock == 0)

    sort_map = {
        "price_asc":   models.Product.price.asc(),
        "price_desc":  models.Product.price.desc(),
        "rating_desc": models.Product.rating.desc(),
        "newest":      models.Product.created_at.desc(),
    }
    query = query.order_by(sort_map.get(sort_by, models.Product.created_at.desc()))

    total = query.count()
    pages = max(1, (total + limit - 1) // limit)
    page = min(page, pages)
    offset = (page - 1) * limit

    items = query.offset(offset).limit(limit).all()

    result = schemas.ProductPage(
        items=items,
        total=total,
        page=page,
        pages=pages,
        limit=limit,
    )
    cache_set(cache_key, result.model_dump(mode="json"), ttl=60)
    return result


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    rows = (
        db.query(models.Product.category)
        .filter(models.Product.is_active == True)
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


@router.get("/{product_id}", response_model=schemas.ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = (
        db.query(models.Product)
        .filter(models.Product.id == product_id, models.Product.is_active == True)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/{product_id}/variants", response_model=List[schemas.ProductVariantOut])
def list_product_variants(product_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.ProductVariant)
        .filter(models.ProductVariant.product_id == product_id)
        .all()
    )


@router.get("/{product_id}/reviews", response_model=List[schemas.ReviewOut])
def list_product_reviews(product_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.Review)
        .filter(models.Review.product_id == product_id)
        .order_by(models.Review.created_at.desc())
        .all()
    )


@router.post("/{product_id}/reviews", response_model=schemas.ReviewOut, status_code=201)
def create_product_review(
    product_id: int,
    payload: schemas.ReviewCreate,
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
        db.query(models.Review)
        .filter(
            models.Review.product_id == product_id,
            models.Review.user_id == current_user.id,
        )
        .first()
    )
    if existing:
        existing.rating = payload.rating
        existing.comment = payload.comment
        review = existing
    else:
        review = models.Review(
            product_id=product_id,
            user_id=current_user.id,
            rating=payload.rating,
            comment=payload.comment,
        )
        db.add(review)

    db.flush()

    agg = (
        db.query(
            func.avg(models.Review.rating),
            func.count(models.Review.id),
        )
        .filter(models.Review.product_id == product_id)
        .first()
    )
    if agg and agg[1]:
        product.rating = round(Decimal(str(agg[0])), 2)
        product.review_count = int(agg[1])

    db.commit()
    db.refresh(review)
    cache_invalidate_pattern("products:*")
    return review
