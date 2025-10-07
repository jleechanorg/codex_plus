#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHELL_RC_PATH="${CODEX_CEREB_SHELL_RC:-$HOME/.bashrc}"

if [[ -f "$SHELL_RC_PATH" ]]; then
  # shellcheck source=/dev/null
  source "$SHELL_RC_PATH"
fi

missing=()
for var in CEREBRAS_API_KEY CEREBRAS_BASE_URL CEREBRAS_MODEL; do
  if [[ -z "${!var:-}" ]]; then
    missing+=("$var")
  fi
done

if (( ${#missing[@]} )); then
  for name in "${missing[@]}"; do
    value=$(bash -ic "source \"$SHELL_RC_PATH\" >/dev/null 2>&1; python -c \"import os; print(os.environ.get('${name}',''))\"" 2>/dev/null || true)
    value="${value//$'\r'/}"
    value="${value//$'\n'/}"
    if [[ -n "$value" ]]; then
      export "$name"="$value"
    fi
  done
fi

missing=()
for var in CEREBRAS_API_KEY CEREBRAS_BASE_URL CEREBRAS_MODEL; do
  if [[ -z "${!var:-}" ]]; then
    missing+=("$var")
  fi
done

if (( ${#missing[@]} )); then
  echo "[codex_cereb] Missing environment variables: ${missing[*]}" >&2
  echo "Set them in $SHELL_RC_PATH or export manually before running." >&2
  exit 1
fi

DEFAULT_PORT="${CEREBRAS_PROXY_PORT:-10001}"
PASSTHROUGH_PORT="${CODEX_PASSTHROUGH_PORT:-10000}"
PASSTHROUGH_BASE="http://127.0.0.1:${PASSTHROUGH_PORT}"
export CODEX_PLUS_PROVIDER_MODE="cerebras"
export CODEX_PLUS_UPSTREAM_URL="${CEREBRAS_BASE_URL}"
export OPENAI_API_KEY="${CEREBRAS_API_KEY}"
export OPENAI_BASE_URL="${OPENAI_BASE_URL:-http://127.0.0.1:$DEFAULT_PORT}"
export OPENAI_MODEL="${CEREBRAS_MODEL}"

cleanup() {
  if [[ -n "${UVICORN_PID:-}" ]]; then
    kill "$UVICORN_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

ensure_passthrough_proxy() {
  pushd "$SCRIPT_DIR" >/dev/null
  ./proxy.sh restart >/dev/null
  popd >/dev/null
}

start_cerebras_proxy() {
  if ! lsof -i tcp:"$DEFAULT_PORT" >/dev/null 2>&1; then
    LOG_PATH="/tmp/codex_plus/proxy_${DEFAULT_PORT}.log"
    mkdir -p "$(dirname "$LOG_PATH")"
    pushd "$SCRIPT_DIR" >/dev/null
    nohup env \
      CODEX_PLUS_PROVIDER_MODE="cerebras" \
      CODEX_PLUS_UPSTREAM_URL="${CEREBRAS_BASE_URL}" \
      OPENAI_API_KEY="${CEREBRAS_API_KEY}" \
      OPENAI_BASE_URL="${CEREBRAS_BASE_URL}" \
      OPENAI_MODEL="${CEREBRAS_MODEL}" \
      python -m uvicorn src.codex_plus.main:app \
        --host 127.0.0.1 --port "$DEFAULT_PORT" \
        >"$LOG_PATH" 2>&1 &
    UVICORN_PID=$!
    popd >/dev/null
  fi
}

wait_for_health() {
  local url=$1
  local deadline=$((SECONDS + 45))
  while (( SECONDS < deadline )); do
    if curl -sf "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "[codex_cereb] Proxy health check failed at $url" >&2
  exit 1
}

ensure_passthrough_proxy
wait_for_health "${PASSTHROUGH_BASE}/health"
start_cerebras_proxy
wait_for_health "${OPENAI_BASE_URL}/health"

exec codex "$@"
