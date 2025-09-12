#!/usr/bin/env bash
# Fast status line wrapper: calls project git-header with --status-only
set -euo pipefail
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  ROOT=$(git rev-parse --show-toplevel)
  # Base fast status (no context)
  if [ -f "$ROOT/.claude/hooks/git-header.sh" ]; then
    BASE_LINE=$(bash "$ROOT/.claude/hooks/git-header.sh" --status-only --no-context | sed -n '1p')
  else
    # Fallback minimal header
    REPO=$(basename "$ROOT")
    BR=$(git branch --show-current)
    UP=$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || echo 'no upstream')
    A=0; B=0
    if [ "$UP" != "no upstream" ]; then
      A=$(git rev-list --count "$UP"..HEAD 2>/dev/null || echo 0)
      B=$(git rev-list --count HEAD.."$UP" 2>/dev/null || echo 0)
    fi
    STATUS=""
    if [ "$UP" = "no upstream" ]; then STATUS=" (no remote)";
    elif [ "$A" -eq 0 ] && [ "$B" -eq 0 ]; then STATUS=" (synced)";
    elif [ "$A" -gt 0 ] && [ "$B" -eq 0 ]; then STATUS=" (ahead $A)";
    elif [ "$A" -eq 0 ] && [ "$B" -gt 0 ]; then STATUS=" (behind $B)";
    else STATUS=" (diverged +$A -$B)"; fi
    BASE_LINE="[Dir: $REPO | Local: $BR$STATUS | Remote: $UP | PR: none]"
  fi
  # Try quick PR lookup for current branch using gh (non-fatal)
  PR_SEG="none"
  if command -v gh >/dev/null 2>&1; then
    BRANCH=$(git branch --show-current)
    PR_LINE=$(gh pr list --head "$BRANCH" --json number,url 2>/dev/null | jq -r '.[0] | select(.) | "#\(.number) \(.url)"')
    if [ -n "$PR_LINE" ]; then PR_SEG="$PR_LINE"; fi
  fi
  # Replace PR: segment if present
  if printf '%s' "$BASE_LINE" | grep -q 'PR:'; then
    # Use awk to safely replace the PR segment between 'PR:' and closing bracket
    printf '%s\n' "$BASE_LINE" | awk -v rep="$PR_SEG" '
      BEGIN{OFS=""}
      {
        line=$0
        # find start of PR:
        pr=index(line, "PR: ")
        if (pr>0) {
          head=substr(line,1,pr+3)
          tail=substr(line,pr+4)
          # replace until next ] or end
          rbr=index(tail, "]")
          if (rbr>0) {
            after=substr(tail,rbr)
          } else { after="" }
          print head, " ", rep, after
        } else { print line }
      }
    '
  else
    printf '%s\n' "$BASE_LINE"
  fi
  exit 0
fi
echo "[Not in a git repo]"
