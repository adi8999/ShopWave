"""
SQLAlchemy ORM models for ShopWave.

Monetary fields
---------------
All money values are stored as PostgreSQL NUMERIC(12,2) / SQLite REAL with
DECIMAL in Python.  We never use Float for prices or totals.

Order state machine
-------------------
  draft → awaiting_payment → paid → processing → shipped → delivered
                              ↓            ↓          ↓
                     cancelled/refunded (from awaiting_payment, paid, processing, shipped)

Stock constraints
-----------------
  stock >= 0  (enforced by DB CHECK constraint)
  quantity > 0  (on CartItem and OrderItem)
  price > 0  (on Product and OrderItem)
"""
from decimal import Decimal
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Boolean,
    CheckConstraint,
    UniqueConstraint,
    Numeric,
    Index,
)
from sqlalchemy.orm import relationship

from app.database import Base


# ─── Valid status values ──────────────────────────────────────────────────────

ORDER_STATUSES = (
    "draft",
    "awaiting_payment",
    "paid",
    "processing",
    "shipped",
    "delivered",
    "cancelled",
    "refunded",
)

PAYMENT_STATUSES = ("pending", "paid", "failed", "refunded")


# ─── Users ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    token_version = Column(Integer, default=0, nullable=False)
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_secret = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    cart_items = relationship("CartItem", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="refresh_tokens")


class VerificationToken(Base):
    __tablename__ = "verification_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    purpose = Column(String(30), nullable=False)  # verify_email | reset_password
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String(100), nullable=False)
    target_type = Column(String(50), nullable=False)
    target_id = Column(String(50), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ─── Products ─────────────────────────────────────────────────────────────────

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    # NUMERIC(12,2) → stores exact cents; never Float
    price = Column(Numeric(12, 2), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    image_url = Column(String(500))
    stock = Column(Integer, default=0, nullable=False)
    low_stock_threshold = Column(Integer, default=5, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    rating = Column(Numeric(3, 2), default=Decimal("4.00"))
    review_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("price > 0", name="ck_product_price_positive"),
        CheckConstraint("stock >= 0", name="ck_product_stock_nonneg"),
    )

    cart_items = relationship("CartItem", back_populates="product")
    order_items = relationship("OrderItem", back_populates="product")
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="product", cascade="all, delete-orphan")


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    name = Column(String(120), nullable=False)  # e.g. "Black / M"
    sku = Column(String(64), unique=True, nullable=True)
    price_delta = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    stock = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        CheckConstraint("stock >= 0", name="ck_variant_stock_nonneg"),
    )

    product = relationship("Product", back_populates="variants")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_rating_range"),
        UniqueConstraint("product_id", "user_id", name="uq_review_product_user"),
    )

    product = relationship("Product", back_populates="reviews")
    user = relationship("User")


class WishlistItem(Base):
    __tablename__ = "wishlist_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_wishlist_user_product"),
    )

    product = relationship("Product")


# ─── CartItems ────────────────────────────────────────────────────────────────

class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_cart_item_quantity_positive"),
        UniqueConstraint("user_id", "product_id", name="uq_cart_user_product"),
    )

    user = relationship("User", back_populates="cart_items")
    product = relationship("Product", back_populates="cart_items")


# ─── Orders ───────────────────────────────────────────────────────────────────

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # Monetary totals — NUMERIC(12,2)
    total_amount = Column(Numeric(12, 2), nullable=False)
    discount_amount = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    coupon_code = Column(String(50), nullable=True)

    # State machine values enforced by application logic + CHECK constraint
    status = Column(String(50), default="awaiting_payment", nullable=False)
    payment_status = Column(String(50), default="pending", nullable=False)

    stripe_payment_intent_id = Column(String(255), nullable=True, unique=True, index=True)

    # Shipping snapshot (captured at checkout time, never updated)
    shipping_name = Column(String(100))
    shipping_address = Column(String(500))
    shipping_city = Column(String(100))
    shipping_zip = Column(String(20))

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="ck_order_total_nonneg"),
        CheckConstraint("discount_amount >= 0", name="ck_order_discount_nonneg"),
        CheckConstraint(
            f"status IN {ORDER_STATUSES}",
            name="ck_order_status_valid",
        ),
        CheckConstraint(
            f"payment_status IN {PAYMENT_STATUSES}",
            name="ck_order_payment_status_valid",
        ),
    )

    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


# ─── OrderItems ───────────────────────────────────────────────────────────────

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    # Immutable price snapshot at the time of checkout
    unit_price = Column(Numeric(12, 2), nullable=False)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_item_quantity_positive"),
        CheckConstraint("unit_price > 0", name="ck_order_item_price_positive"),
    )

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")


# ─── Coupons ─────────────────────────────────────────────────────────────────

class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    # Either percent_off (0–100) or amount_off (> 0), not both
    percent_off = Column(Numeric(5, 2), nullable=True)
    amount_off = Column(Numeric(12, 2), nullable=True)
    min_order_amount = Column(Numeric(12, 2), nullable=True)   # minimum cart total to apply
    expires_at = Column(DateTime, nullable=True)
    max_uses = Column(Integer, nullable=True)
    used_count = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "(percent_off IS NULL) != (amount_off IS NULL)",
            name="ck_coupon_one_discount_type",
        ),
        CheckConstraint(
            "percent_off IS NULL OR (percent_off > 0 AND percent_off <= 100)",
            name="ck_coupon_percent_range",
        ),
        CheckConstraint(
            "amount_off IS NULL OR amount_off > 0",
            name="ck_coupon_amount_positive",
        ),
        CheckConstraint("used_count >= 0", name="ck_coupon_used_count_nonneg"),
    )


# ─── Stripe event idempotency ─────────────────────────────────────────────────

class StripeEvent(Base):
    """
    Records every processed Stripe webhook event ID to ensure idempotency.
    If an event_id is already in this table, the webhook handler skips it.
    """
    __tablename__ = "stripe_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(255), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    processed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
