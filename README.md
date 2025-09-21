# Codex-Plus

**HTTP proxy that enhances Codex CLI with power-user features while maintaining identical UI/UX**

Codex-Plus is an HTTP proxy that intercepts Codex CLI requests to add slash commands, hooks, MCP tools, and status line enhancements. It preserves the exact terminal experience while adding extensibility through a sophisticated middleware architecture.

## Features

- ✅ **Transparent HTTP Proxy**: Intercepts Codex CLI via `OPENAI_BASE_URL` environment variable
- ✅ **Advanced Slash Commands**: LLM execution middleware with command file discovery (`.codexplus/commands/`, `.claude/commands/`)
- ✅ **Comprehensive Hook System**: Pre/post-input hooks with Anthropic-aligned lifecycle events
- ✅ **Status Line Integration**: Git status injection with configurable middleware
- ✅ **curl_cffi Cloudflare Bypass**: Chrome impersonation for reliable ChatGPT backend access
- ✅ **Security Validation**: SSRF protection, header sanitization, and input validation
- ✅ **Async Request Logging**: Branch-specific debugging with structured payloads

## Quick Start

```bash
# Clone and setup
git clone https://github.com/jleechanorg/codex_plus.git
cd codex_plus

# Install dependencies  
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Start the proxy
./proxy.sh

# In another terminal, use Codex with interceptor
OPENAI_BASE_URL=http://localhost:10000 codex
```

## Environment Setup

To use Codex-Plus seamlessly, add this to your `~/.bashrc` or `~/.zshrc`:

```bash
# Codex-Plus proxy configuration
export OPENAI_BASE_URL=http://localhost:10000

# Optional: Create alias for convenience
alias codex-plus='OPENAI_BASE_URL=http://localhost:10000 codex'
```

After adding to your shell config:
```bash
source ~/.bashrc  # or ~/.zshrc
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_BASE_URL` | `https://api.openai.com` | Routes Codex CLI through the proxy when set to `http://localhost:10000` |

### Usage Patterns

```bash
# Persistent (recommended): Set in shell config
export OPENAI_BASE_URL=http://localhost:10000
codex  # Always uses proxy

# One-time usage
OPENAI_BASE_URL=http://localhost:10000 codex

# Using alias (if configured)
codex-plus

# Direct Codex CLI (bypass proxy)
OPENAI_BASE_URL=https://api.openai.com codex
```

## Architecture

Codex-Plus uses a FastAPI proxy with curl_cffi to bypass Cloudflare and connect directly to ChatGPT backend:

1. **HTTP Proxy Layer**: FastAPI server intercepting requests at `localhost:10000`
2. **LLM Execution Middleware**: Detects slash commands and instructs Claude to execute command files
3. **Hook System**: Pre/post-input hooks with UserPromptSubmit, PreToolUse, PostToolUse lifecycle events
4. **Status Line Middleware**: Injects git status information into response streams
5. **Security Layer**: SSRF protection, header sanitization, upstream URL validation
6. **Request Logger**: Async logging to `/tmp/codex_plus/{branch}/` for debugging
7. **Cloudflare Bypass**: `curl_cffi.requests.Session(impersonate="chrome124")` for reliable access

## User Stories

See [product_spec.md](./product_spec.md) for complete user stories and acceptance criteria.

## Implementation Status

- ✅ **M1: Simple Passthrough Proxy** - Complete with curl_cffi Cloudflare bypass
- ✅ **M2: Slash Command Processing** - Complete with LLM execution middleware
- ✅ **M3: Hook System** - Complete with Anthropic-aligned lifecycle events
- 🚧 **M4: Enhanced Features** - Status line, security validation, async logging complete
- 📋 **M5: MCP Integration** - Planned for future releases

## Available Slash Commands

| Command | Description | File Location |
|---------|-------------|---------------|
| `/copilot` | Autonomous PR processing with comment coverage tracking | `.codexplus/commands/copilot.md` |
| `/echo` | Echo arguments for testing | `.codexplus/commands/echo.md` |
| `/hello` | Simple greeting with timestamp and fun facts | `.codexplus/commands/hello.md` |
| `/test-args` | Test argument passing and parsing | `.codexplus/commands/test-args.md` |

## Development Workflow

### Setup and Running
```bash
# Setup virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Start proxy (managed)
./proxy.sh enable

# Start proxy (development with reload)
uvicorn src.codex_plus.main:app --host 127.0.0.1 --port 10000 --reload

# Check proxy status
./proxy.sh status

# Stop proxy
./proxy.sh disable
```

### Testing
```bash
# Run full test suite
./run_tests.sh

# Run specific tests
pytest tests/test_proxy.py -v
pytest tests/test_enhanced_slash_middleware.py -v
pytest tests/test_hooks.py -v

# Run with coverage
pytest --cov=src/codex_plus --cov-report=html -v

# Run fast tests only (skip slow network tests)
pytest -m "not slow" -v
```

### Health Checks
```bash
# Test proxy health
curl http://localhost:10000/health

# Test with Codex CLI
OPENAI_BASE_URL=http://localhost:10000 codex "test message"

# Test slash command
OPENAI_BASE_URL=http://localhost:10000 codex "/echo hello world"
```

## Project Principles

- **UI Parity**: Looks and behaves exactly like Codex CLI
- **Non-Invasive**: Zero learning curve, feels the same as Codex CLI
- **Extensible by Design**: Simple ways to add commands and integrate tools
- **Predictable Costs Option**: Fixed-cost usage plans where available
- **Fast and Reliable**: Instantaneous interactions and resilient sessions

## License

MIT License - see [LICENSE](./LICENSE) file for details.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for contribution guidelines.