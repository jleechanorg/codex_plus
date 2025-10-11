# Cerebras Integration - Next Steps

## Current Status Summary

### ✅ Completed
1. **Streaming Infrastructure** - Working perfectly
   - No more "stream closed before response.completed" errors
   - Proper SSE event handling
   - Response ID consistency enforced

2. **Cerebras Middleware** - Fully implemented
   - Request transformation (ChatGPT → Cerebras format)
   - Model support: `gpt-oss-120b`
   - Tool calling supported (not stripped)
   - Reasoning tokens available

3. **Logging Infrastructure** - Ready for analysis
   - ChatGPT response logging at `/tmp/codex_plus/chatgpt_responses/latest_response.txt`
   - Cerebras request/response logging at `/tmp/codex_plus/cerebras_debug/`
   - Detailed chunk-level debugging

### ⚠️ Blocked
- **Tool Call Format Unknown** - Two attempts unsuccessful
  - Format 1: `function_call_delta` → Events sent, not executed
  - Format 2: `content_block_delta` (Claude-style) → Events sent, not executed
- **Usage Limit** - Cannot capture real ChatGPT responses (resets in ~5 hours)

## Action Plan

### Phase 1: Capture Real Format (Est: 1 hour after reset)
**When:** Usage limit resets (5 hours from now)

**Tasks:**
1. Start proxy in ChatGPT mode (NOT Cerebras)
   ```bash
   ./proxy.sh start  # Defaults to ChatGPT mode
   ```

2. Run simple test tasks to capture responses:
   ```bash
   export OPENAI_BASE_URL=http://localhost:10000

   # Test 1: Simple echo (text response)
   codex exec --yolo 'echo "hello world"'

   # Test 2: File creation (tool call)
   codex exec --yolo 'create /tmp/test.py that prints fibonacci'

   # Test 3: Multiple tool calls
   codex exec --yolo 'create /tmp/calc.py with add and subtract functions, then test it'
   ```

3. Analyze captured responses:
   ```bash
   cat /tmp/codex_plus/chatgpt_responses/latest_response.txt
   ```

4. Document findings in `docs/chatgpt_response_format_analysis.md`

### Phase 2: Update Cerebras Transformation (Est: 2-4 hours)
**Based on captured format analysis**

**Tasks:**
1. Identify exact event types and structure for:
   - Text content deltas
   - Tool call initiation
   - Tool call argument streaming
   - Tool call completion
   - Response completion

2. Update `src/codex_plus/llm_execution_middleware.py`:
   - Lines 551-682: SSE transformation logic
   - Match exact ChatGPT format from captured responses

3. Test with Cerebras:
   ```bash
   export CEREBRAS_MODEL=gpt-oss-120b
   ./proxy.sh restart --cerebras
   export OPENAI_BASE_URL=http://localhost:10000
   codex exec --yolo 'create /tmp/hello.py'
   ls -la /tmp/hello.py  # Verify file exists
   ```

### Phase 3: Validation & Documentation (Est: 1 hour)
**Tasks:**
1. Run comprehensive tests:
   ```bash
   # Test different task types
   codex exec --yolo 'echo test'  # Simple
   codex exec --yolo 'create /tmp/fib.py'  # File creation
   codex exec --yolo 'find all TODO comments'  # Read-only
   ```

2. Update documentation:
   - `CLAUDE.md`: Add Cerebras usage instructions
   - `README.md`: Update features list
   - `roadmap/cerebras_integration.md`: Mark as complete

3. Create PR description update with:
   - Working features
   - Known limitations
   - Testing evidence

## Technical Notes

### Current Event Formats Tried

**Attempt 1: OpenAI-style `function_call_delta`**
```json
{
  "type": "response.output_item.delta",
  "item_id": "item_0",
  "output_index": 0,
  "delta": {
    "type": "function_call_delta",
    "index": 0,
    "id": "call_abc123",
    "function": {"name": "shell", "arguments": "..."}
  }
}
```

**Attempt 2: Claude-style `content_block_delta`**
```json
// Start
{
  "type": "content_block_start",
  "index": 0,
  "content_block": {
    "type": "tool_use",
    "id": "toolu_123",
    "name": "shell"
  }
}

// Deltas
{
  "type": "content_block_delta",
  "index": 0,
  "delta": {
    "type": "input_json_delta",
    "partial_json": "..."
  }
}

// Stop
{
  "type": "content_block_stop",
  "index": 0
}
```

### Hypothesis
The `/responses` API likely uses a completely different event structure that we haven't discovered. Possibilities:
1. Tool calls sent as single complete event (not streamed)
2. Different event type entirely (e.g., `response.tool_use.delta`)
3. Nested structure we haven't tried
4. Requires additional metadata we're missing

## Success Criteria

- [ ] Cerebras model executes tool calls successfully
- [ ] Files created in `/tmp` when requested
- [ ] Shell commands execute and return output
- [ ] No streaming errors or disconnections
- [ ] Response format matches ChatGPT exactly

## Risks & Mitigations

**Risk:** Real format is proprietary and undocumented
**Mitigation:** Capture multiple response examples, reverse engineer from patterns

**Risk:** Format changes between Codex versions
**Mitigation:** Document Codex version used (0.42.0), include in logs

**Risk:** Tool execution might require additional events
**Mitigation:** Compare successful ChatGPT responses vs our Cerebras output

## Estimated Completion

- **Best Case:** 4-6 hours (if format is straightforward)
- **Likely Case:** 8-12 hours (iterative format discovery)
- **Worst Case:** 16+ hours (complex format requiring multiple attempts)

## Commits So Far

1. `573d853` - Initial streaming fix with tool call transformation
2. `4a811e2` - Claude-style content_block events attempt
3. `65bfab8` - ChatGPT response logging infrastructure

## Files to Watch

- `/tmp/codex_plus/chatgpt_responses/latest_response.txt` - Real ChatGPT responses
- `/tmp/codex_plus/proxy.log` - Proxy debug logs
- `/tmp/codex_plus/cerebras_debug/last_request.json` - Cerebras request format
- `src/codex_plus/llm_execution_middleware.py` - Core transformation logic
