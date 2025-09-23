"""
codex_task_engine/agent.py
Task Execution System Component - Subagent runtime wrapper.
"""

import asyncio
from typing import Optional

from .api_client import CompletionResult, ModelAPIClientFactory
from .config import AgentConfig
from .exceptions import TaskTimeoutError
from .models import TaskResult


class SubagentInstance:
    """Isolated execution environment for a single agent invocation."""

    def __init__(
        self,
        task_id: str,
        config: AgentConfig,
        prompt: str,
        description: str = "",
        invocation_name: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        self.task_id = task_id
        self.config = config
        self.prompt = prompt
        self.description = description
        self.invocation_name = invocation_name or config.name
        self.timeout = timeout if timeout is not None else config.timeout or 30
        self.api_client = ModelAPIClientFactory.create(config.model)

    async def execute_with_timeout(self) -> TaskResult:
        """Execute the agent workflow with timeout protection."""
        try:
            return await asyncio.wait_for(self.execute(), timeout=self.timeout)
        except asyncio.TimeoutError as exc:
            raise TaskTimeoutError(
                f"Agent {self.config.name} timed out after {self.timeout}s"
            ) from exc

    async def execute(self) -> TaskResult:
        """Execute the agent and return a TaskResult."""
        system_prompt = self.build_system_prompt()

        completion: CompletionResult = await self.api_client.complete(
            system=system_prompt,
            user=self.prompt,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            tools=[{"name": tool} for tool in self.config.tools],
            timeout=self.timeout,
        )

        return TaskResult(
            task_id=self.task_id,
            content=completion.content,
            subagent_type=self.invocation_name,
            success=True,
            tool_calls=completion.tool_calls,
            execution_time=completion.execution_time,
            token_usage=completion.token_usage,
        )

    def build_system_prompt(self) -> str:
        """Assemble the final system prompt for the agent invocation."""
        segments = []
        if self.config.system_prompt:
            segments.append(self.config.system_prompt.strip())
        if self.config.instructions:
            segments.append(self.config.instructions.strip())
        if self.description:
            segments.append(self.description.strip())
        return "\n\n".join(segment for segment in segments if segment)
