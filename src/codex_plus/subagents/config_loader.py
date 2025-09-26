"""
Agent Configuration Loader

This module is kept for compatibility with existing imports.
The main implementation has been moved to task_api.py for better organization.
"""

from ..task_api import AgentConfigLoader, AgentConfig

__all__ = ['AgentConfigLoader', 'AgentConfig']