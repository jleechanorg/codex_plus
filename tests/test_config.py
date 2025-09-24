"""
Unit tests for the simplified agent configuration loader.
"""

import textwrap

import pytest

from codex_task_engine.config import AgentConfigLoader


def _write_agent_file(tmp_path, filename: str = "code_reviewer.yaml") -> None:
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    content = textwrap.dedent(
        """
        ---
        name: code-reviewer
        description: Reviews code for potential issues
        tools:
          - search
          - plan
        model: claude-3-5-sonnet-20241022
        temperature: 0.2
        max_tokens: 2048
        timeout: 25
        ---
        # Instructions

        Focus on security concerns and coding standards.
        """
    ).strip()
    (agents_dir / filename).write_text(content, encoding="utf-8")


def test_loader_discovers_yaml_agents(tmp_path):
    _write_agent_file(tmp_path)
    loader = AgentConfigLoader(base_dir=str(tmp_path))

    configs = loader.load_all()

    assert "code_reviewer" in configs
    config = configs["code_reviewer"]
    assert config.name == "code-reviewer"
    assert config.description.startswith("Reviews code")
    assert config.tools == ["search", "plan"]
    assert config.instructions.startswith("Focus on security")
    assert config.timeout == 25


@pytest.mark.asyncio
async def test_async_load_agent_config(tmp_path):
    _write_agent_file(tmp_path, filename="tester.yml")
    loader = AgentConfigLoader(base_dir=str(tmp_path))

    config = await loader.load_agent_config("tester")

    assert config.name == "code-reviewer"
    assert config.instructions is not None
