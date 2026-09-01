from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr


# ─── Auth ────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserOut


# ─── Products ────────────────────────────────────────────────────────────────

class ProductOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price: float
    category: str
    image_url: Optional[str]
    stock: int
    rating: float
    review_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    category: str
    image_url: Optional[str] = None
    stock: int = 0
    rating: float = 4.0
    review_count: int = 0


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    stock: Optional[int] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None


# ─── Cart ────────────────────────────────────────────────────────────────────

class CartItemAdd(BaseModel):
    product_id: int
    quantity: int = 1


class CartItemUpdate(BaseModel):
    quantity: int


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
    unit_price: float
    product: ProductOut

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: int
    total_amount: float
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
    total_amount: float
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
    total_revenue: float


class SalesSummary(BaseModel):
    total_revenue: float
    total_orders: int
    total_products: int
    total_users: int
    recent_orders: List[AllOrderOut]
    top_products: List[TopProduct]


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


class PaymentIntentResponse(BaseModel):
    client_secret: str
    payment_intent_id: str
    amount: int  # in cents
    publishable_key: str


class CheckoutWithPayment(BaseModel):
    shipping_name: str
    shipping_address: str
    shipping_city: str
    shipping_zip: str
    payment_intent_id: Optional[str] = None
