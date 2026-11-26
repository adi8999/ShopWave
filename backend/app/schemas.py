"""
Pydantic schemas for ShopWave API.

Monetary fields use Decimal (not float) throughout.  The API serialises them
as strings or numbers – Pydantic handles the conversion automatically.
"""
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator


# ─── Auth ────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    mfa_code: Optional[str] = None


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    is_admin: bool
    is_verified: bool = False
    mfa_enabled: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class VerifyEmailRequest(BaseModel):
    token: str


class MfaVerifyRequest(BaseModel):
    code: str


# ─── Products ────────────────────────────────────────────────────────────────

class ProductOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price: Decimal
    category: str
    image_url: Optional[str]
    stock: int
    low_stock_threshold: int = 5
    is_active: bool = True
    rating: Optional[Decimal] = None
    review_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductVariantCreate(BaseModel):
    name: str
    sku: Optional[str] = None
    price_delta: Decimal = Decimal("0.00")
    stock: int = 0

    @field_validator("stock")
    @classmethod
    def stock_nonneg(cls, v: int) -> int:
        if v < 0:
            raise ValueError("stock cannot be negative")
        return v


class ProductVariantOut(BaseModel):
    id: int
    product_id: int
    name: str
    sku: Optional[str] = None
    price_delta: Decimal
    stock: int

    model_config = {"from_attributes": True}


class ReviewCreate(BaseModel):
    rating: int
    comment: Optional[str] = None

    @field_validator("rating")
    @classmethod
    def rating_range(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError("rating must be between 1 and 5")
        return v


class ReviewOut(BaseModel):
    id: int
    product_id: int
    user_id: int
    rating: int
    comment: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class WishlistItemOut(BaseModel):
    id: int
    product_id: int
    created_at: datetime
    product: ProductOut

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: Decimal
    category: str
    image_url: Optional[str] = None
    stock: int = 0
    rating: Decimal = Decimal("4.00")
    review_count: int = 0

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("price must be greater than 0")
        return v

    @field_validator("stock")
    @classmethod
    def stock_nonneg(cls, v: int) -> int:
        if v < 0:
            raise ValueError("stock cannot be negative")
        return v


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    stock: Optional[int] = None
    rating: Optional[Decimal] = None
    review_count: Optional[int] = None

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("price must be greater than 0")
        return v


# ─── Cart ────────────────────────────────────────────────────────────────────

class CartItemAdd(BaseModel):
    product_id: int
    quantity: int = 1

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("quantity must be at least 1")
        return v


class CartItemUpdate(BaseModel):
    quantity: int

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("quantity must be at least 1")
        return v


class CartItemOut(BaseModel):
    id: int
    product_id: int
    quantity: int
    product: ProductOut

    model_config = {"from_attributes": True}


# ─── Orders ──────────────────────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    shipping_name: str
    shipping_address: str
    shipping_city: str
    shipping_zip: str


class OrderItemOut(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_price: Decimal
    product: ProductOut

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: int
    total_amount: Decimal
    discount_amount: Decimal = Decimal("0.00")
    coupon_code: Optional[str] = None
    status: str
    payment_status: Optional[str] = "pending"
    stripe_payment_intent_id: Optional[str] = None
    shipping_name: Optional[str]
    shipping_address: Optional[str]
    shipping_city: Optional[str]
    shipping_zip: Optional[str]
    created_at: datetime
    items: List[OrderItemOut]

    model_config = {"from_attributes": True}


# ─── Admin / Sales ────────────────────────────────────────────────────────────

class AllOrderOut(BaseModel):
    id: int
    total_amount: Decimal
    status: str
    shipping_name: Optional[str]
    shipping_city: Optional[str]
    created_at: datetime
    user_id: int
    item_count: int

    model_config = {"from_attributes": True}


class TopProduct(BaseModel):
    product_id: int
    product_name: str
    total_sold: int
    total_revenue: Decimal


class DailyRevenue(BaseModel):
    date: str
    revenue: Decimal
    orders: int


class SalesSummary(BaseModel):
    total_revenue: Decimal
    total_orders: int
    total_products: int
    total_users: int
    recent_orders: List[AllOrderOut]
    top_products: List[TopProduct]
    paid_orders_count: int = 0
    average_order_value: Decimal = Decimal("0.00")
    conversion_rate: float = 0.0
    low_stock_count: int = 0
    daily_revenue: List[DailyRevenue] = []


class AuditLogOut(BaseModel):
    id: int
    admin_id: int
    action: str
    target_type: str
    target_id: Optional[str] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Pagination ───────────────────────────────────────────────────────────────

class ProductPage(BaseModel):
    items: List[ProductOut]
    total: int
    page: int
    pages: int
    limit: int


# ─── Payments (Stripe) ────────────────────────────────────────────────────────

class PaymentIntentCreate(BaseModel):
    order_id: int
    coupon_code: Optional[str] = None


class PaymentIntentResponse(BaseModel):
    client_secret: str
    payment_intent_id: str
    amount: int  # in cents
    discount_amount: Decimal = Decimal("0.00")
    publishable_key: str


class CheckoutWithPayment(BaseModel):
    shipping_name: str
    shipping_address: str
    shipping_city: str
    shipping_zip: str
    # NOTE: payment_intent_id supplied here is NEVER used to mark an order paid.
    # It is stored for reference only; Stripe webhooks are the source of truth.
    payment_intent_id: Optional[str] = None
    coupon_code: Optional[str] = None


# ─── Coupons ─────────────────────────────────────────────────────────────────

class CouponCreate(BaseModel):
    code: str
    percent_off: Optional[Decimal] = None
    amount_off: Optional[Decimal] = None
    min_order_amount: Optional[Decimal] = None
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None
    is_active: bool = True


class CouponOut(BaseModel):
    id: int
    code: str
    percent_off: Optional[Decimal] = None
    amount_off: Optional[Decimal] = None
    min_order_amount: Optional[Decimal] = None
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None
    used_count: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CouponValidateRequest(BaseModel):
    code: str
    subtotal: Decimal


class CouponValidateResponse(BaseModel):
    valid: bool
    message: str
    code: Optional[str] = None
    discount_amount: Decimal = Decimal("0.00")
    final_total: Decimal
