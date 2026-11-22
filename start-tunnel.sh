#!/usr/bin/env bash
# start-tunnel.sh — Starts Cloudflare Quick Tunnel for remote access to JARVIS

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

SERVER_PID=""
# Check if backend is already listening on port 8000
if ! curl -sf http://localhost:8000/health >/dev/null 2>&1; then
  echo "Backend not detected on port 8000. Starting JARVIS servers..."
  ./start-mobile.sh &
  SERVER_PID=$!
  # Wait for backend to be ready
  for i in {1..30}; do
    if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
else
  echo "JARVIS backend already running on port 8000."
fi

echo "Starting Cloudflare HTTPS Tunnel..."
LOG_FILE=$(mktemp)
cloudflared tunnel --url http://localhost:8000 > "$LOG_FILE" 2>&1 &
TUNNEL_PID=$!

# Wait until trycloudflare URL appears
TUNNEL_URL=""
for i in {1..30}; do
  TUNNEL_URL=$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$LOG_FILE" | head -n 1)
  if [ -n "$TUNNEL_URL" ]; then
    break
  fi
  sleep 1
done

if [ -z "$TUNNEL_URL" ]; then
  echo "Error: Failed to obtain Cloudflare tunnel URL." >&2
  cat "$LOG_FILE" >&2
  kill "$TUNNEL_PID" 2>/dev/null || true
  [[ -n "$SERVER_PID" ]] && kill "$SERVER_PID" 2>/dev/null || true
  rm -f "$LOG_FILE"
  exit 1
fi

FULL_LINK="https://propirate99.github.io/Jarvis/?api=$TUNNEL_URL"

echo ""
echo "========================================================"
echo "JARVIS Live Mobile Link:"
echo "$FULL_LINK"
echo "========================================================"
echo ""
echo "Tip: Open this link on your phone (or any remote browser)."
echo "Press Ctrl+C to terminate the tunnel."

# Clean up processes on Ctrl+C or script termination
cleanup() {
  echo ""
  echo "Stopping Cloudflare tunnel..."
  kill "$TUNNEL_PID" 2>/dev/null || true
  if [ -n "$SERVER_PID" ]; then
    echo "Stopping server process ($SERVER_PID)..."
    kill "$SERVER_PID" 2>/dev/null || true
  fi
  rm -f "$LOG_FILE"
  echo "Done."
  exit 0
}

trap cleanup INT TERM EXIT
wait "$TUNNEL_PID"

