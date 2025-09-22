"""
YAML-based agent configuration loader following Anthropic Claude Code CLI patterns.

This module implements the official Anthropic subagent configuration format:
https://docs.claude.com/en/docs/claude-code/sub-agents
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

import yaml

logger = logging.getLogger(__name__)


@dataclass
class AgentConfiguration:
    """Agent configuration following Anthropic's specification."""
    
    # Required fields from Anthropic docs
    name: str
    description: str
    
    # Optional fields with defaults
    tools: List[str] = field(default_factory=list)
    model: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.7
    max_tokens: int = 4096
    
    # System prompt and instructions
    system_prompt: Optional[str] = None
    instructions: Optional[str] = None
    
    # Security and access control
    allowed_paths: List[str] = field(default_factory=list)
    forbidden_paths: List[str] = field(default_factory=list)
    capabilities: Set[str] = field(default_factory=set)
    
    # Metadata
    version: str = "1.0.0"
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    @classmethod
    def from_yaml(cls, yaml_content: str) -> 'AgentConfiguration':
        """Parse agent configuration from YAML with frontmatter."""
        # Extract frontmatter and body following Anthropic pattern
        frontmatter, body = cls._parse_frontmatter(yaml_content)
        
        # Merge frontmatter and body configurations
        config = {}
        if frontmatter:
            config.update(frontmatter)
        
        # Parse body as additional configuration or instructions
        if body and body.strip():
            # Try to parse as YAML first
            try:
                body_config = yaml.safe_load(body)
                if isinstance(body_config, dict):
                    # Merge body config, frontmatter takes precedence
                    for key, value in body_config.items():
                        if key not in config:
                            config[key] = value
                elif isinstance(body_config, str):
                    # Treat as instructions if not already set
                    if 'instructions' not in config:
                        config['instructions'] = body_config
            except yaml.YAMLError:
                # Parse as markdown with sections
                body_sections = cls._parse_body_sections(body)

                # Extract system prompt and instructions from sections
                if 'system_prompt' not in config and 'system_prompt' in body_sections:
                    config['system_prompt'] = body_sections['system_prompt']

                if 'instructions' not in config and 'instructions' in body_sections:
                    config['instructions'] = body_sections['instructions']

                # If no specific sections found, treat entire body as instructions
                if 'instructions' not in config and not body_sections:
                    config['instructions'] = body.strip()
        
        # Validate required fields
        if 'name' not in config:
            raise ValueError("Agent configuration must include 'name' field")
        if 'description' not in config:
            raise ValueError("Agent configuration must include 'description' field")
        
        # Convert capabilities list to set
        if 'capabilities' in config and isinstance(config['capabilities'], list):
            config['capabilities'] = set(config['capabilities'])
        
        # Create configuration object
        return cls(**{k: v for k, v in config.items() if k in cls.__dataclass_fields__})
    
    @staticmethod
    def _parse_body_sections(body: str) -> Dict[str, str]:
        """Parse markdown sections from body content."""
        sections = {}

        # Split body into sections based on markdown headers
        lines = body.split('\n')
        current_section = None
        current_content = []

        for line in lines:
            # Check for markdown headers
            if line.strip().startswith('# System Prompt'):
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = 'system_prompt'
                current_content = []
            elif line.strip().startswith('# Instructions'):
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = 'instructions'
                current_content = []
            elif current_section:
                current_content.append(line)

        # Add the last section
        if current_section and current_content:
            sections[current_section] = '\n'.join(current_content).strip()

        return sections

    @staticmethod
    def _parse_frontmatter(content: str) -> tuple[Optional[Dict], str]:
        """Parse YAML frontmatter from content."""
        # Anthropic uses --- delimited frontmatter
        frontmatter_pattern = re.compile(r'^---\s*\n(.*?)\n---\s*(?:\n|$)', re.DOTALL)
        match = frontmatter_pattern.match(content)
        
        if match:
            frontmatter_text = match.group(1)
            body = content[match.end():]
            
            try:
                frontmatter = yaml.safe_load(frontmatter_text)
                return frontmatter, body
            except yaml.YAMLError as e:
                logger.error(f"Failed to parse frontmatter: {e}")
                return None, content
        
        # No frontmatter found, treat entire content as body
        return None, content
    
    def to_yaml(self) -> str:
        """Convert configuration to YAML format with frontmatter."""
        # Prepare frontmatter data
        frontmatter_data = {
            'name': self.name,
            'description': self.description,
            'model': self.model,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
        }
        
        if self.tools:
            frontmatter_data['tools'] = self.tools
        
        if self.allowed_paths:
            frontmatter_data['allowed_paths'] = self.allowed_paths
        
        if self.forbidden_paths:
            frontmatter_data['forbidden_paths'] = self.forbidden_paths
        
        if self.capabilities:
            frontmatter_data['capabilities'] = list(self.capabilities)
        
        if self.version != "1.0.0":
            frontmatter_data['version'] = self.version
        
        if self.author:
            frontmatter_data['author'] = self.author
        
        if self.tags:
            frontmatter_data['tags'] = self.tags
        
        # Generate YAML with frontmatter
        yaml_content = "---\n"
        yaml_content += yaml.safe_dump(frontmatter_data, default_flow_style=False)
        yaml_content += "---\n\n"
        
        # Add system prompt and instructions
        if self.system_prompt:
            yaml_content += f"# System Prompt\n\n{self.system_prompt}\n\n"
        
        if self.instructions:
            yaml_content += f"# Instructions\n\n{self.instructions}\n"
        
        return yaml_content
    
    def validate(self) -> List[str]:
        """Validate agent configuration and return list of issues."""
        issues = []
        
        # Check required fields
        if not self.name:
            issues.append("Agent name is required")
        
        if not self.description:
            issues.append("Agent description is required")
        
        # Validate model
        valid_models = [
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307"
        ]
        if self.model not in valid_models:
            issues.append(f"Invalid model: {self.model}")
        
        # Validate temperature
        if not 0 <= self.temperature <= 2:
            issues.append(f"Temperature must be between 0 and 2, got {self.temperature}")
        
        # Validate tools
        valid_tools = [
            "Read", "Write", "Edit", "MultiEdit", "NotebookEdit",
            "Bash", "WebSearch", "WebFetch", "Task",
            "Glob", "Grep", "TodoWrite", "BashOutput", "KillShell"
        ]
        for tool in self.tools:
            if tool not in valid_tools:
                issues.append(f"Unknown tool: {tool}")
        
        # Check path conflicts
        for allowed in self.allowed_paths:
            for forbidden in self.forbidden_paths:
                if Path(allowed).resolve() == Path(forbidden).resolve():
                    issues.append(f"Path conflict: {allowed} is both allowed and forbidden")
        
        return issues


class AgentConfigurationLoader:
    """Loads and manages agent configurations from .claude/agents/ directory."""
    
    def __init__(self, base_dir: Optional[str] = None):
        """Initialize loader with base directory."""
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        self.agents_dir = self.base_dir / ".claude" / "agents"
        self.configurations: Dict[str, AgentConfiguration] = {}
        
        # Also check .codexplus/agents for backward compatibility
        self.alt_agents_dir = self.base_dir / ".codexplus" / "agents"
    
    def load_all(self) -> Dict[str, AgentConfiguration]:
        """Load all agent configurations from directories."""
        self.configurations = {}
        
        # Load from .claude/agents (primary)
        if self.agents_dir.exists():
            self._load_from_directory(self.agents_dir)
        
        # Load from .codexplus/agents (fallback)
        if self.alt_agents_dir.exists():
            self._load_from_directory(self.alt_agents_dir)
        
        return self.configurations
    
    def _load_from_directory(self, directory: Path):
        """Load agent configurations from a directory."""
        # Load YAML files
        for yaml_file in directory.glob("*.yaml"):
            self._load_agent_file(yaml_file)

        for yml_file in directory.glob("*.yml"):
            self._load_agent_file(yml_file)

        # Load JSON files (backward compatibility)
        for json_file in directory.glob("*.json"):
            self._load_json_file(json_file)
    
    def _load_agent_file(self, file_path: Path):
        """Load a single agent configuration file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            config = AgentConfiguration.from_yaml(content)
            
            # Validate configuration
            issues = config.validate()
            if issues:
                logger.warning(f"Configuration issues in {file_path}: {issues}")
            
            # Use filename (without extension) as agent ID
            agent_id = file_path.stem
            self.configurations[agent_id] = config
            
            logger.info(f"Loaded agent configuration: {agent_id} from {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to load agent configuration from {file_path}: {e}")
    
    def _load_json_file(self, file_path: Path):
        """Load JSON configuration (backward compatibility)."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert JSON format to AgentConfiguration
            config = AgentConfiguration(
                name=data.get('name', file_path.stem),
                description=data.get('description', ''),
                tools=data.get('tools', []),
                model=data.get('model', 'claude-3-5-sonnet-20241022'),
                temperature=data.get('temperature', 0.7),
                max_tokens=data.get('max_tokens', 4096),
                system_prompt=data.get('system_prompt'),
                instructions=data.get('instructions'),
                allowed_paths=data.get('allowed_paths', []),
                forbidden_paths=data.get('forbidden_paths', []),
                capabilities=set(data.get('capabilities', [])),
                version=data.get('version', '1.0.0'),
                author=data.get('author'),
                tags=data.get('tags', [])
            )
            
            agent_id = file_path.stem
            self.configurations[agent_id] = config
            
            logger.info(f"Loaded JSON agent configuration: {agent_id}")
            
        except Exception as e:
            logger.error(f"Failed to load JSON configuration from {file_path}: {e}")
    
    def save_agent(self, agent_id: str, config: AgentConfiguration, format: str = 'yaml'):
        """Save agent configuration to file."""
        # Ensure directory exists
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        
        if format == 'yaml':
            file_path = self.agents_dir / f"{agent_id}.yaml"
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(config.to_yaml())
        else:
            file_path = self.agents_dir / f"{agent_id}.json"
            data = {
                'name': config.name,
                'description': config.description,
                'tools': config.tools,
                'model': config.model,
                'temperature': config.temperature,
                'max_tokens': config.max_tokens,
                'system_prompt': config.system_prompt,
                'instructions': config.instructions,
                'allowed_paths': config.allowed_paths,
                'forbidden_paths': config.forbidden_paths,
                'capabilities': list(config.capabilities),
                'version': config.version,
                'author': config.author,
                'tags': config.tags
            }
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        
        logger.info(f"Saved agent configuration: {agent_id} to {file_path}")
    
    def get_agent(self, agent_id: str) -> Optional[AgentConfiguration]:
        """Get agent configuration by ID."""
        return self.configurations.get(agent_id)
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """List all available agents with metadata."""
        return [
            {
                'id': agent_id,
                'name': config.name,
                'description': config.description,
                'tools': config.tools,
                'model': config.model,
                'tags': config.tags
            }
            for agent_id, config in self.configurations.items()
        ]
    
    def create_default_agents(self):
        """Create default agent configurations following Anthropic patterns."""
        default_agents = [
            AgentConfiguration(
                name="Code Reviewer",
                description="Specialized agent for code review and security analysis",
                tools=["Read", "Grep", "WebSearch"],
                model="claude-3-5-sonnet-20241022",
                temperature=0.3,
                system_prompt="""You are a specialized code review agent.
Focus on:
- Security vulnerabilities
- Performance issues
- Code quality and best practices
- Potential bugs
Provide actionable feedback with specific line references.""",
                capabilities={"code_analysis", "security_review"},
                tags=["review", "security", "quality"]
            ),
            
            AgentConfiguration(
                name="Test Runner",
                description="Executes tests and analyzes results",
                tools=["Read", "Bash", "BashOutput"],
                model="claude-3-5-sonnet-20241022",
                temperature=0.2,
                system_prompt="""You are a test execution specialist.
Your responsibilities:
- Run test suites
- Analyze test failures
- Generate test reports
- Suggest test improvements
Always validate test outputs and provide clear summaries.""",
                capabilities={"test_execution", "coverage_analysis"},
                tags=["testing", "validation", "ci"]
            ),
            
            AgentConfiguration(
                name="Documentation Writer",
                description="Creates and maintains project documentation",
                tools=["Read", "Write", "Edit", "WebSearch"],
                model="claude-3-5-sonnet-20241022",
                temperature=0.7,
                system_prompt="""You are a technical documentation specialist.
Focus on:
- Clear, concise explanations
- Code examples
- API documentation
- User guides
Follow the project's documentation standards.""",
                capabilities={"documentation", "technical_writing"},
                tags=["docs", "writing", "api"]
            ),
            
            AgentConfiguration(
                name="Debugger",
                description="Analyzes errors and traces issues",
                tools=["Read", "Grep", "Bash", "BashOutput"],
                model="claude-3-5-sonnet-20241022",
                temperature=0.3,
                system_prompt="""You are a debugging specialist.
Your approach:
- Systematic error analysis
- Stack trace interpretation
- Root cause identification
- Fix recommendations
Provide step-by-step debugging instructions.""",
                capabilities={"debugging", "error_analysis"},
                tags=["debug", "troubleshooting", "errors"]
            ),
            
            AgentConfiguration(
                name="Refactoring Agent",
                description="Improves code structure and design",
                tools=["Read", "Edit", "MultiEdit"],
                model="claude-3-5-sonnet-20241022",
                temperature=0.4,
                system_prompt="""You are a code refactoring specialist.
Principles:
- SOLID principles
- DRY (Don't Repeat Yourself)
- Clean code practices
- Performance optimization
Maintain functionality while improving structure.""",
                capabilities={"refactoring", "optimization"},
                tags=["refactor", "clean-code", "optimization"]
            )
        ]
        
        # Save default agents
        for i, config in enumerate(default_agents):
            agent_id = config.name.lower().replace(" ", "-")
            self.save_agent(agent_id, config)
        
        logger.info(f"Created {len(default_agents)} default agent configurations")


# Export classes
__all__ = [
    'AgentConfiguration',
    'AgentConfigurationLoader'
]