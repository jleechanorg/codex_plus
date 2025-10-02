"""
codex_task_engine/exceptions.py
Task Execution System - Exception Classes
"""


class TaskExecutionError(Exception):
    """Base exception for task execution errors"""
    pass


class AgentNotFoundError(TaskExecutionError):
    """Raised when specified agent type doesn't exist"""
    pass


class AgentConfigError(TaskExecutionError):
    """Raised when agent configuration is invalid"""
    pass


class TaskTimeoutError(TaskExecutionError):
    """Raised when agent execution times out"""
    pass


class APIError(TaskExecutionError):
    """Raised when API calls fail"""
    pass


class ToolAccessError(TaskExecutionError):
    """Raised when agent tries to access restricted tools"""
    pass
