"""
Request logging utilities for debugging and monitoring
"""
import json
import logging
import asyncio
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
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(RequestLogger._log_payload_to_file_async(body))
            except RuntimeError:
                # No running event loop, run the coroutine to completion
                asyncio.run(RequestLogger._log_payload_to_file_async(body))
        except Exception as e:
            logger.error(f"Failed to log request payload: {e}")

    @staticmethod
    async def _log_payload_to_file_async(body: bytes) -> None:
        """Log payload to branch-specific directory asynchronously"""
        # Get current git branch name asynchronously
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "--abbrev-ref", "HEAD",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=3.0)
            branch = stdout.decode().strip() if stdout else "unknown"
        except Exception:
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
