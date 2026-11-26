import os
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_admin_user, log_admin_action
from app.database import get_db, cache_invalidate_pattern
from app.routers.orders import apply_transition, restore_stock_for_order

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ─── Product CRUD ─────────────────────────────────────────────────────────────

@router.get("/products", response_model=List[schemas.ProductOut])
def admin_list_products(
    include_inactive: bool = Query(True),
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_admin_user),
):
    q = db.query(models.Product)
    if not include_inactive:
        q = q.filter(models.Product.is_active == True)
    return q.order_by(models.Product.id).all()


@router.post("/products", response_model=schemas.ProductOut, status_code=201)
def admin_create_product(
    product_data: schemas.ProductCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_admin_user),
):
    product = models.Product(**product_data.model_dump())
    db.add(product)
    db.flush()
    log_admin_action(db, admin.id, "create_product", "product", str(product.id), product.name, request)
    db.commit()
    db.refresh(product)
    cache_invalidate_pattern("products:*")
    return product


@router.put("/products/{product_id}", response_model=schemas.ProductOut)
def admin_update_product(
    product_id: int,
    product_data: schemas.ProductUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_admin_user),
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = product_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    log_admin_action(
        db, admin.id, "update_product", "product", str(product.id),
        f"fields={list(update_data.keys())}", request,
    )
    db.commit()
    db.refresh(product)
    cache_invalidate_pattern("products:*")
    return product


@router.delete("/products/{product_id}", status_code=204)
def admin_delete_product(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_admin_user),
):
    """Soft-delete a product by setting is_active=False."""
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.is_active = False
    log_admin_action(db, admin.id, "soft_delete_product", "product", str(product.id), product.name, request)
    db.commit()
    cache_invalidate_pattern("products:*")


@router.post("/products/{product_id}/variants", response_model=schemas.ProductVariantOut, status_code=201)
def admin_create_variant(
    product_id: int,
    payload: schemas.ProductVariantCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_admin_user),
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    variant = models.ProductVariant(product_id=product_id, **payload.model_dump())
    db.add(variant)
    db.flush()
    log_admin_action(db, admin.id, "create_variant", "product_variant", str(variant.id), payload.name, request)
    db.commit()
    db.refresh(variant)
    return variant


@router.post("/products/upload-image")
async def admin_upload_product_image(
    request: Request,
    file: UploadFile = File(...),
    admin: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Upload a product image to S3 / Cloudflare R2 (when S3_BUCKET is configured)."""
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, and WebP images are allowed")

    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image exceeds 5 MB limit")

    bucket = os.getenv("S3_BUCKET")
    if not bucket:
        raise HTTPException(
            status_code=503,
            detail="Object storage (S3_BUCKET) is not configured.",
        )

    import boto3
    ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[file.content_type]
    key = f"products/{uuid.uuid4().hex}.{ext}"
    s3_client = boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT_URL"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )
    s3_client.put_object(Bucket=bucket, Key=key, Body=contents, ContentType=file.content_type)
    public_base = os.getenv("S3_PUBLIC_URL", f"https://{bucket}.s3.amazonaws.com")
    url = f"{public_base.rstrip('/')}/{key}"
    log_admin_action(db, admin.id, "upload_image", "product_image", key, url, request)
    db.commit()
    return {"image_url": url, "key": key}


@router.get("/low-stock", response_model=List[schemas.ProductOut])
def admin_low_stock_products(
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_admin_user),
):
    return (
        db.query(models.Product)
        .filter(
            models.Product.is_active == True,
            models.Product.stock <= models.Product.low_stock_threshold,
        )
        .order_by(models.Product.stock.asc())
        .all()
    )


# ─── Sales / Analytics ────────────────────────────────────────────────────────

def _resolve_date_window(range_key: str, start_date: Optional[str], end_date: Optional[str]):
    now = datetime.utcnow()
    if range_key == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0), now
    if range_key == "7d":
        return now - timedelta(days=7), now
    if range_key == "30d":
        return now - timedelta(days=30), now
    if range_key == "custom":
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="start_date and end_date are required for custom range")
        try:
            s = datetime.fromisoformat(start_date)
            e = datetime.fromisoformat(end_date)
            if e < s:
                raise HTTPException(status_code=400, detail="end_date must be >= start_date")
            return s, e
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid ISO date format")
    return None, None


@router.get("/sales", response_model=schemas.SalesSummary)
def admin_sales_summary(
    range: str = Query("all", description="today | 7d | 30d | custom | all"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_admin_user),
):
    """
    Sales analytics:
    - Revenue is calculated ONLY from paid orders excluding cancelled/refunded.
    - Supports today, 7d, 30d, custom, and all-time ranges.
    """
    dt_start, dt_end = _resolve_date_window(range, start_date, end_date)

    paid_filter = [
        models.Order.payment_status == "paid",
        models.Order.status.notin_(["cancelled", "refunded"]),
    ]
    all_orders_q = db.query(models.Order)
    paid_orders_q = db.query(models.Order).filter(*paid_filter)

    if dt_start and dt_end:
        all_orders_q = all_orders_q.filter(models.Order.created_at >= dt_start, models.Order.created_at <= dt_end)
        paid_orders_q = paid_orders_q.filter(models.Order.created_at >= dt_start, models.Order.created_at <= dt_end)

    paid_orders = paid_orders_q.all()
    total_revenue = sum((Decimal(str(o.total_amount)) for o in paid_orders), Decimal("0.00"))
    paid_count = len(paid_orders)
    total_orders = all_orders_q.count()
    aov = round(total_revenue / paid_count, 2) if paid_count > 0 else Decimal("0.00")
    conversion_rate = round((paid_count / total_orders) * 100, 2) if total_orders > 0 else 0.0

    total_products = db.query(func.count(models.Product.id)).filter(models.Product.is_active == True).scalar() or 0
    total_users = db.query(func.count(models.User.id)).scalar() or 0
    low_stock_count = (
        db.query(func.count(models.Product.id))
        .filter(
            models.Product.is_active == True,
            models.Product.stock <= models.Product.low_stock_threshold,
        )
        .scalar() or 0
    )

    # Daily revenue breakdown
    daily_map: dict[str, dict] = {}
    for o in paid_orders:
        day_str = o.created_at.strftime("%Y-%m-%d")
        bucket = daily_map.setdefault(day_str, {"revenue": Decimal("0.00"), "orders": 0})
        bucket["revenue"] += Decimal(str(o.total_amount))
        bucket["orders"] += 1
    daily_revenue = [
        schemas.DailyRevenue(date=d, revenue=round(v["revenue"], 2), orders=v["orders"])
        for d, v in sorted(daily_map.items())
    ]

    # Recent 10 orders
    recent_raw = (
        db.query(
            models.Order,
            func.count(models.OrderItem.id).label("item_count"),
        )
        .outerjoin(models.OrderItem, models.OrderItem.order_id == models.Order.id)
        .group_by(models.Order.id)
        .order_by(models.Order.created_at.desc())
        .limit(10)
        .all()
    )
    recent_orders = [
        schemas.AllOrderOut(
            id=order.id,
            total_amount=order.total_amount,
            status=order.status,
            shipping_name=order.shipping_name,
            shipping_city=order.shipping_city,
            created_at=order.created_at,
            user_id=order.user_id,
            item_count=item_count or 0,
        )
        for order, item_count in recent_raw
    ]

    # Top 5 products by paid units sold
    top_q = (
        db.query(
            models.OrderItem.product_id,
            models.Product.name,
            func.sum(models.OrderItem.quantity).label("total_sold"),
            func.sum(models.OrderItem.quantity * models.OrderItem.unit_price).label("total_revenue"),
        )
        .join(models.Product, models.Product.id == models.OrderItem.product_id)
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .filter(*paid_filter)
    )
    if dt_start and dt_end:
        top_q = top_q.filter(models.Order.created_at >= dt_start, models.Order.created_at <= dt_end)

    top_raw = (
        top_q.group_by(models.OrderItem.product_id, models.Product.name)
        .order_by(func.sum(models.OrderItem.quantity).desc())
        .limit(5)
        .all()
    )
    top_products = [
        schemas.TopProduct(
            product_id=row.product_id,
            product_name=row.name,
            total_sold=int(row.total_sold or 0),
            total_revenue=round(Decimal(str(row.total_revenue or 0)), 2),
        )
        for row in top_raw
    ]

    return schemas.SalesSummary(
        total_revenue=round(total_revenue, 2),
        total_orders=total_orders,
        total_products=total_products,
        total_users=total_users,
        recent_orders=recent_orders,
        top_products=top_products,
        paid_orders_count=paid_count,
        average_order_value=aov,
        conversion_rate=conversion_rate,
        low_stock_count=low_stock_count,
        daily_revenue=daily_revenue,
    )


# ─── Order management ─────────────────────────────────────────────────────────

@router.get("/orders", response_model=List[schemas.AllOrderOut])
def admin_list_orders(
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_admin_user),
):
    raw = (
        db.query(
            models.Order,
            func.count(models.OrderItem.id).label("item_count"),
        )
        .outerjoin(models.OrderItem, models.OrderItem.order_id == models.Order.id)
        .group_by(models.Order.id)
        .order_by(models.Order.created_at.desc())
        .all()
    )
    return [
        schemas.AllOrderOut(
            id=order.id,
            total_amount=order.total_amount,
            status=order.status,
            shipping_name=order.shipping_name,
            shipping_city=order.shipping_city,
            created_at=order.created_at,
            user_id=order.user_id,
            item_count=item_count or 0,
        )
        for order, item_count in raw
    ]


@router.patch("/orders/{order_id}/status")
async def admin_update_order_status(
    order_id: int,
    status: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_admin_user),
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    prev_status = order.status
    apply_transition(order, status)

    if status == "cancelled" and prev_status != "cancelled":
        restore_stock_for_order(order, db)

    log_admin_action(
        db, admin.id, "update_order_status", "order", str(order.id),
        f"{prev_status} -> {status}", request,
    )
    db.commit()

    try:
        from app.routers.orders import manager
        await manager.broadcast(order_id, {"order_id": order_id, "status": status})
    except Exception:
        pass
    return {"id": order.id, "status": order.status}


@router.get("/audit-logs", response_model=List[schemas.AuditLogOut])
def admin_list_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_admin_user),
):
    return (
        db.query(models.AuditLog)
        .order_by(models.AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
