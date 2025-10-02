"""
Request logging utilities for debugging and monitoring
"""
import json
import logging
import asyncio
import inspect
import aiofiles
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class RequestLogger:
    """Handles request logging for debugging purposes"""

    @staticmethod
    def log_request_payload(body: bytes, path: str) -> None:
        """Log request payload for /responses endpoint"""
        if not body or path != "responses":
            return

        try:
            # Schedule async logging without blocking
            def _close_if_pending(coro) -> None:
                """Close coroutine if it wasn't scheduled/awaited (e.g., mocked loop)."""
                if inspect.iscoroutine(coro) and hasattr(coro, "close"):
                    try:
                        coro.close()
                    except RuntimeError:
                        # Coroutine already executed; nothing to clean up
                        pass

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running event loop, run the coroutine to completion
                coroutine = RequestLogger._log_payload_to_file_async(body)
                try:
                    asyncio.run(coroutine)
                finally:
                    _close_if_pending(coroutine)
            else:
                coroutine = RequestLogger._log_payload_to_file_async(body)
                try:
                    task = loop.create_task(coroutine)
                except Exception:
                    _close_if_pending(coroutine)
                    raise

                # When the event loop is mocked in tests, create_task may return a MagicMock or coroutine.
                if not isinstance(task, asyncio.Task):
                    _close_if_pending(coroutine)

                    # AsyncMock returns a coroutine object; close it so tests don't emit warnings.
                    if inspect.iscoroutine(task) and hasattr(task, "close"):
                        try:
                            task.close()
                        except RuntimeError:
                            pass
        except Exception as e:
            logger.error(f"Failed to log request payload: {e}")

    @staticmethod
    async def _log_payload_to_file_async(body: bytes) -> None:
        """Log payload to branch-specific directory asynchronously"""
        # Get current git branch name asynchronously
        communicate_coro = None
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "--abbrev-ref", "HEAD",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            communicate_coro = proc.communicate()
            stdout, _ = await asyncio.wait_for(communicate_coro, timeout=3.0)
            branch = stdout.decode().strip() if stdout else "unknown"
        except Exception:
            if inspect.iscoroutine(communicate_coro) and hasattr(communicate_coro, "close"):
                try:
                    communicate_coro.close()
                except RuntimeError:
                    pass
            branch = "unknown"

        # Validate branch name to prevent path traversal
        if not branch or ".." in branch or "/" in branch:
            branch = "unknown"

        # Parse JSON with specific error handling
        try:
            payload = json.loads(body)
            logger.info(f"Parsed payload with keys: {list(payload.keys())}")
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in request body: {e}")
            return
        except Exception as e:
            logger.error(f"Unexpected error parsing JSON: {e}")
            return

        # Create directory with branch name - async
        log_dir = Path(f"/tmp/codex_plus/{branch}")
        try:
            # Create directory asynchronously using asyncio.to_thread
            await asyncio.to_thread(log_dir.mkdir, parents=True, exist_ok=True)
        except Exception as e:
            logger.debug(f"Failed to create log directory: {e}")
            return  # Cannot proceed without directory

        # Write files asynchronously using aiofiles
        try:
            # Write payload file
            log_file = log_dir / "request_payload.json"
            payload_content = json.dumps(payload, indent=2)

            async with aiofiles.open(log_file, 'w') as f:
                await f.write(payload_content)
            logger.info(f"Logged full payload to {log_file}")

            # Also log instructions if available
            if "instructions" in payload and isinstance(payload["instructions"], str):
                instructions_file = log_dir / "instructions.txt"
                async with aiofiles.open(instructions_file, 'w') as f:
                    await f.write(payload["instructions"])
                logger.info(f"Logged instructions to {instructions_file}")
        except Exception as e:
            logger.debug(f"Async file logging failed: {e}")
            # Best effort logging - don't raise exceptions
