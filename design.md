# Codex-Plus Design Document: Hybrid Architecture

**Version:** 2.0  
**Date:** September 7, 2025  
**Architecture:** Node.js Middleware + Python LiteLLM Proxy

## Executive Summary

Codex-Plus uses a hybrid architecture combining Node.js middleware for Codex-specific features (slash commands, hooks, MCP) with Python LiteLLM for robust multi-provider LLM routing. This approach provides the best of both worlds: JavaScript ecosystem flexibility and enterprise-grade LLM proxy capabilities.

## Architecture Overview

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Codex CLI  │───▶│  Node.js Proxy   │───▶│  LiteLLM Proxy  │───▶│  LLM Providers  │
│  (Client)   │    │  (Port 3000)     │    │  (Port 4000)    │    │ (OpenAI/Azure/  │
└─────────────┘    └──────────────────┘    └─────────────────┘    │  Anthropic)     │
                            │                                      └─────────────────┘
                            ▼
                   ┌──────────────────┐
                   │  Codex Features  │
                   │ • Slash Commands │
                   │ • Hooks System   │
                   │ • MCP Integration│
                   │ • Config (.claude│
                   │   /.codex compat)│
                   └──────────────────┘
```

## Component Responsibilities

### Node.js Middleware (Port 3000)
**Purpose:** Handle Codex-Plus specific functionality while preserving streaming

**Responsibilities:**
- Parse and execute slash commands from `.claude/commands/` or `.codex/commands/`
- Execute lifecycle hooks (PreToolUse, PostToolUse, UserPromptSubmit, etc.)
- Handle MCP server integration (HTTP/SSE + OAuth)
- Configuration management with `.claude` → `.codex` fallback
- Security: permission prompts, shell execution controls
- Request preprocessing and response postprocessing

**Technology Stack:**
- **Framework:** Express.js or Fastify
- **Config:** YAML/JSON parsing with environment variable expansion
- **Streaming:** Native Node.js streams with pipeline support
- **Security:** Sandboxed shell execution, regex-based redaction

### Python LiteLLM Proxy (Port 4000)
**Purpose:** Enterprise-grade LLM routing and provider abstraction

**Responsibilities:**
- Multi-provider routing (OpenAI, Anthropic, Azure, ChatGPT subscriptions)
- Load balancing, failover, and circuit breaking
- Cost tracking and usage monitoring
- Streaming response handling
- Rate limiting and caching
- Model aliasing and request transformation

**Technology Stack:**
- **Core:** LiteLLM library with proxy server
- **Installation:** `pip install 'litellm[proxy]'`
- **Configuration:** Environment variables and config files
- **Monitoring:** Built-in Prometheus metrics

## Request Flow

### 1. Normal LLM Request
```
Codex CLI → Node.js (3000) → LiteLLM (4000) → Provider API → Response Stream
```

### 2. Slash Command Request  
```
Codex CLI → Node.js (3000) → Process Command → Generate Prompt → LiteLLM (4000) → Provider → Response
```

### 3. Hook-Enabled Request
```
Codex CLI → Node.js (3000) → PreHook → LiteLLM (4000) → PostHook → Response
```

## Installation & Setup

### Prerequisites
```bash
# Node.js environment
node --version  # v18+
npm --version

# Python environment for LiteLLM
python --version  # 3.8+
pip --version
```

### Step 1: Install LiteLLM
```bash
# Install LiteLLM with proxy support
pip install 'litellm[proxy]'

# Verify installation
litellm --help
```

### Step 2: Configure LiteLLM
```bash
# Create LiteLLM configuration
mkdir -p config
cat > config/litellm_config.yaml << EOF
model_list:
  - model_name: gpt-4
    litellm_params:
      model: openai/gpt-4
      api_key: os.environ/OPENAI_API_KEY
  
  - model_name: claude-3-5-sonnet
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: gpt-5
    litellm_params:
      model: openai/gpt-5
      api_key: os.environ/OPENAI_API_KEY

router_settings:
  routing_strategy: usage-based-routing
  model_group_alias: {"gpt5-high": "gpt-5", "gpt-high": "gpt-5"}

general_settings:
  cost_tracking: true
  stream: true
  max_budget: 100
  budget_duration: 30d
EOF
```

### Step 3: Start LiteLLM Proxy
```bash
# Start LiteLLM proxy on port 4000
litellm --config config/litellm_config.yaml --port 4000 --host 0.0.0.0

# Or with environment variables
OPENAI_API_KEY=your_key ANTHROPIC_API_KEY=your_key \
litellm --config config/litellm_config.yaml --port 4000
```

### Step 4: Install Node.js Dependencies
```bash
# Install core dependencies
npm init -y
npm install express fastify axios dotenv js-yaml marked

# Development dependencies
npm install --save-dev nodemon typescript @types/node
```

## Configuration System

### Directory Structure
```
codex_plus/
├── config/
│   ├── litellm_config.yaml     # LiteLLM proxy configuration
│   └── codex_plus.json         # Node.js middleware config
├── .claude/                    # Primary config directory (checked first)
│   ├── commands/               # Slash commands (Markdown/JS/Python)
│   │   ├── git.md             # /git command
│   │   └── frontend/          # Namespaced commands
│   │       └── component.md   # /component command
│   ├── settings.json          # Hooks and user settings
│   └── .mcp.json             # MCP server configurations
├── .codex/                    # Fallback config directory
│   └── [same structure as .claude]
└── src/
    ├── middleware.js          # Node.js proxy server
    ├── slash_commands.js      # Slash command processor
    ├── hooks.js              # Hook execution engine
    └── mcp_client.js         # MCP integration
```

### Configuration Precedence
1. **Enterprise policies** (read-only, admin-defined)
2. **Command line arguments** (runtime overrides)
3. **Local project** (`.claude/settings.json` or `.codex/settings.json`)
4. **Shared project** (`.mcp.json`, team configurations)
5. **User global** (`~/.claude/settings.json` or `~/.codex/settings.json`)

## Performance Characteristics

### Latency Budget
| Component | Target Latency | Notes |
|-----------|----------------|-------|
| **Node.js Processing** | ≤10ms p95 | Slash commands, hooks |
| **Inter-service Call** | ≤5ms p95 | localhost HTTP |  
| **LiteLLM Processing** | ≤35ms p95 | Provider routing |
| **Total Overhead** | ≤50ms p95 | Codex-Plus added latency |

### Streaming Performance
- **Passthrough Mode:** Zero buffering for normal requests
- **Processed Mode:** Minimal buffering for slash command responses
- **Hook Mode:** Stream after hook completion (configurable)

## Security Model

### Shell Execution
```javascript
// Permission-based shell execution
const executeShell = async (command, context) => {
  // 1. Check if shell execution is allowed for this command
  if (!hasPermission(command, context.allowedTools)) {
    throw new Error('Shell execution not permitted');
  }
  
  // 2. Prompt user for project-scope execution
  if (context.scope === 'project' && !context.trustedProject) {
    const approved = await promptUser('Allow shell execution? (Y/N/A)');
    if (!approved) return null;
  }
  
  // 3. Execute with restrictions
  return await sandboxedExec(command, {
    timeout: 30000,
    outputLimit: 64 * 1024,
    networkAccess: false
  });
};
```

### Data Redaction
```javascript
// Built-in redaction patterns
const REDACTION_PATTERNS = [
  /sk-[a-zA-Z0-9]{20,50}/g,           // OpenAI API keys
  /pk\.[a-zA-Z0-9]{20,50}/g,          // Anthropic API keys  
  /AKIA[0-9A-Z]{16}/g,                // AWS access keys
  /eyJ[a-zA-Z0-9+/=]+\.[a-zA-Z0-9+/=]+\.[a-zA-Z0-9+/=_-]+/g // JWTs
];
```

## Development Workflow

### 1. Development Mode
```bash
# Terminal 1: Start LiteLLM with auto-reload
litellm --config config/litellm_config.yaml --port 4000 --reload

# Terminal 2: Start Node.js middleware with nodemon  
npm run dev  # nodemon src/middleware.js

# Terminal 3: Test with Codex CLI
export OPENAI_BASE_URL=http://localhost:3000
codex "Hello world"
```

### 2. Production Mode
```bash
# Use process managers
pm2 start ecosystem.config.js

# Or systemd services
systemctl start codex-plus-litellm
systemctl start codex-plus-middleware
```

### 3. Testing
```bash
# Health checks
curl http://localhost:3000/health    # Node.js middleware
curl http://localhost:4000/health    # LiteLLM proxy

# End-to-end test
curl -X POST http://localhost:3000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4", "messages": [{"role": "user", "content": "test"}]}'
```

## Monitoring & Observability

### Metrics Collection
- **Node.js:** Custom Express middleware for request/response timing
- **LiteLLM:** Built-in Prometheus metrics export
- **Combined:** Unified dashboard showing end-to-end performance

### Key Metrics
- Request count and error rates
- Latency histograms (p50, p95, p99)
- Cost tracking per model/provider
- Hook execution times
- MCP server health and circuit breaker status

## Migration Strategy

### Phase 1: LiteLLM Foundation (Week 1)
1. Install and configure LiteLLM proxy
2. Test provider connectivity (OpenAI, Anthropic)
3. Verify streaming and cost tracking
4. Replace current Python proxy logic

### Phase 2: Node.js Middleware (Week 2)
1. Build Express.js proxy server
2. Implement basic request forwarding to LiteLLM
3. Add slash command parsing and execution
4. Implement configuration system (.claude/.codex)

### Phase 3: Advanced Features (Week 3-4)
1. Hook system implementation
2. MCP integration with HTTP/SSE support
3. Security controls and permission prompts
4. Performance optimization and monitoring

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| **LiteLLM Dependency** | High | Pin versions, maintain fallback to direct API calls |
| **Inter-service Latency** | Medium | Monitor closely, optimize request pipeline |
| **Configuration Complexity** | Low | Comprehensive documentation, validation tools |
| **Security Vulnerabilities** | High | Regular dependency updates, sandbox restrictions |

## Future Considerations

### Scalability
- **Horizontal scaling:** Load balancer → multiple Node.js instances → shared LiteLLM
- **Caching:** Redis integration for configuration and response caching
- **Multi-tenant:** Separate LiteLLM instances per organization/team

### Enterprise Features
- **SAML/SSO integration** for MCP authentication
- **Advanced audit logging** with structured export
- **Custom model fine-tuning** pipeline integration
- **Real-time cost alerts** and budget enforcement