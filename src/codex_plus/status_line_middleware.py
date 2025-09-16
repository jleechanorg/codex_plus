"""
Status line middleware for emitting git status information
"""
import subprocess
import sys as _sys
import logging
import re

logger = logging.getLogger(__name__)


class HookMiddleware:
    """Lightweight middleware to run hook-like side effects around responses.

    This avoids invoking external scripts directly and computes any needed
    status lines using Python and standard git commands.
    """

    def __init__(self, enable_git_status: bool = True):
        self.enable_git_status = enable_git_status

    async def emit_status_line(self) -> None:
        if not self.enable_git_status:
            return
        try:
            # Use the configured git-header.sh script for statusline generation
            result = subprocess.check_output(
                [
                    "bash", "-c",
                    "if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then "
                    "ROOT=$(git rev-parse --show-toplevel); "
                    "[ -x \"$ROOT/.claude/hooks/git-header.sh\" ] && \"$ROOT/.claude/hooks/git-header.sh\" --status-only; "
                    "else echo \"Not in git repo\"; fi"
                ],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()

            if result:
                logger.info("🎯 Git Status Line:")
                logger.info(f"   {result}")
                # Write transient status line to terminal (strip ANSI codes for log)
                clean_result = re.sub(r'\x1b\[[0-9;]*m', '', result)
                print(f"\r{clean_result}", file=_sys.stderr, flush=True)
        except Exception:
            # Best-effort only; never block or raise
            pass