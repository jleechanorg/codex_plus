# Codex-Plus — Product Specification (v2.0)

- Product: Codex-Plus
- Version: 2.0
- Status: Proposed  
- Date: September 7, 2025
- Authors: Development Team

## Executive Summary

Codex-Plus is an HTTP proxy that enhances Codex CLI with power-user features while maintaining identical UI/UX. It operates transparently through environment variable configuration and supports both individual developer workflows and optional enterprise governance.

**Core Features:**
- HTTP proxy integration preserving streaming responses and interactive prompts
- Extensible slash commands with metadata, arguments, and shell/file integration
- Lifecycle hooks for workflow automation at key interaction points
- Remote MCP server support with HTTP/SSE transports and OAuth authentication
- Configuration compatibility system (.claude directories with .codex fallback)
- Optional enterprise features: allowlists, auditing, security policies

**Target Users:**
- **Developers**: Individual workflows with hooks, custom commands, remote MCP tools
- **Teams**: Optional governance, shared configurations, observability
- **Enterprises**: Security policies, audit trails, cost management

## Vision

Codex-Plus is a control plane for AI-assisted development that enhances Codex CLI through an HTTP proxy architecture. It maintains identical terminal experience while adding extensibility through slash commands, hooks, and MCP integrations. The system supports individual developer productivity and scales to enterprise governance without changing core workflows.

## Product Principles

- **Transparent Integration**: HTTP proxy preserves exact Codex CLI experience via `OPENAI_BASE_URL` environment variable
- **Configuration Compatibility**: Check `.claude/` directories first, fallback to `.codex/` for backward compatibility  
- **Extensible by Design**: Simple, discoverable ways to add commands, integrate tools, and automate workflows
- **Security by Default**: Shell execution requires explicit permissions; sensitive data redacted automatically
- **Enterprise Ready**: Optional governance features don't impact individual developer experience

## Core User Stories & Requirements

### 1) HTTP Proxy Integration [MUST]

**User Story:** As a Codex CLI user, I want to enable enhanced features without changing my workflow, so I can add capabilities incrementally.

**Implementation:** HTTP proxy intercepts Codex CLI requests via `OPENAI_BASE_URL=http://localhost:3000`

**Acceptance Criteria:**
- Starting and using the product is indistinguishable from Codex CLI in prompts, streaming, colors, keyboard behavior, and interaction flow
- All non-slash input behaves exactly as in Codex CLI with ≤50ms added latency (p95)
- Interactive question/answer flows remain smooth (e.g., confirmations)
- Real-time streaming responses preserved with ≤0.01% mid-response errors per 10k requests

### 2) Enhanced Slash Commands [MUST]

**User Story:** As a power user, I want sophisticated slash commands with arguments, file references, and shell integration so I can automate complex workflows.

**Implementation:** 
- Markdown files in `.codexplus/commands/` (primary) and `.claude/commands/` (compatibility)
- YAML frontmatter: `allowed-tools`, `argument-hint`, `description`, `model`
- Subdirectories create namespaced commands (e.g., `.claude/commands/frontend/component.md` → `/component` with "(project:frontend)" description)
- Argument placeholders: `$ARGUMENTS` (all args), `$1 $2` (positional)
- Shell inclusion: `!`git status`` (requires `allowed-tools` permissions)
- File references: `@src/utils/helpers.js`
- Advanced commands via JS/Python exports: `module.exports = (args) => { /* logic */ return prompt; }`

**Acceptance Criteria:**
- Slash commands execute immediately without altering non-slash behavior
- `/help` lists available commands with scopes, descriptions, and argument hints
- Dry-run preview shows resolved prompt/commands before execution
- Shell inclusion disabled by default; requires explicit allowlist per command
- Commands support cross-platform environments (Windows/WSL via cmd /c)

### 3) Lifecycle Hooks [MUST]

**User Story:** As a developer, I want to automate workflow steps at key interaction points so I can integrate with my development environment.

**Implementation:**
- Events: `PreToolUse`, `PostToolUse`, `Notification`, `UserPromptSubmit`, `Stop`, `SubagentStop`, `PreCompact`, `SessionStart`, `SessionEnd`
- Configured via `/hooks` slash command with matchers (ToolPattern like `Task`, `Bash`, `*` for all)
- Stored in `~/.claude/settings.json` (checked first) or `~/.codex/settings.json` (fallback)
- Project-level: `.claude/settings.json` or `.codex/settings.json`

**Acceptance Criteria:**
- Hooks execute at specified lifecycle points with JSON input
- Security prompts for shell execution in project scope: "Allow? (Y)es/(N)o/(A)lways"
- Home directory (`~/`) trusted by default; project directory (`./`) requires approval
- Restricted environment: timeouts (configurable per hook), output caps (64KB), no network by default
- Declared permissions required (e.g., `run:prettier`, `read_repo`, `read_env:GITHUB_TOKEN`)

### 4) Remote MCP Integration [MUST]

**User Story:** As a user of external tools, I want to connect to remote MCP servers with authentication so I can use services like GitHub, Linear, or Airtable within my session.

**Implementation:**
- Transport support: stdio, HTTP, SSE
- Command: `codex-plus mcp add <name> <command>` (stdio), `--transport sse <name> <url>` (SSE)
- OAuth 2.0 authentication managed via `/mcp` command
- Scopes: local (project-specific, default), project (shared via `.mcp.json`), user (across projects)
- Environment variables: `--env AIRTABLE_API_KEY=YOUR_KEY`
- Resource references: `@<server>:<resource>` (e.g., `@github:issue://123`)
- Exposed slash commands: `/mcp__github__list_prs`

**Acceptance Criteria:**
- MCP servers connect via HTTP/SSE with OAuth authentication
- `@<server>:<resource>` mentions work in prompts
- MCP prompts exposed as discoverable slash commands with argument hints
- `/mcp list` shows servers, resources, and available prompts
- Per-server circuit breaker (3 failures, 60s cooldown) with graceful degradation
- Output limits configurable via `MAX_MCP_OUTPUT_TOKENS` (default 25,000)
- PII guardrail: prompt text not sent to MCP unless explicitly enabled

### 5) Configuration Compatibility [MUST]

**User Story:** As a Claude Code CLI user, I want my existing configurations to work while having the option to use new features.

**Implementation:** Check `.claude/` directories first, fallback to identical `.codex/` directories with same formats

**Acceptance Criteria:**
- Configuration precedence: enterprise > cmd args > local project > shared project > user
- `/plus status` or `/config list` shows unified view merging all sources
- Environment variable expansion: `${VAR:-default}`
- Guided onboarding via `codex-plus init`

### 6) Security & Permissions [MUST]

**User Story:** As a security-conscious user or enterprise admin, I want explicit control over shell execution, data access, and external connections.

**Implementation:**
- Shell execution requires explicit permissions and user approval
- Default redaction patterns for API keys, JWTs, AWS credentials
- Configurable sensitive file blocking: `permissions.deny` (e.g., `Read(./.env)`)
- Optional signed command/hook packs for enterprise (e.g., minisign)

**Acceptance Criteria:**
- First shell execution in project prompts for approval
- Sensitive data automatically redacted in logs and outputs  
- Command provenance displayed before first run
- Enterprise mode can require signed artifacts (`requireSigned: true`)

### 7) Enterprise Features [SHOULD]

**User Story:** As an enterprise admin, I want governance controls for model access, endpoints, and audit trails.

**Implementation:**
- Model allowlists with runtime enforcement
- Endpoint allowlists blocking unauthorized URLs
- Structured audit logs with redaction, exportable to SIEM
- Prometheus/JSON metrics export

**Acceptance Criteria:**
- Blocked models show clear error: "This workspace allows: ${models}"
- Unauthorized endpoints return 403 with guidance
- Metrics track request count, status codes, latency histograms
- 99.9% monthly uptime excluding ≤30min planned maintenance

### 8) Performance & Reliability [SHOULD]

**User Story:** As a daily user, I want the proxy to be fast and reliable so it doesn't interfere with my flow.

**Acceptance Criteria:**
- Latency overhead ≤50ms p95, ≤85ms p99 across 10k requests
- Stream integrity: ≤0.01% mid-response errors with automatic retry
- Responsive during long outputs and extended sessions
- Accessibility: coherent sentence chunks for screen readers, alt text for rich outputs

## Built-in Commands

| Command | Description | Usage |
|---------|-------------|--------|
| `/help` | List all slash commands with scopes, descriptions, and argument hints | `/help [pattern]` |
| `/status` | Show proxy status, active MCP servers, and configuration sources | `/status` |
| `/hooks` | Configure lifecycle hooks interactively | `/hooks` |
| `/mcp` | Manage MCP server connections and authentication | `/mcp add/list/auth` |
| `/plus` | Unified configuration view and system management | `/plus status/init` |
| `/save` | Export current session transcript | `/save [filename]` |

## Technical Architecture

### High-Level Design
```
Codex CLI → HTTP Proxy (localhost:3000) → OpenAI API
    ↓
Config Manager (.claude → .codex fallback)
    ↓
Slash Command Engine (MD/JS/Python)
    ↓  
Hook System (Lifecycle Events)
    ↓
MCP Client (HTTP/SSE + OAuth)
    ↓
Metrics & Security (Prometheus + Audit)
```

### Implementation Stack
- **Language**: Node.js with optional Python support
- **Proxy**: Express.js or Fastify with streaming support
- **Config**: YAML/JSON parsing with environment variable expansion
- **Security**: Sandboxed shell execution, permission-based access
- **MCP**: HTTP/SSE clients with OAuth 2.0 flow
- **Metrics**: Prometheus client with histogram/gauge support

### Configuration Precedence
1. **Enterprise** (read-only admin policies)
2. **Command Arguments** (runtime overrides)
3. **Local Project** (`.claude/settings.json` or `.codex/settings.json`)
4. **Shared Project** (`.mcp.json`, team configurations)
5. **User Global** (`~/.claude/settings.json` or `~/.codex/settings.json`)

## Configuration Examples

### Slash Command (Markdown)
```markdown
---
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*)
argument-hint: [message]
description: Create a git commit with staging
model: claude-3-5-haiku-20241022
---

Stage all changes and create commit with message: $ARGUMENTS

Current status:
!`git status --porcelain`

Review changes:
!`git diff --cached`
```

### Advanced Slash Command (JavaScript)
```javascript
module.exports = (args) => {
  const branch = args[0] || 'main';
  return `Analyze the diff for branch ${branch}: !`git diff ${branch}...HEAD``;
};
```

### Hook Configuration
```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Write",
      "command": "echo 'Writing to: $file' >> .codex-plus.log",
      "timeout": 5,
      "permissions": ["run:echo"]
    }],
    "PostToolUse": [{
      "matcher": "*",
      "command": "notify-send 'Tool completed: $tool'",
      "permissions": ["run:notify-send"]
    }]
  }
}
```

### MCP Configuration
```json
{
  "mcpServers": {
    "github": {
      "transport": "sse",
      "url": "https://mcp.github.com/sse",
      "auth": {
        "type": "oauth2",
        "scopes": ["repo:read", "issues:read"]
      }
    },
    "airtable": {
      "command": "npx -y airtable-mcp-server",
      "env": {"AIRTABLE_API_KEY": "${AIRTABLE_API_KEY}"}
    }
  }
}
```

## Use Cases & Examples

### Developer Workflow Automation
```bash
# Setup custom git workflow
echo "---\nallowed-tools: Bash(git:*)\n---\n!`git status`\n!`git add -A`\n!`git commit -m '$ARGUMENTS'`" > ~/.claude/commands/commit.md

# Use in session
/commit "feat: add user authentication"
```

### Team MCP Integration  
```bash
# Admin adds shared MCP server
codex-plus mcp add --scope project --transport sse linear https://mcp.linear.app

# Developers use in conversation
"Review issue @linear:issue://ENG-123 and create implementation plan"
```

### Enterprise Security
```json
{
  "security": {
    "modelAllowlist": ["claude-3-5-sonnet", "claude-3-5-haiku"],
    "endpointAllowlist": ["api.anthropic.com", "api.openai.com"],
    "requireSigned": true,
    "permissions": {
      "deny": ["Read(./.env)", "Read(secrets/**)", "Bash(rm:*)"]
    }
  }
}
```

## Success Metrics & SLOs

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Latency Overhead** | ≤50ms p95, ≤85ms p99 | Rolling 10k requests |
| **Stream Integrity** | ≤0.01% mid-response errors | Rolling 10k requests |
| **Uptime** | 99.9% monthly | Excluding ≤30min planned maintenance |
| **Hook Execution** | ≤5s timeout default | Per-hook configurable |
| **MCP Response** | Circuit breaker at 3 failures | 60s cooldown per server |

## Implementation Roadmap

### Phase 1: Core Proxy (Q4 2025)
- ✅ HTTP proxy with streaming support
- ✅ Basic slash commands (Markdown)
- ✅ Configuration system (.claude/.codex)
- [ ] Hook system (PreToolUse, PostToolUse)
- [ ] Security permissions and prompts

### Phase 2: MCP & Advanced Features (Q1 2026)  
- [ ] Remote MCP (HTTP/SSE transport)
- [ ] OAuth 2.0 authentication flow
- [ ] Advanced slash commands (JS/Python)
- [ ] Circuit breaker and PII protection
- [ ] Unified configuration view

### Phase 3: Enterprise & Polish (Q2 2026)
- [ ] Model/endpoint allowlists
- [ ] Signed command packs
- [ ] Prometheus metrics export
- [ ] Audit logging and SIEM integration
- [ ] Performance optimization

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Upstream API Changes** | High | Version compatibility checks, graceful degradation |
| **Security Vulnerabilities** | High | Sandboxed execution, permission prompts, code signing |
| **Performance Degradation** | Medium | Async operations, connection pooling, metrics monitoring |
| **MCP Server Failures** | Medium | Circuit breakers, graceful fallbacks, retry logic |
| **Configuration Complexity** | Low | Guided onboarding, unified status view, validation |

## Compatibility & Migration

- **Codex CLI Compatibility**: v0.29+ required, auto-detected via `/version`
- **Claude Code CLI**: Slash commands follow established conventions
- **Configuration Migration**: Automatic `.codex` → `.claude` detection and migration prompts
- **Rollback**: Simple environment variable unset restores original Codex CLI behavior

## Competitive Positioning

| Capability | Codex-Plus | GitHub Copilot | Cursor | Claude Code |
|------------|------------|----------------|--------|-------------|
| **Proxy Governance** | ✅ Full | ❌ None | ❌ None | ❌ None |
| **Remote MCP** | ✅ HTTP/SSE/OAuth | ❌ None | ❌ None | ⚠️ Limited |
| **Enterprise Security** | ✅ Allowlists/Audit | ⚠️ Limited | ❌ None | ❌ None |
| **CLI Experience** | ✅ Identical | ⚠️ Different | ⚠️ Different | ✅ Identical |
| **Extensibility** | ✅ Hooks/Commands | ⚠️ Extensions | ⚠️ Limited | ⚠️ Limited |
