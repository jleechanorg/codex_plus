"""
Codex Plus - Enhanced Codex CLI with Task Execution Engine

Provides a Task() function that is 100% API compatible with Claude Code's Task tool,
along with comprehensive performance monitoring and baseline establishment.
"""

from .task_api import (
    Task,
    TaskResult,
    list_available_agents,
    get_performance_statistics,
    establish_performance_baseline,
    export_performance_metrics
)

__all__ = [
    "Task",
    "TaskResult",
    "list_available_agents",
    "get_performance_statistics",
    "establish_performance_baseline",
    "export_performance_metrics"
]
