# ChatGPT vs Cerebras Response Format Comparison

**Date**: 2025-10-04
**Purpose**: Understand correct transformation for Cerebras reasoning + tool_calls

## ChatGPT Format (Real Response - Tool Calling)

**Test**: `OPENAI_BASE_URL=http://localhost:10000 codex exec --yolo "create a file /tmp/test_chatgpt_tool.py with a simple add function"`

**Key Events**:
```
event: response.created
data: {"type":"response.created","sequence_number":0,...}

event: response.in_progress
data: {"type":"response.in_progress","sequence_number":1,...}

event: response.output_item.added (REASONING)
data: {"type":"response.output_item.added","sequence_number":2,"output_index":0,"item":{"id":"rs_...","type":"reasoning","encrypted_content":"...","summary":[]}}

event: response.reasoning_summary_part.added
...

event: response.output_item.done (REASONING)
data: {"type":"response.output_item.done","sequence_number":10,"output_index":0,"item":{"id":"rs_...","type":"reasoning",...}}

event: response.output_item.added (MESSAGE)
data: {"type":"response.output_item.added","sequence_number":11,"output_index":1,"item":{"id":"msg_...","type":"message","status":"in_progress","content":[],"role":"assistant"}}

event: response.content_part.added
...

event: response.output_text.delta
...

event: response.completed
```

**Key Findings**:
1. **TWO separate output items**: reasoning (index 0) + message (index 1)
2. Reasoning has encrypted_content and summary events
3. Message contains the actual text response
4. Each output item has its own `output_item.added` and `output_item.done` events

## Cerebras Format (OpenAI-Compatible SSE)

**Test**: `OPENAI_BASE_URL=http://localhost:10001 codex exec --yolo "create fibonacci function"`

**Structure**:
```
data: {"id":"chatcmpl-...","choices":[{"delta":{"role":"assistant"},"index":0}],...}

data: {"id":"chatcmpl-...","choices":[{"delta":{"reasoning":"We"},"index":0}],...}
data: {"id":"chatcmpl-...","choices":[{"delta":{"reasoning":" need"},"index":0}],...}
... (lines 2-324: reasoning tokens)

data: {"id":"chatcmpl-...","choices":[{"delta":{"tool_calls":[{"function":{"name":"shell","arguments":""},"type":"function","id":"c559def5a","index":0}]},"index":0}],...}
data: {"id":"chatcmpl-...","choices":[{"delta":{"tool_calls":[{"function":{"arguments":"..."},"type":"function","index":0}]},"index":0}],...}
... (lines 325+: tool_call arguments streaming)
```

**Key Findings**:
1. **Single stream** with different delta types
2. `delta.reasoning` appears BEFORE `delta.tool_calls`
3. Tool call has: `function.name`, `function.arguments`, `id`, `type`
4. No separate output items - everything in one choice stream

## Current Transformation Bug

**What My Code Does** (commit `42815af`):
1. ✅ Triggers `response.created` on first `delta.role`
2. ❌ Sends `output_item.added` with `type: "reasoning"` when reasoning appears
3. ❌ Never sends `output_item.added` with `type: "function_call"` for tool calls

**What Should Happen**:
1. ✅ Send `response.created` on first `delta.role`
2. ✅ Send `output_item.added` with `type: "reasoning"` (output_index 0)
3. ✅ Stream reasoning summary events
4. ✅ Send `output_item.done` for reasoning (output_index 0)
5. ✅ Send `output_item.added` with `type: "function_call"` (output_index 1) when tool_calls appears
6. ✅ Stream function call arguments
7. ✅ Send `output_item.done` for function_call (output_index 1)

## Solution Design

### Option A: Two Output Items (Match ChatGPT Exactly)
```python
# Track multiple output items
output_items = []  # List of (type, data) tuples
current_output_index = 0

# On first reasoning delta:
yield output_item.added(type="reasoning", output_index=0)
# ... stream reasoning ...
yield output_item.done(type="reasoning", output_index=0)
current_output_index = 1

# On first tool_calls delta:
yield output_item.added(type="function_call", output_index=1)
# ... stream function call ...
yield output_item.done(type="function_call", output_index=1)
```

### Option B: Suppress Reasoning (Simpler)
```python
# Buffer reasoning tokens but don't send output_item
accumulated_reasoning = []

# On reasoning delta:
accumulated_reasoning.append(delta["reasoning"])
# (don't send any events)

# On tool_calls delta:
yield output_item.added(type="function_call", output_index=0)
# ... stream function call ...
yield output_item.done(type="function_call", output_index=0)
```

## Recommendation

**Use Option A** - Match ChatGPT's exact format with two output items.

**Rationale**:
- ChatGPT DOES send reasoning as separate output item (encrypted)
- Codex CLI already handles reasoning output items correctly
- More faithful to actual ChatGPT behavior
- Preserves reasoning for potential future display

**Implementation Location**: `src/codex_plus/llm_execution_middleware.py` lines 636-688

## Evidence Files

- ChatGPT response: `/tmp/codex_plus/chatgpt_responses/latest_response.txt`
- Cerebras response: `/tmp/codex_plus/cerebras_responses/latest_response.txt`
- Proxy logs (10000): `/tmp/codex_plus/proxy.log`
- Proxy logs (10001): `/tmp/codex_plus/proxy_10001.log`

## CRITICAL FINDING (2025-10-04 22:53)

**ChatGPT DOES NOT send function_call events!**

Examination of `/tmp/codex_plus/chatgpt_responses/latest_response.txt` shows:
- Output item 0: `type: "reasoning"` (encrypted)
- Output item 1: `type: "message"` (NOT function_call!)
- Tool execution happens INTERNALLY in Codex CLI
- The message item contains the RESULT of tool execution

This means:
1. ❌ We should NOT be transforming Cerebras to ChatGPT `/responses` format
2. ✅ We should keep Cerebras in OpenAI SSE format and let Codex handle it
3. ✅ Tool calls are executed by parsing OpenAI `tool_calls` deltas
4. ❌ ChatGPT format is for DISPLAYING results, not for tool execution

**Correct approach**: Let Cerebras responses stay in OpenAI format (with reasoning tokens), don't transform to ChatGPT events at all.
