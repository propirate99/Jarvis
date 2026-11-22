#!/usr/bin/env bash
# start-mobile.sh — JARVIS 1B  Mobile Mode
#
# Starts FastAPI + Next.js bound to 0.0.0.0, so any device on the same
# Wi-Fi network can access the full JARVIS UI with real-time streaming.
#
# Usage:  ./start-mobile.sh
# Stop :  Ctrl+C  (both servers are terminated cleanly)

set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Sanity checks ─────────────────────────────────────────────────────────────
if [[ ! -d "$ROOT/backend/app" || ! -d "$ROOT/frontend/app" ]]; then
  echo "ERROR: JARVIS project folders not found at: $ROOT" >&2
  exit 1
fi
if [[ ! -x "$ROOT/backend/.venv/bin/uvicorn" ]]; then
  echo "ERROR: Backend venv not found. Run install.sh (or install-mobile.sh) first." >&2
  exit 1
fi
if [[ ! -x "$ROOT/frontend/node_modules/.bin/next" ]]; then
  echo "ERROR: Frontend node_modules not found. Run 'npm install' inside frontend/ first." >&2
  exit 1
fi

# ── Detect Mac's LAN IP (try en0 → en1 → en2) ────────────────────────────────
WIFI_IP=""
for IFACE in en0 en1 en2; do
  WIFI_IP="$(ipconfig getifaddr "$IFACE" 2>/dev/null || true)"
  [[ -n "$WIFI_IP" ]] && break
done
if [[ -z "$WIFI_IP" ]]; then
  echo "ERROR: Could not detect Mac's Wi-Fi IP. Connect to Wi-Fi and try again." >&2
  exit 1
fi

WEB_ORIGIN="http://${WIFI_IP}:3000"
API_URL="http://${WIFI_IP}:8000"
WS_URL="ws://${WIFI_IP}:8000/ws"

# ── Automatically clear stale processes on ports 8000 & 3000 ─────────────────
for PORT in 8000 3000; do
  if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Freeing port $PORT from stale process..."
    lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t | xargs kill -9 2>/dev/null || true
    sleep 0.5
  fi
done

# ── Write .env.local so Next.js knows which backend URL to proxy ───────────────
ENV_FILE="$ROOT/frontend/.env.local"
mkdir -p "$(dirname "$ENV_FILE")"
TMP_ENV="$(mktemp)"
[[ -f "$ENV_FILE" ]] && grep -v '^NEXT_PUBLIC_JARVIS_API_URL=' "$ENV_FILE" >"$TMP_ENV" || true
printf 'NEXT_PUBLIC_JARVIS_API_URL=%s\n' "$API_URL" >>"$TMP_ENV"
mv "$TMP_ENV" "$ENV_FILE"

# ── Pre-build frontend for instant hydration (eliminates Turbopack dev lag) ──
echo "Building optimized frontend assets..."
(
  cd "$ROOT/frontend"
  export NEXT_PUBLIC_JARVIS_API_URL="$API_URL"
  ./node_modules/.bin/next build
)

# ── Cleanup handler ────────────────────────────────────────────────────────────
cleanup() {
  echo ""
  echo "Stopping JARVIS servers..."
  [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
  [[ -n "${BACKEND_PID:-}" ]]  && kill "$BACKEND_PID"  2>/dev/null || true
  [[ -n "${FRONTEND_PID:-}" ]] && wait "$FRONTEND_PID" 2>/dev/null || true
  [[ -n "${BACKEND_PID:-}" ]]  && wait "$BACKEND_PID"  2>/dev/null || true
  echo "Done."
}
trap cleanup INT TERM EXIT

# ── Start banner ──────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║           JARVIS 1B  —  MOBILE MODE                 ║"
echo "╠══════════════════════════════════════════════════════╣"
printf "║  Mac Wi-Fi IP   : %-34s ║\n" "$WIFI_IP"
printf "║  Mobile Browser : %-34s ║\n" "$WEB_ORIGIN"
printf "║  Local Mac Web  : %-34s ║\n" "http://localhost:3000"
printf "║  Backend API    : %-34s ║\n" "$API_URL"
printf "║  WebSocket URL  : %-34s ║\n" "$WS_URL"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  On phone: same Wi-Fi -> open Mobile Browser URL   ║"
echo "║  SSE + WebSockets stream tokens in real-time        ║"
echo "║  Press Ctrl+C here to stop all servers cleanly      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Start FastAPI backend (binds to 0.0.0.0:8000) ────────────────────────────
(
  cd "$ROOT/backend"
  export JARVIS_WEB_ORIGIN="$WEB_ORIGIN"
  exec .venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload
) &
BACKEND_PID=$!

# ── Start Next.js frontend in production mode (instant hydration on phones) ──
(
  cd "$ROOT/frontend"
  export NEXT_PUBLIC_JARVIS_API_URL="$API_URL"
  exec ./node_modules/.bin/next start --hostname 0.0.0.0 --port 3000
) &
FRONTEND_PID=$!

# ── Keep alive — exit if either server crashes ────────────────────────────────
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 2
done

echo "One of the JARVIS servers exited unexpectedly." >&2
exit 1
