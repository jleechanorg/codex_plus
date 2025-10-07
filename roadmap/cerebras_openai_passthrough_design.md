# Cerebras OpenAI SSE Passthrough Design

## Background
Codex CLI currently proxies requests to upstream LLM providers via `src/codex_plus/llm_execution_middleware.py`. The ChatGPT integration already speaks OpenAI-compatible SSE, enabling Codex CLI to:
- parse `delta.tool_calls` deltas
- dispatch tool executions locally
- surface reasoning tokens and textual responses

The Cerebras integration replicates the ChatGPT transformation layer and rewrites upstream OpenAI SSE into `response.output_item.*` events. While reasoning shows up, Codex CLI never sees tool call deltas, so no tools run and `codex exec --yolo` hangs at the prompt.

## Problem Statement
We must let Codex CLI consume Cerebras streaming responses in a way that unlocks tool execution. The initial implementation attempted to reshape Cerebras SSE into ChatGPT `/responses` events, but the CLI never saw `tool_calls` and therefore never ran shell commands.

## Goals
- Surface Cerebras reasoning/tool-call deltas to Codex CLI in the shape it expects (ChatGPT `/responses` schema).
- Execute `shell` tool calls locally when Cerebras finishes with `finish_reason="tool_calls"`.
- Stream a synthesized assistant message summarizing command results so the CLI session completes cleanly.
- Maintain async-friendly streaming with minimal latency overhead.
- Provide sufficient logging for debugging without leaking sensitive payloads.

## Non-Goals
- Re-implement Codex CLI tool orchestration.
- Buffer entire responses or convert to ChatGPT `/responses` events.
- Modify ChatGPT integration path.
- Introduce persistent state in the middleware.

## Current Behavior Summary
1. Middleware detects `CODEX_PLUS_PROVIDER_MODE == "cerebras"`.
2. SSE chunks are parsed and transformed into synthetic `/responses` events (`response.output_item.*`).
3. Extra metadata (`sequence_number`, `item_id`, etc.) is added to mimic ChatGPT events.
4. Codex CLI receives the stream but never triggers tool execution; files like `/tmp/test.py` remain absent.

## Proposed Approach
Translate Cerebras SSE into ChatGPT-style events while bridging tool execution inside the proxy:
1. Stream Cerebras `data:` chunks, buffering until complete SSE events are decoded.
2. Emit `event: response.*` payloads mirroring ChatGPT semantics (sequence numbers, item ids, etc.).
3. Accumulate `delta.tool_calls[..].function.arguments` into a JSON buffer.
4. When Cerebras stops with `finish_reason="tool_calls"`, parse the JSON, execute the requested shell command locally, and capture stdout/stderr/exit code.
5. Synthesize a follow-up assistant message summarizing the command outcome, then emit `response.completed` plus the `[DONE]` sentinel.

## High-Level Data Flow
```
Codex CLI ──> FastAPI Proxy ──> Cerebras `/chat/completions`
                       │
                       ├─ Receives upstream SSE (reasoning + tool_calls)
                       ├─ Emits ChatGPT-style `response.function_call.arguments.delta`
                       ├─ Executes the shell tool call locally
                       └─ Streams a final assistant message + completion
```

## Detailed Design
### Middleware Changes (`llm_execution_middleware.py`)
- Buffer partial SSE chunks and parse into discrete Cerebras events.
- Map `delta.reasoning` to `response.output_item.added` / `response.output_item.done` (encrypted placeholder).
- Map `delta.tool_calls` segments to `response.function_call.arguments.delta` events with sequence numbers, output indices, and call ids.
- When tool call JSON completes, execute the command with `asyncio.create_subprocess_exec`, honouring `workdir`, `timeout_ms`, and extra env vars.
- Log execution metadata at INFO level (command, cwd, duration) while truncating stdout/stderr in the streamed summary.
- Append an assistant message summarizing the command output so the CLI session concludes normally.

### Logging
- Raw Cerebras SSE recorded to `/tmp/codex_plus/cerebras_responses/latest_response.txt`.
- Transformed `/responses` events recorded to `/tmp/codex_plus/cerebras_transformed/latest_response.txt` for diffing.
- INFO logs annotate command execution (command, cwd, exit code); DEBUG logs emit per-event metadata.

### Configuration Guardrails
- Use environment flag (e.g., `CODEX_PLUS_CEREBRAS_FORMAT=passthrough`) for controlled rollout.
- Fallback to previous transformer if flag toggled off.

## Testing Strategy
1. Unit-ish test using recorded Cerebras SSE fixture:
   - New test module `tests/test_cerebras_sse_passthrough.py`.
   - Feed mock SSE stream, assert emitted chunks equal input and reasoning/tool call markers preserved.
2. Local smoke test:
   - `export CODEX_PLUS_UPSTREAM_URL="https://api.cerebras.ai/v1"`
   - `export CODEX_PLUS_PROVIDER_MODE="cerebras"`
   - `uvicorn src.codex_plus.main:app --host 127.0.0.1 --port 10001`
   - `OPENAI_BASE_URL=http://localhost:10001 codex exec --yolo "create /tmp/test_passthrough.py with bubble sort"`
   - Validate `/tmp/test_passthrough.py` exists and contains requested content.
3. Regression test with ChatGPT path to confirm no unintended changes.

## Observability & Metrics
- Track counts of SSE events forwarded vs. dropped.
- Emit warning if non-SSE payload encountered (e.g., JSON body).
- Optionally record last `finish_reason` for debugging.

## Risks & Mitigations
- **Chunk Boundary Handling**: Partial events may break parsing. Mitigation: we buffer and only emit complete SSE frames.
- **Double Execution**: CLI may later start executing tools itself. We track `response.function_call.arguments.delta`; if future versions resume local execution we can gate our runner behind a feature flag.
- **Missing Metadata**: Cerebras arguments may omit `workdir`/`timeout`. We default to proxy cwd and infinite timeout, logging fallbacks.
- **Future Protocol Changes**: Unknown event types are logged and passed through so we can adapt quickly.

## Rollout Plan
1. Implement passthrough under feature flag.
2. Validate locally with Codex CLI.
3. Update documentation (`CLAUDE.md`, relevant roadmap) with new behavior and env vars.
4. Remove legacy transformer once confidence established.

## Open Questions
- Does Codex CLI need explicit heartbeat events? (Based on logs, no, but verify during testing.)
- Should we attempt to synthesize reasoning summaries similar to ChatGPT? (Out of scope for now.)
- Do we need to redact tool arguments in debug logs to avoid sensitive data leakage? (Likely yes; plan for safe logging helper.)
