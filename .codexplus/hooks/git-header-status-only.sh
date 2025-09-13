#!/usr/bin/env bash
# Standalone fast git header (status-only) with PR via gh (if available)
# No external script calls; designed to be fast and non-blocking.

set -euo pipefail

color_cyan='\033[1;36m'
color_reset='\033[0m'

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[Not in a git repo]"
  exit 0
fi

ROOT=$(git rev-parse --show-toplevel)
REPO=$(basename "$ROOT")
BR=$(git branch --show-current)
UP=$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || echo 'no upstream')

# Ahead/behind
A=0; B=0
if [ "$UP" != "no upstream" ]; then
  A=$(git rev-list --count "$UP"..HEAD 2>/dev/null || echo 0)
  B=$(git rev-list --count HEAD.."$UP" 2>/dev/null || echo 0)
fi

STATUS=""
if [ "$UP" = "no upstream" ]; then
  STATUS=" (no remote)"
elif [ "$A" -eq 0 ] && [ "$B" -eq 0 ]; then
  STATUS=" (synced)"
elif [ "$A" -gt 0 ] && [ "$B" -eq 0 ]; then
  STATUS=" (ahead $A)"
elif [ "$A" -eq 0 ] && [ "$B" -gt 0 ]; then
  STATUS=" (behind $B)"
else
  STATUS=" (diverged +$A -$B)"
fi

# PR lookup via gh (best-effort, quick) — avoid jq requirement by using gh --jq
PR_SEG="none"
if command -v gh >/dev/null 2>&1; then
  PR_LINE=$(gh pr list --head "$BR" --json number,url --jq '.[0] | select(.) | "#\(.number) \(.url)"' 2>/dev/null || echo "")
  if [ -n "$PR_LINE" ]; then PR_SEG="$PR_LINE"; fi
fi

# Print header (with minimal color if supported)
printf "%b[Dir: %s | Local: %s%s | Remote: %s | PR: %s]%b\n" \
  "$color_cyan" "$REPO" "$BR" "$STATUS" "$UP" "$PR_SEG" "$color_reset"

exit 0
