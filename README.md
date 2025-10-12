# Codex-Plus

> ⚠️ **Prototype ahead:** Codex-Plus is an actively evolving experiment. Expect rough edges and be prepared to tweak scripts, paths, and shell configuration for your local environment.

Codex-Plus is a FastAPI-based HTTP proxy that augments the Codex CLI with live status line telemetry, slash command orchestration, and Anthropic-aligned hooks—without altering the CLI UX. These three layers are the primary value-add: real-time status context, declarative slash automation, and lifecycle hooks that drive custom workflows. The proxy forwards authenticated Codex traffic to the ChatGPT backend using `curl_cffi` Chrome impersonation so that all original capabilities remain available.

## Quick Start

```bash
# Clone and bootstrap
git clone https://github.com/jleechanorg/codex_plus.git
cd codex_plus
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure your shell helpers (detects bashrc/zshrc automatically)
./install.sh

# Launch the proxy
./proxy.sh

# Use Codex (routes through proxy when the managed process is alive)
codex "hello"
```

The generated shell snippet adds a `codex()` wrapper that automatically routes through `http://localhost:10000` whenever `proxy.sh` is running, along with a `codexd` alias for fast development mode. If you prefer manual control, export `OPENAI_BASE_URL=http://localhost:10000` before running `codex`.

### Shell Integration Details

`install.sh` inspects your default shell (`$SHELL`) and updates the first matching file from `~/.bashrc`, `~/.bash_profile`, `~/.zshrc`, `~/.zprofile`, or `~/.profile`. The appended block:

- Exports `CODEX_PLUS_REPO` so helper aliases can call `proxy.sh` from anywhere.
- Sets `CODEX_PLUS_PROXY_PORT=10000` for consistent tooling.
- Defines `codex_plus_proxy()` and the `codex-plus-proxy` alias for interacting with `proxy.sh` (`enable`, `disable`, `status`, etc.).
- Wraps the `codex` function to only hijack calls when the proxy PID file indicates an active process, falling back to the system `codex` binary otherwise.

Re-run `./install.sh` if you relocate the repo or switch shells, and double-check the appended snippet to make sure it matches your local workflow.

## Feature Highlights

- **Transparent proxying:** `src/codex_plus/main_sync_cffi.py` uses `curl_cffi.requests.Session(impersonate="chrome124")` to forward Codex CLI requests directly to `https://chatgpt.com/backend-api/codex` while preserving streaming behavior.
- **Slash command orchestration:** `src/codex_plus/llm_execution_middleware.py` discovers markdown command definitions in `.codexplus/commands/` (and the legacy `.claude/commands/`) and prompts Claude to execute them with argument substitution.
- **Hook lifecycle engine:** `src/codex_plus/hooks.py` loads Python hooks and declarative JSON entries from `.codexplus/hooks/`, `.claude/hooks/`, and associated settings files, honoring priority, enable flags, and Anthropic lifecycle events (UserPromptSubmit, PreToolUse, PostToolUse, Stop, etc.).
- **Status line middleware:** `src/codex_plus/status_line_middleware.py` fuses hook-produced status lines with fallback Git metadata when command hooks do not respond in time.
- **Request logging:** `src/codex_plus/request_logger.py` captures structured payloads under `/tmp/codex_plus/<branch>/` for debugging and branch-specific auditing.
- **Safety guardrails:** SSRF protection, header sanitization, and upstream validation run before forwarding to the ChatGPT backend.

Explore `.codexplus/commands/` for ready-to-run slash commands like `/copilot`, `/echo`, `/hello`, and `/test-args`. You can also check `.codexplus/hooks/` for Python hook samples with YAML/docstring metadata. Running `./install.sh` now mirrors these commands into `~/.codexplus/commands/` and `~/.claude/commands/`. This ensures they remain available when you work inside other repositories (including `/reviewdeep`).

## Repository Tour

| Path | Purpose |
| --- | --- |
| `src/codex_plus/` | Core proxy modules (`main_sync_cffi.py`, middleware, hook system, logging). |
| `.codexplus/` | Project-scoped commands and hook examples loaded at runtime. |
| `scripts/` | Operational helpers (Codex/Claude launcher scripts, coverage, CI utilities, macOS launchd integration). |
| `tests/` | Pytest suite covering proxy routing, middleware behavior, hooks, and logging. |
| `run_tests.sh` | Convenience wrapper that mirrors CI expectations before committing. |
| `proxy.sh` | Managed lifecycle for starting/stopping the FastAPI proxy on port 10000. |
| `product_spec.md`, `design.md`, `roadmap/` | Product requirements, design explorations, and planning artifacts. |

Additional architecture notes and guardrails live in [CLAUDE.md](./CLAUDE.md) and [AGENTS.md](./AGENTS.md); read them before making changes to critical proxy paths.

## Development & Testing

```bash
# Run the primary test suite
./run_tests.sh

# Or target specific cases
pytest tests/test_proxy.py -v
pytest tests/test_enhanced_slash_middleware.py -v
pytest tests/test_hooks.py -v

# Coverage support
pytest --cov=src/codex_plus --cov-report=html -v
scripts/run_tests_with_coverage.sh
```

Set `NO_NETWORK=1` to force network-dependent tests into mocked mode. When manually validating, ensure authenticated Codex CLI calls succeed (200 responses) and unauthenticated requests still return 401.

## Operational Guardrails

- **Do not modify protected files**: `src/codex_plus/main_sync_cffi.py`, `src/codex_plus/llm_execution_middleware.py`, `src/codex_plus/main.py`, and `proxy.sh` have strict invariants. Breaking `curl_cffi` usage, the upstream URL, or port 10000 will render the proxy unusable.
- **Respect hook boundaries**: Only extend behavior via middleware, hooks, or the command system. Avoid altering authentication header forwarding logic or streaming response handling.
- **Security posture**: Never log authentication tokens or session cookies; use the structured logger utilities instead of ad-hoc prints.

## Troubleshooting Tips

- Verify the proxy PID file lives in `/tmp/codex_plus/proxy.pid`. If stale, run `./proxy.sh disable` followed by `./proxy.sh enable`.
- If slash commands or hooks fail to load, inspect the logs emitted by `HookSystem` and `llm_execution_middleware` (they emit detailed INFO/DEBUG traces).
- Status line glitches often come from slow custom commands—tune the timeout in `.codexplus/settings.json` or rely on the built-in Git fallback.

## License

Codex-Plus is released under the [MIT License](./LICENSE).

---

Because this project is still a prototype, expect to adapt the automation, shell helpers, and infrastructure scripts to match your local environment (e.g., alternate shells, package managers, or API credentials). Contributions are welcome—just coordinate major changes through issues or discussions first.
