"""
Comprehensive integration tests for the agent orchestration system.

This test suite validates the entire agent orchestration middleware including:
- Agent middleware initialization and loading
- Agent invocation pattern detection (all three patterns)
- Request processing through the middleware
- Result injection into requests
- Error handling and edge cases
- Integration with existing middleware chain
- Concurrent agent execution scenarios

Uses pytest with async support and realistic test scenarios.
"""

import asyncio
import json
import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from typing import Dict, Any, List

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.codex_plus.agent_orchestrator_middleware import (
    AgentOrchestrationMiddleware,
    AgentExecutionContext,
    AgentResult,
    create_agent_orchestrator_middleware
)
from src.codex_plus.subagents.config_loader import (
    AgentConfiguration,
    AgentConfigurationLoader
)


# Shared fixtures at module level
@pytest.fixture
def temp_base_dir():
    """Create temporary base directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_agents_config():
    """Create test agent configurations."""
    return {
        "code-reviewer": AgentConfiguration(
            name="Code Reviewer",
            description="Reviews code for security and quality",
            tools=["Read", "Grep", "WebSearch"],
            model="claude-3-5-sonnet-20241022",
            temperature=0.3,
            capabilities={"code_review", "security_review"},
            tags=["review", "security", "code_review"],
            system_prompt="You are a code review specialist.",
            instructions="Focus on security vulnerabilities and code quality."
        ),
        "test-runner": AgentConfiguration(
            name="Test Runner",
            description="Executes and analyzes tests",
            tools=["Read", "Bash", "BashOutput"],
            model="claude-3-5-sonnet-20241022",
            temperature=0.2,
            capabilities={"testing", "test_execution", "coverage_analysis"},
            tags=["testing", "validation"],
            system_prompt="You are a test execution specialist.",
            instructions="Run tests and analyze results systematically."
        ),
        "debugger": AgentConfiguration(
            name="Debugger",
            description="Analyzes errors and traces issues",
            tools=["Read", "Grep", "Bash"],
            model="claude-3-5-sonnet-20241022",
            temperature=0.3,
            capabilities={"debugging", "error_analysis"},
            tags=["debug", "troubleshooting", "debugging"],
            system_prompt="You are a debugging specialist.",
            instructions="Provide systematic error analysis."
        )
    }


@pytest.fixture
def middleware_with_agents(temp_base_dir, test_agents_config):
    """Create middleware instance with test agents."""
    # Create agents directory and files
    agents_dir = temp_base_dir / ".claude" / "agents"
    agents_dir.mkdir(parents=True)

    # Save test agent configurations
    loader = AgentConfigurationLoader(base_dir=temp_base_dir)
    for agent_id, config in test_agents_config.items():
        loader.save_agent(agent_id, config)

    # Create middleware with test configuration
    middleware = AgentOrchestrationMiddleware(
        max_concurrent_agents=2,
        agent_timeout=5
    )

    # Override the base directory for testing
    middleware.config_loader = AgentConfigurationLoader(base_dir=temp_base_dir)
    middleware._load_agents()

    return middleware


@pytest.fixture
def mock_request():
    """Create mock FastAPI request object."""
    from types import SimpleNamespace

    request = Mock(spec=Request)
    request.headers = {}
    # Use SimpleNamespace instead of Mock to avoid auto-attribute creation
    request.state = SimpleNamespace()
    request.body = AsyncMock()
    return request


@pytest.fixture
def execution_context(mock_request):
    """Create test execution context."""
    return AgentExecutionContext(mock_request, "/test/working/dir")


class TestAgentOrchestrationMiddleware:
    """Test the AgentOrchestrationMiddleware class."""

    def test_middleware_initialization(self, middleware_with_agents):
        """Test that middleware initializes correctly with agent configurations."""
        assert isinstance(middleware_with_agents, AgentOrchestrationMiddleware)
        assert len(middleware_with_agents.agents) == 3
        assert "code-reviewer" in middleware_with_agents.agents
        assert "test-runner" in middleware_with_agents.agents
        assert "debugger" in middleware_with_agents.agents
        assert middleware_with_agents.max_concurrent_agents == 2
        assert middleware_with_agents.agent_timeout == 5

    def test_factory_function(self):
        """Test the factory function creates middleware correctly."""
        middleware = create_agent_orchestrator_middleware(
            max_concurrent_agents=5,
            agent_timeout=10
        )
        assert isinstance(middleware, AgentOrchestrationMiddleware)
        assert middleware.max_concurrent_agents == 5
        assert middleware.agent_timeout == 10


class TestAgentInvocationDetection:
    """Test agent invocation pattern detection."""

    def test_detect_explicit_agent_invocation(self, middleware_with_agents):
        """Test detection of explicit agent command /agent."""
        request_body = {
            "input": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "/agent code-reviewer Review this function for security issues"
                        }
                    ]
                }
            ]
        }

        invocation = middleware_with_agents.detect_agent_invocation(request_body)

        assert invocation is not None
        assert invocation["type"] == "explicit"
        assert invocation["agent_id"] == "code-reviewer"
        assert invocation["task"] == "Review this function for security issues"
        assert "/agent code-reviewer" in invocation["original_text"]

    def test_detect_multi_agent_invocation(self, middleware_with_agents):
        """Test detection of multi-agent command /agents run."""
        request_body = {
            "messages": [
                {
                    "role": "user",
                    "content": "/agents run code-reviewer,test-runner Analyze this codebase comprehensively"
                }
            ]
        }

        invocation = middleware_with_agents.detect_agent_invocation(request_body)

        assert invocation is not None
        assert invocation["type"] == "multi_agent"
        assert invocation["agent_ids"] == ["code-reviewer", "test-runner"]
        assert invocation["task"] == "Analyze this codebase comprehensively"

    def test_detect_auto_delegation_invocation(self, middleware_with_agents):
        """Test detection of auto-delegation command /delegate."""
        request_body = {
            "input": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "/delegate Debug this error and fix the failing tests"
                        }
                    ]
                }
            ]
        }

        invocation = middleware_with_agents.detect_agent_invocation(request_body)

        assert invocation is not None
        assert invocation["type"] == "auto_delegate"
        assert invocation["task"] == "Debug this error and fix the failing tests"

    def test_detect_no_agent_invocation(self, middleware_with_agents):
        """Test that non-agent requests are not detected."""
        request_body = {
            "messages": [
                {
                    "role": "user",
                    "content": "Just a regular question about Python"
                }
            ]
        }

        invocation = middleware_with_agents.detect_agent_invocation(request_body)
        assert invocation is None

    def test_detect_case_insensitive_commands(self, middleware_with_agents):
        """Test that agent commands are case insensitive."""
        request_body = {
            "messages": [
                {
                    "role": "user",
                    "content": "/AGENT test-runner Run all unit tests"
                }
            ]
        }

        invocation = middleware_with_agents.detect_agent_invocation(request_body)

        assert invocation is not None
        assert invocation["type"] == "explicit"
        assert invocation["agent_id"] == "test-runner"


class TestAgentSelection:
    """Test agent selection logic for auto-delegation."""

    def test_select_agents_for_code_review_task(self, middleware_with_agents):
        """Test agent selection for code review tasks."""
        task = "Please review this code for quality and analyze it"
        agents = middleware_with_agents.select_agents_for_task(task)

        # The task contains "review" and "analyze" which should match code_review pattern
        # The code-reviewer agent has capabilities={"code_review", ...} and tags=["code_review", ...]
        assert "code-reviewer" in agents

    def test_select_agents_for_testing_task(self, middleware_with_agents):
        """Test agent selection for testing tasks."""
        task = "Run tests and validate coverage for this module"
        agents = middleware_with_agents.select_agents_for_task(task)

        assert "test-runner" in agents

    def test_select_agents_for_debugging_task(self, middleware_with_agents):
        """Test agent selection for debugging tasks."""
        task = "Debug this error and trace the root cause"
        agents = middleware_with_agents.select_agents_for_task(task)

        assert "debugger" in agents

    def test_select_agents_with_available_agents_filter(self, middleware_with_agents):
        """Test agent selection with available agents filter."""
        task = "Review code and run tests"
        available_agents = ["test-runner"]

        agents = middleware_with_agents.select_agents_for_task(task, available_agents)

        assert agents == ["test-runner"]
        assert "code-reviewer" not in agents

    def test_select_agents_no_match(self, middleware_with_agents):
        """Test agent selection when no agents match the task."""
        task = "Write a blog post about cats"
        agents = middleware_with_agents.select_agents_for_task(task)

        assert len(agents) == 0


class TestAgentExecution:
    """Test agent execution functionality."""

    @pytest.mark.asyncio
    async def test_execute_single_agent_success(self, middleware_with_agents, execution_context):
        """Test successful execution of a single agent."""
        with patch.object(middleware_with_agents, '_execute_agent_request', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = "Agent execution successful"

            result = await middleware_with_agents.execute_agent("code-reviewer", "Review this code", execution_context)

            assert result.success is True
            assert result.agent_id == "code-reviewer"
            assert result.task == "Review this code"
            assert "Agent execution successful" in result.output
            assert result.duration > 0

    @pytest.mark.asyncio
    async def test_execute_single_agent_failure(self, middleware_with_agents, execution_context):
        """Test agent execution failure handling."""
        with patch.object(middleware_with_agents, '_execute_agent_request', new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = Exception("Execution failed")

            result = await middleware_with_agents.execute_agent("code-reviewer", "Review this code", execution_context)

            assert result.success is False
            assert result.agent_id == "code-reviewer"
            assert "Execution failed" in result.error

    @pytest.mark.asyncio
    async def test_execute_agent_timeout(self, middleware_with_agents, execution_context):
        """Test agent execution timeout handling."""
        # Set a very short timeout for testing
        middleware_with_agents.agent_timeout = 0.1

        with patch.object(middleware_with_agents, '_execute_agent_request', new_callable=AsyncMock) as mock_execute:
            # Simulate slow execution
            async def slow_execution(*args, **kwargs):
                await asyncio.sleep(1)
                return "Should not reach here"

            mock_execute.side_effect = slow_execution

            result = await middleware_with_agents.execute_agent("code-reviewer", "Review this code", execution_context)

            assert result.success is False
            assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_execute_agent_nonexistent(self, middleware_with_agents, execution_context):
        """Test execution of non-existent agent."""
        result = await middleware_with_agents.execute_agent("nonexistent", "Some task", execution_context)

        assert result.success is False
        assert "not found" in result.error


class TestParallelAgentExecution:
    """Test parallel agent execution functionality."""

    @pytest.mark.asyncio
    async def test_execute_agents_parallel_success(self, middleware_with_agents, execution_context):
        """Test successful parallel execution of multiple agents."""
        with patch.object(middleware_with_agents, 'execute_agent', new_callable=AsyncMock) as mock_execute:
            # Mock successful executions
            mock_execute.side_effect = [
                AgentResult("code-reviewer", "task1", True, "Review complete", "", 1.0),
                AgentResult("test-runner", "task2", True, "Tests passed", "", 1.5)
            ]

            agent_tasks = [("code-reviewer", "task1"), ("test-runner", "task2")]
            results = await middleware_with_agents.execute_agents_parallel(agent_tasks, execution_context)

            assert len(results) == 2
            assert all(r.success for r in results)
            assert results[0].agent_id == "code-reviewer"
            assert results[1].agent_id == "test-runner"

    @pytest.mark.asyncio
    async def test_execute_agents_parallel_concurrent_limit(self, middleware_with_agents, execution_context):
        """Test parallel execution respects concurrent agent limit."""
        # Middleware is configured with max_concurrent_agents=2
        agent_tasks = [
            ("code-reviewer", "task1"),
            ("test-runner", "task2"),
            ("debugger", "task3")  # This should be limited
        ]

        with patch.object(middleware_with_agents, 'execute_agent', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = AgentResult("test", "task", True, "Success", "", 1.0)

            results = await middleware_with_agents.execute_agents_parallel(agent_tasks, execution_context)

            # Should only execute max_concurrent_agents (2) agents
            assert len(results) == 2
            assert mock_execute.call_count == 2


class TestRequestProcessing:
    """Test main request processing functionality."""

    @pytest.mark.asyncio
    async def test_process_request_agent_command(self, middleware_with_agents, mock_request):
        """Test processing request with agent command."""
        body_data = {
            "input": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "/agent code-reviewer Review this function"
                        }
                    ]
                }
            ]
        }
        mock_request.body = AsyncMock(return_value=json.dumps(body_data).encode())
        mock_request.headers = {}

        with patch.object(middleware_with_agents, 'execute_agent', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = AgentResult(
                "code-reviewer", "Review this function", True, "Review complete", "", 1.0
            )

            result = await middleware_with_agents.process_request(mock_request, "/responses")

            assert result is not None
            assert isinstance(result, dict)
            # Check that result was injected into request
            assert "input" in result

    @pytest.mark.asyncio
    async def test_process_request_non_agent_command(self, middleware_with_agents, mock_request):
        """Test processing request without agent commands."""
        body_data = {
            "messages": [
                {"role": "user", "content": "Regular question"}
            ]
        }
        mock_request.body = AsyncMock(return_value=json.dumps(body_data).encode())

        result = await middleware_with_agents.process_request(mock_request, "/responses")
        assert result is None

    @pytest.mark.asyncio
    async def test_process_request_wrong_path(self, middleware_with_agents, mock_request):
        """Test processing request on wrong path."""
        body_data = {
            "input": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "/agent code-reviewer Review code"
                        }
                    ]
                }
            ]
        }
        mock_request.body = AsyncMock(return_value=json.dumps(body_data).encode())

        result = await middleware_with_agents.process_request(mock_request, "/wrong-path")
        assert result is None

    @pytest.mark.asyncio
    async def test_process_request_multi_agent(self, middleware_with_agents, mock_request):
        """Test processing multi-agent request."""
        body_data = {
            "messages": [
                {
                    "role": "user",
                    "content": "/agents run code-reviewer,test-runner Analyze this project"
                }
            ]
        }
        mock_request.body = AsyncMock(return_value=json.dumps(body_data).encode())
        mock_request.headers = {}

        with patch.object(middleware_with_agents, 'execute_agents_parallel', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = [
                AgentResult("code-reviewer", "task", True, "Review done", "", 1.0),
                AgentResult("test-runner", "task", True, "Tests done", "", 1.5)
            ]

            result = await middleware_with_agents.process_request(mock_request, "/responses")

            assert result is not None
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_request_auto_delegation(self, middleware_with_agents, mock_request):
        """Test processing auto-delegation request."""
        body_data = {
            "input": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "/delegate Debug this error and run tests"
                        }
                    ]
                }
            ]
        }
        mock_request.body = AsyncMock(return_value=json.dumps(body_data).encode())
        mock_request.headers = {}

        with patch.object(middleware_with_agents, 'select_agents_for_task') as mock_select:
            with patch.object(middleware_with_agents, 'execute_agents_parallel', new_callable=AsyncMock) as mock_execute:
                mock_select.return_value = ["debugger", "test-runner"]
                mock_execute.return_value = [
                    AgentResult("debugger", "task", True, "Debug done", "", 1.0),
                    AgentResult("test-runner", "task", True, "Tests done", "", 1.5)
                ]

                result = await middleware_with_agents.process_request(mock_request, "/responses")

                assert result is not None
                mock_select.assert_called_once()
                mock_execute.assert_called_once()


class TestStatusAndUtilities:
    """Test status reporting and utility functions."""

    def test_get_agent_status(self, middleware_with_agents):
        """Test getting agent orchestrator status."""
        status = middleware_with_agents.get_agent_status()

        assert "loaded_agents" in status
        assert "agent_list" in status
        assert "active_executions" in status
        assert "max_concurrent_agents" in status
        assert "agent_timeout" in status
        assert "configuration_paths" in status

        assert status["loaded_agents"] == 3
        assert len(status["agent_list"]) == 3
        assert "code-reviewer" in status["agent_list"]
        assert status["max_concurrent_agents"] == 2
        assert status["agent_timeout"] == 5

    def test_create_agent_payload(self, middleware_with_agents, execution_context):
        """Test creation of agent execution payload."""
        config = middleware_with_agents.agents["code-reviewer"]
        task = "Review this code for security issues"

        payload = middleware_with_agents._create_agent_payload(config, task, execution_context)

        assert payload["model"] == config.model
        assert payload["temperature"] == config.temperature
        assert payload["max_tokens"] == config.max_tokens
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1]["role"] == "user"
        assert payload["messages"][1]["content"] == task


class TestAgentAccessValidation:
    """Test agent access validation."""

    def test_validate_agent_access_success(self, middleware_with_agents, execution_context):
        """Test successful agent access validation."""
        issues = middleware_with_agents.validate_agent_access("code-reviewer", execution_context)
        assert len(issues) == 0

    def test_validate_agent_access_nonexistent_agent(self, middleware_with_agents, execution_context):
        """Test validation of non-existent agent."""
        issues = middleware_with_agents.validate_agent_access("nonexistent", execution_context)
        assert len(issues) == 1
        assert "not found" in issues[0]

    def test_validate_agent_access_forbidden_path(self, middleware_with_agents, execution_context):
        """Test validation with forbidden path access."""
        # Add forbidden path
        middleware_with_agents.agents["code-reviewer"].forbidden_paths = ["/test/working"]

        issues = middleware_with_agents.validate_agent_access("code-reviewer", execution_context)
        assert len(issues) == 1
        assert "forbidden path" in issues[0]


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases."""

    def test_agent_execution_context_logging(self, mock_request):
        """Test execution context logging functionality."""
        context = AgentExecutionContext(mock_request, "/test/dir")

        context.log("Test message 1")
        context.log("Test message 2")

        assert len(context.execution_log) == 2
        assert "Test message 1" in context.execution_log[0]
        assert "Test message 2" in context.execution_log[1]
        # Check timestamps are included
        assert "[" in context.execution_log[0]
        assert "s]" in context.execution_log[0]

    def test_agent_result_to_dict(self):
        """Test AgentResult to_dict conversion."""
        result = AgentResult(
            agent_id="test-agent",
            task="test task",
            success=True,
            output="test output",
            error="test error",
            duration=1.5
        )

        result_dict = result.to_dict()

        assert result_dict["agent_id"] == "test-agent"
        assert result_dict["task"] == "test task"
        assert result_dict["success"] is True
        assert result_dict["output"] == "test output"
        assert result_dict["error"] == "test error"
        assert result_dict["duration"] == 1.5
        assert "timestamp" in result_dict

    def test_middleware_with_no_agents(self, temp_base_dir):
        """Test middleware behavior with no agent configurations."""
        # Create middleware without any agents
        middleware = AgentOrchestrationMiddleware()
        middleware.config_loader = AgentConfigurationLoader(base_dir=temp_base_dir)

        # Mock the create_default_agents method to prevent creating default agents
        with patch.object(middleware.config_loader, 'create_default_agents'):
            middleware._load_agents()

        assert len(middleware.agents) == 0

        # Agent selection should return empty list
        agents = middleware.select_agents_for_task("test task")
        assert len(agents) == 0

    @pytest.mark.asyncio
    async def test_agent_request_execution_integration(self, middleware_with_agents):
        """Test the actual agent request execution method."""
        config = middleware_with_agents.agents["code-reviewer"]
        payload = {
            "model": config.model,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "messages": [
                {"role": "system", "content": "You are a code reviewer"},
                {"role": "user", "content": "Review this function"}
            ]
        }

        # Test the actual execution method
        result = await middleware_with_agents._execute_agent_request(payload, config)

        assert isinstance(result, str)
        assert len(result) > 0
        assert "Agent Execution:" in result
        assert config.name in result


class TestIntegrationWithMiddlewareChain:
    """Test integration with existing middleware chain."""

    def test_middleware_integration_with_fastapi(self, middleware_with_agents):
        """Test middleware integration with FastAPI application."""
        app = FastAPI()

        @app.middleware("http")
        async def agent_middleware(request: Request, call_next):
            # Simulate middleware integration
            if request.url.path == "/responses":
                modified_body = await middleware_with_agents.process_request(request, "/responses")
                if modified_body:
                    request.state.modified_body = modified_body

            response = await call_next(request)
            return response

        @app.post("/responses")
        async def responses_endpoint(request: Request):
            if hasattr(request.state, 'modified_body'):
                return {"modified": True, "body": request.state.modified_body}
            else:
                body = await request.body()
                return {"modified": False, "body": json.loads(body) if body else {}}

        client = TestClient(app)

        request_data = {
            "input": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "/agent code-reviewer Review this code"
                        }
                    ]
                }
            ]
        }

        with patch.object(middleware_with_agents, 'execute_agent', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = AgentResult(
                "code-reviewer", "Review this code", True, "Review complete", "", 1.0
            )

            response = client.post("/responses", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["modified"] is True
            assert "input" in data["body"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])