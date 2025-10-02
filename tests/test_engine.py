"""Tests for the task execution engine and subagent runtime."""

import textwrap

import pytest

from codex_task_engine.config import AgentConfigLoader
from codex_task_engine.engine import TaskExecutionEngine


def _write_agent(tmp_path, name: str = "analysis_agent.yaml") -> None:
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    agents_dir.joinpath(name).write_text(
        textwrap.dedent(
            """
            ---
            name: analysis-agent
            description: Provides high level analysis
            model: claude-3-5-sonnet-20241022
            temperature: 0.1
            max_tokens: 1024
            tools: []
            ---
            # Instructions

            Summarise user intent before answering.
            """
        ).strip(),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_execute_task_returns_successful_result(tmp_path):
    _write_agent(tmp_path, name="analysis.yaml")
    loader = AgentConfigLoader(base_dir=str(tmp_path))
    engine = TaskExecutionEngine(config_loader=loader, max_concurrent=2)

    result = await engine.execute_task(
        subagent_type="analysis",
        prompt="Write a concise summary of the new feature.",
        description="Respond with bullet points only.",
    )

    assert result.success is True
    assert result.subagent_type == "analysis"
    # The mock client echoes system + user prompts
    assert result.content.endswith("Write a concise summary of the new feature.")
    assert result.execution_time is not None


@pytest.mark.asyncio
async def test_parallel_tasks_isolates_failures(tmp_path):
    _write_agent(tmp_path, name="first.yaml")
    _write_agent(tmp_path, name="second.yaml")

    loader = AgentConfigLoader(base_dir=str(tmp_path))
    engine = TaskExecutionEngine(config_loader=loader, max_concurrent=2)

    # Second task references a non-existent agent to trigger an error result.
    tasks = [
        {"subagent_type": "first", "prompt": "Task one"},
        {"subagent_type": "missing", "prompt": "Task two"},
    ]

    results = await engine.execute_parallel_tasks(tasks)

    assert len(results) == 2
    assert results[0].success is True
    assert results[1].success is False
    assert "missing" in (results[1].error or "")
