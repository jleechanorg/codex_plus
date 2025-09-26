# Repository Guidelines

## Project Structure & Module Organization
FastAPI proxy code resides under `src/codex_plus/`; keep middleware async-safe and avoid mutating protected files noted in `CLAUDE.md`. Hooks and command helpers live in `.codexplus/hooks/` (primary) and `.claude/hooks/` (legacy examples). End-to-end and unit tests sit in `tests/`, mirroring module names; use the same folder when adding coverage. Scripts such as `proxy.sh`, `run_tests.sh`, and environment helpers are in the repo root.

## Build, Test, and Development Commands
Create a virtualenv with `python -m venv venv && source venv/bin/activate`, then install dependencies via `pip install -r requirements.txt`. Run the proxy locally using `./proxy.sh` for the managed workflow or `uvicorn src.codex_plus.main:app --host 127.0.0.1 --port 10000 --reload` when debugging. Execute quick checks with `pytest -q`; prefer `./run_tests.sh` before commits for the full suite and lint-adjacent sanity. Use `pytest -k <pattern>` to iterate on focused scenarios.

## Coding Style & Naming Conventions
Follow idiomatic modern Python with 4-space indentation, descriptive snake_case for functions, and PascalCase for classes. Keep modules small and streaming aware; never replace `curl_cffi.requests.Session(impersonate="chrome124")` or the upstream URL `https://chatgpt.com/backend-api/codex`. Leverage existing `logging` instances at INFO for lifecycle events and DEBUG for deep traces; avoid print statements in production paths.

## Testing Guidelines
Write tests alongside new features using `pytest` and `pytest-asyncio`. Name files `test_<feature>.py` and functions `test_<behavior>` to match current patterns. Network-dependent behavior must default to mocks so the suite passes with `NO_NETWORK=1`. Validate new integrations with both `pytest -q` and targeted scenarios (e.g., `pytest tests/test_enhanced_slash_middleware.py -v`).

## Commit & Pull Request Guidelines
Adopt conventional-style prefixes: `fix(middleware): ...`, `refactor(hooks): ...`, or `test(proxy): ...`. Each PR description should include Goal, Modifications, Necessity, and Integration Proof, plus links to issues or logs when relevant. Document manual validation (`./run_tests.sh`, local Codex CLI smoke) and attach screenshots for UX-facing updates.

## Security & Configuration Tips
Never log authentication tokens or session cookies. Maintain the streaming proxy path without inserting external scripts or blocking 401 passthrough behavior. Respect `proxy.sh` defaults (port 10000) and ensure authenticated Codex CLI requests succeed while unauthenticated ones return 401. Update `CLAUDE.md` and this guide if lifecycle or invariants change.

**Codex runner reminder:** the Task API now launches agents with `codex exec --yolo` by default. Keep your `.claude/agents/*.md` instructions compatible with that flag (no extra sandbox approvals required) and only override the runner when a custom command is absolutely necessary.
