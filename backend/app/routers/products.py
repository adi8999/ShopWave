import hashlib
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_admin_user
from app.database import get_db, cache_get, cache_set

router = APIRouter(prefix="/api/products", tags=["products"])


def _make_cache_key(**kwargs) -> str:
    """Create a deterministic Redis key from query params."""
    raw = json.dumps(kwargs, sort_keys=True)
    digest = hashlib.md5(raw.encode()).hexdigest()
    return f"products:{digest}"


# ─── List products (with search / filter / sort / pagination) ────────────────

@router.get("", response_model=schemas.ProductPage)
def list_products(
    q: Optional[str] = Query(None, description="Search by name/description"),
    category: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    sort_by: Optional[str] = Query(
        "newest",
        description="price_asc | price_desc | rating_desc | newest"
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    # Try Redis cache first
    cache_key = _make_cache_key(
        q=q, category=category, min_price=min_price,
        max_price=max_price, sort_by=sort_by, page=page, limit=limit
    )
    cached = cache_get(cache_key)
    if cached:
        return cached

    query = db.query(models.Product)

    # Full-text search across name and description
    if q:
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

    # Sorting
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

    # Cache for 5 minutes
    cache_set(cache_key, result.model_dump(mode="json"), ttl=300)

    return result


# ─── Categories ──────────────────────────────────────────────────────────────

@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    rows = db.query(models.Product.category).distinct().all()
    return [r[0] for r in rows]


# ─── Single product ───────────────────────────────────────────────────────────

@router.get("/{product_id}", response_model=schemas.ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
