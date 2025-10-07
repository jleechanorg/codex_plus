"""Utility helpers for inspecting Cerebras tool output follow-up requests.

These helpers are intentionally lightweight so they can run inside the proxy's
request path without introducing blocking network calls.  The logger mirrors
the structure we already use for capturing prompt payloads under
``/tmp/codex_plus/<branch>/`` but stores information in the
``/tmp/codex_plus/cereb_conversion`` directory that the oncall team monitors
when validating the Cerebras integration.

The helpers are designed to be safe to call from async contexts – all file
operations happen in a background executor via ``asyncio.to_thread`` – and the
payload is lightly redacted to avoid leaking bearer tokens.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, MutableMapping, Optional

logger = logging.getLogger(__name__)


LOG_DIR = Path("/tmp/codex_plus/cereb_conversion")
"""Location used for the Cerebras conversion debugging logs."""


@dataclass(slots=True)
class ToolOutputRecord:
    """Represents a structured log entry for a tool output submission."""

    path: str
    body: Mapping[str, object]
    headers: Mapping[str, str]

    def redact(self) -> "ToolOutputRecord":
        """Return a copy of the record with sensitive headers removed.

        The Codex CLI includes the same authentication cookie that the ChatGPT
        backend expects.  We do not want that value to end up on disk.  When we
        need to debug authentication issues we can rely on the proxy's main
        request logs instead.
        """

        safe_headers: MutableMapping[str, str] = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in {"cookie", "authorization"}
        }

        return ToolOutputRecord(path=self.path, body=self.body, headers=safe_headers)


async def ensure_log_dir() -> None:
    """Make sure the Cerebras debugging directory exists."""

    if LOG_DIR.exists():
        return

    def _mkdir() -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    await asyncio.to_thread(_mkdir)


async def _write_json(path: Path, data: Mapping[str, object]) -> None:
    """Write *data* to ``path`` using ``asyncio.to_thread``."""

    def _dump() -> None:
        with path.open("w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2, ensure_ascii=False)

    await asyncio.to_thread(_dump)


async def record_tool_outputs(
    *,
    path: str,
    body_bytes: Optional[bytes],
    headers: Mapping[str, str],
) -> Optional[Path]:
    """Persist a snapshot of a tool output follow-up request.

    Parameters
    ----------
    path:
        The request path, e.g. ``"responses/resp_123/tool_outputs"``.
    body_bytes:
        Raw request body, assumed to be JSON encoded.  ``None`` or invalid JSON
        payloads are ignored to avoid raising in the proxy hot-path.
    headers:
        The request headers used to redact authentication fields in the stored
        snapshot.

    Returns
    -------
    Path or ``None``
        The file path where the log entry was written.  ``None`` indicates we
        skipped logging because the payload could not be decoded.
    """

    if not body_bytes:
        logger.debug("Cerebras tool output record skipped: empty body")
        return None

    try:
        parsed = json.loads(body_bytes)
    except json.JSONDecodeError:
        logger.warning("Cerebras tool output record skipped: body not JSON")
        return None

    record = ToolOutputRecord(path=path, body=parsed, headers=dict(headers)).redact()

    await ensure_log_dir()

    log_file = LOG_DIR / f"tool_outputs_{os.getpid()}_{asyncio.get_running_loop().time():.0f}.json"
    await _write_json(log_file, {
        "path": record.path,
        "body": record.body,
        "headers": record.headers,
    })

    logger.info("🪵 Recorded Cerebras tool output follow-up to %s", log_file)
    return log_file

