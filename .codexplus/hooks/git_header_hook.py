---
name: git-header
type: post-output
priority: 90
enabled: false
---
import os
import sys
import logging
import subprocess
from codex_plus.hooks import Hook

logger = logging.getLogger(__name__)

class GitHeaderHook(Hook):
    """Disabled; functionality moved to middleware to avoid direct scripts."""

    async def post_output(self, response):
        return response
