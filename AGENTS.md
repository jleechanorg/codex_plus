# Repository Guidelines

## Project Structure & Module Organization
Core proxy code lives in `src/codex_plus/` (e.g., `main_sync_cffi.py`, `llm_execution_middleware.py`, `status_line_middleware.py`). Project-specific hooks and slash-command assets belong in `.codexplus/` (`hooks/`, `commands/`, `settings.json`). Regression and integration tests are under `tests/`, including `tests/claude/hooks/` for legacy hook scenarios. Operational scripts—`proxy.sh`, `run_tests.sh`, and helpers inside `scripts/`—sit at the repo root alongside product docs such as `design.md`, `roadmap/`, and `testing_llm/` playbooks.

## Build, Test, and Development Commands
Create an isolated environment with `python -m venv venv && source venv/bin/activate`, then `pip install -r requirements.txt`. Use `./proxy.sh enable` (or `./proxy.sh` shorthand) to start the proxy on port 10000; run `./proxy.sh status` for quick health checks. For focused debugging, `uvicorn src.codex_plus.main:app --host 127.0.0.1 --port 10000 --reload` mirrors the managed script. Run fast feedback with `pytest -q`; execute the full CI simulation via `./run_tests.sh`. Lint and static-analysis coverage lives in `scripts/run_lint.sh` (Ruff, isort, mypy, Bandit) and `scripts/run_tests_with_coverage.sh`.

## Coding Style & Naming Conventions
Adhere to PEP 8 defaults with 4-space indentation, snake_case functions, and PascalCase classes. Maintain streaming-friendly async code—never replace `curl_cffi.requests.Session(impersonate="chrome124")`, alter the upstream `https://chatgpt.com/backend-api/codex`, or change the 10000 port binding. Reuse existing module-level `logging` instances (INFO for lifecycle, DEBUG for deep traces) and avoid bare `print`. Keep middleware surgical: prefer dependency injection or lifespan constructs over global state.

## Testing Guidelines
Pytest is configured by `pytest.ini` with default verbosity, strict markers, and test discovery limited to `tests/`. Name files `test_<topic>.py` and functions `test_<behavior>`. Exercise async paths with `pytest-asyncio`; cover hook flows via `tests/test_hooks_*.py` and `tests/claude/hooks/`. When network behavior is unavoidable, guard it with the `network` marker so suites pass with `NO_NETWORK=1`. Before pushing, run `pytest -q` plus any targeted suites (e.g., `pytest tests/test_proxy.py -k streaming`).

## Commit & Pull Request Guidelines
Use Conventional Commit-style prefixes: `fix(middleware): …`, `refactor(hooks): …`, `test(proxy): …`. PR descriptions must document Goal, Modifications, Necessity, and Integration Proof, with links to relevant issues or command logs. Note the test surface you executed (`./run_tests.sh`, selective pytest targets) and attach screenshots for any terminal UX change.

## Security & Configuration Tips
Never log credentials or tokens, and keep proxy request paths free of external shell calls. Preserve 401 passthrough for unauthenticated traffic while ensuring authenticated Codex CLI calls succeed. Standard usage is `OPENAI_BASE_URL=http://localhost:10000 codex`; document any deviation. Update both this guide and `CLAUDE.md` whenever hook lifecycles or invariants evolve.

## Agent Workflow Notes
Consult `CLAUDE.md` before edits; protected files (`main_sync_cffi.py`, `llm_execution_middleware.py`, `main.py`, `proxy.sh`) should not change without explicit approval. Hooks follow the Anthropic-aligned lifecycle and load settings from `.codexplus/settings.json`. When adding automation, keep commands idempotent and short-lived to respect the proxy’s streaming guarantees.
