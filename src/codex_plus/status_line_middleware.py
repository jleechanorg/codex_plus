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
        self._cached_status_line = None
        self._cache_task = None
        self._cache_lock = asyncio.Lock()

    async def get_status_line(self, working_directory: Optional[str] = None) -> Optional[str]:
        """Get status line content without printing it"""
        if not self.enable_git_status or not self.hook_manager:
            return None
        try:
            # Use the configurable hook system's run_status_line method
            result = await self.hook_manager.run_status_line(working_directory)

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

    def get_cached_status_line(self) -> Optional[str]:
        """Get cached status line (non-blocking)"""
        return self._cached_status_line

    async def start_background_status_update(self):
        """Start background task to update status line cache"""
        if self._cache_task and not self._cache_task.done():
            return
        self._cache_task = asyncio.create_task(self._background_update_loop())
        logger.info("🔄 Started background status line update task")

    async def stop_background_status_update(self):
        """Stop background status updates and wait for clean shutdown."""
        if not self._cache_task:
            return
        if not self._cache_task.done():
            self._cache_task.cancel()
            try:
                await self._cache_task
            except asyncio.CancelledError:
                pass
        self._cache_task = None

    async def _background_update_loop(self):
        """Background loop to update status line cache every 30 seconds"""
        update_count = 0
        try:
            while True:
                try:
                    await self._update_status_cache()
                    update_count += 1
                    # Only log every 10 updates to reduce spam
                    if update_count % 10 == 0:
                        logger.info(f"📊 Background status line: {update_count} updates completed")
                    await asyncio.sleep(30)  # Update every 30 seconds (less frequent)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.debug(f"Background status update failed: {e}")
                    await asyncio.sleep(10)  # Retry after 10 seconds on error
        except asyncio.CancelledError:
            logger.debug("Background status line update loop cancelled")
            raise
        finally:
            logger.debug("Background status line update loop stopped")

    async def _update_status_cache(self):
        """Update the cached status line"""
        if not self.enable_git_status:
            return

        # If git status is enabled but no hook manager, set a basic fallback
        if not self.hook_manager:
            async with self._cache_lock:
                if self._cached_status_line is None:
                    self._cached_status_line = "[Dir: codex_plus | Local: current-branch | Remote: origin/branch | PR: unknown]"
            return

        async with self._cache_lock:
            try:
                # Use the configurable hook system's run_status_line method with timeout
                result = await asyncio.wait_for(
                    self.hook_manager.run_status_line(),
                    timeout=2.0
                )

                if result:
                    # Only log occasionally to reduce spam
                    logger.debug("🎯 Git Status Line updated in background")
                    # Strip ANSI codes for HTTP header
                    clean_result = re.sub(r'\x1b\[[0-9;]*m', '', result)
                    self._cached_status_line = clean_result
                else:
                    self._cached_status_line = "[Dir: codex_plus | Local: current-branch | Remote: origin/branch | PR: unknown]"
            except Exception as e:
                logger.debug(f"Status line update failed: {e}")
                # Keep existing cache or set fallback
                if self._cached_status_line is None:
                    self._cached_status_line = "[Dir: codex_plus | Local: current-branch | Remote: origin/branch | PR: unknown]"

    async def emit_status_line(self) -> None:
        """Legacy method - kept for compatibility"""
        result = await self.get_status_line()
        if result:
            print(f"\r{result}", file=_sys.stderr, flush=True)
