# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Codex-Plus** is an HTTP proxy that intercepts Codex CLI requests to add power-user features (slash commands, hooks, MCP tools, persistent sessions) while maintaining identical UI/UX to Codex CLI.

**Architecture**: FastAPI-based HTTP proxy that forwards requests to `api.openai.com` with transparent streaming support.

## Development Commands

### Core Development
```bash
# Setup and activation
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate  
pip install -r requirements.txt

# Run tests (TDD approach - always run tests first)
pytest test_proxy.py -v                    # Run all tests
pytest test_proxy.py::TestClass::test_name -v  # Run specific test
pytest -k "test_name_pattern" -v           # Run pattern-matched tests

# Start development server
./proxy.sh                                 # Start proxy (default)
./proxy.sh enable                          # Start proxy explicitly
./proxy.sh status                          # Check proxy status
./proxy.sh restart                         # Restart proxy
./proxy.sh disable                         # Stop proxy

# Manual server start (for debugging)
python start.py                            # Direct server start
uvicorn main:app --host 127.0.0.1 --port 3000 --reload  # With reload
```

### Usage with Codex CLI
```bash
# Set environment variable to use proxy
export OPENAI_BASE_URL=http://localhost:3000
codex  # Now uses proxy

# Or one-time usage
OPENAI_BASE_URL=http://localhost:3000 codex
```

### Testing and Validation
```bash
# Health check
curl http://localhost:3000/health

# Test proxy forwarding manually
curl -X POST http://localhost:3000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_token" \
  -d '{"model": "claude-3", "messages": [{"role": "user", "content": "test"}]}'
```

## Architecture Details

### Current Implementation (M1 - Simple Passthrough Proxy)
- **Entry Point**: `main.py` - FastAPI application with single proxy route
- **Startup**: `start.py` - Uvicorn server configuration (127.0.0.1:3000)
- **Control**: `proxy.sh` - Process management (start/stop/status/restart)
- **Testing**: `test_proxy.py` - Comprehensive TDD test suite (11 tests)

### Request Flow
1. Codex CLI → HTTP proxy (localhost:3000) 
2. Proxy forwards to `api.openai.com` with preserved headers/streaming
3. Response streams back through proxy to Codex CLI
4. Special handling: `/health` endpoint returns local status (not forwarded)

### Key Components
- **Streaming Support**: `httpx.AsyncClient.stream()` preserves real-time responses
- **Header Management**: Filters hop-by-hop headers, preserves auth/content headers  
- **Error Passthrough**: HTTP errors (401, 429, 500) forwarded transparently
- **Process Management**: PID-based daemon control via `proxy.sh`

## Development Milestones

### ✅ M1: Simple Passthrough Proxy (Complete)
- HTTP proxy intercepting Codex requests via `OPENAI_BASE_URL`
- FastAPI + httpx async streaming to `api.openai.com`
- Complete TDD test coverage (request forwarding, streaming, errors)
- Process management and health monitoring

### 🚧 M2: Slash Command Processing (Next)
- Intercept and parse `/command` syntax before forwarding
- Implement core commands: `/help`, `/status`, `/quit`, `/save`
- Maintain non-slash input passthrough behavior
- Add command discovery and execution framework

### 📋 M3: Hook System (Planned)
- Pre-input hooks: modify prompts before sending to API  
- Post-output hooks: process responses after receiving from API
- Configurable hook chains and conditional execution
- Hook state persistence across sessions

### 📋 M4: MCP Integration (Planned)
- Remote MCP tool discovery and invocation
- Tool result integration into conversation context
- MCP protocol compatibility with Claude Code CLI conventions

## File Structure
```
codex_plus/
├── main.py           # FastAPI proxy application
├── start.py          # Uvicorn server startup
├── proxy.sh          # Process control script  
├── test_proxy.py     # TDD test suite
├── requirements.txt  # Python dependencies
├── proxy.log         # Runtime logs
├── proxy.pid         # Process ID file
├── README.md         # Project documentation
├── product_spec.md   # User stories and acceptance criteria
└── .claude/          # Slash commands and configurations
```

## Testing Strategy

**Test-Driven Development (TDD)**: All new features must be implemented with failing tests first, then implementation, then passing tests.

### Test Categories
- **Core Request Interception**: Verify forwarding behavior for different endpoints
- **Streaming Response Types**: Test JSON, SSE, binary streaming preservation
- **Error Conditions**: Ensure 401, 404, 429, 500 errors pass through correctly  
- **Special Cases**: Local `/health` endpoint handling

### Test Execution
```bash
# Run full test suite (required before commits)
pytest test_proxy.py -v

# Run with coverage
pytest test_proxy.py --cov=main --cov-report=html -v

# Run specific test matrices
pytest test_proxy.py::TestSimplePassthroughProxy::test_request_forwarding -v
```

## Implementation Guidelines

### Code Style
- **FastAPI**: Use async/await for all I/O operations
- **Error Handling**: Always preserve upstream HTTP status codes and messages
- **Streaming**: Use `httpx.AsyncClient.stream()` for real-time response handling
- **Logging**: Use structured logging for debugging and monitoring

### Security Considerations  
- **Header Filtering**: Remove hop-by-hop headers to prevent header injection
- **Input Validation**: Validate slash commands and parameters before processing
- **API Key Handling**: Never log or expose API keys in proxy responses
- **Process Isolation**: Run proxy with minimal required permissions

### Debugging
```bash
# View real-time logs
tail -f proxy.log

# Debug with verbose logging
PYTHONPATH=. uvicorn main:app --host 127.0.0.1 --port 3000 --log-level debug

# Test connectivity
curl -v http://localhost:3000/health
```

## Integration Notes

### Claude Code CLI Compatibility
- Slash commands follow Claude Code CLI conventions (`/help`, `/status`, `/save`)
- MCP tools integration matches Claude Code CLI behavior patterns
- Hook system designed for Claude Code CLI workflow compatibility

### Environment Variables
```bash
export OPENAI_BASE_URL=http://localhost:3000  # Route Codex through proxy
export PYTHONPATH=.                           # For local module imports
```

### Development Workflow
1. **Feature Planning**: Update milestone tracking in README.md
2. **TDD Implementation**: Write failing tests first
3. **Code Implementation**: Implement minimal code to pass tests
4. **Integration Testing**: Test with actual Codex CLI
5. **Documentation**: Update CLAUDE.md and product_spec.md as needed

## Future Considerations

### Scalability
- Multi-user session management (post-M1)
- Load balancing and rate limiting (if needed)
- Persistent session storage (M3/M4)

### Extensions
- Plugin system for custom slash commands
- Integration with development environment tools
- Advanced hook scripting capabilities