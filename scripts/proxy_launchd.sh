#!/bin/bash
# Launchd-friendly proxy runner that keeps the uvicorn process in the foreground
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="$SCRIPT_DIR/venv"
DEFAULT_RUNTIME_DIR="${CODEX_PROXY_RUNTIME_DIR:-/tmp/codex_plus}"

mkdir -p "$DEFAULT_RUNTIME_DIR"
if [ ! -f "$DEFAULT_RUNTIME_DIR/proxy.log" ]; then
  touch "$DEFAULT_RUNTIME_DIR/proxy.log"
fi
if [ ! -f "$DEFAULT_RUNTIME_DIR/proxy.err" ]; then
  touch "$DEFAULT_RUNTIME_DIR/proxy.err"
fi

unset CODEX_PLUS_LOGGING_MODE
if [ -f "$DEFAULT_RUNTIME_DIR/launchd.env" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$DEFAULT_RUNTIME_DIR/launchd.env"
  set +a
fi

RUNTIME_DIR="${CODEX_PROXY_RUNTIME_DIR:-$DEFAULT_RUNTIME_DIR}"
PID_FILE="$RUNTIME_DIR/proxy.pid"
LOG_FILE="$RUNTIME_DIR/proxy.log"
ERROR_LOG_FILE="$RUNTIME_DIR/proxy.err"
LAUNCHD_ENV_FILE="$RUNTIME_DIR/launchd.env"

if [ "$RUNTIME_DIR" != "$DEFAULT_RUNTIME_DIR" ]; then
  mkdir -p "$RUNTIME_DIR"
  if [ ! -f "$LOG_FILE" ]; then
    touch "$LOG_FILE"
  fi
  if [ ! -f "$ERROR_LOG_FILE" ]; then
    touch "$ERROR_LOG_FILE"
  fi
fi
chmod 644 "$LOG_FILE" "$ERROR_LOG_FILE" 2>/dev/null || true

if [ ! -d "$VENV_PATH" ]; then
  echo "Virtualenv missing at $VENV_PATH" >&2
  exit 1
fi

cd "$SCRIPT_DIR"
# shellcheck disable=SC1091
source "$VENV_PATH/bin/activate"
EXTRA_PYTHONPATH="$SCRIPT_DIR/src"
if [ -n "${PYTHONPATH:-}" ]; then
  export PYTHONPATH="$EXTRA_PYTHONPATH:${PYTHONPATH}"
else
  export PYTHONPATH="$EXTRA_PYTHONPATH"
fi

echo $$ > "$PID_FILE"

exec python -c "
import sys, os
try:
    from codex_plus.main_sync_cffi import app
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=10000, log_level='info')
except Exception as e:
    print(f'STARTUP_ERROR: {e}', file=sys.stderr)
    sys.exit(1)
" >> "$LOG_FILE" 2>> "$ERROR_LOG_FILE"
