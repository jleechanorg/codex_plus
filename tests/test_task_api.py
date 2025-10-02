from __future__ import annotations

import asyncio
import textwrap
from pathlib import Path

import pytest

from codex_plus.task_api import AgentConfigLoader, Task, TaskExecutionEngine, TaskStatus


@pytest.fixture()
def agents_dir(tmp_path: Path) -> Path:
    agents_path = tmp_path / ".claude" / "agents"
    agents_path.mkdir(parents=True)
    return agents_path


def write_agent(agents_dir: Path, name: str, body: str) -> Path:
    path = agents_dir / f"{name}.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_agent_config_loader_parses_front_matter(agents_dir: Path) -> None:
    body = textwrap.dedent(
        """
        ---
        description: Expert code reviewer
        max_tokens: 1024
        temperature: 0.1
        timeout: 12
        metadata:
          domain: backend
        ---
        # Review instructions
        Analyze the following request:
        {prompt}
        """
    ).strip()
    write_agent(agents_dir, "code_reviewer", body)

    loader = AgentConfigLoader(agents_dir=agents_dir)
    config = loader.load_config("code_reviewer")

    assert config.name == "code_reviewer"
    assert config.description == "Expert code reviewer"
    assert config.max_tokens == 1024
    assert config.temperature == pytest.approx(0.1)
    assert config.timeout == pytest.approx(12.0)
    assert config.metadata == {"metadata": {"domain": "backend"}}


@pytest.mark.asyncio
async def test_execute_task_async_runs_runner(agents_dir: Path) -> None:
    write_agent(
        agents_dir,
        "echo",
        "Respond to the user: {prompt}",
    )

    async def runner(config, prompt, task_id):
        return f"agent={config.name}|prompt={prompt}|task_id={task_id}"

    engine = TaskExecutionEngine(config_loader=AgentConfigLoader(agents_dir=agents_dir), runner=runner)
    result = await engine.execute_task_async("echo", "hello world")

    assert result.status is TaskStatus.COMPLETED
    assert result.output.startswith("agent=echo|prompt=hello world|task_id=")
    assert result.is_successful()


@pytest.mark.asyncio
async def test_execute_task_async_validation_error(agents_dir: Path) -> None:
    engine = TaskExecutionEngine(config_loader=AgentConfigLoader(agents_dir=agents_dir))
    result = await engine.execute_task_async("", "")

    assert result.status is TaskStatus.FAILED
    assert "subagent_type" in (result.error or "")


@pytest.mark.asyncio
async def test_execute_task_async_missing_agent(agents_dir: Path) -> None:
    engine = TaskExecutionEngine(config_loader=AgentConfigLoader(agents_dir=agents_dir))
    result = await engine.execute_task_async("missing", "do something")

    assert result.status is TaskStatus.FAILED
    assert "missing" in (result.error or "")


@pytest.mark.asyncio
async def test_execute_task_external_runner(agents_dir: Path) -> None:
    write_agent(
        agents_dir,
        "echo-agent",
        textwrap.dedent(
            """\
            ---
            name: echo-agent
            description: Echo agent
            runner:
              command: python -c "import sys; print(sys.stdin.read())"
              prompt_in_stdin: true
            ---
            """
        ),
    )

    loader = AgentConfigLoader(agents_dir=agents_dir)
    engine = TaskExecutionEngine(config_loader=loader)

    prompt = "hello from task api"
    result = await engine.execute_task_async("echo-agent", prompt)

    assert result.status is TaskStatus.COMPLETED
    assert prompt in result.output
    assert result.error is None


def test_task_function_uses_global_engine(monkeypatch, agents_dir: Path) -> None:
    write_agent(agents_dir, "echo", "Return: {prompt}")
    engine = TaskExecutionEngine(config_loader=AgentConfigLoader(agents_dir=agents_dir))

    monkeypatch.setattr("codex_plus.task_api._engine", engine, raising=False)
    result = Task("echo", "task payload")
    assert result.status is TaskStatus.COMPLETED
    assert "task payload" in result.output


def test_task_called_with_running_loop_errors(monkeypatch, agents_dir: Path) -> None:
    write_agent(agents_dir, "echo", "Return: {prompt}")
    engine = TaskExecutionEngine(config_loader=AgentConfigLoader(agents_dir=agents_dir))

    async def call_task():
        monkeypatch.setattr("codex_plus.task_api._engine", engine, raising=False)
        with pytest.raises(RuntimeError):
            Task("echo", "payload")

    asyncio.run(call_task())
