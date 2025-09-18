"""
Request logging utilities for debugging and monitoring
"""
import json
import logging
import asyncio
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
            loop = asyncio.get_event_loop()
            loop.create_task(RequestLogger._log_payload_to_file_async(body))
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

        payload = json.loads(body)
        logger.info(f"Parsed payload with keys: {list(payload.keys())}")

        # Create directory with branch name - async
        log_dir = Path(f"/tmp/codex_plus/{branch}")
        try:
            # Use asyncio for directory creation
            proc = await asyncio.create_subprocess_exec(
                "mkdir", "-p", str(log_dir),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await proc.wait()
        except Exception:
            pass  # Best effort logging

        # Write files asynchronously using async file operations
        try:
            # Write payload file
            log_file = log_dir / "request_payload.json"
            payload_content = json.dumps(payload, indent=2)
            proc = await asyncio.create_subprocess_exec(
                "tee", str(log_file),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await proc.communicate(input=payload_content.encode())
            logger.info(f"Logged full payload to {log_file}")

            # Also log instructions if available
            if "instructions" in payload:
                instructions_file = log_dir / "instructions.txt"
                proc = await asyncio.create_subprocess_exec(
                    "tee", str(instructions_file),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                await proc.communicate(input=payload["instructions"].encode())
                logger.info(f"Logged instructions to {instructions_file}")
        except Exception as e:
            logger.debug(f"Async file logging failed: {e}")
            # Fallback: best-effort logging without blocking
            pass