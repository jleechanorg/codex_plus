"""Shared dataclasses for the Codex task execution system."""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class TaskResult:
    """Container for results produced by subagent task execution."""

    task_id: str
    content: str
    subagent_type: str
    success: bool
    tool_calls: Optional[List[Dict]] = None
    execution_time: Optional[float] = None
    token_usage: Optional[Dict[str, int]] = None
    error: Optional[str] = None
