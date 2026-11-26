#!/bin/bash
# =============================================================================
# deploy/redeploy.sh — Pull latest code, run Alembic migrations, roll out,
# verify health, and automatically roll back on failure.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="${REPO_ROOT}"
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIST="/var/www/shopwave"
SERVICE_NAME="shopwave"
HEALTH_URL="http://127.0.0.1:8000/health"

PREV_COMMIT="$(git -C "$APP_DIR" rev-parse HEAD)"

rollback() {
  echo "❌ Deployment failed — rolling back to $PREV_COMMIT..."
  git -C "$APP_DIR" checkout "$PREV_COMMIT"
  sudo systemctl restart "$SERVICE_NAME" || true
  exit 1
}
trap rollback ERR

echo "🔄 Redeploying ShopWave (previous commit: $PREV_COMMIT)..."

# ── 1. Pull latest code ───────────────────────────────────────────────────────
git -C "$APP_DIR" pull --ff-only
echo "✅ Code updated."

# ── 2. Install backend dependencies & run Alembic migrations BEFORE rollout ──
cd "$BACKEND_DIR"
source venv/bin/activate
pip install -r requirements.txt --quiet
alembic upgrade head
deactivate
echo "✅ Dependencies updated and Alembic migrations applied."

# ── 3. Restart backend service ────────────────────────────────────────────────
sudo systemctl restart "$SERVICE_NAME"
sleep 3

# ── 4. Health check ──────────────────────────────────────────────────────────
if ! curl -fsS "$HEALTH_URL" > /dev/null; then
  echo "❌ Health check failed at $HEALTH_URL"
  rollback
fi
echo "✅ Backend health check passed."

# ── 5. Build and cleanly replace frontend dist (remove old files) ─────────────
if [[ -d "$APP_DIR/frontend" ]] && command -v npm &> /dev/null; then
  echo "📦 Building frontend..."
  cd "$APP_DIR/frontend"
  npm ci --quiet
  npm run build
  sudo mkdir -p "$FRONTEND_DIST"
  sudo rm -rf "${FRONTEND_DIST:?}/"*
  sudo cp -r "$APP_DIR/frontend/dist/." "$FRONTEND_DIST/"
  echo "✅ Frontend deployed cleanly to $FRONTEND_DIST"
fi

# ── 6. Reload Nginx ──────────────────────────────────────────────────────────
sudo nginx -t && sudo systemctl reload nginx
echo "✅ Nginx reloaded."

echo "🎉 Redeploy complete!"
