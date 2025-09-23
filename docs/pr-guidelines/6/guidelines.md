# PR #6 Guidelines - Subagent Orchestration Middleware

## 🎯 PR-Specific Principles
- Preserve the proxy's security boundary: never expose writable REST surfaces from `main_sync_cffi.py` without authentication.
- Treat agent identifiers as untrusted input and hard-sanitize before touching the filesystem.
- Keep long-running middleware state changes serialized; reloads of shared registries must use locks or single-threaded workers.

## 🚫 PR-Specific Anti-Patterns
### ❌ **Unauthenticated Proxy Management**
`main_sync_cffi.py` now publishes `/agents` CRUD endpoints that accept arbitrary HTTP calls. Because the proxy sits on localhost:10000, *any* process on the box can POST data and mutate `.claude/agents`.

### ✅ **Secure Control Channel**
Expose agent lifecycle operations only through a trusted, authenticated channel (e.g., CLI command that writes locally) or disable the surface entirely. The proxy route should continue to forward requests only.

### ❌ **Path Traversal via Agent IDs**
`save_agent()` concatenates the provided agent ID directly into the path, so a name like `../../tmp/pwn` escapes `/.claude/agents` and overwrites arbitrary files.

### ✅ **Slugify Identifiers**
Normalize agent IDs with a whitelist (e.g., `[a-z0-9-]`) and reject any string containing a path separator before writing.

## 📋 Implementation Patterns for This PR
- Mount new REST routers behind FastAPI dependencies that verify an auth token.
- Wrap agent registry reloads (`_load_agents`) inside an `asyncio.Lock` to keep concurrent requests consistent.
- Unit test the identifier sanitizer with malicious examples (`../`, absolute paths, whitespace, unicode).

## 🔧 Specific Implementation Guidelines
- Introduce a `sanitize_agent_id()` utility and call it before every filesystem touch.
- Add regression tests in `tests/test_agent_config_loader.py` that assert directory escape attempts raise `HTTPException` 400.
- Update integration tests to confirm unauthenticated HTTP calls cannot mutate `.claude/agents`.
