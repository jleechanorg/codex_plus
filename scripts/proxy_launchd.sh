#!/bin/bash
# Launchd-friendly proxy runner that keeps the uvicorn process in the foreground
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="$SCRIPT_DIR/venv"

if [ ! -d "$VENV_PATH" ]; then
  echo "Virtualenv missing at $VENV_PATH" >&2
  exit 1
fi

cd "$SCRIPT_DIR"
source "$VENV_PATH/bin/activate"
EXTRA_PYTHONPATH="$SCRIPT_DIR/src"
if [ -n "${PYTHONPATH:-}" ]; then
  export PYTHONPATH="$EXTRA_PYTHONPATH:$PYTHONPATH"
else
  export PYTHONPATH="$EXTRA_PYTHONPATH"
fi

exec python -c "
import sys
from codex_plus.main_sync_cffi import app
import uvicorn
uvicorn.run(app, host='127.0.0.1', port=10000, log_level='info')
"
