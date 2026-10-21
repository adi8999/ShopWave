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
uvicorn main:app --reload --port 8000
```

API Documentation will be available at: `http://localhost:8000/docs`

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Visit the app at: `http://localhost:5173`

---

## ☁️ AWS Single-Server Deployment Guide

ShopWave is configured for single-server production deployment on **AWS EC2 (Ubuntu 22.04 / 24.04)** paired with an **AWS RDS PostgreSQL** managed database.

### 🏗️ Production Architecture
- **Nginx (Reverse Proxy)**:
  - Serves compiled static frontend files directly from `/var/www/shopwave` with `try_files $uri /index.html` (for React Router client-side routing).
  - Reverse proxies `/api/` requests to Gunicorn on `127.0.0.1:8000`.
  - Terminates TLS/HTTPS via Let's Encrypt certificates managed by Certbot.
- **Systemd Service (`shopwave.service`)**:
  - Manages Gunicorn running Uvicorn workers (`gunicorn main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000`).
  - Auto-starts on boot and restarts automatically on failures.
- **Database**:
  - AWS RDS PostgreSQL accessed privately over port 5432.

---

### 🔑 Required Environment Variables

Create `backend/.env` on the EC2 server (refer to `backend/.env.example`):

| Variable | Description | Example |
|---|---|---|
| `SECRET_KEY` | 32+ character random secret for JWT signing | Generate via `python3 -c 'import secrets; print(secrets.token_hex(32))'` |
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql://user:password@rds-endpoint.amazonaws.com:5432/shopwave` |
| `ALLOWED_ORIGINS` | Comma-separated allowed CORS origins | `https://yourdomain.com,https://www.yourdomain.com` |
| `ADMIN_EMAIL` | Admin login email | `admin@yourdomain.com` |
| `ADMIN_PASSWORD` | Admin initial password (never hardcoded) | Strong password |
| `STRIPE_SECRET_KEY` | Stripe live/test secret key | `sk_test_...` |
| `STRIPE_PUBLISHABLE_KEY` | Stripe live/test publishable key | `pk_test_...` |
| `GEMINI_API_KEY` | Google Gemini API key for chatbot | `AIzaSy...` |

---

### 🚀 Initial Provisioning on EC2

1. **SSH into your EC2 instance**:
   ```bash
   ssh -i your-key.pem ubuntu@<ec2-ip-or-dns>
   ```

2. **Clone the repository and set up environment**:
   ```bash
   git clone https://github.com/adi8999/ShopWave.git /home/ubuntu/shopwave
   cd /home/ubuntu/shopwave
   cp backend/.env.example backend/.env
   nano backend/.env  # Fill in your real RDS, SECRET_KEY, and other credentials
   ```

3. **Run the provisioning script**:
   ```bash
   bash deploy/setup_ec2.sh yourdomain.com
   ```
   *This script verifies `backend/.env`, installs system packages (Python, Nginx, Certbot), sets up the Python venv, seeds initial data, configures the systemd daemon, and sets up Nginx.*

---

### 🔒 Enabling HTTPS (SSL/TLS)

Once your domain's DNS `A` records (e.g. `yourdomain.com` and `www.yourdomain.com`) point to your EC2 instance's Elastic IP, run:

```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Certbot will automatically obtain certificates from Let's Encrypt, configure HTTPS in Nginx, set up automatic HTTP -> HTTPS redirection, and register a systemd auto-renewal timer.

---

### 🔄 Redeploying Updates

Whenever you push new code to GitHub, deploy the updates to EC2 with a single command:

```bash
cd /home/ubuntu/shopwave
bash deploy/redeploy.sh
```

This script:
1. Pulls the latest commits from Git.
2. Updates backend dependencies in `venv`.
3. Restarts the `shopwave` systemd backend service.
4. Copies updated `frontend/dist` to `/var/www/shopwave`.
5. Verifies and reloads Nginx.

---

### 🛡️ "Before Going Live" Checklist

Before launching your production application, complete these essential steps:

- [ ] **Rotate RDS Password**: If your RDS password was ever stored in plain text or shared, rotate it immediately in the AWS RDS Console and update `DATABASE_URL` in `backend/.env`.
- [ ] **Set a Strong `SECRET_KEY`**: Ensure `SECRET_KEY` is at least 32 characters long.
  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"
  ```
- [ ] **Set Admin Credentials**: Set `ADMIN_EMAIL` and a unique `ADMIN_PASSWORD` in `backend/.env`, then run:
  ```bash
  cd /home/ubuntu/shopwave/backend && source venv/bin/activate && python -m app.seed
  ```
- [ ] **Lock Down RDS Security Group**:
  - Open AWS RDS Console -> Databases -> your DB -> Connectivity & security -> VPC security groups.
  - Delete any inbound rule permitting `0.0.0.0/0` on port 5432.
  - Add an inbound rule allowing Type: `PostgreSQL` (port 5432) with Source set to the **Security Group ID of your EC2 instance** (e.g., `sg-0abc123...`).
- [ ] **Configure Strict CORS**: In `backend/.env`, set `ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com` (no wildcards or local addresses in production).
- [ ] **Restart Backend Service**:
  ```bash
  sudo systemctl restart shopwave
  ```


---

## 📄 Resume Bullet Point

> **AI Chatbot & Tool Integration**: Built an end-to-end AI shopping assistant in FastAPI and React using Gemini function calling, allowing users to query catalog items and fetch live order statuses via natural language conversation.
