# ⚡ ShopWave — Full-Stack E-Commerce Platform

A production-ready e-commerce web application featuring user authentication, shopping cart persistence, dynamic product catalog management, administrative CRUD & sales analytics dashboard, and an **AI-powered shopping assistant chatbot with Google Gemini tool calling**, deployed on **AWS EC2** and **AWS RDS (PostgreSQL)**.

---

## 🌟 Key Features

- **🤖 AI Shopping Assistant & Customer Support Chatbot**:
  - **Tool Calling (Function Calling)**: Powered by Google Gemini / OpenRouter multi-turn function calling with live database execution.
    - `search_products(query, max_price, category)`: Scans catalog products across multiple fields, prices, and categories.
    - `get_order_status(order_id)`: Fetches live order fulfillment status (`processing`, `shipped`, `delivered`), total amount, shipping destination, and itemized receipts.
  - **Interactive Clickable Product Cards**: Chatbot responses include interactive product cards with images, prices, ratings, direct links to product pages, and a **1-click "Add to Cart"** button.
  - **Floating Drawer & Navbar Trigger**: Accessible via a floating widget launcher button at the bottom-right and an **AI Assistant** pill in the top navigation bar.
  - **Quick Suggestion Chips**: Instant starter prompts (e.g. *"Tech under $300"*, *"Track order #1001"*, *"Daily essentials"*, *"Shipping & returns"*).
  - **Session Persistence**: Chat history persists across page navigation using `sessionStorage`.
- **Storefront & Catalog**:
  - Browse products across multiple categories (Electronics, Clothing, Books, Home).
  - Search by title, filter by category, and sort by price range.
  - Interactive product detail pages with real-time stock availability.
  - **Customer Reviews & Ratings**: Submit 1–5 star reviews with verified purchase detection (automatically checks user order history for the item) and real-time average score updates.
- **Cart & Order Checkout**:
  - Persistent shopping cart synced with backend API per user.
  - Stripe payment processing integration with card validation.
  - Multi-item checkout flow with address validation and stock updates.
  - Order history tracking with item breakdown and status updates.
- **Authentication & Security**:
  - User registration & login with JWT bearer tokens.
  - Secure password hashing using native `bcrypt`.
  - Account-level data isolation (users only see their own cart and orders).
- **Admin Panel & Sales Monitoring**:
  - Role-based authorization (`is_admin=True` check on protected routes).
  - **Full Product CRUD**: Add, edit, and delete catalog products inline with confirm modals.
  - **Sales Analytics Dashboard**: Real-time revenue, order counts, top-selling products visualization, and order status management.

---

## 🛠️ Architecture & Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 19, Vite, React Router 7, Axios, Lucide Icons, React Hot Toast, Stripe Elements |
| **Backend** | FastAPI (Python 3.11+), Uvicorn / Gunicorn, Pydantic v2, SQLAlchemy ORM |
| **AI & LLM** | Google Gemini (`google-genai`), OpenAI / OpenRouter Tool Calling API |
| **Database & Cache** | PostgreSQL (AWS RDS) / SQLite (Local Dev), Redis |
| **Server & Deployment** | AWS EC2 (Ubuntu 22.04 / 24.04), Nginx Reverse Proxy, Systemd Service |

---

## 🤖 AI Chatbot Architecture

```
User in Browser (React ChatWidget / Navbar Trigger)
        │
        ▼ (POST /api/chat with message & history)
FastAPI Backend (/api/chat)
        │
        ▼ (Prompt + System Instructions + Database Tools)
Google Gemini LLM / OpenRouter
        │
        ├─► [Tool Call: search_products] ──► Query Product Table (SQLAlchemy)
        ├─► [Tool Call: get_order_status] ──► Query Order & OrderItem Tables
        │
        ▼ (Tool Output Fed Back into LLM Context)
Google Gemini Synthesizes Conversational Answer
        │
        ▼ (JSON: reply text + structured product cards + tool metadata)
React Chat Drawer (Renders message + interactive product cards + 1-click cart add)
```

---

## 🚀 Local Development Setup

### 1. Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Configure your keys in backend/.env:
# GEMINI_API_KEY=your_gemini_api_key (or OPENROUTER_API_KEY=...)
# DATABASE_URL=sqlite:///./shopwave.db (for local development)

# Run database migrations and auto-seed products
python -m app.seed

# Start FastAPI dev server
uvicorn main:app --reload --port 8001
```

API Documentation will be available at: `http://localhost:8001/docs`

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Visit the app at: `http://localhost:5173`

---

## ☁️ AWS Deployment Setup

- **Backend**: Hosted on AWS EC2 behind Nginx reverse proxy using Gunicorn systemd service.
- **Database**: Hosted on AWS RDS PostgreSQL instance with security group ingress rules on port 5432.
- **Deploy Script**: Run `./deploy/setup_ec2.sh` on EC2 for automated environment configuration.

---

## 👤 Admin Access

- **Email**: `admin@shopwave.com`
- **Password**: `Admin@123`

---

## 📄 Resume Bullet Point

> **AI Chatbot & Tool Integration**: Built an end-to-end AI shopping assistant in FastAPI and React using Gemini function calling, allowing users to query catalog items and fetch live order statuses via natural language conversation.
