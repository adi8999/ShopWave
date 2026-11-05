#!/bin/bash
# =============================================================================
# deploy/redeploy.sh — Pull latest code and restart ShopWave
# Usage: bash redeploy.sh
# Run on the EC2 instance whenever you push new changes to GitHub.
# =============================================================================
set -euo pipefail

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

echo "🔄 Redeploying ShopWave..."

# ── 1. Pull latest code ───────────────────────────────────────────────────────
git -C "$APP_DIR" pull
echo "✅ Code updated."

# ── 2. Install / update backend dependencies ─────────────────────────────────
cd "$BACKEND_DIR"
source venv/bin/activate
pip install -r requirements.txt --quiet
deactivate
echo "✅ Backend dependencies installed."

# ── 3. Restart backend service ────────────────────────────────────────────────
sudo systemctl restart "$SERVICE_NAME"
echo "✅ Backend service restarted."

# ── 4. Build and copy frontend dist ──────────────────────────────────────────
if [[ -d "$APP_DIR/frontend" ]] && command -v npm &> /dev/null; then
  echo "📦 Updating and building frontend..."
  cd "$APP_DIR/frontend"
  npm install --quiet
  npm run build
  sudo mkdir -p "$FRONTEND_DIST"
  sudo cp -r "$APP_DIR/frontend/dist/." "$FRONTEND_DIST/"
  echo "✅ Frontend built and copied to $FRONTEND_DIST"
elif [[ -d "$APP_DIR/frontend/dist" ]]; then
  sudo mkdir -p "$FRONTEND_DIST"
  sudo cp -r "$APP_DIR/frontend/dist/." "$FRONTEND_DIST/"
  echo "✅ Frontend dist copied to $FRONTEND_DIST"
else
  echo "⚠️  frontend/dist not found — skipping frontend update."
fi

# ── 5. Reload Nginx (picks up any config changes) ─────────────────────────────
sudo nginx -t && sudo systemctl reload nginx
echo "✅ Nginx reloaded."

echo ""
echo "🎉 Redeploy complete! ShopWave is up to date."
