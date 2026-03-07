# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚨 CRITICAL: DO NOT BREAK THE PROXY 🚨

**MANDATORY REQUIREMENTS - NEVER CHANGE THESE:**
1. **MUST use `curl_cffi.requests.Session(impersonate="chrome124")`** - Regular requests WILL FAIL (Cloudflare blocks them)
2. **MUST forward to `https://chatgpt.com/backend-api/codex`** - This is NOT OpenAI API
3. **NO API KEYS** - Codex uses session cookies/JWT from `~/.config/codex/auth.json`
4. **NEVER replace proxy forwarding logic** - Only extend with middleware
5. **ALWAYS test that normal requests still get 401** - This means proxy is working

**Common Mistakes to Avoid:**
- ❌ Using `httpx` or regular `requests` → Cloudflare will block
- ❌ Looking for OPENAI_API_KEY → Codex doesn't use API keys
- ❌ Changing the upstream URL → Must be ChatGPT backend
- ❌ Removing Chrome impersonation → Instant Cloudflare block

## Authentication & Request Flow

The proxy forwards all requests with authentication headers intact to the ChatGPT backend. The Codex CLI provides session cookies/JWT tokens in headers, which the proxy preserves during forwarding.

**Expected Behavior:**
- ✅ **With valid Codex CLI session**: Requests succeed and return 200 + LLM responses
- ❌ **Without authentication headers**: 401 Unauthorized from ChatGPT backend
- ❌ **With invalid/expired session**: 401 Unauthorized from ChatGPT backend
- ❌ **Backend routing issues**: 404 errors (indicates proxy/upstream config problems)

**Testing Guidelines:**
- ✅ **Authenticated**: `OPENAI_BASE_URL=http://localhost:10000 codex "test"` → Should return 200 + LLM response
- ❌ **Unauthenticated**: `curl -X POST http://localhost:10000/responses [...]` → Returns 401 (expected)
- **Never expect 401 to mean "working"** - 401 means "no valid auth provided"

**CRITICAL**: A working proxy should return 200 for authenticated Codex CLI requests. Getting 401 constantly means authentication forwarding is broken.

## 🚨🚨🚨 CODEBASE PROTECTION RULES 🚨🚨🚨

**🔒 PROTECTED FILES - MODIFICATIONS FORBIDDEN:**
- `src/codex_plus/main_sync_cffi.py` - Core proxy with curl_cffi forwarding
- `src/codex_plus/llm_execution_middleware.py` - Contains curl_cffi session logic
- `proxy.sh` - Critical startup command and port configuration
- `src/codex_plus/main.py` - Protected import wrapper

**❌ ABSOLUTELY FORBIDDEN CHANGES:**
- Replacing curl_cffi with any other HTTP client (requests, httpx, aiohttp)
- Modifying upstream URL from `https://chatgpt.com/backend-api/codex`
- Changing port from 10000 (Codex CLI expects this port)
- Removing Chrome impersonation from curl_cffi sessions
- Altering authentication header forwarding logic
- Breaking streaming response handling

**✅ SAFE MODIFICATION ZONES:**
- Hook system files in `.codexplus/hooks/` and `.claude/hooks/`
- Hook processing logic in `hooks.py` module
- Status line middleware functionality
- Request/response logging and debugging
- Command file reading and slash command processing
- Security validation functions (as long as they don't break forwarding)

**🛡️ PROTECTION ENFORCEMENT:**
All critical files contain extensive warning comments marking protected vs safe-to-modify sections.
Follow these comments religiously - they mark the exact boundaries of what can be safely changed.

**💀 CONSEQUENCE OF VIOLATIONS:**
Breaking these rules will immediately break ALL Codex functionality, blocking requests and preventing communication with ChatGPT backend. The proxy will stop working entirely.

## Project Overview

**Codex-Plus** is an HTTP proxy that intercepts Codex CLI requests to add power-user features (slash commands, hooks, MCP tools, persistent sessions) while maintaining identical UI/UX to Codex CLI.

**Architecture**: FastAPI proxy using `curl_cffi` with Chrome impersonation to bypass Cloudflare and forward to ChatGPT backend.

**Current Implementation**: The proxy now includes integrated LLM execution middleware that instructs Claude to natively execute slash commands by reading command definition files from `.codexplus/commands/` or `.claude/commands/` directories.

## Development Commands

### Core Development
```bash

## Testing Philosophy — Real Over Fake

**Always prefer real end-to-end tests.** Mocks and stubs are only acceptable for isolated unit tests.

For any suite or artifact under `testing_*/`:
- No mocks
- No monkeypatching
- No stubbed external service behavior (Slack, GitHub, databases, etc.)
- No direct registry/state injection
- No modifying the system under test while claiming verification

`testing_*` directories may only trigger the system from the outside and observe evidence. If a test needs simulated internals, it belongs in `src/tests/` (or equivalent unit test directory) and must not be described as end-to-end proof.

When an agent tries to create a file under `testing_*/` that contains mocks or stubs, it must block itself and log the violation to `.claude/blocked_violations.log` with:
- Timestamp
- Full path it attempted to create
- The specific rule violated

If a real test is too slow or expensive, ask the user — do not silently downgrade to a fake.

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
uvicorn main:app --host 127.0.0.1 --port 10000 --reload  # With reload
```

### Usage with Codex CLI
```bash
# Set environment variable to use proxy
export OPENAI_BASE_URL=http://localhost:10000
codex  # Now uses proxy

# Or one-time usage
OPENAI_BASE_URL=http://localhost:10000 codex
```

### Testing and Validation
```bash
# Health check
curl http://localhost:10000/health

# Test proxy forwarding manually
curl -X POST http://localhost:10000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_token" \
  -d '{"model": "claude-3", "messages": [{"role": "user", "content": "test"}]}'
```

## Architecture Details

### Current Implementation (M2 - Slash Command Processing + Proxy)
- **Entry Point**: `src/codex_plus/main.py` - Thin re-export wrapper
- **Core Application**: `src/codex_plus/main_sync_cffi.py` - FastAPI with integrated LLM execution middleware
- **Middleware**: `src/codex_plus/llm_execution_middleware.py` - Instructs Claude to execute slash commands natively
- **Request Logging**: `src/codex_plus/request_logger.py` - Async logging for debugging
- **Startup**: Via `proxy.sh` or `uvicorn src.codex_plus.main:app --host 127.0.0.1 --port 10000`
- **Control**: `proxy.sh` - Enhanced process management with health checks and cleanup
- **Testing**: Comprehensive test suite in `tests/` directory with CI/CD integration

### Request Flow
1. Codex CLI → HTTP proxy (localhost:10000)
2. **Pre-input Hooks** process request body and apply UserPromptSubmit lifecycle hooks
3. **LLM Execution Middleware** detects slash commands and injects execution instructions
4. **Status Line Middleware** prepares git status information for injection
5. Modified request forwarded to `https://chatgpt.com/backend-api/codex` with preserved headers/streaming
6. **Status Line** injected at start of response stream if available
7. Claude receives instructions to natively execute slash commands by reading `.codexplus/commands/*.md` files
8. **Post-output Hooks** process streaming response (non-blocking)
9. Response streams back through proxy to Codex CLI
10. **Hook Side Effects** execute Stop hooks and other lifecycle events
11. Special handling: `/health` endpoint returns local status (not forwarded)

### Key Components
- **Streaming Support**: `curl_cffi.requests.Session(impersonate="chrome124").request(..., stream=True)` with `iter_content` preserves real-time responses
- **Slash Command Detection**: Regex pattern matching for `/command` syntax in request bodies
- **Command File Resolution**: Searches `.codexplus/commands/` then `.claude/commands/` for command definitions
- **LLM Instruction Injection**: Modifies requests to instruct Claude to execute commands natively
- **Hook System**: Comprehensive lifecycle event support (UserPromptSubmit, PreToolUse, PostToolUse, Stop, etc.)
- **Status Line Middleware**: Git status injection with configurable hooks and async subprocess calls
- **Security Validation**: SSRF protection, header sanitization, upstream URL validation
- **Header Management**: Filters hop-by-hop headers, preserves auth/content headers
- **Error Passthrough**: HTTP errors (401, 429, 500) forwarded transparently
- **Process Management**: Enhanced PID-based daemon control via `proxy.sh` with health checks
- **Async Request Logging**: Branch-specific debugging logs in `/tmp/codex_plus/`
- **Hook Execution**: Settings-driven hooks with JSON stdin/stdout protocol and timeout controls
- **FastAPI Lifespan**: Session start/end hook integration with application lifecycle

## Development Milestones

### ✅ M1: Simple Passthrough Proxy (Complete)
- HTTP proxy intercepting Codex requests via `OPENAI_BASE_URL`
- FastAPI + curl_cffi streaming to `https://chatgpt.com/backend-api/codex`
- Complete TDD test coverage (request forwarding, streaming, errors)
- Process management and health monitoring

### ✅ M2: Slash Command Processing (Complete)
- ✅ Intercept and parse `/command` syntax in request bodies
- ✅ LLM execution middleware that instructs Claude to natively execute commands
- ✅ Command file resolution from `.codexplus/commands/` and `.claude/commands/`
- ✅ Advanced slash commands like `/copilot` for autonomous PR processing
- ✅ Maintain non-slash input passthrough behavior
- ✅ Security validation and SSRF protection

### ✅ M3: Enhanced Features (Complete)
- ✅ Async request logging for debugging
- ✅ Branch-specific log organization
- ✅ Enhanced security validation (header sanitization, upstream URL validation)
- ✅ Comprehensive test coverage expansion
- ✅ Hook system integration (UserPromptSubmit, PreToolUse, PostToolUse, Stop, SessionStart/End)
- ✅ Status line middleware with git status injection
- ✅ Settings-based hooks with JSON stdin/stdout protocol

### 🚧 M4: Advanced Hook Features (In Progress)
- ✅ Complete hook lifecycle event support
- ✅ Settings-driven hook execution with timeouts
- ✅ Pre/post-input hooks with YAML frontmatter and Python classes
- ✅ Hook middleware integration with FastAPI lifespan
- 📋 Advanced command templating and composition
- 📋 Hook debugging and development tools

### 📋 M5: MCP Integration (Planned)
- Remote MCP tool discovery and invocation
- Tool result integration into conversation context
- MCP protocol compatibility with Claude Code CLI conventions

## File Structure
```
codex_plus/
├── src/codex_plus/              # Main package
│   ├── __init__.py
│   ├── main.py                  # Thin re-export wrapper
│   ├── main_sync_cffi.py        # Core FastAPI proxy with middleware
│   ├── llm_execution_middleware.py  # LLM execution middleware
│   ├── request_logger.py        # Async request logging
│   ├── hooks.py                 # Hook system implementation
│   └── status_line_middleware.py # Git status line injection
├── tests/                       # Comprehensive test suite
│   ├── conftest.py              # Pytest configuration
│   ├── test_proxy.py            # Core proxy tests
│   ├── test_enhanced_slash_middleware.py # Slash command tests
│   ├── test_llm_execution.py    # LLM execution tests
│   ├── test_request_logger.py   # Request logging tests
│   ├── test_hooks.py            # Hook system tests
│   ├── test_hooks_integration.py # Hook integration tests
│   ├── test_copilot_command.py  # Copilot command tests
│   └── claude/hooks/            # Hook-specific tests
├── .codexplus/                  # Primary configuration
│   ├── commands/                # Slash command definitions
│   │   ├── copilot.md           # Autonomous PR processing
│   │   ├── echo.md              # Echo test command
│   │   ├── hello.md             # Hello world command
│   │   └── test-args.md         # Argument testing
│   ├── hooks/                   # Hook implementations
│   │   ├── add_context.py       # UserPromptSubmit hook example
│   │   ├── post_add_header.py   # Post-output hook example
│   │   └── shared_utils.py      # Hook utilities
│   └── settings.json            # Project-level hook configuration
├── .github/workflows/           # CI/CD
│   └── tests.yml                # GitHub Actions test workflow
├── scripts/                     # Development and deployment scripts
│   ├── claude_mcp.sh
│   ├── claude_start.sh
│   ├── coverage.sh
│   ├── run_tests_with_coverage.sh
│   └── ...
├── testing_llm/                 # LLM testing documentation
│   ├── 01_basic_proxy_test.md
│   ├── 02_hook_integration.md
│   └── ...
├── infrastructure-scripts/      # Deployment helpers
├── roadmap/                     # Development roadmap
├── proxy.sh                     # Enhanced process control script
├── run_tests.sh                 # Local CI simulation
├── pytest.ini                  # Pytest configuration
├── requirements.txt             # Python dependencies
├── README.md                    # Project documentation
├── product_spec.md             # User stories and acceptance criteria
├── design.md                   # Architecture design
├── AGENTS.md                    # Repository guidelines
└── CLAUDE.md                   # This file - AI assistant guidance
```

## Testing Strategy

**Test-Driven Development (TDD)**: All new features must be implemented with failing tests first, then implementation, then passing tests.

### Test Categories
- **Core Request Interception**: Verify forwarding behavior for different endpoints
- **LLM Execution Middleware**: Test slash command detection and instruction injection
- **Hook System**: Test pre/post-input hooks, lifecycle events, settings-based hooks
- **Security Validation**: SSRF protection, header sanitization, upstream URL validation
- **Streaming Response Types**: Test JSON, SSE, binary streaming preservation
- **Error Conditions**: Ensure 401, 404, 429, 500 errors pass through correctly
- **Special Cases**: Local `/health` endpoint handling
- **Async Request Logging**: Branch-specific logging functionality
- **Integration Tests**: End-to-end testing with real commands and hooks
- **Command Processing**: Test slash command expansion, argument substitution
- **Status Line Middleware**: Test git status injection and formatting

### Test Execution
```bash
# Run full test suite (required before commits)
./run_tests.sh                    # Local CI simulation
pytest -v                         # All tests
pytest tests/test_proxy.py -v     # Core proxy tests
pytest tests/test_enhanced_slash_middleware.py -v  # Middleware tests
pytest tests/test_hooks.py -v     # Hook system tests
pytest tests/test_llm_execution.py -v  # LLM execution tests

# Run with coverage
pytest --cov=src/codex_plus --cov-report=html -v
scripts/run_tests_with_coverage.sh # Coverage with HTML report

# Run specific test patterns
pytest -k "test_slash_command" -v
pytest -k "test_security" -v
pytest -k "test_hooks" -v
pytest -m "not slow" -v          # Skip slow network tests
```

## Implementation Guidelines

### Code Style
- **FastAPI**: Use async/await for all I/O operations
- **Error Handling**: Always preserve upstream HTTP status codes and messages
- **Streaming**: Use `curl_cffi` streaming via `iter_content` for real-time response handling
- **Middleware Pattern**: LLM execution middleware for request modification
- **Logging**: Use structured logging for debugging and monitoring
- **Package Structure**: Proper Python package layout under `src/codex_plus/`

### Security Considerations  
- **SSRF Protection**: Validate upstream URLs and prevent internal network access
- **Header Sanitization**: Remove dangerous headers and prevent header injection
- **Input Validation**: Validate slash commands, paths, and content-length
- **Path Traversal Prevention**: Block attempts to access unauthorized paths
- **Content Size Limits**: Enforce request size limits (10MB default)
- **Process Isolation**: Run proxy with minimal required permissions

### Debugging
```bash
# View real-time logs (enhanced locations)
tail -f /tmp/codex_plus/proxy.log
tail -f /tmp/codex_plus/<branch>/request_payload.json

# Debug with verbose logging
PYTHONPATH=src uvicorn src.codex_plus.main:app --host 127.0.0.1 --port 10000 --log-level debug

# Test connectivity and health
curl -v http://localhost:10000/health
./proxy.sh status

# Test slash command detection
echo '{"input": [{"type": "message", "content": [{"type": "input_text", "text": "/copilot"}]}]}' | \
  curl -X POST http://localhost:10000/responses -H "Content-Type: application/json" -d @-
```

## Integration Notes

### Claude Code CLI Compatibility
- LLM execution middleware instructs Claude to natively execute slash commands
- Command definitions stored in `.codexplus/commands/` and `.claude/commands/`
- Advanced commands like `/copilot` for autonomous PR processing
- Maintains identical UI/UX to Codex CLI while adding power-user features

### Hooks Lifecycle (Anthropic-Aligned)
- Events supported: UserPromptSubmit, PreToolUse, PostToolUse, Notification, Stop, PreCompact, SessionStart, SessionEnd
- Sources: `.codexplus/settings.json` (project first), `.claude/settings.json` (fallback)
- Format (per Anthropic docs):
  {
    "hooks": {
      "EventName": [
        { "matcher": "ToolPattern", "hooks": [ { "type": "command", "command": "...", "timeout": 5 } ] }
      ]
    }
  }
- Execution: commands receive JSON on stdin; exit 2 blocks; stdout JSON may include additionalContext or feedback
- Python .py hooks with YAML frontmatter still work for `pre-input`/`post-output` using `Hook` subclasses

### Implementation Details
- No external scripts in the request path; a lightweight middleware prints git status line
- Settings-driven hooks are executed around `/responses` and detected slash commands
- Session start/end hooks are fired via FastAPI lifespan handlers
- Import safety: we do not mutate `sys.path` when loading hooks; .py hooks import `codex_plus.hooks` directly

### Environment Variables
```bash
export OPENAI_BASE_URL=http://localhost:10000  # Route Codex through proxy
export PYTHONPATH=src                          # For package imports
export NO_NETWORK=1                           # CI simulation mode
```

### Development Workflow
1. **Feature Planning**: Update milestone tracking in CLAUDE.md
2. **TDD Implementation**: Write failing tests first using `./run_tests.sh`
3. **Code Implementation**: Implement minimal code to pass tests
4. **Security Review**: Ensure SSRF protection and input validation
5. **Integration Testing**: Test with actual Codex CLI and slash commands
6. **Documentation**: Update CLAUDE.md and architecture documentation

## Future Considerations

### Scalability
- Multi-user session management and isolation
- Load balancing and rate limiting for production use
- Persistent session storage and state management
- Horizontal scaling with multiple proxy instances

### Extensions
- Plugin system for custom slash commands
- Advanced hook scripting with pre/post processing
- Integration with development environment tools (IDEs, CI/CD)
- Real-time collaboration features
- WebSocket support for enhanced streaming
