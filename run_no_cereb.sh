#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_HOST="127.0.0.1"
TARGET_PORT=10000
RUNTIME_DIR="/tmp/codex_plus"
FORWARD_PID_FILE="$RUNTIME_DIR/no_cereb_forward.pid"
FORWARD_LOG="$RUNTIME_DIR/no_cereb_forward.log"

mkdir -p "$RUNTIME_DIR"

# Allow caller override; default comes from ~/.bashrc export.
FORWARD_PORT="${CODEX_NO_CEREB_PORT:-11000}"

echo "🛠  Preparing Codex proxy without Cerebras on port ${FORWARD_PORT} (forwarding -> ${TARGET_PORT})."

# Clean up any existing forwarder
if [ -f "$FORWARD_PID_FILE" ]; then
  old_pid=$(cat "$FORWARD_PID_FILE" 2>/dev/null || true)
  if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
    echo "Stopping previous port-forwarder (PID $old_pid)."
    kill "$old_pid" 2>/dev/null || true
    sleep 1
  fi
  rm -f "$FORWARD_PID_FILE"
fi

# Ensure forward port is free before continuing
if lsof -i ":${FORWARD_PORT}" >/dev/null 2>&1; then
  echo "Port ${FORWARD_PORT} is already in use; unable to continue." >&2
  exit 1
fi

export OPENAI_BASE_URL="http://${DEFAULT_HOST}:${FORWARD_PORT}"

pushd "$SCRIPT_DIR" >/dev/null

./proxy.sh enable

# Wait for the primary proxy to be ready.
for _ in {1..15}; do
  if curl -fsS "http://${DEFAULT_HOST}:${TARGET_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS "http://${DEFAULT_HOST}:${TARGET_PORT}/health" >/dev/null 2>&1; then
  echo "Primary proxy on port ${TARGET_PORT} did not respond to health check." >&2
  exit 1
fi

echo "🚚 Primary proxy healthy; forwarding ${DEFAULT_HOST}:${FORWARD_PORT} -> ${TARGET_PORT}."

nohup python3 "$SCRIPT_DIR/scripts/port_forward.py" "$FORWARD_PORT" "$DEFAULT_HOST" "$TARGET_PORT" \
  >"$FORWARD_LOG" 2>&1 &
forward_pid=$!
echo "$forward_pid" > "$FORWARD_PID_FILE"

sleep 1

if ! kill -0 "$forward_pid" >/dev/null 2>&1; then
  echo "Failed to start port forwarder. Check $FORWARD_LOG for details." >&2
  exit 1
fi

if curl -fsS "http://${DEFAULT_HOST}:${FORWARD_PORT}/health" >/dev/null 2>&1; then
  echo "✅ Forward proxy health check succeeded on port ${FORWARD_PORT}."
else
  echo "⚠️  Forward proxy running but health check via port ${FORWARD_PORT} failed (this may happen before first request)." >&2
fi

echo "🎉 Codex proxy ready on http://${DEFAULT_HOST}:${FORWARD_PORT} (no Cerebras)."

popd >/dev/null
