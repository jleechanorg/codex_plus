# AGENTS.md

This repository is agent-friendly. If you are an agent (e.g., Codex CLI, Claude Code), follow these guidelines when making changes:

- Always consult CLAUDE.md first. It contains the authoritative constraints and protocols for this project (proxy invariants, testing approach, and feature architecture). See: CLAUDE.md

- Hooks lifecycle (high level):
  - We support Anthropic-style hooks configured via `.codexplus/settings.json` and `.claude/settings.json`.
  - Events: UserPromptSubmit, PreToolUse, PostToolUse, Notification, Stop, PreCompact, SessionStart, SessionEnd.
  - Use the exact schema in CLAUDE.md; command hooks receive JSON on stdin and can block with exit code 2.

- Code changes etiquette:
  - Keep proxy invariants intact (see CLAUDE.md “CRITICAL” section).
  - Prefer small, surgical patches with tests. If you add new behavior, add TDD-style unit tests in `tests/`.
  - Avoid mutating `sys.path` in loaders; prefer explicit imports or path-based loaders.
  - Do not introduce external script calls on the request hot path; use in-process Python where possible.

- Testing:
  - Run `pytest -q` before pushing.
  - Network-dependent tests should default to mock/fallbacks to keep CI deterministic.

- Documentation:
  - If you change hook behavior or lifecycle, update both this file and CLAUDE.md to keep agents in sync with human guidelines.

