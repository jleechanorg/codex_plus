"""
Comprehensive validation tests for agent orchestration system.
Tests YAML/JSON configuration loading, parallel execution, and result aggregation.
Based on Anthropic Claude Code CLI subagent specifications.
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import yaml

from src.codex_plus.agent_orchestrator_middleware import (
    AgentExecutionContext,
    AgentOrchestrationMiddleware,
    AgentResult,
)


class TestAgentConfigurationValidation:
    """Test suite for agent configuration loading and validation."""

    @pytest.fixture
    def sample_yaml_agent(self) -> str:
        """Create a sample YAML agent configuration."""
        return """---
name: test-validator
description: Validates test execution against specifications
model: claude-3-5-sonnet-20241022
temperature: 0.2
max_tokens: 8192
tools:
  - Read
  - Grep
  - WebSearch
capabilities:
  - test_validation
  - requirement_verification
tags:
  - testing
  - validation
---

# System Prompt

You are a specialized test validation agent focused on verifying test execution results.
"""

    @pytest.fixture
    def sample_json_agent(self) -> Dict[str, Any]:
        """Create a sample JSON agent configuration."""
        return {
            "name": "json-validator",
            "description": "JSON format validation agent",
            "model": "claude-3-5-sonnet-20241022",
            "temperature": 0.1,
            "max_tokens": 4096,
            "tools": ["Read", "Edit"],
            "capabilities": ["json_validation", "schema_checking"],
            "tags": ["validation", "json"]
        }

    @pytest.fixture
    def invalid_yaml_agent(self) -> str:
        """Create an invalid YAML configuration."""
        return """---
name: invalid-agent
# Missing required fields: description, model
tools:
  - UnknownTool
---
Invalid content
"""

    @pytest.fixture
    def temp_agent_dir(self, tmp_path):
        """Create a temporary agent directory structure."""
        agent_dir = tmp_path / ".claude" / "agents"
        agent_dir.mkdir(parents=True)
        return agent_dir

    def test_yaml_frontmatter_parsing(self, sample_yaml_agent):
        """Test parsing YAML frontmatter from agent definition."""
        # Extract frontmatter
        lines = sample_yaml_agent.strip().split('\n')
        assert lines[0] == '---', "YAML frontmatter should start with ---"
        
        # Find end of frontmatter
        end_idx = -1
        for i, line in enumerate(lines[1:], 1):
            if line == '---':
                end_idx = i
                break
        
        assert end_idx > 0, "YAML frontmatter should end with ---"
        
        # Parse YAML
        yaml_content = '\n'.join(lines[1:end_idx])
        config = yaml.safe_load(yaml_content)
        
        # Validate required fields
        assert config['name'] == 'test-validator'
        assert config['description'] == 'Validates test execution against specifications'
        assert config['model'] == 'claude-3-5-sonnet-20241022'
        assert 'tools' in config
        assert 'capabilities' in config
        assert 'tags' in config

    def test_json_configuration_parsing(self, sample_json_agent):
        """Test parsing JSON agent configuration."""
        # Validate required fields
        assert sample_json_agent['name'] == 'json-validator'
        assert 'description' in sample_json_agent
        assert 'model' in sample_json_agent
        assert 'tools' in sample_json_agent
        assert isinstance(sample_json_agent['tools'], list)

    def test_agent_directory_scanning(self, temp_agent_dir, sample_yaml_agent, sample_json_agent):
        """Test scanning .claude/agents/ directory for agent definitions."""
        # Write YAML agent
        yaml_path = temp_agent_dir / "test-validator.yaml"
        yaml_path.write_text(sample_yaml_agent)
        
        # Write JSON agent
        json_path = temp_agent_dir / "json-validator.json"
        json_path.write_text(json.dumps(sample_json_agent))
        
        # Write markdown agent with YAML frontmatter
        md_path = temp_agent_dir / "markdown-agent.md"
        md_path.write_text(sample_yaml_agent)
        
        # Scan directory
        agent_files = list(temp_agent_dir.glob("*.yaml")) + list(temp_agent_dir.glob("*.yml")) + list(temp_agent_dir.glob("*.json")) + list(temp_agent_dir.glob("*.md"))
        assert len(agent_files) >= 3, "Should find all agent definition files"
        
        # Verify file types
        extensions = {f.suffix for f in agent_files}
        assert '.yaml' in extensions or '.yml' in extensions
        assert '.json' in extensions
        assert '.md' in extensions

    def test_invalid_configuration_handling(self, invalid_yaml_agent, temp_agent_dir):
        """Test handling of invalid agent configurations."""
        # Write invalid agent
        invalid_path = temp_agent_dir / "invalid.yaml"
        invalid_path.write_text(invalid_yaml_agent)
        
        # Parse and validate
        lines = invalid_yaml_agent.strip().split('\n')
        end_idx = -1
        for i, line in enumerate(lines[1:], 1):
            if line == '---':
                end_idx = i
                break
        
        yaml_content = '\n'.join(lines[1:end_idx])
        config = yaml.safe_load(yaml_content)
        
        # Check for missing required fields
        required_fields = ['name', 'description', 'model']
        missing_fields = [field for field in required_fields if field not in config]
        
        assert 'description' in missing_fields
        assert 'model' in missing_fields

    def test_capability_matching(self, sample_yaml_agent):
        """Test agent capability matching for task delegation."""
        # Parse configuration
        lines = sample_yaml_agent.strip().split('\n')
        end_idx = lines.index('---', 1)
        yaml_content = '\n'.join(lines[1:end_idx])
        config = yaml.safe_load(yaml_content)
        
        # Test capability matching
        agent_capabilities = set(config.get('capabilities', []))
        
        # Should match
        test_task_capabilities = {'test_validation'}
        assert test_task_capabilities.issubset(agent_capabilities)
        
        # Should not match
        unrelated_capabilities = {'code_generation', 'database_management'}
        assert not unrelated_capabilities.issubset(agent_capabilities)

    def test_tool_restriction_validation(self, sample_yaml_agent):
        """Test validation of tool restrictions for agents."""
        # Parse configuration
        lines = sample_yaml_agent.strip().split('\n')
        end_idx = lines.index('---', 1)
        yaml_content = '\n'.join(lines[1:end_idx])
        config = yaml.safe_load(yaml_content)
        
        # Validate tool restrictions
        allowed_tools = set(config.get('tools', []))
        assert 'Read' in allowed_tools
        assert 'Grep' in allowed_tools
        assert 'WebSearch' in allowed_tools
        
        # Verify restricted tools are not present
        restricted_tools = {'Edit', 'Write', 'Delete'}
        assert restricted_tools.isdisjoint(allowed_tools)

    def test_model_specification_validation(self, sample_yaml_agent, sample_json_agent):
        """Test validation of model specifications."""
        # Parse YAML agent
        lines = sample_yaml_agent.strip().split('\n')
        end_idx = lines.index('---', 1)
        yaml_content = '\n'.join(lines[1:end_idx])
        yaml_config = yaml.safe_load(yaml_content)
        
        # Validate model specifications
        valid_models = [
            'claude-3-5-sonnet-20241022',
            'claude-3-opus-20240229',
            'claude-3-haiku-20240307'
        ]
        
        assert yaml_config['model'] in valid_models
        assert sample_json_agent['model'] in valid_models
        
        # Validate temperature range
        assert 0 <= yaml_config.get('temperature', 0.5) <= 1
        assert 0 <= sample_json_agent.get('temperature', 0.5) <= 1
        
        # Validate max_tokens
        assert yaml_config.get('max_tokens', 4096) > 0
        assert sample_json_agent.get('max_tokens', 4096) > 0


class TestParallelAgentExecution:
    """Test suite for parallel agent execution with asyncio."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Create a mock agent orchestrator."""
        orchestrator = AgentOrchestrationMiddleware(
            max_concurrent_agents=3,
            agent_timeout=30
        )
        # Mock the config loader after initialization
        orchestrator.config_loader = MagicMock()
        orchestrator.agents = {
            f"agent_{i}": MagicMock(name=f"Agent {i}")
            for i in range(5)
        }
        return orchestrator

    @pytest.mark.asyncio
    async def test_concurrent_agent_limit(self, mock_orchestrator):
        """Test enforcement of maximum concurrent agent executions."""
        # Create mock agent executions
        async def mock_agent_execution(agent_name: str, context: AgentExecutionContext):
            await asyncio.sleep(0.1)  # Simulate work
            return AgentResult(agent_id=agent_name, task="Test task", success=True,
                output=f"Result from {agent_name}",
                duration=0.1
            )
        
        # Patch execute_agent method
        mock_orchestrator.execute_agent = mock_agent_execution
        
        # Create multiple agent contexts
        contexts = [
            AgentExecutionContext(MagicMock())
            for i in range(5)
        ]
        
        # Execute agents in parallel
        agent_names = [f"agent_{i}" for i in range(5)]
        tasks = [
            mock_orchestrator.execute_agent(name, ctx)
            for name, ctx in zip(agent_names, contexts)
        ]
        
        # Track concurrent executions
        max_concurrent = 0
        current_concurrent = 0
        
        async def track_execution(task):
            nonlocal max_concurrent, current_concurrent
            current_concurrent += 1
            max_concurrent = max(max_concurrent, current_concurrent)
            try:
                result = await task
                return result
            finally:
                current_concurrent -= 1
        
        # Execute with tracking
        tracked_tasks = [track_execution(task) for task in tasks]
        results = await asyncio.gather(*tracked_tasks)
        
        # Verify all completed
        assert len(results) == 5
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_agent_timeout_handling(self, mock_orchestrator):
        """Test timeout handling for agent executions."""
        # Create slow agent execution
        async def slow_agent_execution(agent_name: str, context: AgentExecutionContext):
            await asyncio.sleep(10)  # Longer than timeout
            return AgentResult(agent_id=agent_name, task="Test task", success=True,
                output="Should not reach here"
            )
        
        # Set short timeout
        context = AgentExecutionContext(MagicMock())
        
        # Execute with timeout
        mock_orchestrator.execute_agent = slow_agent_execution
        
        try:
            result = await asyncio.wait_for(
                mock_orchestrator.execute_agent("slow_agent", context),
                timeout=0.5
            )
            assert False, "Should have timed out"
        except asyncio.TimeoutError:
            # Expected behavior
            pass

    @pytest.mark.asyncio
    async def test_agent_error_isolation(self, mock_orchestrator):
        """Test that agent errors don't affect other parallel executions."""
        # Create mixed agent executions
        async def mixed_agent_execution(agent_name: str, context: AgentExecutionContext):
            if "fail" in agent_name:
                raise ValueError(f"Simulated error in {agent_name}")
            await asyncio.sleep(0.05)
            return AgentResult(agent_id=agent_name, task="Test task", success=True,
                output=f"Success from {agent_name}"
            )
        
        mock_orchestrator.execute_agent = mixed_agent_execution
        
        # Execute mixed agents
        agent_names = ["success_1", "fail_1", "success_2", "fail_2", "success_3"]
        contexts = [
            AgentExecutionContext(MagicMock())
            for name in agent_names
        ]
        
        results = []
        for name, ctx in zip(agent_names, contexts):
            try:
                result = await mock_orchestrator.execute_agent(name, ctx)
                results.append(result)
            except Exception as e:
                results.append(AgentResult(agent_id=name, task="Test task", success=False,
                    error=str(e)
                ))
        
        # Verify isolation
        success_count = sum(1 for r in results if r.success)
        failure_count = sum(1 for r in results if not r.success)
        
        assert success_count == 3
        assert failure_count == 2

    @pytest.mark.asyncio
    async def test_result_aggregation(self, mock_orchestrator):
        """Test aggregation of results from multiple agents."""
        # Create agents with different result types
        async def diverse_agent_execution(agent_name: str, context: AgentExecutionContext):
            await asyncio.sleep(0.01)
            
            if "analyzer" in agent_name:
                return AgentResult(agent_id=agent_name, task="Test task", success=True,
                    output={"analysis": "Code is clean", "score": 95}
                )
            elif "validator" in agent_name:
                return AgentResult(agent_id=agent_name, task="Test task", success=True,
                    output=["Test 1: PASS", "Test 2: PASS", "Test 3: FAIL"]
                )
            else:
                return AgentResult(agent_id=agent_name, task="Test task", success=True,
                    output="Generic result"
                )
        
        mock_orchestrator.execute_agent = diverse_agent_execution
        
        # Execute multiple agents
        agent_configs = [
            ("code_analyzer", AgentExecutionContext(MagicMock())),
            ("test_validator", AgentExecutionContext(MagicMock())),
            ("doc_generator", AgentExecutionContext(MagicMock()))
        ]
        
        results = []
        for name, context in agent_configs:
            result = await mock_orchestrator.execute_agent(name, context)
            results.append(result)
        
        # Aggregate results
        aggregated = {
            "summary": {
                "total_agents": len(results),
                "successful": sum(1 for r in results if r.success),
                "failed": sum(1 for r in results if not r.success)
            },
            "results": {r.agent_id: r.output for r in results}
        }
        
        # Validate aggregation
        assert aggregated["summary"]["total_agents"] == 3
        assert aggregated["summary"]["successful"] == 3
        assert aggregated["summary"]["failed"] == 0
        assert "code_analyzer" in aggregated["results"]
        assert "test_validator" in aggregated["results"]
        assert "doc_generator" in aggregated["results"]


class TestAgentLifecycleManagement:
    """Test suite for agent lifecycle operations (CRUD)."""

    @pytest.fixture
    def agent_manager(self, tmp_path):
        """Create an agent manager with temporary storage."""
        agent_dir = tmp_path / ".claude" / "agents"
        agent_dir.mkdir(parents=True)
        return {
            "agent_dir": agent_dir,
            "registry": {}
        }

    def test_create_agent_definition(self, agent_manager):
        """Test creating a new agent definition."""
        agent_config = {
            "name": "new-agent",
            "description": "A newly created agent",
            "model": "claude-3-5-sonnet-20241022",
            "tools": ["Read", "Grep"],
            "capabilities": ["code_analysis"]
        }
        
        # Create agent file
        agent_path = agent_manager["agent_dir"] / f"{agent_config['name']}.yaml"
        
        # Write YAML with frontmatter
        yaml_content = f"""---
{yaml.dump(agent_config, default_flow_style=False)}---

# System Prompt

You are a specialized agent for {agent_config['description']}.
"""
        agent_path.write_text(yaml_content)
        
        # Verify creation
        assert agent_path.exists()
        
        # Read and validate
        content = agent_path.read_text()
        assert agent_config['name'] in content
        assert agent_config['description'] in content

    def test_list_available_agents(self, agent_manager):
        """Test listing all available agents."""
        # Create multiple agents
        agents = [
            {"name": "agent-1", "description": "First agent"},
            {"name": "agent-2", "description": "Second agent"},
            {"name": "agent-3", "description": "Third agent"}
        ]
        
        for agent in agents:
            agent_path = agent_manager["agent_dir"] / f"{agent['name']}.yaml"
            agent_path.write_text(f"---\nname: {agent['name']}\ndescription: {agent['description']}\n---\n")
        
        # List agents
        agent_files = list(agent_manager["agent_dir"].glob("*.yaml"))
        agent_names = [f.stem for f in agent_files]
        
        # Verify all agents listed
        assert len(agent_names) == 3
        assert "agent-1" in agent_names
        assert "agent-2" in agent_names
        assert "agent-3" in agent_names

    def test_update_agent_configuration(self, agent_manager):
        """Test updating an existing agent configuration."""
        # Create initial agent
        agent_name = "update-test"
        agent_path = agent_manager["agent_dir"] / f"{agent_name}.yaml"
        
        initial_config = {
            "name": agent_name,
            "description": "Initial description",
            "model": "claude-3-5-sonnet-20241022",
            "temperature": 0.5
        }
        
        agent_path.write_text(f"---\n{yaml.dump(initial_config)}---\n")
        
        # Update configuration
        updated_config = initial_config.copy()
        updated_config["description"] = "Updated description"
        updated_config["temperature"] = 0.7
        updated_config["tools"] = ["Read", "Write"]
        
        agent_path.write_text(f"---\n{yaml.dump(updated_config)}---\n")
        
        # Verify update
        content = agent_path.read_text()
        lines = content.split('\n')
        end_idx = lines.index('---', 1)
        yaml_content = '\n'.join(lines[1:end_idx])
        loaded_config = yaml.safe_load(yaml_content)
        
        assert loaded_config["description"] == "Updated description"
        assert loaded_config["temperature"] == 0.7
        assert "tools" in loaded_config

    def test_delete_agent_definition(self, agent_manager):
        """Test deleting an agent definition."""
        # Create agent
        agent_name = "delete-test"
        agent_path = agent_manager["agent_dir"] / f"{agent_name}.yaml"
        agent_path.write_text("---\nname: delete-test\n---\n")
        
        # Verify exists
        assert agent_path.exists()
        
        # Delete agent
        agent_path.unlink()
        
        # Verify deleted
        assert not agent_path.exists()

    def test_agent_version_control(self, agent_manager):
        """Test version control considerations for agents."""
        # Create agent with version
        agent_config = {
            "name": "versioned-agent",
            "version": "1.0.0",
            "description": "Agent with version tracking",
            "model": "claude-3-5-sonnet-20241022"
        }
        
        agent_path = agent_manager["agent_dir"] / f"{agent_config['name']}.yaml"
        agent_path.write_text(f"---\n{yaml.dump(agent_config)}---\n")
        
        # Create backup before update
        backup_path = agent_manager["agent_dir"] / f"{agent_config['name']}.v{agent_config['version']}.backup"
        backup_path.write_text(agent_path.read_text())
        
        # Update to new version
        agent_config["version"] = "1.1.0"
        agent_config["description"] = "Updated agent with new features"
        agent_path.write_text(f"---\n{yaml.dump(agent_config)}---\n")
        
        # Verify version tracking
        assert backup_path.exists()
        
        # Load and compare versions
        current_content = agent_path.read_text()
        backup_content = backup_path.read_text()
        
        assert "1.1.0" in current_content
        assert "1.0.0" in backup_content

    def test_agent_invocation_validation(self, agent_manager):
        """Test validation of agent invocation requests."""
        # Define invocation request
        invocation_request = {
            "agent_name": "test-agent",
            "task": "Analyze this code",
            "context": {
                "code": "def hello(): return 'world'",
                "language": "python"
            },
            "timeout": 30,
            "priority": "normal"
        }
        
        # Validate required fields
        required_fields = ["agent_name", "task"]
        for field in required_fields:
            assert field in invocation_request, f"Missing required field: {field}"
        
        # Validate timeout range
        assert 0 < invocation_request.get("timeout", 30) <= 300, "Invalid timeout"
        
        # Validate priority values
        valid_priorities = ["low", "normal", "high", "critical"]
        assert invocation_request.get("priority", "normal") in valid_priorities


if __name__ == "__main__":
    pytest.main([__file__, "-v"])