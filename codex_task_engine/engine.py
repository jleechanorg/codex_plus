"""
codex_task_engine/engine.py
Task Execution System - Core Engine
"""

import asyncio
import time
from typing import Dict, List, Optional

from .config import AgentConfigLoader
from .agent import SubagentInstance
from .exceptions import TaskExecutionError
from .models import TaskResult


class TaskExecutionEngine:
    """Core engine for task execution with multi-agent coordination."""

    def __init__(
        self,
        max_concurrent: int = 10,
        config_loader: Optional[AgentConfigLoader] = None,
    ) -> None:
        """Initialize the task execution engine.

        Args:
            max_concurrent: Maximum number of concurrent agent tasks
            config_loader: Optional pre-configured loader for agent settings
        """
        self.max_concurrent = max_concurrent
        self.active_tasks: Dict[str, SubagentInstance] = {}
        self.task_semaphore = asyncio.Semaphore(max_concurrent)
        self.config_loader = config_loader or AgentConfigLoader()
        self.task_counter = 0

    def generate_task_id(self) -> str:
        """Generate a unique task identifier."""
        self.task_counter += 1
        return f"task_{self.task_counter}_{int(time.time())}"

    async def execute_task(
        self,
        subagent_type: str,
        prompt: str,
        description: str = "",
    ) -> TaskResult:
        """Execute a single task using the specified subagent type."""
        start_time = time.time()
        task_id = self.generate_task_id()

        try:
            async with self.task_semaphore:
                agent_config = await self.config_loader.load_agent_config(subagent_type)

                subagent = SubagentInstance(
                    task_id=task_id,
                    config=agent_config,
                    prompt=prompt,
                    description=description,
                    invocation_name=subagent_type,
                )

                self.active_tasks[task_id] = subagent

                try:
                    result = await subagent.execute_with_timeout()
                    result.execution_time = time.time() - start_time
                    return result
                finally:
                    self.active_tasks.pop(task_id, None)

        except Exception as exc:  # pragma: no cover - defensive catch
            execution_time = time.time() - start_time
            error_msg = f"Agent {subagent_type} failed: {exc}"

            return TaskResult(
                task_id=task_id,
                content="",
                subagent_type=subagent_type,
                success=False,
                execution_time=execution_time,
                error=error_msg,
            )

    async def execute_parallel_tasks(self, tasks: List[Dict[str, str]]) -> List[TaskResult]:
        """Execute multiple tasks in parallel."""
        if not tasks:
            return []

        coroutines = [
            self.execute_task(
                subagent_type=task.get("subagent_type", ""),
                prompt=task.get("prompt", ""),
                description=task.get("description", ""),
            )
            for task in tasks
        ]

        results = await asyncio.gather(*coroutines, return_exceptions=True)

        processed: List[TaskResult] = []
        for index, result in enumerate(results):
            if isinstance(result, TaskExecutionError):
                processed.append(
                    TaskResult(
                        task_id=f"parallel_error_{index}",
                        content=f"Task failed: {result}",
                        subagent_type=tasks[index].get("subagent_type", "unknown"),
                        success=False,
                        error=str(result),
                    )
                )
            elif isinstance(result, Exception):  # pragma: no cover - unexpected
                processed.append(
                    TaskResult(
                        task_id=f"parallel_error_{index}",
                        content=f"Task failed: {result}",
                        subagent_type=tasks[index].get("subagent_type", "unknown"),
                        success=False,
                        error=str(result),
                    )
                )
            else:
                processed.append(result)

        return processed

    def get_active_tasks(self) -> List[str]:
        """Return the list of currently active task IDs."""
        return list(self.active_tasks.keys())

    def get_engine_status(self) -> Dict[str, int]:
        """Return basic engine status metrics."""
        active_count = len(self.active_tasks)
        return {
            "max_concurrent": self.max_concurrent,
            "active_tasks": active_count,
            "available_slots": self.max_concurrent - active_count,
            "task_counter": self.task_counter,
        }


_global_engine: Optional[TaskExecutionEngine] = None


def get_global_task_engine() -> TaskExecutionEngine:
    """Return the global task engine instance, creating it if needed."""
    global _global_engine
    if _global_engine is None:
        _global_engine = TaskExecutionEngine()
    return _global_engine


async def Task(subagent_type: str, prompt: str, description: str = "") -> TaskResult:
    """Public helper mirroring Claude Code's Task helper."""
    engine = get_global_task_engine()
    return await engine.execute_task(subagent_type, prompt, description)
