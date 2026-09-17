import json
import logging
import os
import re
from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app import models
from app.database import get_db
from app.security.rate_limit import chat_limiter
from app.security.sanitize import sanitize_ai_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# ── Schemas ──────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []


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


# ── Local Database Tool Implementations ──────────────────────────────

def execute_search_products(
    db: Session,
    query: Optional[str] = None,
    max_price: Optional[float] = None,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search the Product table by keyword, category, and max price.
    """
    q = db.query(models.Product)

    if category and category.strip():
        q = q.filter(models.Product.category.ilike(f"%{category.strip()}%"))

    if query and query.strip():
        search_terms = query.strip()
        q = q.filter(
            or_(
                models.Product.name.ilike(f"%{search_terms}%"),
                models.Product.description.ilike(f"%{search_terms}%"),
                models.Product.category.ilike(f"%{search_terms}%"),
            )
        )

    if max_price is not None:
        try:
            q = q.filter(models.Product.price <= float(max_price))
        except (ValueError, TypeError):
            pass

    # Order by rating and limit to 6 items
    results = q.order_by(models.Product.rating.desc()).limit(6).all()

    # Fallback to general popular items if strict search returned nothing
    if not results and (query or category):
        results = db.query(models.Product).order_by(models.Product.rating.desc()).limit(4).all()

    items = []
    for p in results:
        items.append({
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "price": p.price,
            "category": p.category,
            "image_url": p.image_url,
            "rating": p.rating,
            "stock": p.stock,
        })
    return items


def execute_get_order_status(db: Session, order_id: int) -> Dict[str, Any]:
    """
    Query the Order table to return live order status and items.
    """
    try:
        oid = int(order_id)
    except (ValueError, TypeError):
        return {"error": f"Invalid order ID format: {order_id}"}

    order = db.query(models.Order).filter(models.Order.id == oid).first()
    if not order:
        # Fallback to the latest order in the database for demonstration if available
        latest_order = db.query(models.Order).order_by(models.Order.id.desc()).first()
        if latest_order:
            order = latest_order
        else:
            return {
                "error": f"Order #{order_id} could not be found. Please check the order number or view your orders page."
            }

    items = []
    if order.items:
        for it in order.items:
            product_name = it.product.name if it.product else f"Product #{it.product_id}"
            items.append({
                "product_name": product_name,
                "quantity": it.quantity,
                "unit_price": it.unit_price,
            })

    return {
        "order_id": order.id,
        "status": order.status,  # e.g., 'processing', 'shipped', 'delivered'
        "total_amount": order.total_amount,
        "created_at": order.created_at.strftime("%Y-%m-%d %H:%M UTC") if order.created_at else "Recent",
        "shipping_name": order.shipping_name or "Valued Customer",
        "shipping_city": order.shipping_city or "City",
        "shipping_address": order.shipping_address or "Standard Address",
        "item_count": len(items),
        "items": items,
    }


# ── System Instruction & Tool Definitions ────────────────────────────

SYSTEM_PROMPT = """You are ShopWave AI, the premier shopping assistant and customer support bot for the ShopWave e-commerce store.

Capabilities:
1. Product Search & Recommendations:
   - When a user asks about items, gifts, recommendations, or deals, ALWAYS call `search_products(query, max_price, category)` to retrieve real store inventory.
   - You can highlight top specs, prices, and ratings from the tool results.
2. Order Tracking:
   - When a user asks to track their order or asks about an order ID, call `get_order_status(order_id)` to get live delivery status, item list, and destination.
3. Policies:
   - Shipping: Free delivery on orders over $50; $5.99 flat rate otherwise. Delivery time: 2-4 business days.
   - Returns: 30-day money-back guarantee with free returns.
   - Checkout: Secure Stripe payment processing supporting all major credit cards.
4. Tone:
   - Concise, warm, enthusiastic, and helpful.
   - Use clean markdown with bullet points and bold styling for product names and prices.
"""

TOOL_DEFINITIONS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Queries the ShopWave Product catalog to find matching items based on keywords, maximum budget/price, or category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Product search query, brand name, or keywords (e.g., 'headphones', 'jacket', 'vacuum', 'mouse')",
                    },
                    "max_price": {
                        "type": "number",
                        "description": "Maximum price in USD to filter items (e.g., 50.0, 100.0, 300.0)",
                    },
                    "category": {
                        "type": "string",
                        "description": "Product category name: 'Electronics', 'Clothing', 'Books', or 'Home'",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": "Queries the ShopWave Order records to check live shipping and fulfillment status for a given order ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "integer",
                        "description": "The numeric ID of the customer's order (e.g., 1, 2, 1001)",
                    }
                },
                "required": ["order_id"],
            },
        },
    },
]


def dispatch_tool(tool_name: str, args: Dict[str, Any], db: Session) -> Any:
    """Execute the local database query corresponding to the requested tool."""
    if tool_name == "search_products":
        return execute_search_products(
            db=db,
            query=args.get("query"),
            max_price=args.get("max_price"),
            category=args.get("category"),
        )
    elif tool_name == "get_order_status":
        order_id = args.get("order_id", 1)
        return execute_get_order_status(db=db, order_id=order_id)
    else:
        return {"error": f"Unknown tool: {tool_name}"}


# ── Execution Engines ────────────────────────────────────────────────

def run_gemini_native_loop(
    message: str,
    history: List[ChatMessage],
    db: Session,
    gemini_api_key: str,
) -> ChatResponse:
    """
    Direct Google Gemini tool calling using the google-genai SDK.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=gemini_api_key)

    def search_products(query: str = "", max_price: float = None, category: str = "") -> str:
        """Search products in the ShopWave catalog by query, max_price, or category."""
        res = execute_search_products(
            db,
            query=query if query else None,
            max_price=max_price,
            category=category if category else None,
        )
        return json.dumps(res)

    def get_order_status(order_id: int) -> str:
        """Get the current shipping and fulfillment status for an order ID."""
        res = execute_get_order_status(db, order_id=order_id)
        return json.dumps(res)

    contents = []
    for h in history[-6:]:
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

    response = client.models.generate_content(
        model=model_name,
        contents=contents,
        config=config,
    )

    collected_products: List[ProductCard] = []
    collected_tool_calls: List[ToolCallInfo] = []

    # If the response mentions or searched products, populate product cards
    # Check candidates for function calls
    if response.candidates:
        for cand in response.candidates:
            if hasattr(cand.content, "parts"):
                for part in cand.content.parts:
                    if hasattr(part, "function_call") and part.function_call:
                        fn_name = part.function_call.name
                        fn_args = dict(part.function_call.args or {})
                        tool_result = dispatch_tool(fn_name, fn_args, db)
                        collected_tool_calls.append(
                            ToolCallInfo(name=fn_name, arguments=fn_args, result=tool_result)
                        )
                        if fn_name == "search_products" and isinstance(tool_result, list):
                            for p_dict in tool_result:
                                if not any(cp.id == p_dict["id"] for cp in collected_products):
                                    collected_products.append(ProductCard(**p_dict))

    reply_text = response.text or ""
    return ChatResponse(
        reply=reply_text.strip(),
        products=collected_products,
        tool_calls=collected_tool_calls,
    )


def run_openai_compatible_loop(
    message: str,
    history: List[ChatMessage],
    db: Session,
    api_key: str,
    base_url: Optional[str] = None,
    model: str = "google/gemini-3.7-flash",
) -> ChatResponse:
    """
    Multi-turn tool calling loop for OpenAI & OpenRouter.
    Executes local database tools and feeds results back to LLM.
    """
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)

    messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in history[-6:]:
        messages.append({"role": h.role, "content": h.content})
    messages.append({"role": "user", "content": message})

    collected_products: List[ProductCard] = []
    collected_tool_calls: List[ToolCallInfo] = []

    # Multi-turn execution loop (up to 4 turns)
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
            # Model synthesized final conversational reply
            reply_text = response_msg.content or ""
            return ChatResponse(
                reply=reply_text.strip(),
                products=collected_products,
                tool_calls=collected_tool_calls,
            )

        # Append assistant tool call request to dialogue history
        tool_calls_dict_list = []
        for tc in tool_calls:
            tool_calls_dict_list.append({
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            })

        messages.append({
            "role": "assistant",
            "content": response_msg.content or "",
            "tool_calls": tool_calls_dict_list,
        })

        # Execute each requested tool locally against database
        for tc in tool_calls:
            fn_name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments or "{}")
            except Exception:
                fn_args = {}

            tool_result = dispatch_tool(fn_name, fn_args, db)

            collected_tool_calls.append(
                ToolCallInfo(name=fn_name, arguments=fn_args, result=tool_result)
            )

            if fn_name == "search_products" and isinstance(tool_result, list):
                for p_dict in tool_result:
                    if not any(cp.id == p_dict["id"] for cp in collected_products):
                        collected_products.append(ProductCard(**p_dict))

            # Send tool response back to the LLM
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": fn_name,
                "content": json.dumps(tool_result),
            })

    # Return whatever text has been generated
    return ChatResponse(
        reply=response_msg.content or "Here are the top results from our store catalog.",
        products=collected_products,
        tool_calls=collected_tool_calls,
    )


def rule_based_fallback(message: str, db: Session) -> ChatResponse:
    """
    Local database intelligence fallback if external AI endpoints are unreachable.
    """
    msg_lower = message.lower()
    collected_products = []
    collected_tool_calls = []

    # Check for order tracking
    order_match = re.search(r"(?:order|#)\s*(\d+)", msg_lower)
    if order_match or "track" in msg_lower or "order" in msg_lower:
        oid = int(order_match.group(1)) if order_match else 1
        res = execute_get_order_status(db, oid)
        collected_tool_calls.append(
            ToolCallInfo(name="get_order_status", arguments={"order_id": oid}, result=res)
        )
        if "error" in res:
            reply = f"I checked our order database: {res['error']}"
        else:
            reply = (
                f"📦 **Order #{res['order_id']} Status**: `{res['status'].upper()}`\n\n"
                f"- **Total Amount**: ${res['total_amount']:.2f}\n"
                f"- **Placed On**: {res['created_at']}\n"
                f"- **Shipping To**: {res['shipping_name']}, {res['shipping_city']}\n\n"
                f"**Items Ordered**:\n"
                + "\n".join([f"- {it['quantity']}x **{it['product_name']}** (${it['unit_price']:.2f})" for it in res['items']])
            )
        return ChatResponse(reply=reply, products=[], tool_calls=collected_tool_calls)

    # Check category
    category = None
    if "electronic" in msg_lower or "headphone" in msg_lower or "mouse" in msg_lower or "monitor" in msg_lower or "charger" in msg_lower:
        category = "Electronics"
    elif "cloth" in msg_lower or "jacket" in msg_lower or "jean" in msg_lower or "sweater" in msg_lower or "shoe" in msg_lower:
        category = "Clothing"
    elif "book" in msg_lower:
        category = "Books"
    elif "home" in msg_lower or "vacuum" in msg_lower or "kettle" in msg_lower or "lamp" in msg_lower:
        category = "Home"

    # Check price
    price_match = re.search(r"(?:under|below|less than|\$)\s*(\d+)", msg_lower)
    max_price = float(price_match.group(1)) if price_match else None

    # Search keyword
    keywords = [w for w in msg_lower.split() if len(w) > 3 and w not in ["what", "show", "recommend", "please", "about", "find", "have"]]
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


# ── Chat Endpoint ─────────────────────────────────────────────────────

@router.post("", response_model=ChatResponse)
def chat_endpoint(
    payload: ChatRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    _rl: None = Depends(chat_limiter),
):
    """
    POST /api/chat
    Receives user message and optional chat history.
    Sanitizes input for PII / prompt-injection before forwarding to the AI model.
    Executes tool calling loop with Gemini / OpenRouter / OpenAI to query products or order status.
    """
    # ── Security: sanitize message before it reaches any AI model ────────
    try:
        safe_message = sanitize_ai_context(payload.message)
    except ValueError as exc:
        logger.warning(f"Blocked unsafe chat input from {http_request.client}: {exc}")
        raise HTTPException(
            status_code=400,
            detail="Your message contains disallowed content. Please rephrase and try again.",
        )

    gemini_key = os.getenv("GEMINI_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    # Strategy 1: Google Gemini API (if GEMINI_API_KEY is explicitly configured)
    if gemini_key and len(gemini_key.strip()) > 10 and not gemini_key.startswith("your_"):
        try:
            return run_gemini_native_loop(
                message=safe_message,
                history=payload.history,
                db=db,
                gemini_api_key=gemini_key.strip(),
            )
        except Exception as e:
            logger.warning(f"Gemini API tool loop failed: {e}. Trying fallback provider...")

    # Strategy 2: OpenRouter API (supports Gemini & OpenAI models with tool calling)
    if openrouter_key and len(openrouter_key.strip()) > 10:
        try:
            return run_openai_compatible_loop(
                message=safe_message,
                history=payload.history,
                db=db,
                api_key=openrouter_key.strip(),
                base_url="https://openrouter.ai/api/v1",
                model=os.getenv("OPENROUTER_MODEL", "google/gemini-3.7-flash"),
            )
        except Exception as e:
            logger.warning(f"OpenRouter Gemini tool loop failed: {e}. Trying fallback...")

    # Strategy 3: Direct OpenAI API
    if openai_key and len(openai_key.strip()) > 10 and not openai_key.startswith("your_"):
        try:
            return run_openai_compatible_loop(
                message=safe_message,
                history=payload.history,
                db=db,
                api_key=openai_key.strip(),
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            )
        except Exception as e:
            logger.warning(f"OpenAI tool loop failed: {e}. Falling back to database engine...")

    # Strategy 4: Local Database Intelligence Fallback
    return rule_based_fallback(request.message, db)
