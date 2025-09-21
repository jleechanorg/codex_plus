# AGENTS.md

This repository is agent-friendly. If you are an agent (e.g., Codex CLI, Claude Code), follow these guidelines when making changes. Always read CLAUDE.md first — it is the single source of truth for project invariants.

Link: CLAUDE.md

## Scope and Precedence
- This AGENTS.md applies repo-wide unless a deeper nested AGENTS.md overrides specific sections.
- CLI invariants and proxy rules in CLAUDE.md take precedence over anything here.
- Direct user/developer instructions in the active task supersede AGENTS.md when in conflict.

## Non‑Negotiable Invariants (mirror of CLAUDE.md)
- Use `curl_cffi.requests.Session(impersonate="chrome124")` for upstream calls.
- Forward to `https://chatgpt.com/backend-api/codex` unchanged (no API keys).
- Do not add external script calls in the critical request path.
- Maintain streaming behavior and correct header filtering.

## Hooks Lifecycle (Anthropic-Aligned)
- Supported events: `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Notification`, `Stop`, `PreCompact`, `SessionStart`, `SessionEnd`.
- Settings sources: `.codexplus/settings.json` (higher priority), `.claude/settings.json`.
- Schema: see CLAUDE.md; hooks use `type: "command"`, receive JSON via stdin, exit code `2` blocks.
- .py file hooks with YAML frontmatter still work for `pre-input`/`post-output` by subclassing `codex_plus.hooks.Hook`.
- The proxy uses FastAPI lifespan to trigger `SessionStart`/`SessionEnd`.
- The hook loader does not mutate `sys.path`; .py hooks should import `codex_plus.hooks` directly.

## Code Change Etiquette
- Prefer surgical patches; keep changes minimal and targeted.
- For new behavior, add tests under `tests/` using the patterns already present (TDD where possible).
- Avoid global state where feasible; prefer lifespan or explicit DI for setup/teardown.
- Logging: use the existing `logging` instances; prefer INFO for lifecycle and DEBUG for deep traces.

## Testing Guidance
- Run `pytest -q` before pushing.
- Network-dependent tests must default to mock/fallbacks (CI sets `NO_NETWORK=1`).
- When patching HTTP, avoid caching session objects so test patches apply.
- Keep tests hermetic: write temp files under `/tmp/<branch>` or pytest tmp paths; clean up artifacts.

## Git and PR Workflow
- Commit messages: concise prefix + scope (e.g., `fix(middleware): …`, `refactor(hooks): …`, `test(hooks): …`).
- Update the PR description with a File Justification section:
  - Goal, Modifications, Necessity, Integration Proof.
- For comment processing, prefer `/commentfetch` → analysis → `/commentreply` with structured `responses.json`.

## Directory Conventions
- `src/codex_plus/`: Python proxy and middleware — keep code async-safe, streaming-friendly.
- `.codexplus/hooks/`: Project-specific Python hooks (YAML frontmatter) and helper scripts for settings hooks.
- `.claude/hooks/`: Legacy/demo hooks; safe to ignore if no frontmatter; avoid changes unless needed.
- `tests/`: Unit/integration tests — prefer mocking upstream and side-effects through temp markers.
- `docs/`: Update CLAUDE.md when changing invariants or lifecycle; keep AGENTS.md in sync (and vice versa).

## Security & Secrets
- Never log tokens or secrets. Mask sensitive paths in CI logs.
- Command hooks execute with developer credentials; keep them minimal and time-bounded.

## Agent UX
- Use short preamble messages describing grouped actions and plans.
- Maintain an `update_plan` with compact, verifiable steps for multi-phase tasks.
- Keep responses concise; link to file paths instead of pasting large content.

## Quick Checklists

Pre-Push:
- [ ] `pytest -q` green
- [ ] No external scripts on request path
- [ ] Hooks loader avoids `sys.path` mutation
- [ ] Docs updated (CLAUDE.md/AGENTS.md) if lifecycle changed

PR Update:
- [ ] File Justification (Goal, Modifications, Necessity, Integration Proof)
- [ ] Note test coverage or new tests added

