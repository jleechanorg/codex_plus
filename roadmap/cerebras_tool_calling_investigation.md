# Cerebras Tool Calling Investigation

## Current Status

**Streaming:** ✅ WORKING - No more "stream closed before response.completed" errors

**Tool Calling:** ⚠️ NOT WORKING - Events sent but not executed by Codex CLI

## What's Working

1. **Event Sequence:** Complete SSE stream accepted without errors
   - `response.created` with ID and status
   - `response.output_item.added` with item metadata
   - Content/tool deltas streaming correctly
   - `response.completed` with ID

2. **Model Configuration:** Successfully using `gpt-oss-120b`
   - Supports tool calling (tools not stripped)
   - Outputs reasoning tokens (`delta.reasoning`)
   - Generates proper tool call deltas

3. **Cerebras Integration:** Proxy correctly transforms requests/responses
   - ChatGPT format → Cerebras format
   - Cerebras SSE → ChatGPT SSE
   - Authentication and streaming working

## Format Attempts

### Attempt 1: `function_call_delta`
```json
{
  "type": "response.output_item.delta",
  "item_id": "item_0",
  "output_index": 0,
  "delta": {
    "type": "function_call_delta",
    "index": 0,
    "id": "tool_call_id",
    "function": {"name": "shell", "arguments": "..."}
  }
}
```
**Result:** Events sent successfully, no execution

### Attempt 2: Claude-style `content_block_delta`
```json
// First delta
{
  "type": "content_block_start",
  "index": 0,
  "content_block": {
    "type": "tool_use",
    "id": "tool_id",
    "name": "shell"
  }
}

// Subsequent deltas
{
  "type": "content_block_delta",
  "index": 0,
  "delta": {
    "type": "input_json_delta",
    "partial_json": "..."
  }
}

// Finish
{
  "type": "content_block_stop",
  "index": 0
}
```
**Result:** Events sent successfully, no execution

## Analysis

The fact that:
1. No streaming errors occur
2. Codex CLI accepts the full event sequence
3. Different delta formats behave identically (accepted but not executed)

Suggests that the `/responses` API format is **fundamentally different** from what we're attempting.

### Hypothesis

The ChatGPT `/responses` API likely doesn't use streaming deltas for tool calls at all.
Instead, it might:

1. Send the complete tool call in a single event (not streamed)
2. Use a completely different event type we haven't discovered
3. Require additional metadata or event sequencing

### Evidence

- Text content deltas (`delta.text`) also don't display, suggesting even basic content streaming format is wrong
- The fact that Codex CLI works with ChatGPT backend means there's a specific format we haven't discovered
- We're hitting usage limits preventing us from capturing real ChatGPT responses

## Next Steps

1. **Wait for usage limit reset** to capture real ChatGPT `/responses` traffic
2. **Set up logging proxy** that saves actual ChatGPT responses to files
3. **Analyze real response format** to understand the correct event structure
4. **Implement exact format match** based on actual ChatGPT responses

## Technical Debt

- Tool call transformation code exists but uses incorrect format
- Text content streaming also not working (lower priority)
- Need to handle reasoning tokens (`delta.reasoning`) from gpt-oss model

## Files Modified

- `src/codex_plus/llm_execution_middleware.py`: SSE transformation logic
  - Lines 618-652: Tool call delta transformation
  - Lines 654-678: Completion event with content_block_stop
- `proxy.sh`: Cerebras mode support
- `roadmap/cerebras_streaming_format_fix.md`: Initial streaming fix documentation

## Commits

- `573d853`: Initial streaming support with event transformation
  - Fixed "stream closed before response.completed" error
  - Added tool call delta transformation (incorrect format)
  - Dynamic upstream URL support

## Conclusion

**Cerebras streaming integration is 50% complete:**
- ✅ Streaming infrastructure works perfectly
- ✅ No errors or stream disconnections
- ✅ Model generates correct tool calls
- ⚠️ Tool call format unknown without real ChatGPT API capture
- ⚠️ Need actual `/responses` API documentation or traffic capture

**Recommended Action:** Pause Cerebras integration until we can capture real ChatGPT responses or obtain `/responses` API documentation.
