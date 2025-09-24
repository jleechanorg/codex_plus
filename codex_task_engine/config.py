"""
codex_task_engine/config.py
Task Execution System - Agent Configuration
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from codex_task_engine.exceptions import AgentNotFoundError

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Simplified agent configuration for task engine."""

    # Core fields
    name: str
    description: str

    # Optional fields
    tools: List[str] = field(default_factory=list)
    model: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: Optional[int] = 30

    # Instructions
    system_prompt: Optional[str] = None
    instructions: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict) -> "AgentConfig":
        """Create config from dictionary."""
        field_names = set(cls.__dataclass_fields__.keys())  # type: ignore[attr-defined]
        filtered = {key: value for key, value in data.items() if key in field_names}
        return cls(**filtered)

    @classmethod
    def from_yaml_content(cls, content: str) -> "AgentConfig":
        """Parse configuration from YAML content with optional frontmatter."""
        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", content, re.DOTALL)

        if frontmatter_match:
            frontmatter_yaml = frontmatter_match.group(1)
            body = content[frontmatter_match.end() :]

            try:
                config = yaml.safe_load(frontmatter_yaml) or {}
            except yaml.YAMLError as exc:  # pragma: no cover - logged for diagnostics
                logger.error("Failed to parse YAML frontmatter in agent file: %s", exc)
                config = {}

            if body.strip() and "instructions" not in config:
                trimmed_body = body.strip()
                lowered = trimmed_body.lower()
                if lowered.startswith("# instructions"):
                    trimmed_body = trimmed_body.split("\n", 1)[1].strip() if "\n" in trimmed_body else ""
                elif lowered.startswith("# system prompt"):
                    # Skip system prompt header and preserve rest as instructions if present
                    trimmed_body = trimmed_body.split("\n", 1)[1].strip() if "\n" in trimmed_body else ""
                config["instructions"] = trimmed_body
        else:
            try:
                parsed = yaml.safe_load(content)
                config = parsed if isinstance(parsed, dict) else {}
            except yaml.YAMLError:
                config = {}

            if not config:
                config = {"instructions": content.strip()}

        if "name" not in config or not config["name"]:
            raise ValueError("Agent configuration must include a 'name'")
        if "description" not in config or not config["description"]:
            raise ValueError("Agent configuration must include a 'description'")

        return cls.from_dict(config)


class AgentConfigLoader:
    """Loads agent configurations from .claude/agents directory."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        self.agents_dir = self.base_dir / ".claude" / "agents"
        self._cache: Optional[Dict[str, AgentConfig]] = None

    def load_all(self) -> Dict[str, AgentConfig]:
        """Load all agent configurations from disk."""
        if self._cache is not None:
            return self._cache

        configs: Dict[str, AgentConfig] = {}

        if not self.agents_dir.exists():
            logger.warning("Agents directory not found: %s", self.agents_dir)
            self._cache = configs
            return configs

        for pattern in ("*.yaml", "*.yml", "*.md"):
            for file_path in self.agents_dir.glob(pattern):
                self._load_yaml_like_file(file_path, configs)

        for file_path in self.agents_dir.glob("*.json"):
            self._load_json_file(file_path, configs)

        logger.info("Loaded %d agent configurations", len(configs))
        self._cache = configs
        return configs

    def get_agent_config(self, name: str) -> AgentConfig:
        """Return the configuration for a specific agent."""
        configs = self.load_all()

        if name not in configs:
            available = ", ".join(sorted(configs.keys())) or "none"
            raise AgentNotFoundError(
                f"Agent '{name}' not found. Available agents: {available}"
            )

        return configs[name]

    async def load_agent_config(self, name: str) -> AgentConfig:
        """Async helper that delegates to the synchronous loader."""
        if self._cache is None:
            await asyncio.to_thread(self.load_all)
        return await asyncio.to_thread(self.get_agent_config, name)

    def _load_yaml_like_file(self, file_path: Path, configs: Dict[str, AgentConfig]) -> None:
        try:
            with file_path.open("r", encoding="utf-8") as handle:
                content = handle.read()

            config = AgentConfig.from_yaml_content(content)
            agent_id = file_path.stem
            configs[agent_id] = config
            logger.debug("Loaded YAML agent '%s' from %s", agent_id, file_path)
        except Exception as exc:  # pragma: no cover - logged for diagnostics
            logger.error("Failed to load agent file %s: %s", file_path, exc)

    def _load_json_file(self, file_path: Path, configs: Dict[str, AgentConfig]) -> None:
        try:
            with file_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)

            if "name" not in data or not data["name"]:
                data["name"] = file_path.stem
            if "description" not in data or not data["description"]:
                data["description"] = f"Agent generated from {file_path.name}"

            config = AgentConfig.from_dict(data)
            agent_id = file_path.stem
            configs[agent_id] = config
            logger.debug("Loaded JSON agent '%s' from %s", agent_id, file_path)
        except Exception as exc:  # pragma: no cover - logged for diagnostics
            logger.error("Failed to load agent JSON %s: %s", file_path, exc)
