import json
from typing import List, Dict, Set
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user, get_admin_user
from app.database import get_db

router = APIRouter(prefix="/api/orders", tags=["orders"])


# ─── WebSocket Connection Manager ─────────────────────────────────────────────

class ConnectionManager:
    """Manages active WebSocket connections per order_id."""

    def __init__(self):
        # order_id -> set of WebSocket connections
        self.active: Dict[int, Set[WebSocket]] = {}

    async def connect(self, order_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active.setdefault(order_id, set()).add(websocket)

    def disconnect(self, order_id: int, websocket: WebSocket):
        if order_id in self.active:
            self.active[order_id].discard(websocket)
            if not self.active[order_id]:
                del self.active[order_id]

    async def broadcast(self, order_id: int, data: dict):
        """Send a JSON message to all clients watching a specific order."""
        sockets = list(self.active.get(order_id, set()))
        for ws in sockets:
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                self.active[order_id].discard(ws)


manager = ConnectionManager()


# ─── WebSocket endpoint ───────────────────────────────────────────────────────

@router.websocket("/ws/{order_id}")
async def order_tracking_ws(
    order_id: int,
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    WebSocket for real-time order status updates.
    Connect with: ws://<host>/api/orders/ws/<order_id>?token=<jwt>
    """
    from app.auth import get_current_user
    from fastapi.security import OAuth2PasswordBearer
    from app import auth as auth_module

    # Manually validate JWT from query param
    try:
        user = auth_module.get_current_user.__wrapped__(token=token, db=db)  # type: ignore[attr-defined]
    except Exception:
        # Fallback manual decode
        try:
            from jose import jwt as jose_jwt
            import os
            payload = jose_jwt.decode(token, os.getenv("SECRET_KEY", ""), algorithms=["HS256"])
            user_id = payload.get("sub")
            user = db.query(models.User).filter(models.User.id == int(user_id)).first()
            if not user:
                await websocket.close(code=4001)
                return
        except Exception:
            await websocket.close(code=4001)
            return

    # Verify the order belongs to this user (or user is admin)
    order = (
        db.query(models.Order)
        .filter(models.Order.id == order_id)
        .first()
    )
    if not order or (order.user_id != user.id and not user.is_admin):
        await websocket.close(code=4003)
        return

    await manager.connect(order_id, websocket)
    # Send current status immediately on connect
    try:
        await websocket.send_text(json.dumps({
            "order_id": order_id,
            "status": order.status,
            "payment_status": order.payment_status,
        }))
        while True:
            # Keep-alive: wait for client ping/messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(order_id, websocket)


# ─── REST endpoints ───────────────────────────────────────────────────────────

@router.post("/checkout", response_model=schemas.OrderOut, status_code=201)
def checkout(
    checkout_data: schemas.CheckoutWithPayment,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart_items = (
        db.query(models.CartItem)
        .filter(models.CartItem.user_id == current_user.id)
        .all()
    )
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # Validate stock and calculate total
    total = 0.0
    for item in cart_items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        if not product or product.stock < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for {product.name if product else 'item'}"
            )
        total += product.price * item.quantity

    # Set status based on whether Stripe payment is already confirmed
    initial_status = "processing" if checkout_data.payment_intent_id else "pending_payment"
    initial_payment_status = "paid" if checkout_data.payment_intent_id else "pending"

    # Create order
    order = models.Order(
        user_id=current_user.id,
        total_amount=round(total, 2),
        status=initial_status,
        payment_status=initial_payment_status,
        stripe_payment_intent_id=checkout_data.payment_intent_id,
        shipping_name=checkout_data.shipping_name,
        shipping_address=checkout_data.shipping_address,
        shipping_city=checkout_data.shipping_city,
        shipping_zip=checkout_data.shipping_zip,
    )
    db.add(order)
    db.flush()  # get order.id

    # Create order items and deduct stock
    for item in cart_items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        order_item = models.OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price=product.price,
        )
        db.add(order_item)
        product.stock -= item.quantity

    # Clear cart
    db.query(models.CartItem).filter(models.CartItem.user_id == current_user.id).delete()
    db.commit()
    db.refresh(order)
    return order


@router.get("/me", response_model=List[schemas.OrderOut])
def get_my_orders(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.Order)
        .filter(models.Order.user_id == current_user.id)
        .order_by(models.Order.created_at.desc())
        .all()
    )


@router.get("/{order_id}", response_model=schemas.OrderOut)
def get_order(
    order_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = (
        db.query(models.Order)
        .filter(models.Order.id == order_id, models.Order.user_id == current_user.id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
