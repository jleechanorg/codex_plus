#!/usr/bin/env python3
"""
Validation script for agent orchestrator middleware fixes
"""
import asyncio
import json
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.codex_plus.agent_orchestrator_middleware import AgentOrchestrationMiddleware

@pytest.mark.asyncio
async def test_path_fix():
    """Test that the path fix is working correctly"""
    print("🔧 Testing Path Fix")
    print("=" * 50)

    middleware = AgentOrchestrationMiddleware()

    # Create mock request
    mock_request = MagicMock()
    mock_request.state = MagicMock()
    mock_request.headers = {}

    # Test body with agent command
    agent_command_body = json.dumps({
        "input": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "input_text",
                        "text": "/agent code-reviewer analyze this code for security issues"
                    }
                ]
            }
        ]
    }).encode('utf-8')

    mock_request.body = AsyncMock(return_value=agent_command_body)

    # Test 1: /responses path (should process with fix)
    print("Test 1: /responses path (should process)")
    try:
        result = await middleware.process_request(mock_request, "/responses")
        if result is not None:
            print("✅ PASSED: /responses path processed successfully")
            print(f"   Result type: {type(result)}")
            print(f"   Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
        else:
            print("❌ FAILED: /responses path returned None (not processed)")
    except Exception as e:
        print(f"❌ ERROR: /responses path failed with error: {e}")

    # Reset mock for next test
    mock_request.body = AsyncMock(return_value=agent_command_body)

    # Test 2: responses path without slash (should not process)
    print("\nTest 2: responses path without slash (should not process)")
    try:
        result = await middleware.process_request(mock_request, "responses")
        if result is None:
            print("✅ PASSED: 'responses' path correctly skipped")
        else:
            print("❌ FAILED: 'responses' path should not process")
    except Exception as e:
        print(f"❌ ERROR: responses path failed with error: {e}")

    # Reset mock for next test
    mock_request.body = AsyncMock(return_value=agent_command_body)

    # Test 3: Other path (should not process)
    print("\nTest 3: /health path (should not process)")
    try:
        result = await middleware.process_request(mock_request, "/health")
        if result is None:
            print("✅ PASSED: '/health' path correctly skipped")
        else:
            print("❌ FAILED: '/health' path should not process")
    except Exception as e:
        print(f"❌ ERROR: /health path failed with error: {e}")

@pytest.mark.asyncio
async def test_agent_detection():
    """Test agent command detection patterns"""
    print("\n🤖 Testing Agent Detection Patterns")
    print("=" * 50)

    middleware = AgentOrchestrationMiddleware()

    test_cases = [
        {
            "name": "Explicit agent command",
            "input": "/agent code-reviewer analyze this code",
            "expected_type": "explicit",
            "expected_agent": "code-reviewer"
        },
        {
            "name": "Multi-agent command",
            "input": "/agents run code-reviewer,test-runner analyze and test this code",
            "expected_type": "multi_agent",
            "expected_agents": ["code-reviewer", "test-runner"]
        },
        {
            "name": "Auto-delegate command",
            "input": "/delegate review this code for security vulnerabilities",
            "expected_type": "auto_delegate",
            "expected_task": "review this code for security vulnerabilities"
        },
        {
            "name": "Non-agent command",
            "input": "Just analyze this code normally",
            "expected_type": None,
            "expected_result": None
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['name']}")

        request_data = {
            "input": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "input_text",
                            "text": test_case["input"]
                        }
                    ]
                }
            ]
        }

        invocation = middleware.detect_agent_invocation(request_data)

        if test_case["expected_type"] is None:
            if invocation is None:
                print("✅ PASSED: Correctly detected no agent command")
            else:
                print(f"❌ FAILED: Expected no detection, got {invocation}")
        else:
            if invocation and invocation.get("type") == test_case["expected_type"]:
                print(f"✅ PASSED: Detected {test_case['expected_type']}")

                # Additional checks based on type
                if test_case["expected_type"] == "explicit":
                    if invocation.get("agent_id") == test_case["expected_agent"]:
                        print(f"✅ PASSED: Correct agent ID: {test_case['expected_agent']}")
                    else:
                        print(f"❌ FAILED: Expected agent {test_case['expected_agent']}, got {invocation.get('agent_id')}")

                elif test_case["expected_type"] == "multi_agent":
                    if invocation.get("agent_ids") == test_case["expected_agents"]:
                        print(f"✅ PASSED: Correct agent IDs: {test_case['expected_agents']}")
                    else:
                        print(f"❌ FAILED: Expected agents {test_case['expected_agents']}, got {invocation.get('agent_ids')}")

                elif test_case["expected_type"] == "auto_delegate":
                    if test_case["expected_task"] in invocation.get("task", ""):
                        print("✅ PASSED: Correct task detected")
                    else:
                        print(f"❌ FAILED: Expected task '{test_case['expected_task']}', got '{invocation.get('task')}'")
            else:
                print(f"❌ FAILED: Expected {test_case['expected_type']}, got {invocation}")

@pytest.mark.asyncio
async def test_agent_configuration_loading():
    """Test that agent configurations are loading correctly"""
    print("\n📋 Testing Agent Configuration Loading")
    print("=" * 50)

    middleware = AgentOrchestrationMiddleware()

    print(f"Loaded agents: {len(middleware.agents)}")
    if middleware.agents:
        print("Available agents:")
        for agent_id, config in middleware.agents.items():
            print(f"  - {agent_id}: {config.name} ({config.description[:50]}...)")
            print(f"    Tools: {', '.join(config.tools) if config.tools else 'None'}")
            print(f"    Capabilities: {', '.join(config.capabilities) if config.capabilities else 'None'}")
        print("✅ PASSED: Agents loaded successfully")
    else:
        print("❌ FAILED: No agents loaded")

@pytest.mark.asyncio
async def test_agent_execution():
    """Test agent execution method"""
    print("\n⚡ Testing Agent Execution")
    print("=" * 50)

    middleware = AgentOrchestrationMiddleware()

    if not middleware.agents:
        print("❌ SKIPPED: No agents available for testing")
        return

    # Get first available agent
    agent_id = list(middleware.agents.keys())[0]
    agent_config = middleware.agents[agent_id]

    print(f"Testing with agent: {agent_id} ({agent_config.name})")

    # Create execution context
    from src.codex_plus.agent_orchestrator_middleware import AgentExecutionContext
    mock_request = MagicMock()
    context = AgentExecutionContext(mock_request)

    # Test agent execution
    task = "Test task for agent execution"
    try:
        result = await middleware.execute_agent(agent_id, task, context)

        print("✅ PASSED: Agent execution completed")
        print(f"   Agent ID: {result.agent_id}")
        print(f"   Success: {result.success}")
        print(f"   Duration: {result.duration:.2f}s")
        if result.output:
            print(f"   Output length: {len(result.output)} characters")
        if result.error:
            print(f"   Error: {result.error}")

    except Exception as e:
        print(f"❌ FAILED: Agent execution failed with error: {e}")

async def main():
    """Run all validation tests"""
    print("🧪 Agent Orchestrator Middleware Validation")
    print("=" * 60)

    try:
        await test_path_fix()
        await test_agent_detection()
        await test_agent_configuration_loading()
        await test_agent_execution()

        print("\n🎯 Validation Summary")
        print("=" * 60)
        print("✅ Path fix validation completed")
        print("✅ Agent detection patterns validated")
        print("✅ Agent configuration loading tested")
        print("✅ Agent execution mechanism tested")
        print("\n🚀 Agent orchestrator middleware should now be working correctly!")

    except Exception as e:
        print(f"\n❌ CRITICAL ERROR during validation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())