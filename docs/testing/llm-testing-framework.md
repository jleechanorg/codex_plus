# LLM Testing Framework for Codex Plus

## Overview

The Codex Plus proxy can be tested using LLM-executable test scenarios. This framework provides structured testing for proxy functionality, authentication, and system integration.

## Core Testing Areas

### 1. Proxy Functionality
- **Health Checks**: Verify `/health` endpoint responds correctly
- **Authentication Flow**: Test auth header forwarding to ChatGPT backend
- **Request Processing**: Validate request/response cycle
- **Streaming**: Confirm streaming responses work properly

### 2. Development Workflow
- **Port Configuration**: Ensure proxy uses port 10000 (no conflicts)
- **Error Handling**: Verify proper error passthrough (401, 404, 500)
- **Logging**: Check request logging and debugging capabilities
- **CI/CD**: Validate GitHub Actions workflow

### 3. Integration Testing
- **Codex CLI Integration**: Test `OPENAI_BASE_URL=http://localhost:10000 codex`
- **Module Loading**: Verify proper Python module imports
- **Configuration**: Test settings and environment variables

## Testing Commands

### Basic Proxy Test
```bash
# Start proxy
./proxy.sh restart

# Test health endpoint
curl http://localhost:10000/health

# Test unauthenticated request (should return 401)
curl -X POST http://localhost:10000/responses \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5","instructions":"Test"}'

# Test authenticated request
OPENAI_BASE_URL=http://localhost:10000 codex exec --yolo "test proxy"
```

### Expected Results
- ✅ **Health check**: Returns `{"status": "healthy"}`
- ✅ **Unauthenticated**: Returns `401 Unauthorized` (expected)
- ✅ **Authenticated**: Returns `200 OK` with LLM response (working proxy!)

### Authentication Validation
```bash
# Verify proxy logs show request processing
tail -f /tmp/codex_plus/proxy.log

# Check request logging works
ls /tmp/codex_plus/$(git branch --show-current)/
```

## Development Guidelines

### Key Success Indicators
1. **Port 10000**: No conflicts with AI Universe Frontend (port 3000)
2. **Authentication**: 200 responses for valid Codex CLI requests
3. **Error Handling**: Proper 401/404/500 passthrough
4. **Module Loading**: Clean Python imports with src/ layout
5. **CI**: Tests pass in GitHub Actions with timeout handling

### Common Issues
- **404 with AI Universe paths**: Indicates port conflict (use 10000)
- **Module import errors**: Check PYTHONPATH configuration
- **Constant 401s**: Authentication forwarding broken
- **CI timeouts**: Need proper timeout configuration

## Architecture Notes

### Request Flow
1. **Codex CLI** → HTTP proxy (localhost:10000)
2. **Proxy** → ChatGPT backend with preserved headers
3. **Response** streams back through proxy to CLI
4. **Logging** captures request data for debugging

### Key Components
- **curl_cffi**: Chrome impersonation for Cloudflare bypass
- **FastAPI**: Async request handling and streaming
- **Request Logger**: Async logging to branch-specific directories
- **Authentication**: Header preservation and forwarding

This framework ensures reliable proxy functionality and smooth development workflow.