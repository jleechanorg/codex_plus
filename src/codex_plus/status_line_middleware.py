"""
Status line middleware for emitting git status information
"""
import asyncio
import sys as _sys
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class HookMiddleware:
    """Lightweight middleware to run hook-like side effects around responses.

    This integrates with the configurable hook system to emit status lines.
    """

    def __init__(self, hook_manager=None, enable_git_status: bool = True):
        self.hook_manager = hook_manager
        self.enable_git_status = enable_git_status

    async def get_status_line(self) -> Optional[str]:
        """Get status line content without printing it"""
        if not self.enable_git_status or not self.hook_manager:
            return None
        try:
            # Use the configurable hook system's run_status_line method
            result = await self.hook_manager.run_status_line()

            if result:
                logger.info("🎯 Git Status Line:")
                logger.info(f"   {result}")
                # Strip ANSI codes for HTTP header
                clean_result = re.sub(r'\x1b\[[0-9;]*m', '', result)
                return clean_result
            return None
        except Exception:
            # Best-effort only; never block or raise
            return None

    async def emit_status_line(self) -> None:
        """Legacy method - kept for compatibility"""
        result = await self.get_status_line()
        if result:
            print(f"\r{result}", file=_sys.stderr, flush=True)