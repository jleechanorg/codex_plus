"""
Test suite for YAML-based agent configuration loader.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from src.codex_plus.subagents.config_loader import (
    AgentConfiguration,
    AgentConfigurationLoader
)


class TestAgentConfiguration:
    """Test AgentConfiguration class."""
    
    def test_from_yaml_with_frontmatter(self):
        """Test parsing YAML with frontmatter."""
        yaml_content = """---
name: Test Agent
description: A test agent for unit testing
tools:
  - Read
  - Write
model: claude-3-5-sonnet-20241022
temperature: 0.5
capabilities:
  - code_analysis
  - testing
---

# System Prompt

You are a specialized test agent.

# Instructions

Follow these instructions carefully.
"""
        config = AgentConfiguration.from_yaml(yaml_content)
        
        assert config.name == "Test Agent"
        assert config.description == "A test agent for unit testing"
        assert config.tools == ["Read", "Write"]
        assert config.model == "claude-3-5-sonnet-20241022"
        assert config.temperature == 0.5
        assert set(config.capabilities) == {"code_analysis", "testing"}
        assert "Follow these instructions" in config.instructions
    
    def test_from_yaml_without_frontmatter(self):
        """Test parsing YAML without frontmatter."""
        yaml_content = """
name: Simple Agent
description: A simple agent
tools:
  - Read
"""
        config = AgentConfiguration.from_yaml(yaml_content)
        
        assert config.name == "Simple Agent"
        assert config.description == "A simple agent"
        assert config.tools == ["Read"]
    
    def test_from_yaml_missing_required_fields(self):
        """Test that missing required fields raise ValueError."""
        yaml_content = """---
tools:
  - Read
---"""
        
        with pytest.raises(ValueError, match="must include 'name'"):
            AgentConfiguration.from_yaml(yaml_content)
    
    def test_to_yaml(self):
        """Test converting configuration to YAML."""
        config = AgentConfiguration(
            name="Export Agent",
            description="Test YAML export",
            tools=["Read", "Write"],
            temperature=0.8,
            capabilities={"testing"},
            system_prompt="You are a test agent.",
            instructions="Do testing tasks."
        )
        
        yaml_output = config.to_yaml()
        
        assert "name: Export Agent" in yaml_output
        assert "description: Test YAML export" in yaml_output
        assert "- Read" in yaml_output
        assert "- Write" in yaml_output
        assert "temperature: 0.8" in yaml_output
        assert "You are a test agent" in yaml_output
        assert "Do testing tasks" in yaml_output
    
    def test_validate_valid_config(self):
        """Test validation of valid configuration."""
        config = AgentConfiguration(
            name="Valid Agent",
            description="A valid agent",
            model="claude-3-5-sonnet-20241022",
            temperature=1.0,
            tools=["Read", "Write"]
        )
        
        issues = config.validate()
        assert len(issues) == 0
    
    def test_validate_invalid_model(self):
        """Test validation catches invalid model."""
        config = AgentConfiguration(
            name="Invalid Model Agent",
            description="Agent with invalid model",
            model="gpt-4"
        )
        
        issues = config.validate()
        assert any("Invalid model" in issue for issue in issues)
    
    def test_validate_invalid_temperature(self):
        """Test validation catches invalid temperature."""
        config = AgentConfiguration(
            name="Invalid Temp Agent",
            description="Agent with invalid temperature",
            temperature=3.0
        )
        
        issues = config.validate()
        assert any("Temperature must be between" in issue for issue in issues)
    
    def test_validate_unknown_tools(self):
        """Test validation catches unknown tools."""
        config = AgentConfiguration(
            name="Unknown Tool Agent",
            description="Agent with unknown tool",
            tools=["Read", "UnknownTool"]
        )
        
        issues = config.validate()
        assert any("Unknown tool: UnknownTool" in issue for issue in issues)
    
    def test_validate_path_conflicts(self, tmp_path):
        """Test validation catches path conflicts."""
        test_path = str(tmp_path / "test")
        
        config = AgentConfiguration(
            name="Path Conflict Agent",
            description="Agent with path conflicts",
            allowed_paths=[test_path],
            forbidden_paths=[test_path]
        )
        
        issues = config.validate()
        assert any("Path conflict" in issue for issue in issues)


class TestAgentConfigurationLoader:
    """Test AgentConfigurationLoader class."""
    
    @pytest.fixture
    def temp_base_dir(self):
        """Create temporary base directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def loader_with_agents(self, temp_base_dir):
        """Create loader with test agent configurations."""
        # Create .claude/agents directory
        agents_dir = temp_base_dir / ".claude" / "agents"
        agents_dir.mkdir(parents=True)
        
        # Create test agent YAML file
        agent_yaml = """---
name: Test Agent
description: A test agent
tools:
  - Read
  - Write
model: claude-3-5-sonnet-20241022
temperature: 0.7
---

# Instructions
This is a test agent.
"""
        (agents_dir / "test-agent.yaml").write_text(agent_yaml)
        
        # Create test agent JSON file (backward compatibility)
        agent_json = {
            "name": "JSON Agent",
            "description": "A JSON-based agent",
            "tools": ["Read"],
            "model": "claude-3-5-sonnet-20241022"
        }
        (agents_dir / "json-agent.json").write_text(json.dumps(agent_json))
        
        loader = AgentConfigurationLoader(base_dir=temp_base_dir)
        return loader
    
    def test_load_all(self, loader_with_agents):
        """Test loading all agent configurations."""
        configs = loader_with_agents.load_all()
        
        assert len(configs) == 2
        assert "test-agent" in configs
        assert "json-agent" in configs
        
        # Check YAML agent
        yaml_agent = configs["test-agent"]
        assert yaml_agent.name == "Test Agent"
        assert yaml_agent.tools == ["Read", "Write"]
        
        # Check JSON agent
        json_agent = configs["json-agent"]
        assert json_agent.name == "JSON Agent"
        assert json_agent.tools == ["Read"]
    
    def test_load_from_alt_directory(self, temp_base_dir):
        """Test loading from .codexplus/agents directory."""
        # Create .codexplus/agents directory
        alt_dir = temp_base_dir / ".codexplus" / "agents"
        alt_dir.mkdir(parents=True)
        
        # Create agent file
        agent_yaml = """---
name: Alt Agent
description: Agent from alt directory
---
"""
        (alt_dir / "alt-agent.yaml").write_text(agent_yaml)
        
        loader = AgentConfigurationLoader(base_dir=temp_base_dir)
        configs = loader.load_all()
        
        assert "alt-agent" in configs
        assert configs["alt-agent"].name == "Alt Agent"
    
    def test_save_agent_yaml(self, temp_base_dir):
        """Test saving agent configuration as YAML."""
        loader = AgentConfigurationLoader(base_dir=temp_base_dir)
        
        config = AgentConfiguration(
            name="Saved Agent",
            description="Test saving",
            tools=["Read"]
        )
        
        loader.save_agent("saved-agent", config, format='yaml')
        
        # Check file was created
        file_path = temp_base_dir / ".claude" / "agents" / "saved-agent.yaml"
        assert file_path.exists()
        
        # Load and verify
        loader.load_all()
        saved_config = loader.get_agent("saved-agent")
        assert saved_config.name == "Saved Agent"
    
    def test_save_agent_json(self, temp_base_dir):
        """Test saving agent configuration as JSON."""
        loader = AgentConfigurationLoader(base_dir=temp_base_dir)
        
        config = AgentConfiguration(
            name="JSON Save Agent",
            description="Test JSON saving",
            tools=["Write"]
        )
        
        loader.save_agent("json-save", config, format='json')
        
        # Check file was created
        file_path = temp_base_dir / ".claude" / "agents" / "json-save.json"
        assert file_path.exists()
        
        # Verify JSON content
        with open(file_path) as f:
            data = json.load(f)
            assert data["name"] == "JSON Save Agent"
            assert data["tools"] == ["Write"]
    
    def test_get_agent(self, loader_with_agents):
        """Test getting specific agent configuration."""
        loader_with_agents.load_all()
        
        agent = loader_with_agents.get_agent("test-agent")
        assert agent is not None
        assert agent.name == "Test Agent"
        
        # Non-existent agent
        missing = loader_with_agents.get_agent("missing")
        assert missing is None
    
    def test_list_agents(self, loader_with_agents):
        """Test listing all agents."""
        loader_with_agents.load_all()
        
        agents_list = loader_with_agents.list_agents()
        assert len(agents_list) == 2
        
        # Check structure
        for agent_info in agents_list:
            assert "id" in agent_info
            assert "name" in agent_info
            assert "description" in agent_info
            assert "tools" in agent_info
            assert "model" in agent_info
    
    def test_create_default_agents(self, temp_base_dir):
        """Test creating default agent configurations."""
        loader = AgentConfigurationLoader(base_dir=temp_base_dir)
        loader.create_default_agents()
        
        # Check files were created
        agents_dir = temp_base_dir / ".claude" / "agents"
        yaml_files = list(agents_dir.glob("*.yaml"))
        
        assert len(yaml_files) >= 5  # At least 5 default agents
        
        # Load and verify
        configs = loader.load_all()
        assert "code-reviewer" in configs
        assert "test-runner" in configs
        assert "documentation-writer" in configs
        assert "debugger" in configs
        assert "refactoring-agent" in configs
    
    def test_load_invalid_yaml(self, temp_base_dir):
        """Test handling of invalid YAML files."""
        agents_dir = temp_base_dir / ".claude" / "agents"
        agents_dir.mkdir(parents=True)
        
        # Create invalid YAML
        (agents_dir / "invalid.yaml").write_text("{{invalid yaml content")
        
        loader = AgentConfigurationLoader(base_dir=temp_base_dir)
        
        # Should handle error gracefully
        with patch('src.codex_plus.subagents.config_loader.logger') as mock_logger:
            configs = loader.load_all()
            assert "invalid" not in configs
            mock_logger.error.assert_called()
    
    def test_load_with_validation_issues(self, temp_base_dir):
        """Test loading configuration with validation issues."""
        agents_dir = temp_base_dir / ".claude" / "agents"
        agents_dir.mkdir(parents=True)
        
        # Create agent with invalid tool
        agent_yaml = """---
name: Invalid Tool Agent
description: Has invalid tool
tools:
  - Read
  - InvalidTool
---
"""
        (agents_dir / "invalid-tool.yaml").write_text(agent_yaml)
        
        loader = AgentConfigurationLoader(base_dir=temp_base_dir)
        
        with patch('src.codex_plus.subagents.config_loader.logger') as mock_logger:
            configs = loader.load_all()
            
            # Should still load but with warning
            assert "invalid-tool" in configs
            mock_logger.warning.assert_called()


class TestIntegration:
    """Integration tests for configuration system."""
    
    def test_full_workflow(self, tmp_path):
        """Test complete workflow of creating, saving, and loading agents."""
        loader = AgentConfigurationLoader(base_dir=tmp_path)
        
        # Create and save multiple agents
        agents = [
            AgentConfiguration(
                name=f"Agent {i}",
                description=f"Test agent {i}",
                tools=["Read", "Write"] if i % 2 == 0 else ["Bash"],
                temperature=0.5 + i * 0.1,
                capabilities={f"capability_{i}"}
            )
            for i in range(3)
        ]
        
        for i, config in enumerate(agents):
            loader.save_agent(f"agent-{i}", config)
        
        # Reload and verify
        new_loader = AgentConfigurationLoader(base_dir=tmp_path)
        configs = new_loader.load_all()
        
        assert len(configs) == 3
        
        for i in range(3):
            agent = configs[f"agent-{i}"]
            assert agent.name == f"Agent {i}"
            assert agent.description == f"Test agent {i}"
            assert agent.temperature == 0.5 + i * 0.1
    
    def test_mixed_formats(self, tmp_path):
        """Test loading mixed YAML and JSON formats."""
        loader = AgentConfigurationLoader(base_dir=tmp_path)
        
        # Save as YAML
        yaml_config = AgentConfiguration(
            name="YAML Agent",
            description="Saved as YAML",
            tools=["Read"]
        )
        loader.save_agent("yaml-agent", yaml_config, format='yaml')
        
        # Save as JSON
        json_config = AgentConfiguration(
            name="JSON Agent",
            description="Saved as JSON",
            tools=["Write"]
        )
        loader.save_agent("json-agent", json_config, format='json')
        
        # Load all
        configs = loader.load_all()
        
        assert len(configs) == 2
        assert configs["yaml-agent"].name == "YAML Agent"
        assert configs["json-agent"].name == "JSON Agent"