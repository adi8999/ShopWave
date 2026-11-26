# ⚡ ShopWave — Full-Stack E-Commerce Platform

> **Project Status**: **Staging / Hardening In Progress** — Core payment, security, migration, email abstraction, and AI-safety controls have been implemented and covered by automated tests. ShopWave is **not** guaranteed loophole-free; always complete environment-specific security checks (credential rotation, RDS security groups, TLS certificates, live Redis, and Stripe webhook verification) before handling real customer traffic.

ShopWave is a full-stack e-commerce web application built with **React 19**, **FastAPI**, **PostgreSQL / SQLite**, **Redis**, **Stripe**, and an **AI shopping assistant** with allowlisted tools and user-scoped data access.

---

## 🏗️ System Architecture

```mermaid
flowchart LR
    Browser["React 19 + Vite SPA"] -->|HTTPS / WSS| Nginx["Nginx Reverse Proxy\n(HSTS, CSP, TLS, Size Limits)"]
    Nginx -->|/api/*, /health, /metrics| FastAPI["FastAPI + Gunicorn\n(Uvicorn Workers)"]
    Nginx -->|/api/orders/ws/*| WS["WebSocket Manager\n(Single-Use Ticket Auth)"]
    FastAPI --> DB[("PostgreSQL / RDS\n(NUMERIC(12,2), Alembic)")]
    FastAPI --> Redis[("Redis\n(Rate Limits, WS Tickets, Cache)")]
    FastAPI --> Stripe["Stripe API & Signed Webhooks"]
    FastAPI --> Email["Email Provider\n(SMTP / AWS SES)"]
    FastAPI --> AI["Gemini / OpenAI / OpenRouter\n(Allowlisted Tools, Sanitized)"]
    FastAPI --> S3["S3 / Cloudflare R2\n(Product Image Uploads)"]
```

---

## 📊 Data Model Overview

- **Users (`users`)**: `id`, `name`, `email`, `hashed_password` (bcrypt), `is_admin`, `is_verified`, `token_version`, `mfa_enabled`, `mfa_secret`.
- **Products (`products`)**: `id`, `name`, `description`, `price` (`NUMERIC(12,2) > 0`), `category`, `stock` (`>= 0`), `low_stock_threshold`, `is_active` (soft-delete), `rating`, `review_count`.
- **Product Variants (`product_variants`)**: `id`, `product_id`, `name`, `sku`, `price_delta` (`NUMERIC(12,2)`), `stock` (`>= 0`).
- **Reviews (`reviews`)**: `id`, `product_id`, `user_id`, `rating` (`1–5`), `comment`.
- **Wishlist (`wishlist_items`)**: `id`, `user_id`, `product_id`.
- **Cart (`cart_items`)**: `id`, `user_id`, `product_id`, `quantity` (`> 0`).
- **Orders (`orders`) & OrderItems (`order_items`)**: `total_amount` (`NUMERIC(12,2)`), `discount_amount` (`NUMERIC(12,2)`), `status` (`draft -> awaiting_payment -> paid -> processing -> shipped -> delivered`, plus `cancelled` / `refunded`), `payment_status`, `stripe_payment_intent_id`, immutable `unit_price` snapshots.
- **Stripe Events (`stripe_events`)**: `event_id` (unique) for webhook idempotency.
- **Coupons (`coupons`)**: `code`, `percent_off` / `amount_off`, `min_order_amount`, `expires_at`, `max_uses`, `used_count`, `is_active`.
- **Tokens & Audit (`refresh_tokens`, `verification_tokens`, `audit_logs`)**: Refresh token rotation, one-time email/password-reset tokens, and admin action audit trail.

---

## 🔑 Demo & Stripe Test Credentials

> **Note**: Demo credentials are for local/staging evaluation only. **Never** use demo passwords or Stripe test keys in production.

| Role | Email | Password | Notes |
|---|---|---|---|
| **Demo Customer** | `demo@yourdomain.com` | Set via `DEMO_USER_PASSWORD` | Seeded by `python -m app.seed` |
| **Store Admin** | `admin@yourdomain.com` | Set via `ADMIN_PASSWORD` | Admin dashboard & analytics |
| **Stripe Test Mode** | — | — | Use `sk_test_...`, `pk_test_...`, `whsec_...` |

---

## ⚙️ Environment Variables

### Backend (`backend/.env` — never commit!)
Copy [backend/.env.example](backend/.env.example) to `backend/.env` and replace placeholders:

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes (32+ chars) | JWT & tracking token signing secret |
| `ENVIRONMENT` | Prod: `production` | Enables fail-closed Redis, mandatory `STRIPE_WEBHOOK_SECRET`, and disables console email |
| `FRONTEND_URL` | Yes | Base URL used in verification and password reset links |
| `DATABASE_URL` | Yes | PostgreSQL (`postgresql://...`) or SQLite (`sqlite:///./shopwave.db`) |
| `REDIS_URL` | Prod: Yes | Redis connection URL (e.g. `redis://localhost:6379`) |
| `ALLOWED_ORIGINS` | Yes | Comma-separated CORS origins |
| `TRUSTED_PROXIES` | Prod: Yes | Comma-separated proxy IPs allowed to set `X-Forwarded-For` (`127.0.0.1,::1`) |
| `EMAIL_PROVIDER` | Prod: `smtp` or `ses` | `console` (dev only), `smtp`, `ses`, or `memory` (tests) |
| `EMAIL_FROM` | Email | Sender email address |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_USE_TLS` | If `EMAIL_PROVIDER=smtp` | SMTP delivery settings |
| `AWS_SES_REGION` | If `EMAIL_PROVIDER=ses` | AWS region for SES |
| `STRIPE_SECRET_KEY` | Payments | Stripe secret key (`sk_test_...` / `sk_live_...`) |
| `STRIPE_PUBLISHABLE_KEY` | Payments | Stripe publishable key |
| `STRIPE_WEBHOOK_SECRET` | Prod: Yes | Stripe webhook signing secret (`whsec_...`) |
| `S3_BUCKET` / `S3_ENDPOINT_URL` / `S3_PUBLIC_URL` | Optional | S3 or Cloudflare R2 bucket for product image uploads |
| `SENTRY_DSN` | Optional | Sentry DSN for error tracking |
| `GEMINI_API_KEY` / `OPENAI_API_KEY` / `OPENROUTER_API_KEY` | Optional | AI assistant provider key |

---

## 🚀 Local Development & Migrations

### 1. Backend Setup & Alembic Migrations
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Apply database migrations (never rely on create_all() in production)
alembic upgrade head

# Optional: seed demo data
python -m app.seed

# Start dev server
uvicorn main:app --reload --port 8000
```

### 2. Frontend Setup
```bash
cd frontend
npm ci
npm run dev
```

### 3. Stripe Webhook Local Testing
```bash
stripe listen --forward-to localhost:8000/api/payments/webhook
```
Copy the printed `whsec_...` into `backend/.env` as `STRIPE_WEBHOOK_SECRET`.

---

## 🧪 Testing & Coverage

### Backend Unit & SQLite Tests (`pytest` + `pytest-cov`)
```bash
cd backend
pytest tests/ -v --cov=app --cov-report=term-missing
```

### PostgreSQL & Redis Integration Tests
Integration tests in `backend/tests/integration/test_postgres_redis.py` run automatically in GitHub Actions against `postgres:16` and `redis:7` service containers, or locally when `POSTGRES_TEST_URL` and `REDIS_TEST_URL` are provided:
```bash
cd backend
POSTGRES_TEST_URL="postgresql://shopwave:shopwave_ci_password@localhost:5432/shopwave_test" \
REDIS_TEST_URL="redis://localhost:6379/0" \
pytest tests/integration/ -v
```
When those variables are unset, integration tests skip cleanly instead of falsely passing against SQLite.

### Frontend Unit & Playwright E2E Tests
```bash
cd frontend
npm ci
npm run test -- --run
npm run build

# Install Chromium dependencies (required in CI / fresh machines) and run E2E
npx playwright install --with-deps chromium
npm run test:e2e
```

---

## ☁️ Staging & Deployment Procedures

### Staging Validation Checklist
1. Deploy to a staging environment with `ENVIRONMENT=production`, staging PostgreSQL (RDS/Neon), staging Redis, and `EMAIL_PROVIDER=smtp` or `ses`.
2. Run `alembic upgrade head` against staging PostgreSQL.
3. Run `POSTGRES_TEST_URL=... REDIS_TEST_URL=... pytest tests/ -v` against staging-equivalent services.
4. Verify Stripe test-mode webhooks (`stripe trigger payment_intent.succeeded`, `payment_intent.payment_failed`, `charge.refunded`).
5. Run `npm run build` and `npm run test:e2e` against the staging preview build.

### Option A: AWS (EC2 + RDS + Nginx + Systemd)
1. **RDS Security Group**: Restrict inbound port `5432` exclusively to the EC2 instance's security group (never `0.0.0.0/0`).
2. **Systemd**: Install `deploy/shopwave.service` to `/etc/systemd/system/shopwave.service` (`NoNewPrivileges=true`, `ProtectSystem=strict`, `PrivateTmp=true`).
3. **Nginx**: Copy `deploy/nginx.conf` to `/etc/nginx/sites-available/shopwave`, set `YOUR_DOMAIN`, and run `sudo certbot --nginx -d YOUR_DOMAIN`.
4. **Automated Rollout**: GitHub Actions (`.github/workflows/deploy.yml`) triggers `deploy/redeploy.sh` after CI passes and manual environment approval, running `alembic upgrade head` before restarting Gunicorn, checking `/health`, and rolling back on failure.

### Option B: Alternative (Docker / Render / Railway)
1. Set `ENVIRONMENT=production`, `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `EMAIL_PROVIDER`, and `ALLOWED_ORIGINS`.
2. Run `alembic upgrade head` as a pre-deploy release command.
3. Start the API with `gunicorn main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`.

---

## 🔐 Owner-Only Security Checklist (Credential Rotation & History Cleanup)

Automated repository changes **cannot** rotate external provider credentials or safely rewrite shared Git history without owner coordination:
1. **Rotate Credentials**: Rotate any database passwords (RDS/Neon), `SECRET_KEY`, Stripe keys/webhook secrets, SMTP/AWS keys, and AI provider keys (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`) that existed in local `.env` files or prior deployments.
2. **Purge Git History (if needed)**: `ShopWave-fixed.zip` was previously committed (`e7cc1d8`) and has now been untracked (`git rm --cached`). While inspection showed only `backend/.env.example` inside that zip, if you want to permanently scrub archive files from Git history, run [`git-filter-repo`](https://github.com/newren/git-filter-repo) on a fresh mirror clone:
   ```bash
   git clone --mirror https://github.com/adi8999/ShopWave.git
   cd ShopWave.git
   git filter-repo --invert-paths --path ShopWave-fixed.zip
   git push --force --all
   ```

---

## 💾 Disaster Recovery & Backups

```bash
# Backup
pg_dump "$DATABASE_URL" --format=custom --file="shopwave_$(date +%Y%m%d_%H%M%S).dump"

# Restore
pg_restore --clean --if-exists --dbname="$DATABASE_URL" shopwave_YYYYMMDD_HHMMSS.dump
alembic upgrade head
```

---

## ⚠️ Known Limitations

- Password-reset and email-verification delivery relies on `EMAIL_PROVIDER` (`smtp` or `ses` in production; `console` logs redacted metadata in non-production only).
- Checkout concurrency locking (`SELECT ... FOR UPDATE`) requires PostgreSQL; SQLite unit tests exercise the application logic without true row-level locks.
- Frontend checkout uses Stripe Elements test/sandbox flow; ensure `VITE_STRIPE_PUBLISHABLE_KEY` matches your Stripe environment.

---

## 🤝 Contributing & License

1. Fork the repository and create a feature branch.
2. Run backend (`pytest`) and frontend (`npm run test -- --run`) suites before opening a PR.
3. Licensed under the **MIT License**.
