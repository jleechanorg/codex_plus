"""
codex_task_engine/api_client.py
Task Execution System Component - Minimal model client abstraction.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class CompletionResult:
    """Represents the result of a model completion call."""

    content: str
    tool_calls: Optional[List[Dict]] = None
    execution_time: Optional[float] = None
    token_usage: Optional[Dict[str, int]] = None


class BaseModelClient:
    """Interface for model clients used by subagents."""

    def __init__(self, model: str) -> None:
        self.model = model

    async def complete(
        self,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
        tools: Optional[List[Dict]] = None,
        timeout: Optional[int] = None,
    ) -> CompletionResult:
        raise NotImplementedError

    async def complete_with_tool_results(
        self,
        previous: CompletionResult,
        tool_results: List[Dict],
    ) -> CompletionResult:
        raise NotImplementedError


class SimpleModelAPIClient(BaseModelClient):
    """Deterministic mock client that emulates LLM behaviour for tests."""

    async def complete(
        self,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
        tools: Optional[List[Dict]] = None,
        timeout: Optional[int] = None,
    ) -> CompletionResult:
        start = time.time()
        await asyncio.sleep(0)  # allow cooperative scheduling

        prompt_parts = [part for part in (system.strip(), user.strip()) if part]
        combined = "\n\n".join(prompt_parts) if prompt_parts else ""

        elapsed = time.time() - start
        token_usage = {
            "input_tokens": len(system.split()) + len(user.split()),
            "output_tokens": len(combined.split()),
        }

        return CompletionResult(
            content=combined,
            tool_calls=[],
            execution_time=elapsed,
            token_usage=token_usage,
        )

    async def complete_with_tool_results(
        self,
        previous: CompletionResult,
        tool_results: List[Dict],
    ) -> CompletionResult:
        await asyncio.sleep(0)
        extra_context = "\n\n".join(
            f"Tool {result.get('name', 'unknown')} responded: {result.get('output', '')}"
            for result in tool_results
        )

        merged_content = previous.content
        if extra_context:
            merged_content = f"{merged_content}\n\n{extra_context}".strip()

        return CompletionResult(
            content=merged_content,
            tool_calls=previous.tool_calls or [],
            execution_time=previous.execution_time,
            token_usage=previous.token_usage,
        )


class ModelAPIClientFactory:
    """Factory for creating model API clients."""

    @staticmethod
    def create(model: str) -> BaseModelClient:
        # In a real implementation this would route to different providers.
        return SimpleModelAPIClient(model=model)
