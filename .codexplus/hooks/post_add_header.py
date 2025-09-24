#!/usr/bin/env python3
"""
Hook Metadata:
name: add-header
type: post-output
priority: 50
enabled: true
"""

import logging

from codex_plus.hooks import Hook
from fastapi.responses import Response

logger = logging.getLogger(__name__)


class AddHeader(Hook):
    """Post-output hook that attaches an identifying header."""

    name = "add-header"

    async def post_output(self, response: Response) -> Response:
        """Attempt to append an identifying header to the response."""
        try:
            response.headers["X-Hooked"] = "1"
        except Exception as exc:  # pragma: no cover - best-effort logging
            logger.debug("Failed to add header to response: %s", exc)
        return response


hook = AddHeader(
    "add-header",
    {"type": "post-output", "priority": 50, "enabled": True},
)

