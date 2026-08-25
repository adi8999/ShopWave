from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app import models, schemas
from app.auth import get_admin_user
from app.database import get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ─── Product CRUD ─────────────────────────────────────────────────────────────

@router.get("/products", response_model=List[schemas.ProductOut])
def admin_list_products(
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_admin_user),
):
    return db.query(models.Product).order_by(models.Product.id).all()


@router.post("/products", response_model=schemas.ProductOut, status_code=201)
def admin_create_product(
    product_data: schemas.ProductCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_admin_user),
):
    product = models.Product(**product_data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.put("/products/{product_id}", response_model=schemas.ProductOut)
def admin_update_product(
    product_id: int,
    product_data: schemas.ProductUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_admin_user),
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = product_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)
    return product


@router.delete("/products/{product_id}", status_code=204)
def admin_delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_admin_user),
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()


# ─── Sales / Analytics ────────────────────────────────────────────────────────

@router.get("/sales", response_model=schemas.SalesSummary)
def admin_sales_summary(
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_admin_user),
):
    total_revenue = db.query(func.sum(models.Order.total_amount)).scalar() or 0.0
    total_orders = db.query(func.count(models.Order.id)).scalar() or 0
    total_products = db.query(func.count(models.Product.id)).scalar() or 0
    total_users = db.query(func.count(models.User.id)).scalar() or 0

    # Recent 10 orders with item count
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
    recent_orders = []
    for order, item_count in recent_raw:
        recent_orders.append(
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
        )

    # Top 5 products by units sold
    top_raw = (
        db.query(
            models.OrderItem.product_id,
            models.Product.name,
            func.sum(models.OrderItem.quantity).label("total_sold"),
            func.sum(models.OrderItem.quantity * models.OrderItem.unit_price).label("total_revenue"),
        )
        .join(models.Product, models.Product.id == models.OrderItem.product_id)
        .group_by(models.OrderItem.product_id, models.Product.name)
        .order_by(func.sum(models.OrderItem.quantity).desc())
        .limit(5)
        .all()
    )
    top_products = [
        schemas.TopProduct(
            product_id=row.product_id,
            product_name=row.name,
            total_sold=row.total_sold or 0,
            total_revenue=round(row.total_revenue or 0, 2),
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
def admin_update_order_status(
    order_id: int,
    status: str,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_admin_user),
):
    valid = {"processing", "shipped", "delivered", "cancelled"}
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"Status must be one of {valid}")
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = status
    db.commit()
    return {"id": order.id, "status": order.status}
