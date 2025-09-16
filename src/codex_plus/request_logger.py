"""
Request logging utilities for debugging and monitoring
"""
import json
import logging
import subprocess
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
            RequestLogger._log_payload_to_file(body)
        except Exception as e:
            logger.error(f"Failed to log request payload: {e}")

    @staticmethod
    def _log_payload_to_file(body: bytes) -> None:
        """Log payload to branch-specific directory"""
        # Get current git branch name
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            text=True,
            timeout=5  # Add timeout for security
        ).strip()

        # Validate branch name to prevent path traversal
        if not branch or ".." in branch or "/" in branch:
            branch = "unknown"

        payload = json.loads(body)
        logger.info(f"Parsed payload with keys: {list(payload.keys())}")

        # Create directory with branch name
        log_dir = Path(f"/tmp/codex_plus/{branch}")
        log_dir.mkdir(parents=True, exist_ok=True)

        # Write the full payload to see structure
        log_file = log_dir / "request_payload.json"
        log_file.write_text(json.dumps(payload, indent=2))

        logger.info(f"Logged full payload to {log_file}")

        # Also log just the instructions if available
        if "instructions" in payload:
            instructions_file = log_dir / "instructions.txt"
            instructions_file.write_text(payload["instructions"])
            logger.info(f"Logged instructions to {instructions_file}")