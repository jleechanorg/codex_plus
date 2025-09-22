# Agent Orchestrator Middleware Integration Guide

This document explains how to integrate the new `AgentOrchestrationMiddleware` with the existing FastAPI proxy architecture.

## Overview

The `AgentOrchestrationMiddleware` provides:

1. **Agent Command Detection**: Recognizes `/agent`, `/agents`, and `/delegate` commands
2. **Configuration Loading**: Uses existing `config_loader.py` to load agents from `.claude/agents/`
3. **Parallel Execution**: Runs multiple agents concurrently with timeout controls
4. **Security Validation**: Enforces path restrictions and access controls
5. **Result Aggregation**: Formats agent outputs for conversation injection

## Integration Steps

### 1. Import the Middleware

Add to `main_sync_cffi.py` after the existing middleware imports:

```python
# ✅ SAFE TO MODIFY: Agent orchestrator middleware
from .agent_orchestrator_middleware import create_agent_orchestrator_middleware

# Initialize agent orchestrator middleware
logger.info("Initializing agent orchestrator middleware")
agent_middleware = create_agent_orchestrator_middleware(
    max_concurrent_agents=3,
    agent_timeout=30
)
```

### 2. Add Agent Processing to Request Pipeline

In the `proxy()` function, add agent processing after pre-input hooks but before middleware forwarding:

```python
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, path: str):
    # ... existing code for security validation and pre-input hooks ...

    # ✅ SAFE TO MODIFY: Agent orchestrator processing
    # Process agent commands before slash command middleware
    if path == "responses":
        try:
            modified_request_data = await agent_middleware.process_request(request, path)
            if modified_request_data:
                # Agent commands were processed, update request body
                modified_body = json.dumps(modified_request_data).encode('utf-8')
                request.state.modified_body = modified_body
                logger.info("Agent orchestrator: request body modified with agent results")
        except Exception as e:
            logger.error(f"Agent orchestrator failed: {e}")
            # Continue with normal processing if agent orchestration fails

    # ... existing status line and middleware processing ...
```

### 3. Add Agent Status Endpoint

Add a new endpoint to check agent status:

```python
@app.get("/agents/status")
async def agent_status():
    """Get agent orchestrator status - not forwarded"""
    try:
        status = agent_middleware.get_agent_status()
        return JSONResponse(status)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
```

## Agent Command Patterns

### Explicit Agent Execution
```bash
/agent code-reviewer Review this Python function for security issues
/agent test-runner Run the test suite and report coverage
```

### Multi-Agent Parallel Execution
```bash
/agents run code-reviewer,test-runner Analyze this module comprehensively
```

### Auto-Delegation
```bash
/delegate Review this code for bugs and write tests for it
# Automatically selects code-reviewer and test-runner agents
```

## Agent Configuration

Agents are configured in `.claude/agents/` directory using YAML format following Anthropic patterns:

```yaml
---
name: "Code Reviewer"
description: "Specialized agent for code review and security analysis"
model: "claude-3-5-sonnet-20241022"
temperature: 0.3
tools:
  - "Read"
  - "Grep"
  - "WebSearch"
capabilities:
  - "code_analysis"
  - "security_review"
allowed_paths:
  - "./src"
  - "./tests"
forbidden_paths:
  - "./secrets"
tags:
  - "review"
  - "security"
---

You are a specialized code review agent focused on:
- Security vulnerabilities
- Performance issues
- Code quality and best practices
- Potential bugs

Provide actionable feedback with specific line references.
```

## Security Considerations

The middleware implements several security measures:

1. **Path Validation**: Agents can only access allowed paths
2. **Capability Checking**: Tasks are validated against agent capabilities
3. **Execution Timeouts**: Prevents runaway agent processes
4. **Concurrent Limits**: Prevents resource exhaustion
5. **Access Controls**: Enforces agent permission boundaries

## Error Handling

The middleware gracefully handles:

- Agent configuration errors
- Execution timeouts
- Access permission violations
- Network failures
- Invalid command syntax

Failed agent executions are logged but don't break the main proxy pipeline.

## Testing

Test the integration with:

```bash
# Start the proxy
./proxy.sh

# Test agent command detection
echo '{"input": [{"type": "message", "content": [{"type": "input_text", "text": "/agent code-reviewer Review this file"}]}]}' | \
  curl -X POST http://localhost:10000/responses -H "Content-Type: application/json" -d @-

# Check agent status
curl http://localhost:10000/agents/status
```

## Backward Compatibility

The middleware:
- ✅ Does not interfere with existing slash command processing
- ✅ Preserves all proxy forwarding behavior
- ✅ Maintains hook system functionality
- ✅ Works with existing `.codexplus/` and `.claude/` directory structures
- ✅ Gracefully degrades if no agents are configured

## Performance Impact

- **Minimal overhead** when no agent commands are detected
- **Parallel execution** prevents blocking on slow agents
- **Configurable timeouts** prevent resource exhaustion
- **Async processing** maintains streaming response performance