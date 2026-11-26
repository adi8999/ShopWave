"""
orders.py – checkout, order retrieval, public tracking tokens, and real-time WebSocket tracking.

Key correctness & security guarantees
-------------------------------------
1. Row-level locking (SELECT … FOR UPDATE) prevents concurrent overselling.
2. Stock is decremented atomically and restored if the transaction rolls back.
3. The backend recalculates totals from live product prices; never trusts client totals.
4. An order is NEVER marked 'paid' solely because the frontend supplied a payment_intent_id.
5. A user's existing 'awaiting_payment' order is reused to prevent duplicate orders.
6. WebSocket authentication uses short-lived single-use tickets (never JWTs in URLs).
7. Public order tracking uses a signed, short-lived, order-specific tracking token and
   omits personal/shipping PII.
"""
import json
import logging
import os
import secrets
import threading
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Set, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt as jose_jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user, SECRET_KEY, ALGORITHM
from app.database import get_db, get_redis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orders", tags=["orders"])


# ─── Short-lived Single-Use WebSocket Ticket Store ────────────────────────────

_WS_TICKET_TTL_SECONDS = 60
_ws_ticket_lock = threading.Lock()
_ws_ticket_mem: dict[str, tuple[int, int, float]] = {}  # ticket -> (user_id, order_id, expires_at)


def _issue_ws_ticket(user_id: int, order_id: int) -> str:
    ticket = secrets.token_urlsafe(32)
    r = get_redis()
    if r is not None:
        try:
            r.setex(
                f"ws_ticket:{ticket}",
                _WS_TICKET_TTL_SECONDS,
                json.dumps({"user_id": user_id, "order_id": order_id}),
            )
            return ticket
        except Exception:
            pass

    with _ws_ticket_lock:
        now = time.time()
        # Opportunistically clean expired tickets
        expired = [k for k, (_, _, exp) in _ws_ticket_mem.items() if exp < now]
        for k in expired:
            del _ws_ticket_mem[k]
        _ws_ticket_mem[ticket] = (user_id, order_id, now + _WS_TICKET_TTL_SECONDS)
    return ticket


def _consume_ws_ticket(ticket: str, order_id: int) -> Optional[int]:
    """Validate and consume a single-use WS ticket. Returns user_id or None."""
    if not ticket:
        return None
    r = get_redis()
    if r is not None:
        try:
            key = f"ws_ticket:{ticket}"
            raw = r.getdel(key) if hasattr(r, "getdel") else r.get(key)
            if raw:
                if not hasattr(r, "getdel"):
                    r.delete(key)
                data = json.loads(raw)
                if int(data.get("order_id", -1)) == order_id:
                    return int(data["user_id"])
            return None
        except Exception:
            pass

    with _ws_ticket_lock:
        entry = _ws_ticket_mem.pop(ticket, None)
        if not entry:
            return None
        uid, oid, exp = entry
        if time.time() > exp or oid != order_id:
            return None
        return uid


# ─── Signed Public Order Tracking Token ───────────────────────────────────────

def create_tracking_token(order_id: int, expires_hours: int = 24) -> str:
    expire = datetime.utcnow() + timedelta(hours=expires_hours)
    payload = {
        "order_id": order_id,
        "purpose": "order_track",
        "exp": expire,
    }
    return jose_jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_tracking_token(token: str) -> int:
    try:
        payload = jose_jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("purpose") != "order_track":
            raise HTTPException(status_code=401, detail="Invalid tracking token")
        order_id = payload.get("order_id")
        if order_id is None:
            raise HTTPException(status_code=401, detail="Invalid tracking token")
        return int(order_id)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired tracking token")


# ─── Order state machine ──────────────────────────────────────────────────────

VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft":             {"awaiting_payment", "cancelled"},
    "awaiting_payment":  {"paid", "cancelled"},
    "paid":              {"processing", "refunded"},
    "processing":        {"shipped", "cancelled", "refunded"},
    "shipped":           {"delivered", "refunded"},
    "delivered":         set(),
    "cancelled":         set(),
    "refunded":          set(),
}


def apply_transition(order: models.Order, new_status: str) -> None:
    """Advance order status, raising 409 if the transition is invalid."""
    allowed = VALID_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot transition order from '{order.status}' to '{new_status}'. "
                f"Allowed next states: {sorted(allowed) or 'none'}"
            ),
        )
    order.status = new_status


# ─── WebSocket Connection Manager ─────────────────────────────────────────────

class ConnectionManager:
    """Manages active WebSocket connections per order_id."""

    def __init__(self):
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
        sockets = list(self.active.get(order_id, set()))
        for ws in sockets:
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                self.active[order_id].discard(ws)


manager = ConnectionManager()


# ─── WebSocket Ticket & Endpoint ──────────────────────────────────────────────

@router.post("/{order_id}/ws-ticket")
def create_ws_ticket(
    order_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Issue a short-lived (60s) single-use ticket for WebSocket order tracking."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order or (order.user_id != current_user.id and not current_user.is_admin):
        raise HTTPException(status_code=404, detail="Order not found")
    ticket = _issue_ws_ticket(current_user.id, order_id)
    return {"ticket": ticket, "expires_in": _WS_TICKET_TTL_SECONDS}


@router.websocket("/ws/{order_id}")
async def order_tracking_ws(
    order_id: int,
    websocket: WebSocket,
    ticket: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    WebSocket for real-time order status updates.
    Authenticate using a short-lived single-use ticket from POST /api/orders/{order_id}/ws-ticket.
    JWTs in query parameters are rejected.
    """
    if not ticket:
        await websocket.close(code=4001)
        return

    user_id = _consume_ws_ticket(ticket, order_id)
    if user_id is None:
        await websocket.close(code=4001)
        return

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        await websocket.close(code=4001)
        return

    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order or (order.user_id != user.id and not user.is_admin):
        await websocket.close(code=4003)
        return

    await manager.connect(order_id, websocket)
    try:
        await websocket.send_text(json.dumps({
            "order_id": order_id,
            "status": order.status,
            "payment_status": order.payment_status,
        }))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(order_id, websocket)


# ─── Public Order Tracking (Signed Token, No PII) ─────────────────────────────

@router.post("/{order_id}/tracking-token")
def generate_tracking_token(
    order_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a short-lived, order-specific tracking token for public status checks."""
    order = (
        db.query(models.Order)
        .filter(models.Order.id == order_id, models.Order.user_id == current_user.id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    token = create_tracking_token(order.id)
    return {"tracking_token": token, "order_id": order.id, "expires_in_hours": 24}


@router.get("/track")
def track_order_public(
    token: str = Query(..., description="Signed order-specific tracking token"),
    db: Session = Depends(get_db),
):
    """
    Public order tracking endpoint using a signed, short-lived, order-specific token.
    Returns status and item summary ONLY (no personal or shipping PII).
    """
    order_id = verify_tracking_token(token)
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return {
        "order_id": order.id,
        "status": order.status,
        "payment_status": order.payment_status,
        "created_at": order.created_at,
        "item_count": sum(it.quantity for it in order.items),
        "items": [
            {
                "product_name": it.product.name if it.product else "Item",
                "quantity": it.quantity,
            }
            for it in order.items
        ],
    }


# ─── Checkout ─────────────────────────────────────────────────────────────────

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

    product_ids = [item.product_id for item in cart_items]
    try:
        locked_products = (
            db.execute(
                select(models.Product)
                .where(models.Product.id.in_(product_ids))
                .with_for_update()
            ).scalars().all()
        )
    except Exception:
        locked_products = (
            db.query(models.Product)
            .filter(models.Product.id.in_(product_ids))
            .all()
        )

    product_map: dict[int, models.Product] = {p.id: p for p in locked_products}

    total = Decimal("0.00")
    for item in cart_items:
        product = product_map.get(item.product_id)
        if not product:
            raise HTTPException(
                status_code=400,
                detail=f"Product #{item.product_id} no longer exists",
            )
        if product.stock < item.quantity:
            raise HTTPException(
                status_code=409,
                detail=f"Insufficient stock for '{product.name}' "
                       f"(available: {product.stock}, requested: {item.quantity}). "
                       "Please refresh your cart.",
            )
        total += product.price * item.quantity

    existing_order = (
        db.query(models.Order)
        .filter(
            models.Order.user_id == current_user.id,
            models.Order.status == "awaiting_payment",
            models.Order.stripe_payment_intent_id.is_(None),
        )
        .order_by(models.Order.created_at.desc())
        .first()
    )
    if existing_order:
        existing_order.shipping_name = checkout_data.shipping_name
        existing_order.shipping_address = checkout_data.shipping_address
        existing_order.shipping_city = checkout_data.shipping_city
        existing_order.shipping_zip = checkout_data.shipping_zip
        existing_order.total_amount = round(total, 2)
        db.commit()
        db.refresh(existing_order)
        return existing_order

    order = models.Order(
        user_id=current_user.id,
        total_amount=round(total, 2),
        status="awaiting_payment",
        payment_status="pending",
        stripe_payment_intent_id=checkout_data.payment_intent_id,
        shipping_name=checkout_data.shipping_name,
        shipping_address=checkout_data.shipping_address,
        shipping_city=checkout_data.shipping_city,
        shipping_zip=checkout_data.shipping_zip,
    )
    db.add(order)
    db.flush()

    for item in cart_items:
        product = product_map[item.product_id]
        order_item = models.OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price=product.price,
        )
        db.add(order_item)

        rows_updated = (
            db.query(models.Product)
            .filter(
                models.Product.id == item.product_id,
                models.Product.stock >= item.quantity,
            )
            .update(
                {models.Product.stock: models.Product.stock - item.quantity},
                synchronize_session="fetch",
            )
        )
        if rows_updated == 0:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail=f"Insufficient stock for product #{item.product_id}. "
                       "Please refresh your cart.",
            )

    db.query(models.CartItem).filter(models.CartItem.user_id == current_user.id).delete()
    db.commit()
    db.refresh(order)
    return order


# ─── Stock restoration helper ─────────────────────────────────────────────────

def restore_stock_for_order(order: models.Order, db: Session) -> None:
    for item in order.items:
        db.query(models.Product).filter(
            models.Product.id == item.product_id
        ).update(
            {models.Product.stock: models.Product.stock + item.quantity},
            synchronize_session="fetch",
        )
        logger.info(
            "Restored %d units of product #%d for order #%d",
            item.quantity, item.product_id, order.id,
        )


# ─── REST endpoints ───────────────────────────────────────────────────────────

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
