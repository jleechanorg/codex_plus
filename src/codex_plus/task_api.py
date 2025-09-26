"""Task tool compatibility layer for Codex Plus.

This module introduces a lightweight Task API that mirrors the surface area of
Claude Code's Task tool without depending on the proprietary CLI. The goal is to
provide a clean integration point for future sub-agent orchestration while
remaining fully testable in this repository.

Key design points:
- No direct dependency on external CLIs or network calls. The default
  implementation renders the agent prompt locally and returns it so callers can
  decide how to execute the task.
- Configurations are discovered from ``.claude/agents`` with optional YAML
  front-matter, matching Claude's authoring format.
- Comprehensive result objects convey execution status, timing, metadata, and
  error information so downstream tooling can make informed decisions.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
import shutil
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from itertools import count
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution lifecycle states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskExecutionError(Exception):
    """Base exception for Task API failures."""

    def __init__(self, message: str, *, task_id: Optional[str] = None, subagent_type: Optional[str] = None) -> None:
        super().__init__(message)
        self.task_id = task_id
        self.subagent_type = subagent_type
        self.timestamp = datetime.now()


class SubagentNotFoundError(TaskExecutionError):
    """Raised when no agent configuration exists for the requested subagent."""


class ConfigurationError(TaskExecutionError):
    """Raised when an agent configuration file is malformed."""


class ExecutionTimeoutError(TaskExecutionError):
    """Raised when task execution exceeds the configured timeout."""


class ValidationError(TaskExecutionError):
    """Raised when task input arguments are invalid."""


@dataclass
class TaskResult:
    """Container describing the outcome of executing a task."""

    task_id: str
    subagent_type: str
    prompt: str
    description: Optional[str]
    status: TaskStatus
    output: str
    error: Optional[str] = None
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the result for downstream logging or transport."""

        return {
            "task_id": self.task_id,
            "subagent_type": self.subagent_type,
            "prompt": self.prompt,
            "description": self.description,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "config": self.config,
        }

    def is_successful(self) -> bool:
        """True when the task finished without errors."""

        return self.status == TaskStatus.COMPLETED and not self.error


@dataclass
class AgentConfig:
    """Agent configuration authored in ``.claude/agents``."""

    name: str
    description: str
    prompt_template: str
    max_tokens: int = 4000
    temperature: float = 0.7
    timeout: float = 60.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentConfigLoader:
    """Loads agent definitions from the workspace."""

    def __init__(self, agents_dir: Optional[Path] = None) -> None:
        self._agents_dir = agents_dir or self._discover_agents_dir()
        self._config_cache: Dict[str, AgentConfig] = {}
        self._cache_mtime: Dict[str, float] = {}

    def _discover_agents_dir(self) -> Path:
        cwd = Path.cwd()
        for candidate in [cwd, *cwd.parents]:
            agents_dir = candidate / ".claude" / "agents"
            if agents_dir.is_dir():
                return agents_dir
        # Default to the project-local directory even if it does not exist yet.
        return cwd / ".claude" / "agents"

    @property
    def agents_dir(self) -> Path:
        return self._agents_dir

    def list_available_agents(self) -> List[str]:
        if not self._agents_dir.is_dir():
            return []
        return sorted(file.stem for file in self._agents_dir.glob("*.md"))

    def load_config(self, agent_type: str) -> AgentConfig:
        config_path = self._agents_dir / f"{agent_type}.md"
        if not config_path.exists():
            raise SubagentNotFoundError(
                f"Agent configuration not found for '{agent_type}'",
                subagent_type=agent_type,
            )

        mtime = config_path.stat().st_mtime
        cached = self._config_cache.get(agent_type)
        if cached and self._cache_mtime.get(agent_type) == mtime:
            return cached

        try:
            content = config_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigurationError(
                f"Unable to read agent configuration '{agent_type}': {exc}",
                subagent_type=agent_type,
            ) from exc

        config = self._parse_content(agent_type, content)
        self._config_cache[agent_type] = config
        self._cache_mtime[agent_type] = mtime
        return config

    def _parse_content(self, agent_type: str, content: str) -> AgentConfig:
        metadata: Dict[str, Any] = {}
        prompt_template = content.strip()

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) == 3:
                from yaml import safe_load

                yaml_section = parts[1].strip()
                prompt_template = parts[2].strip()
                if yaml_section:
                    try:
                        loaded = safe_load(yaml_section) or {}
                    except Exception as exc:  # pragma: no cover - defensive
                        raise ConfigurationError(
                            f"Failed to parse YAML front matter for '{agent_type}': {exc}",
                            subagent_type=agent_type,
                        ) from exc
                    if not isinstance(loaded, dict):
                        raise ConfigurationError(
                            f"YAML front matter for '{agent_type}' must be a mapping",
                            subagent_type=agent_type,
                        )
                    metadata = loaded

        description = metadata.get("description") or self._derive_description(prompt_template)

        return AgentConfig(
            name=agent_type,
            description=description,
            prompt_template=prompt_template,
            max_tokens=int(metadata.get("max_tokens", 4000)),
            temperature=float(metadata.get("temperature", 0.7)),
            timeout=float(metadata.get("timeout", 60.0)),
            metadata={k: v for k, v in metadata.items() if k not in {"description", "max_tokens", "temperature", "timeout"}},
        )

    def _derive_description(self, prompt_template: str) -> str:
        for line in prompt_template.splitlines():
            candidate = line.strip()
            if candidate and not candidate.startswith("#"):
                return candidate
        return "Task agent"


RunnerType = Callable[[AgentConfig, str, str], Awaitable[str]]


async def _default_runner(config: AgentConfig, prompt: str, task_id: str) -> str:
    """Render the agent prompt locally.

    The default runner returns the rendered prompt so higher-level tooling can
    decide how to issue the request to an LLM or another execution backend.
    """

    rendered = config.prompt_template
    replacements = {
        "{prompt}": prompt,
        "{task_id}": task_id,
    }
    for token, value in replacements.items():
        rendered = rendered.replace(token, value)
    body = rendered if rendered.strip() else prompt
    metadata_lines = [
        "",
        "---",
        "Task Execution Metadata:",
        f"agent: {config.name}",
        f"task_id: {task_id}",
    ]
    rendered = body + "\n" + "\n".join(metadata_lines)

    command = _resolve_command(config)
    if command is not None:
        return await _run_command(command, rendered, config, task_id)

    return rendered


@dataclass
class RunnerCommand:
    """Represents an external command that can execute an agent."""

    argv: List[str]
    prompt_in_stdin: bool = False
    env: Optional[Dict[str, str]] = None


def _resolve_command(config: AgentConfig) -> Optional[RunnerCommand]:
    """Infer an execution command from config metadata or environment."""

    metadata = config.metadata or {}
    command_spec = metadata.get("runner") or metadata.get("runner_command")
    if isinstance(command_spec, str):
        return RunnerCommand(argv=shlex.split(command_spec))
    if isinstance(command_spec, dict):
        argv = command_spec.get("argv") or command_spec.get("command")
        if isinstance(argv, str):
            argv_list = shlex.split(argv)
        elif isinstance(argv, list):
            argv_list = [str(part) for part in argv]
        else:
            argv_list = []
        if argv_list:
            prompt_in_stdin = bool(command_spec.get("prompt_in_stdin"))
            env_override = command_spec.get("env")
            env = {k: str(v) for k, v in env_override.items()} if isinstance(env_override, dict) else None
            return RunnerCommand(argv=argv_list, prompt_in_stdin=prompt_in_stdin, env=env)

    codex_binary = shutil.which("codex")
    if codex_binary is None:
        return None

    argv = [codex_binary, "exec", "--yolo"]
    color = metadata.get("runner_color")
    if isinstance(color, str):
        argv.extend(["--color", color])
    return RunnerCommand(argv=argv)


async def _run_command(command: RunnerCommand, prompt: str, config: AgentConfig, task_id: str) -> str:
    """Execute the configured command and return its stdout."""

    env = os.environ.copy()
    if command.env:
        env.update(command.env)

    argv = list(command.argv)
    process: Optional[asyncio.subprocess.Process] = None
    try:
        if command.prompt_in_stdin:
            process = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await process.communicate(prompt.encode("utf-8"))
        else:
            process = await asyncio.create_subprocess_exec(
                *argv,
                prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await process.communicate()
    except FileNotFoundError as exc:
        raise ConfigurationError(
            f"Runner executable not found for agent '{config.name}': {exc}",
            subagent_type=config.name,
        ) from exc
    except asyncio.CancelledError:  # pragma: no cover - timeout cancellation
        if process is not None:
            process.kill()
            try:
                await process.communicate()
            except Exception:  # noqa: BLE001 - suppress secondary errors
                pass
        raise
    except Exception as exc:  # pragma: no cover - defensive guard
        raise TaskExecutionError(
            f"Failed to launch runner for agent '{config.name}': {exc}",
            task_id=task_id,
            subagent_type=config.name,
        ) from exc

    if process.returncode != 0:
        stderr_text = stderr.decode("utf-8", errors="replace")
        raise TaskExecutionError(
            f"Runner exited with code {process.returncode}: {stderr_text.strip()}",
            task_id=task_id,
            subagent_type=config.name,
        )

    return stdout.decode("utf-8", errors="replace")


class TaskExecutionEngine:
    """Coordinates agent configuration and execution."""

    def __init__(self, *, config_loader: Optional[AgentConfigLoader] = None, runner: Optional[RunnerType] = None) -> None:
        self.config_loader = config_loader or AgentConfigLoader()
        self._runner = runner or _default_runner
        self._task_counter = count(1)
        self._active_tasks: Dict[str, TaskResult] = {}

    def generate_task_id(self) -> str:
        return f"task_{int(time.time() * 1000)}_{next(self._task_counter)}"

    async def execute_task_async(self, subagent_type: str, prompt: str, description: Optional[str] = None) -> TaskResult:
        """Execute a task asynchronously and return a detailed result."""

        try:
            self._validate_inputs(subagent_type, prompt)
            agent_config = self.config_loader.load_config(subagent_type)
        except TaskExecutionError as exc:
            return TaskResult(
                task_id=self.generate_task_id(),
                subagent_type=subagent_type,
                prompt=prompt,
                description=description,
                status=TaskStatus.FAILED,
                output="",
                error=str(exc),
                metadata={"error_type": type(exc).__name__},
            )

        task_id = self.generate_task_id()
        start = time.perf_counter()
        result = TaskResult(
            task_id=task_id,
            subagent_type=subagent_type,
            prompt=prompt,
            description=description or agent_config.description,
            status=TaskStatus.RUNNING,
            output="",
            metadata={"runner": self._runner.__name__ if hasattr(self._runner, "__name__") else "custom"},
            config=asdict(agent_config),
        )
        self._active_tasks[task_id] = result

        try:
            timeout = max(agent_config.timeout, 0.1)
            output = await asyncio.wait_for(self._runner(agent_config, prompt, task_id), timeout=timeout)
        except asyncio.TimeoutError:
            error = ExecutionTimeoutError(
                f"Task '{task_id}' timed out after {timeout} seconds", task_id=task_id, subagent_type=subagent_type
            )
            logger.warning("Task timeout", extra={"task_id": task_id, "subagent_type": subagent_type})
            result.status = TaskStatus.FAILED
            result.error = str(error)
            result.metadata["error_type"] = type(error).__name__
        except TaskExecutionError as exc:
            logger.error("Task execution error", exc_info=exc)
            result.status = TaskStatus.FAILED
            result.error = str(exc)
            result.metadata["error_type"] = type(exc).__name__
        except Exception as exc:  # pragma: no cover - defensive guardrail
            logger.error("Unexpected task execution failure", exc_info=exc)
            result.status = TaskStatus.FAILED
            result.error = str(exc)
            result.metadata["error_type"] = type(exc).__name__
        else:
            result.status = TaskStatus.COMPLETED
            result.output = output
        finally:
            result.execution_time = time.perf_counter() - start
            self._active_tasks.pop(task_id, None)

        return result

    def _validate_inputs(self, subagent_type: str, prompt: str) -> None:
        if not subagent_type or not subagent_type.strip():
            raise ValidationError("subagent_type is required")
        if not prompt or not prompt.strip():
            raise ValidationError("prompt cannot be empty")
        if not subagent_type.replace("_", "").replace("-", "").isalnum():
            raise ValidationError(
                "subagent_type may only include alphanumeric characters, hyphens, and underscores"
            )

    def get_available_agents(self) -> List[str]:
        return self.config_loader.list_available_agents()

    def get_active_tasks(self) -> Dict[str, TaskResult]:
        return dict(self._active_tasks)


_engine: Optional[TaskExecutionEngine] = None


def get_engine() -> TaskExecutionEngine:
    global _engine
    if _engine is None:
        _engine = TaskExecutionEngine()
    return _engine


def Task(subagent_type: str, prompt: str, description: Optional[str] = None) -> TaskResult:  # noqa: N802 - API compatibility
    """Execute a task synchronously using the default engine."""

    engine = get_engine()
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(engine.execute_task_async(subagent_type, prompt, description))

    raise RuntimeError("Task() cannot be called from an active event loop; use await TaskExecutionEngine.execute_task_async")


def list_available_agents() -> List[str]:
    return get_engine().get_available_agents()


def get_task_status(task_id: str) -> Optional[TaskResult]:
    return get_engine().get_active_tasks().get(task_id)


def get_active_task_count() -> int:
    return len(get_engine().get_active_tasks())


__all__ = [
    "Task",
    "TaskResult",
    "TaskStatus",
    "TaskExecutionError",
    "SubagentNotFoundError",
    "ConfigurationError",
    "ExecutionTimeoutError",
    "ValidationError",
    "AgentConfig",
    "AgentConfigLoader",
    "TaskExecutionEngine",
    "list_available_agents",
    "get_task_status",
    "get_active_task_count",
]
