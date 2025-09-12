#!/usr/bin/env bash
# Fast status line wrapper: calls project git-header with --status-only
set -euo pipefail
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  ROOT=$(git rev-parse --show-toplevel)
  if [ -f "$ROOT/.claude/hooks/git-header.sh" ]; then
    bash "$ROOT/.claude/hooks/git-header.sh" --status-only
    exit 0
  fi
fi
echo "[Not in a git repo]"

