"""
Tests for the Codex Plus Subagent System.
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.codex_plus.subagents import (
    AgentCapability,
    AgentContext,
    AgentResult,
    AgentStatus,
    SubAgent,
    SubAgentManager,
)


class TestSubAgent:
    """Test SubAgent base class."""
    
    def test_agent_initialization(self):
        """Test agent initialization with capabilities."""
        agent = SubAgent(
            agent_id="test-agent",
            name="Test Agent",
            description="A test agent",
            capabilities={AgentCapability.READ_FILES, AgentCapability.CODE_ANALYSIS}
        )
        
        assert agent.agent_id == "test-agent"
        assert agent.name == "Test Agent"
        assert agent.status == AgentStatus.IDLE
        assert AgentCapability.READ_FILES in agent.capabilities
        assert AgentCapability.WRITE_FILES not in agent.capabilities
    
    def test_validate_capabilities(self):
        """Test capability validation."""
        agent = SubAgent(
            agent_id="test",
            name="Test",
            description="Test",
            capabilities={AgentCapability.READ_FILES, AgentCapability.CODE_ANALYSIS}
        )
        
        # Should pass - subset of capabilities
        assert agent.validate_capabilities({AgentCapability.READ_FILES})
        
        # Should fail - missing capability
        assert not agent.validate_capabilities({AgentCapability.WRITE_FILES})
        
        # Should pass - exact match
        assert agent.validate_capabilities(
            {AgentCapability.READ_FILES, AgentCapability.CODE_ANALYSIS}
        )
    
    def test_validate_path_access(self):
        """Test path access validation."""
        agent = SubAgent(
            agent_id="test",
            name="Test",
            description="Test",
            capabilities={AgentCapability.READ_FILES}
        )
        
        context = AgentContext(
            allowed_paths=["/tmp/allowed", "/home/user/project"],
            forbidden_paths=["/tmp/allowed/secret", "/etc"]
        )
        
        # Should allow access to allowed paths
        assert agent.validate_path_access("/tmp/allowed/file.txt", context)
        assert agent.validate_path_access("/home/user/project/src/main.py", context)
        
        # Should deny access to forbidden paths
        assert not agent.validate_path_access("/tmp/allowed/secret/key.txt", context)
        assert not agent.validate_path_access("/etc/passwd", context)
        
        # Should deny access to paths outside allowed list
        assert not agent.validate_path_access("/usr/bin/python", context)
    
    def test_task_validation(self):
        """Test task validation against capabilities."""
        agent = SubAgent(
            agent_id="test",
            name="Test",
            description="Test",
            capabilities={AgentCapability.READ_FILES, AgentCapability.CODE_ANALYSIS}
        )
        
        context = AgentContext()
        
        # Should pass for read operations
        assert agent._validate_task("Read file main.py", context)
        
        # Should fail for write operations
        assert not agent._validate_task("Write file output.txt", context)
        
        # Should fail for command execution
        assert not agent._validate_task("Execute bash script", context)
    
    @pytest.mark.asyncio
    async def test_execute_with_timeout(self):
        """Test task execution with timeout."""
        agent = SubAgent(
            agent_id="test",
            name="Test",
            description="Test",
            capabilities={AgentCapability.CODE_ANALYSIS}
        )
        
        # Mock the execution to take too long
        async def slow_task(task, context):
            await asyncio.sleep(10)
            return "Never completes"
        
        agent._execute_task = slow_task
        
        context = AgentContext(timeout=1)  # 1 second timeout
        result = await agent.execute("Analyze code", context)
        
        assert result.status == AgentStatus.TIMEOUT
        assert "timed out" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_execute_with_error(self):
        """Test task execution with error handling."""
        agent = SubAgent(
            agent_id="test",
            name="Test",
            description="Test",
            capabilities={AgentCapability.CODE_ANALYSIS}
        )
        
        # Mock execution to raise error
        async def failing_task(task, context):
            raise ValueError("Task failed")
        
        agent._execute_task = failing_task
        
        context = AgentContext()
        result = await agent.execute("Analyze code", context)
        
        assert result.status == AgentStatus.FAILED
        assert "Task failed" in result.error
    
    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful task execution."""
        agent = SubAgent(
            agent_id="test",
            name="Test",
            description="Test",
            capabilities={AgentCapability.CODE_ANALYSIS}
        )
        
        # Mock successful execution
        async def success_task(task, context):
            return "Analysis complete"
        
        agent._execute_task = success_task
        
        context = AgentContext()
        result = await agent.execute("Analyze code", context)
        
        assert result.status == AgentStatus.COMPLETED
        assert result.output == "Analysis complete"
        assert result.execution_time > 0
    
    def test_secure_prompt_building(self):
        """Test secure prompt generation."""
        agent = SubAgent(
            agent_id="test",
            name="Test Agent",
            description="A test agent",
            capabilities={AgentCapability.READ_FILES}
        )
        
        context = AgentContext(
            allowed_paths=["/project"],
            forbidden_paths=["/project/secrets"],
            parent_context={"user": "test", "session": "123"}
        )
        
        prompt = agent._build_secure_prompt("Read configuration", context)
        
        assert "test" in prompt  # agent_id
        assert "Test Agent" in prompt  # name
        assert "read_files" in prompt  # capabilities
        assert "/project" in prompt  # allowed paths
        assert "/project/secrets" in prompt  # forbidden paths
        assert "Read configuration" in prompt  # task
        assert '"user": "test"' in prompt  # context


class TestSubAgentManager:
    """Test SubAgentManager."""
    
    def test_manager_initialization(self):
        """Test manager initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SubAgentManager(config_dir=tmpdir)
            
            # Should create default agents
            assert len(manager.agents) > 0
            assert "code-reviewer" in manager.agents
            assert "test-runner" in manager.agents
    
    def test_load_agent_configs(self):
        """Test loading agent configurations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test agent config
            config = {
                "id": "custom-agent",
                "name": "Custom Agent",
                "description": "A custom test agent",
                "capabilities": ["read_files", "code_analysis"],
                "config": {"custom": "value"}
            }
            
            config_file = Path(tmpdir) / "custom-agent.json"
            with open(config_file, 'w') as f:
                json.dump(config, f)
            
            manager = SubAgentManager(config_dir=tmpdir)
            
            assert "custom-agent" in manager.agents
            agent = manager.get_agent("custom-agent")
            assert agent.name == "Custom Agent"
            assert AgentCapability.READ_FILES in agent.capabilities
    
    def test_register_agent(self):
        """Test agent registration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SubAgentManager(config_dir=tmpdir)
            
            agent = SubAgent(
                agent_id="new-agent",
                name="New Agent",
                description="Newly registered agent",
                capabilities={AgentCapability.DOCUMENTATION}
            )
            
            manager.register_agent(agent)
            
            assert "new-agent" in manager.agents
            retrieved = manager.get_agent("new-agent")
            assert retrieved == agent
    
    def test_list_agents(self):
        """Test listing agents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SubAgentManager(config_dir=tmpdir)
            
            agents = manager.list_agents()
            
            assert len(agents) > 0
            assert all("id" in agent for agent in agents)
            assert all("name" in agent for agent in agents)
            assert all("capabilities" in agent for agent in agents)
    
    @pytest.mark.asyncio
    async def test_execute_task(self):
        """Test task execution through manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SubAgentManager(config_dir=tmpdir)
            
            # Mock agent execution
            agent = manager.get_agent("code-reviewer")
            agent.execute = AsyncMock(
                return_value=AgentResult(
                    agent_id="code-reviewer",
                    task_id="test-123",
                    status=AgentStatus.COMPLETED,
                    output="Review complete"
                )
            )
            
            result = await manager.execute_task(
                "code-reviewer",
                "Review the code",
                AgentContext()
            )
            
            assert result.status == AgentStatus.COMPLETED
            assert result.output == "Review complete"
            agent.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_parallel(self):
        """Test parallel task execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SubAgentManager(config_dir=tmpdir)
            
            # Mock multiple agents
            for agent_id in ["code-reviewer", "test-runner"]:
                agent = manager.get_agent(agent_id)
                agent.execute = AsyncMock(
                    return_value=AgentResult(
                        agent_id=agent_id,
                        task_id=f"task-{agent_id}",
                        status=AgentStatus.COMPLETED,
                        output=f"Task complete for {agent_id}"
                    )
                )
            
            tasks = [
                ("code-reviewer", "Review code", None),
                ("test-runner", "Run tests", None)
            ]
            
            results = await manager.execute_parallel(tasks)
            
            assert len(results) == 2
            assert all(r.status == AgentStatus.COMPLETED for r in results)
            assert results[0].agent_id == "code-reviewer"
            assert results[1].agent_id == "test-runner"
    
    @pytest.mark.asyncio
    async def test_execute_parallel_with_failure(self):
        """Test parallel execution with some failures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SubAgentManager(config_dir=tmpdir)
            
            # Mock one success and one failure
            reviewer = manager.get_agent("code-reviewer")
            reviewer.execute = AsyncMock(
                return_value=AgentResult(
                    agent_id="code-reviewer",
                    task_id="task-1",
                    status=AgentStatus.COMPLETED,
                    output="Success"
                )
            )
            
            runner = manager.get_agent("test-runner")
            runner.execute = AsyncMock(side_effect=Exception("Test failed"))
            
            tasks = [
                ("code-reviewer", "Review", None),
                ("test-runner", "Test", None)
            ]
            
            results = await manager.execute_parallel(tasks)
            
            assert len(results) == 2
            assert results[0].status == AgentStatus.COMPLETED
            assert results[1].status == AgentStatus.FAILED
            assert "Test failed" in results[1].error
    
    def test_get_agent_for_capability(self):
        """Test finding agent by capability."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SubAgentManager(config_dir=tmpdir)
            
            agent = manager.get_agent_for_capability(AgentCapability.CODE_ANALYSIS)
            
            assert agent is not None
            assert AgentCapability.CODE_ANALYSIS in agent.capabilities
            assert agent.status == AgentStatus.IDLE
    
    def test_get_agents_for_capabilities(self):
        """Test finding multiple agents by capabilities."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SubAgentManager(config_dir=tmpdir)
            
            agents = manager.get_agents_for_capabilities(
                {AgentCapability.READ_FILES}
            )
            
            assert len(agents) > 0
            assert all(
                AgentCapability.READ_FILES in agent.capabilities 
                for agent in agents
            )


class TestAgentContext:
    """Test AgentContext."""
    
    def test_context_initialization(self):
        """Test context initialization with defaults."""
        context = AgentContext()
        
        assert context.task_id is not None
        assert context.timeout == 300
        assert context.max_iterations == 10
        assert context.memory_limit_mb == 512
    
    def test_context_to_dict(self):
        """Test context serialization."""
        context = AgentContext(
            allowed_paths=["/tmp"],
            forbidden_paths=["/etc"],
            environment_vars={"KEY": "value"}
        )
        
        data = context.to_dict()
        
        assert "task_id" in data
        assert data["allowed_paths"] == ["/tmp"]
        assert data["forbidden_paths"] == ["/etc"]
        assert data["environment_vars"] == {"KEY": "value"}


class TestAgentResult:
    """Test AgentResult."""
    
    def test_result_initialization(self):
        """Test result initialization."""
        result = AgentResult(
            agent_id="test",
            task_id="task-123",
            status=AgentStatus.COMPLETED,
            output="Success"
        )
        
        assert result.agent_id == "test"
        assert result.task_id == "task-123"
        assert result.status == AgentStatus.COMPLETED
        assert result.output == "Success"
    
    def test_result_to_dict(self):
        """Test result serialization."""
        result = AgentResult(
            agent_id="test",
            task_id="task-123",
            status=AgentStatus.COMPLETED,
            output="Success",
            execution_time=1.5,
            iterations_used=3
        )
        
        data = result.to_dict()
        
        assert data["agent_id"] == "test"
        assert data["status"] == "completed"
        assert data["execution_time"] == 1.5
        assert data["iterations_used"] == 3