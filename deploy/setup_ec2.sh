#!/bin/bash
# =============================================================================
# deploy/setup_ec2.sh — One-time EC2 provisioning for ShopWave
# Usage: bash setup_ec2.sh <your-domain.com>
# =============================================================================
set -euo pipefail

DOMAIN="${1:-}"
if [[ -z "$DOMAIN" ]]; then
  echo "❌ Usage: bash setup_ec2.sh <your-domain.com>"
  echo "   Example: bash setup_ec2.sh shopwave.example.com"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Use current repo if run from within the clone, else default to /home/ubuntu/shopwave
if [[ -d "$REPO_ROOT/.git" ]]; then
  APP_DIR="$REPO_ROOT"
else
  APP_DIR="/home/ubuntu/shopwave"
fi
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIST="/var/www/shopwave"
SERVICE_NAME="shopwave"

echo "🚀 ShopWave EC2 setup for domain: $DOMAIN"

# ── 1. System packages ────────────────────────────────────────────────────────
sudo apt-get update -y
sudo apt-get install -y \
  python3-pip python3-venv \
  nginx git curl libpq-dev \
  certbot python3-certbot-nginx

# ── 2. Clone / pull repo ──────────────────────────────────────────────────────
if [[ ! -d "$APP_DIR/.git" ]]; then
  echo "📥 Cloning repository..."
  git clone https://github.com/adi8999/ShopWave.git "$APP_DIR"
else
  echo "📥 Repo found at $APP_DIR. Pulling latest code..."
  git -C "$APP_DIR" pull
fi

# ── 3. Check backend .env ─────────────────────────────────────────────────────
if [[ ! -f "$BACKEND_DIR/.env" ]]; then
  echo ""
  echo "❌ STOP: $BACKEND_DIR/.env not found."
  echo "   Copy backend/.env.example to backend/.env and fill in all values:"
  echo "     cp $BACKEND_DIR/.env.example $BACKEND_DIR/.env"
  echo "     nano $BACKEND_DIR/.env"
  echo ""
  exit 1
fi
echo "✅ backend/.env found."

# ── 4. Python virtualenv + dependencies ──────────────────────────────────────
cd "$BACKEND_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
deactivate
echo "✅ Python dependencies installed."

# ── 5. Run DB seed (one-time, manual step) ────────────────────────────────────
echo ""
echo "ℹ️  Seeding database (products + admin user)..."
cd "$BACKEND_DIR"
source venv/bin/activate
python -m app.seed
deactivate

# ── 6. Serve frontend static files ───────────────────────────────────────────
sudo mkdir -p "$FRONTEND_DIST"
if [[ -d "$APP_DIR/frontend/dist" ]]; then
  sudo cp -r "$APP_DIR/frontend/dist/." "$FRONTEND_DIST/"
  echo "✅ Frontend dist copied to $FRONTEND_DIST"
else
  echo "⚠️  frontend/dist not found. Build locally and scp, or run:"
  echo "   cd $APP_DIR/frontend && npm install && npm run build"
  echo "   sudo cp -r $APP_DIR/frontend/dist/. $FRONTEND_DIST/"
fi

# ── 7. Systemd service ────────────────────────────────────────────────────────
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<EOF
[Unit]
Description=ShopWave FastAPI Backend
After=network.target

[Service]
User=ubuntu
WorkingDirectory=${BACKEND_DIR}
Environment="PATH=${BACKEND_DIR}/venv/bin"
EnvironmentFile=${BACKEND_DIR}/.env
ExecStart=${BACKEND_DIR}/venv/bin/gunicorn main:app \\
    -w 2 -k uvicorn.workers.UvicornWorker \\
    --bind 127.0.0.1:8000 \\
    --timeout 120 \\
    --access-logfile - \\
    --error-logfile -
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"
echo "✅ systemd service '$SERVICE_NAME' running."

# ── 8. Nginx config ───────────────────────────────────────────────────────────
sudo tee /etc/nginx/sites-available/shopwave > /dev/null <<EOF
server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN};

    root ${FRONTEND_DIST};
    index index.html;

    # Serve React app — send all unknown paths to index.html (React Router)
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # Proxy /api/ to FastAPI backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }
}
EOF

sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/shopwave /etc/nginx/sites-enabled/shopwave
sudo nginx -t
sudo systemctl restart nginx
echo "✅ Nginx configured and restarted."

# ── 9. HTTPS instructions ─────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════"
echo "🎉 ShopWave setup complete! HTTP is live at http://${DOMAIN}"
echo ""
echo "📋 NEXT: Enable HTTPS (run AFTER your DNS A record points here):"
echo ""
echo "   sudo certbot --nginx -d ${DOMAIN} -d www.${DOMAIN}"
echo ""
echo "   Certbot will obtain a Let's Encrypt certificate and auto-reload Nginx."
echo "   Auto-renewal is already set up via certbot's systemd timer."
echo ""
echo "📋 REMAINING MANUAL STEPS (see README Before-going-live checklist):"
echo "   1. Rotate your RDS password and update DATABASE_URL in .env"
echo "   2. Set a strong SECRET_KEY (python -c 'import secrets; print(secrets.token_hex(32))')"
echo "   3. Set ADMIN_PASSWORD in .env and re-run: python -m app.seed"
echo "   4. Restrict RDS Security Group to accept port 5432 from EC2 SG only"
echo "   5. Set ALLOWED_ORIGINS=https://${DOMAIN} in .env"
echo "   6. Run: sudo systemctl restart shopwave"
echo "════════════════════════════════════════════════════════════"
