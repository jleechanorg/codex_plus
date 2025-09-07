# Codex-Plus

**IDE in the terminal that looks exactly like Codex CLI but adds power-user features**

Codex-Plus provides an "IDE in the terminal" experience that is indistinguishable from Codex CLI, adding slash commands, hooks, remote MCP tools, and persistent sessions without changing how users interact.

## Features

- ✅ **Identical Terminal Experience**: Looks and behaves exactly like Codex CLI
- ✅ **Slash Commands**: Follow Claude Code CLI conventions (`/help`, `/status`, `/save`, etc.)
- ✅ **Pre-Input & Post-Output Hooks**: Enrich prompts and act on responses
- ✅ **Remote MCP Tools**: Use external tools within the session
- ✅ **Persistent Sessions**: Resume work exactly where you left off
- ✅ **Predictable Cost Mode**: Optional fixed-cost usage when available

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
OPENAI_BASE_URL=http://localhost:3000 codex
```

## Environment Setup

To use Codex-Plus seamlessly, add this to your `~/.bashrc` or `~/.zshrc`:

```bash
# Codex-Plus proxy configuration
export OPENAI_BASE_URL=http://localhost:3000

# Optional: Create alias for convenience
alias codex-plus='OPENAI_BASE_URL=http://localhost:3000 codex'
```

After adding to your shell config:
```bash
source ~/.bashrc  # or ~/.zshrc
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_BASE_URL` | `https://api.openai.com` | Routes Codex CLI through the proxy when set to `http://localhost:3000` |

### Usage Patterns

```bash
# Persistent (recommended): Set in shell config
export OPENAI_BASE_URL=http://localhost:3000
codex  # Always uses proxy

# One-time usage
OPENAI_BASE_URL=http://localhost:3000 codex

# Using alias (if configured)
codex-plus

# Direct Codex CLI (bypass proxy)
OPENAI_BASE_URL=https://api.openai.com codex
```

## Architecture

Codex-Plus works by intercepting Codex CLI requests through an HTTP proxy:

1. **HTTP Proxy Layer**: FastAPI server that intercepts OpenAI API calls
2. **Request Processing**: Parses slash commands, applies hooks, handles MCP tools
3. **Response Enhancement**: Post-processes responses and maintains session state
4. **Transparent Passthrough**: Non-slash input behaves exactly like Codex CLI

## User Stories

See [product_spec.md](./product_spec.md) for complete user stories and acceptance criteria.

## Development Status

- ✅ **M1: Simple Passthrough Proxy** - HTTP proxy foundation complete
- 🚧 **M2: Slash Command Processing** - In development
- 📋 **M3: Hook System** - Planned  
- 📋 **M4: MCP Integration** - Planned

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