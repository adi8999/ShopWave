# ⚡ ShopWave — Full-Stack E-Commerce Platform

A production-ready e-commerce web application featuring user authentication, shopping cart persistence, dynamic product catalog management, administrative CRUD & sales analytics dashboard, deployed on **AWS EC2** and **AWS RDS (PostgreSQL)**.

---

## 🌟 Key Features

- **Storefront & Catalog**:
  - Browse products across multiple categories (Electronics, Clothing, Books, Home).
  - Search by title, filter by category, and sort by price range.
  - Interactive product detail pages with real-time stock availability.
- **Cart & Order Checkout**:
  - Persistent shopping cart synced with backend API per user.
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
| **Frontend** | React 19, Vite, React Router 7, Axios, Lucide Icons, React Hot Toast |
| **Backend** | FastAPI (Python 3.14), Gunicorn + Uvicorn Workers, Pydantic v2 |
| **Database** | PostgreSQL (AWS RDS), SQLAlchemy ORM |
| **Server & Deployment** | AWS EC2 (Ubuntu 22.04 / 26.04), Nginx Reverse Proxy, Systemd Service |

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
