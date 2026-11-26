import hashlib
import json
import logging
import os
import re
from typing import List, Optional, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models
from app.auth import get_optional_user
from app.database import get_db, cache_get, cache_set
from app.routers.orders import verify_tracking_token
from app.security.rate_limit import chat_limiter
from app.security.sanitize import sanitize_ai_context, sanitize_search_query, redact_pii

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

MAX_MESSAGE_LENGTH = 500
MAX_HISTORY_LENGTH = 10
PROVIDER_TIMEOUT_SECONDS = float(os.getenv("AI_PROVIDER_TIMEOUT", "15.0"))
PROVIDER_MAX_RETRIES = 1
ALLOWED_AI_TOOLS = {"search_products", "get_order_status"}


# ── Schemas ──────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)
    history: List[ChatMessage] = Field(default=[], max_length=MAX_HISTORY_LENGTH)
    tracking_token: Optional[str] = None

    @field_validator("history")
    @classmethod
    def cap_history(cls, v: List[ChatMessage]) -> List[ChatMessage]:
        if len(v) > MAX_HISTORY_LENGTH:
            raise ValueError(f"history cannot exceed {MAX_HISTORY_LENGTH} messages")
        return v


class ProductCard(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float
    category: str
    image_url: Optional[str] = None
    rating: float = 4.0
    stock: int = 0


class ToolCallInfo(BaseModel):
    name: str
    arguments: Dict[str, Any]
    result: Any


class ChatResponse(BaseModel):
    reply: str
    products: List[ProductCard] = []
    tool_calls: List[ToolCallInfo] = []
    error: Optional[str] = None


# ── Local Database Tool Implementations ──────────────────────────────────────

def execute_search_products(
    db: Session,
    query: Optional[str] = None,
    max_price: Optional[float] = None,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search active products in the catalog.
    Caches query results briefly (30s) keyed by query params, only for active products.
    """
    clean_query = None
    if query and str(query).strip():
        try:
            clean_query = sanitize_search_query(str(query))
        except ValueError:
            clean_query = None

    clean_cat = category.strip()[:50] if category and str(category).strip() else None
    clean_max_price: Optional[float] = None
    if max_price is not None:
        try:
            val = float(max_price)
            if val >= 0:
                clean_max_price = val
        except (ValueError, TypeError):
            pass

    cache_key = "products:ai:" + hashlib.md5(
        json.dumps({"q": clean_query, "max_price": clean_max_price, "category": clean_cat}, sort_keys=True).encode()
    ).hexdigest()
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    q = db.query(models.Product).filter(models.Product.is_active == True)

    if clean_cat:
        q = q.filter(models.Product.category.ilike(f"%{clean_cat}%"))

    if clean_query:
        q = q.filter(
            or_(
                models.Product.name.ilike(f"%{clean_query}%"),
                models.Product.description.ilike(f"%{clean_query}%"),
                models.Product.category.ilike(f"%{clean_query}%"),
            )
        )

    if clean_max_price is not None:
        q = q.filter(models.Product.price <= clean_max_price)

    results = q.order_by(models.Product.rating.desc()).limit(6).all()

    if not results and (clean_query or clean_cat):
        results = (
            db.query(models.Product)
            .filter(models.Product.is_active == True)
            .order_by(models.Product.rating.desc())
            .limit(4)
            .all()
        )

    items = []
    for p in results:
        items.append({
            "id": p.id,
            "name": p.name,
            "description": redact_pii(p.description or ""),
            "price": float(p.price),
            "category": p.category,
            "image_url": p.image_url,
            "rating": float(p.rating) if p.rating is not None else 4.0,
            "stock": p.stock,
        })

    # Short TTL (30s) so price/inventory stays fresh; invalidated on product edits
    cache_set(cache_key, items, ttl=30)
    return items


def execute_get_order_status(
    db: Session,
    order_id: Optional[int] = None,
    user_id: Optional[int] = None,
    tracking_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Query order status strictly scoped to the authenticated user OR a signed tracking token.
    Never falls back to guest/latest order.
    Never exposes internal DB IDs, user IDs, or personal shipping addresses.
    """
    target_order_id: Optional[int] = None

    if tracking_token:
        try:
            target_order_id = verify_tracking_token(tracking_token)
        except HTTPException:
            return {"error": "Invalid or expired tracking token."}
    elif user_id is None:
        return {
            "error": "Authentication is required to view order status. Please sign in or provide a valid tracking token."
        }
    else:
        try:
            target_order_id = int(order_id) if order_id is not None else None
        except (ValueError, TypeError):
            return {"error": "Invalid order ID format."}
        if target_order_id is None or target_order_id <= 0:
            return {"error": "Please specify a valid order number."}

    q = db.query(models.Order).filter(models.Order.id == target_order_id)
    if user_id is not None and not tracking_token:
        q = q.filter(models.Order.user_id == user_id)

    order = q.first()
    if not order:
        return {
            "error": "Order was not found in your account. Please check your order number on the Orders page."
        }

    items = []
    if order.items:
        for it in order.items:
            product_name = it.product.name if it.product else "Product"
            items.append({
                "product_name": redact_pii(product_name),
                "quantity": it.quantity,
                "unit_price": float(it.unit_price),
            })

    # Do NOT return internal DB order_id, user_id, shipping_name, shipping_address, shipping_zip
    return {
        "status": order.status,
        "payment_status": order.payment_status,
        "total_amount": float(order.total_amount),
        "created_at": order.created_at.strftime("%Y-%m-%d %H:%M UTC") if order.created_at else "Recent",
        "item_count": sum(it["quantity"] for it in items),
        "items": items,
    }


# ── System Instruction & Tool Definitions ────────────────────────────────────

SYSTEM_PROMPT = """You are ShopWave AI, the shopping assistant for ShopWave.

Capabilities:
1. Product Search & Recommendations:
   - Call `search_products(query, max_price, category)` to retrieve real store inventory.
2. Order Tracking:
   - Call `get_order_status(order_id)` ONLY when the user is signed in or has a tracking token.
   - Never fabricate order statuses or expose internal IDs or personal addresses.
3. Policies:
   - Shipping: Free delivery on orders over $50; $5.99 flat rate otherwise. 2-4 business days.
   - Returns: 30-day money-back guarantee.
   - Checkout: Secure Stripe payment processing.
"""

TOOL_DEFINITIONS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search active ShopWave products by query, max_price, or category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_price": {"type": "number"},
                    "category": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": "Check fulfillment status for the authenticated user's order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer"},
                },
                "required": ["order_id"],
            },
        },
    },
]


def dispatch_tool(
    tool_name: str,
    args: Dict[str, Any],
    db: Session,
    user_id: Optional[int] = None,
    tracking_token: Optional[str] = None,
) -> Any:
    """Execute an allowlisted local database tool with validated arguments."""
    if tool_name not in ALLOWED_AI_TOOLS:
        logger.warning("Blocked disallowed AI tool call: %s", tool_name)
        return {"error": f"Tool '{tool_name}' is not permitted."}

    if not isinstance(args, dict):
        return {"error": "Invalid tool arguments."}

    if tool_name == "search_products":
        return execute_search_products(
            db=db,
            query=args.get("query"),
            max_price=args.get("max_price"),
            category=args.get("category"),
        )
    elif tool_name == "get_order_status":
        return execute_get_order_status(
            db=db,
            order_id=args.get("order_id"),
            user_id=user_id,
            tracking_token=tracking_token,
        )


def _sanitize_history(history: List[ChatMessage]) -> List[ChatMessage]:
    sanitized: List[ChatMessage] = []
    for h in history[-MAX_HISTORY_LENGTH:]:
        try:
            clean_text = sanitize_ai_context(h.content, max_len=MAX_MESSAGE_LENGTH)
            sanitized.append(ChatMessage(role=h.role, content=clean_text))
        except ValueError:
            # Skip any history entry containing injection payloads
            continue
    return sanitized


def _log_usage(provider: str, model: str, input_chars: int, output_chars: int) -> None:
    est_tokens = (input_chars + output_chars) // 4
    est_cost = round(est_tokens * 0.0000005, 6)
    logger.info(
        "AI_USAGE provider=%s model=%s est_tokens=%d est_cost_usd=%.6f",
        provider, model, est_tokens, est_cost,
    )


# ── Execution Engines ────────────────────────────────────────────────────────

def run_gemini_native_loop(
    message: str,
    history: List[ChatMessage],
    db: Session,
    gemini_api_key: str,
    user_id: Optional[int] = None,
    tracking_token: Optional[str] = None,
) -> ChatResponse:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=gemini_api_key, http_options={"timeout": PROVIDER_TIMEOUT_SECONDS})

    def search_products(query: str = "", max_price: float = None, category: str = "") -> str:
        res = dispatch_tool("search_products", {"query": query, "max_price": max_price, "category": category}, db, user_id)
        return json.dumps(res)

    def get_order_status(order_id: int) -> str:
        res = dispatch_tool("get_order_status", {"order_id": order_id}, db, user_id, tracking_token)
        return json.dumps(res)

    contents = []
    for h in history:
        role = "user" if h.role == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=h.content)]))
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message)]))

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[search_products, get_order_status],
        temperature=0.7,
        max_output_tokens=1000,
    )
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    response = None
    last_exc = None
    for _ in range(PROVIDER_MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(model=model_name, contents=contents, config=config)
            break
        except Exception as exc:
            last_exc = exc
    if response is None:
        raise last_exc  # type: ignore

    collected_products: List[ProductCard] = []
    collected_tool_calls: List[ToolCallInfo] = []

    if response.candidates:
        for cand in response.candidates:
            if hasattr(cand.content, "parts"):
                for part in cand.content.parts:
                    if hasattr(part, "function_call") and part.function_call:
                        fn_name = part.function_call.name
                        fn_args = dict(part.function_call.args or {})
                        tool_result = dispatch_tool(fn_name, fn_args, db, user_id=user_id, tracking_token=tracking_token)
                        collected_tool_calls.append(
                            ToolCallInfo(name=fn_name, arguments=fn_args, result=tool_result)
                        )
                        if fn_name == "search_products" and isinstance(tool_result, list):
                            for p_dict in tool_result:
                                if not any(cp.id == p_dict["id"] for cp in collected_products):
                                    collected_products.append(ProductCard(**p_dict))

    reply_text = redact_pii((response.text or "").strip())
    _log_usage("gemini", model_name, len(message), len(reply_text))
    return ChatResponse(reply=reply_text, products=collected_products, tool_calls=collected_tool_calls)


def run_openai_compatible_loop(
    message: str,
    history: List[ChatMessage],
    db: Session,
    api_key: str,
    base_url: Optional[str] = None,
    model: str = "google/gemini-3.7-flash",
    user_id: Optional[int] = None,
    tracking_token: Optional[str] = None,
) -> ChatResponse:
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=PROVIDER_TIMEOUT_SECONDS,
        max_retries=PROVIDER_MAX_RETRIES,
    )

    messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in history:
        messages.append({"role": h.role, "content": h.content})
    messages.append({"role": "user", "content": message})

    collected_products: List[ProductCard] = []
    collected_tool_calls: List[ToolCallInfo] = []

    response_msg = None
    for _ in range(4):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOL_DEFINITIONS_OPENAI,
            tool_choice="auto",
            max_tokens=1000,
            temperature=0.7,
        )
        response_msg = response.choices[0].message
        tool_calls = getattr(response_msg, "tool_calls", None)

        if not tool_calls:
            reply_text = redact_pii((response_msg.content or "").strip())
            _log_usage("openai_compat", model, len(message), len(reply_text))
            return ChatResponse(reply=reply_text, products=collected_products, tool_calls=collected_tool_calls)

        messages.append({
            "role": "assistant",
            "content": response_msg.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in tool_calls
            ],
        })

        for tc in tool_calls:
            fn_name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments or "{}")
            except Exception:
                fn_args = {}

            tool_result = dispatch_tool(fn_name, fn_args, db, user_id=user_id, tracking_token=tracking_token)
            collected_tool_calls.append(ToolCallInfo(name=fn_name, arguments=fn_args, result=tool_result))

            if fn_name == "search_products" and isinstance(tool_result, list):
                for p_dict in tool_result:
                    if not any(cp.id == p_dict["id"] for cp in collected_products):
                        collected_products.append(ProductCard(**p_dict))

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": fn_name,
                "content": json.dumps(tool_result),
            })

    reply_text = redact_pii((response_msg.content if response_msg else "") or "Here are the top results from our catalog.")
    return ChatResponse(reply=reply_text, products=collected_products, tool_calls=collected_tool_calls)


def rule_based_fallback(
    message: str,
    db: Session,
    user_id: Optional[int] = None,
    tracking_token: Optional[str] = None,
) -> ChatResponse:
    msg_lower = message.lower()
    collected_products = []
    collected_tool_calls = []

    order_match = re.search(r"(?:order|#)\s*(\d+)", msg_lower)
    if order_match or "track" in msg_lower or "order" in msg_lower:
        oid = int(order_match.group(1)) if order_match else None
        res = execute_get_order_status(db, order_id=oid, user_id=user_id, tracking_token=tracking_token)
        collected_tool_calls.append(
            ToolCallInfo(name="get_order_status", arguments={"order_id": oid}, result=res)
        )
        if "error" in res:
            reply = res["error"]
        else:
            reply = (
                f"📦 **Order Status**: `{res['status'].upper()}`\n\n"
                f"- **Total Amount**: ${res['total_amount']:.2f}\n"
                f"- **Placed On**: {res['created_at']}\n\n"
                f"**Items**:\n"
                + "\n".join([f"- {it['quantity']}x **{it['product_name']}** (${it['unit_price']:.2f})" for it in res["items"]])
            )
        return ChatResponse(reply=reply, products=[], tool_calls=collected_tool_calls)

    category = None
    if any(k in msg_lower for k in ("electronic", "headphone", "mouse", "monitor", "charger")):
        category = "Electronics"
    elif any(k in msg_lower for k in ("cloth", "jacket", "jean", "sweater", "shoe")):
        category = "Clothing"
    elif "book" in msg_lower:
        category = "Books"
    elif any(k in msg_lower for k in ("home", "vacuum", "kettle", "lamp")):
        category = "Home"

    price_match = re.search(r"(?:under|below|less than|\$)\s*(\d+)", msg_lower)
    max_price = float(price_match.group(1)) if price_match else None

    keywords = [
        w for w in msg_lower.split()
        if len(w) > 3 and w not in {"what", "show", "recommend", "please", "about", "find", "have"}
    ]
    query_str = " ".join(keywords[:2]) if keywords else ""

    prods = execute_search_products(db, query=query_str or None, max_price=max_price, category=category)
    for p in prods:
        collected_products.append(ProductCard(**p))

    collected_tool_calls.append(
        ToolCallInfo(
            name="search_products",
            arguments={"query": query_str, "max_price": max_price, "category": category},
            result=prods,
        )
    )

    reply = (
        f"I found {len(collected_products)} matching items in the ShopWave catalog! "
        "Explore the product cards below to view full details, ratings, and add them directly to your cart."
    )
    return ChatResponse(reply=reply, products=collected_products, tool_calls=collected_tool_calls)


# ── Chat Endpoint ─────────────────────────────────────────────────────────────

@router.post("", response_model=ChatResponse)
def chat_endpoint(
    payload: ChatRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    _rl: None = Depends(chat_limiter),
    current_user: Optional[models.User] = Depends(get_optional_user),
):
    try:
        safe_message = sanitize_ai_context(payload.message, max_len=MAX_MESSAGE_LENGTH)
    except ValueError as exc:
        logger.warning("Blocked unsafe chat input: %s", exc)
        raise HTTPException(
            status_code=400,
            detail="Your message contains disallowed content. Please rephrase and try again.",
        )

    safe_history = _sanitize_history(payload.history)
    uid: Optional[int] = current_user.id if current_user else None
    tracking_tok = payload.tracking_token

    gemini_key = os.getenv("GEMINI_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    provider_failed = False

    if gemini_key and len(gemini_key.strip()) > 10 and not gemini_key.startswith("your_"):
        try:
            return run_gemini_native_loop(
                message=safe_message,
                history=safe_history,
                db=db,
                gemini_api_key=gemini_key.strip(),
                user_id=uid,
                tracking_token=tracking_tok,
            )
        except Exception as exc:
            logger.error("Gemini provider error: %s", type(exc).__name__)
            provider_failed = True

    if openrouter_key and len(openrouter_key.strip()) > 10:
        try:
            return run_openai_compatible_loop(
                message=safe_message,
                history=safe_history,
                db=db,
                api_key=openrouter_key.strip(),
                base_url="https://openrouter.ai/api/v1",
                model=os.getenv("OPENROUTER_MODEL", "google/gemini-3.7-flash"),
                user_id=uid,
                tracking_token=tracking_tok,
            )
        except Exception as exc:
            logger.error("OpenRouter provider error: %s", type(exc).__name__)
            provider_failed = True

    if openai_key and len(openai_key.strip()) > 10 and not openai_key.startswith("your_"):
        try:
            return run_openai_compatible_loop(
                message=safe_message,
                history=safe_history,
                db=db,
                api_key=openai_key.strip(),
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                user_id=uid,
                tracking_token=tracking_tok,
            )
        except Exception as exc:
            logger.error("OpenAI provider error: %s", type(exc).__name__)
            provider_failed = True

    res = rule_based_fallback(safe_message, db, user_id=uid, tracking_token=tracking_tok)
    if provider_failed:
        res.error = "AI provider temporarily unavailable; served via local assistant."
    return res
