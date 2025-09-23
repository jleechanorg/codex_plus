"""
codex_task_engine/engine.py
Task Execution System - Core Engine
"""

import asyncio
import time
from typing import Dict, List, Optional
from dataclasses import dataclass

from .config import AgentConfigLoader
from .agent import SubagentInstance
from .exceptions import TaskExecutionError, AgentNotFoundError


@dataclass
class TaskResult:
    """Result of a task execution"""
    task_id: str
    content: str
    subagent_type: str
    success: bool
    tool_calls: Optional[List] = None
    execution_time: Optional[float] = None
    token_usage: Optional[Dict] = None
    error: Optional[str] = None


class TaskExecutionEngine:
    """Core engine for task execution with multi-agent coordination"""

    def __init__(self, max_concurrent: int = 10):
        """Initialize the task execution engine

        Args:
            max_concurrent: Maximum number of concurrent agent tasks
        """
        self.max_concurrent = max_concurrent
        self.active_tasks: Dict[str, SubagentInstance] = {}
        self.task_semaphore = asyncio.Semaphore(max_concurrent)
        self.config_loader = AgentConfigLoader()
        self.task_counter = 0

    def generate_task_id(self) -> str:
        """Generate unique task identifier"""
        self.task_counter += 1
        return f"task_{self.task_counter}_{int(time.time())}"

    async def execute_task(
        self,
        subagent_type: str,
        prompt: str,
        description: str = ""
    ) -> TaskResult:
        """Execute a single task using specified subagent type

        Args:
            subagent_type: Type of agent to use (e.g., 'code-review')
            prompt: Task prompt for the agent
            description: Optional task description

        Returns:
            TaskResult containing execution results

        Raises:
            TaskExecutionError: If task execution fails
            AgentNotFoundError: If specified agent type doesn't exist
        """
        start_time = time.time()
        task_id = self.generate_task_id()

        try:
            async with self.task_semaphore:
                # Load and validate agent configuration
                agent_config = await self.config_loader.load_agent_config(subagent_type)

                # Create isolated subagent instance
                subagent = SubagentInstance(
                    task_id=task_id,
                    config=agent_config,
                    prompt=prompt,
                    description=description
                )

                # Track active task
                self.active_tasks[task_id] = subagent

                try:
                    # Execute with timeout and error handling
                    result = await subagent.execute_with_timeout()

                    # Update execution time
                    result.execution_time = time.time() - start_time

                    return result

                finally:
                    # Cleanup
                    if task_id in self.active_tasks:
                        del self.active_tasks[task_id]

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Agent {subagent_type} failed: {str(e)}"

            return TaskResult(
                task_id=task_id,
                content="",
                subagent_type=subagent_type,
                success=False,
                execution_time=execution_time,
                error=error_msg
            )

    async def execute_parallel_tasks(
        self,
        tasks: List[Dict[str, str]]
    ) -> List[TaskResult]:
        """Execute multiple tasks in parallel

        Args:
            tasks: List of task specifications with subagent_type, prompt, description

        Returns:
            List of TaskResult objects
        """
        if not tasks:
            return []

        # Create task coroutines
        task_coroutines = [
            self.execute_task(
                subagent_type=task.get("subagent_type"),
                prompt=task.get("prompt", ""),
                description=task.get("description", "")
            )
            for task in tasks
        ]

        # Execute in parallel with error isolation
        results = await asyncio.gather(*task_coroutines, return_exceptions=True)

        # Convert exceptions to error results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_result = TaskResult(
                    task_id=f"parallel_error_{i}",
                    content=f"Task failed: {str(result)}",
                    subagent_type=tasks[i].get("subagent_type", "unknown"),
                    success=False,
                    error=str(result)
                )
                processed_results.append(error_result)
            else:
                processed_results.append(result)

        return processed_results

    def get_active_tasks(self) -> List[str]:
        """Get list of currently active task IDs"""
        return list(self.active_tasks.keys())

    def get_engine_status(self) -> Dict[str, any]:
        """Get current engine status and metrics"""
        return {
            "max_concurrent": self.max_concurrent,
            "active_tasks": len(self.active_tasks),
            "available_slots": self.max_concurrent - len(self.active_tasks),
            "task_counter": self.task_counter
        }


# Global task engine instance
_global_engine: Optional[TaskExecutionEngine] = None


def get_global_task_engine() -> TaskExecutionEngine:
    """Get or create the global task engine instance"""
    global _global_engine
    if _global_engine is None:
        _global_engine = TaskExecutionEngine()
    return _global_engine


async def Task(subagent_type: str, prompt: str, description: str = "") -> TaskResult:
    """Public Task function - identical interface to Claude Code

    Args:
        subagent_type: Type of agent to use (e.g., 'code-review')
        prompt: Task prompt for the agent
        description: Optional task description

    Returns:
        TaskResult containing execution results
    """
    engine = get_global_task_engine()
    return await engine.execute_task(subagent_type, prompt, description)
