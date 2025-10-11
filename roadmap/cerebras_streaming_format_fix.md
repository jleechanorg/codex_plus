# Cerebras Streaming Format Transformation Fix

## Problem Statement

**Issue**: Codex CLI gets "stream disconnected before completion: stream closed before response.completed" when using Cerebras API through the proxy.

**Root Cause**: Codex CLI expects ChatGPT's `/responses` endpoint format (which includes `response.completed` in the streaming response), but we're returning Cerebras's standard OpenAI-compatible `/chat/completions` format without transformation.

**Evidence**:
- Non-streaming requests work perfectly (tested with `"stream": false`)
- Proxy completes successfully (logs show `200 OK`)
- Error occurs on Codex CLI side: "stream closed before response.completed"
- Cerebras API returns standard OpenAI SSE format, not ChatGPT's proprietary format

## Current Behavior

### Cerebras Streaming Format (Standard OpenAI)
```
data: {"id":"chatcmpl-xxx","choices":[{"delta":{"content":"text"},"index":0}],"model":"qwen-3-coder-480b"}

data: {"id":"chatcmpl-xxx","choices":[{"delta":{},"finish_reason":"stop","index":0}],"model":"qwen-3-coder-480b"}

data: [DONE]
```

### ChatGPT `/responses` Format (Expected by Codex CLI)
```
data: {"type":"response.output_item.delta","delta":{"type":"message","content":[{"type":"text","text":"content"}]}}

data: {"type":"response.completed","response":{...}}
```

**Key Difference**: Codex CLI waits for `response.completed` event to know the stream is done. Cerebras sends `[DONE]` instead.

## Solution Design

### Approach 1: SSE Format Transformation (RECOMMENDED)

Transform Cerebras SSE chunks to match ChatGPT's `/responses` format in real-time.

**Implementation Location**: `src/codex_plus/llm_execution_middleware.py` - in the `stream_response()` generator function

**Transformation Logic**:
1. Parse each SSE chunk from Cerebras
2. If it contains `delta.content`, transform to `response.output_item.delta` format
3. If it contains `finish_reason`, transform to `response.completed` format
4. Yield transformed chunks to Codex CLI

**Pros**:
- Maintains streaming behavior
- Works with existing Codex CLI expectations
- Minimal changes to proxy architecture
- Can be toggled on/off based on upstream

**Cons**:
- Adds complexity to streaming logic
- Need to parse and re-serialize JSON for each chunk
- May introduce latency

### Approach 2: Response Buffering and Reformatting

Buffer the entire Cerebras response and return it in ChatGPT format.

**Pros**:
- Simpler transformation logic
- Guaranteed format correctness

**Cons**:
- ❌ Loses streaming benefits (defeats the purpose)
- ❌ Increases latency significantly
- ❌ Higher memory usage

### Approach 3: Proxy Path Transformation

Create a separate endpoint that handles format transformation.

**Pros**:
- Clean separation of concerns
- Easier to test

**Cons**:
- More complex routing
- Requires changing Codex CLI configuration

## Recommended Solution: Approach 1

Implement SSE format transformation in the streaming generator.

### Implementation Plan

#### Step 1: Add SSE Chunk Parser
Create a helper function to parse SSE chunks:
```python
def parse_sse_chunk(chunk: bytes) -> dict:
    """Parse SSE chunk into event data"""
    lines = chunk.decode('utf-8').strip().split('\n')
    data = None
    for line in lines:
        if line.startswith('data: '):
            data = line[6:]  # Remove 'data: ' prefix
            if data == '[DONE]':
                return {'type': 'done'}
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                pass
    return None
```

#### Step 2: Add Format Transformer
Create a function to transform Cerebras format to ChatGPT format:
```python
def transform_cerebras_to_chatgpt(chunk_data: dict) -> str:
    """Transform Cerebras SSE chunk to ChatGPT /responses format"""
    if chunk_data.get('type') == 'done':
        # Send completion event
        return 'data: {"type":"response.completed","response":{"status":"completed"}}\n\n'

    choices = chunk_data.get('choices', [])
    if not choices:
        return ''

    delta = choices[0].get('delta', {})

    if 'content' in delta:
        # Transform content delta
        transformed = {
            "type": "response.output_item.delta",
            "delta": {
                "type": "message",
                "content": [{"type": "text", "text": delta['content']}]
            }
        }
        return f'data: {json.dumps(transformed)}\n\n'

    if choices[0].get('finish_reason'):
        # Send completion event
        return 'data: {"type":"response.completed","response":{"status":"completed"}}\n\n'

    return ''
```

#### Step 3: Modify Stream Response Generator
Update `stream_response()` in `llm_execution_middleware.py`:
```python
def stream_response():
    response_closed = False
    try:
        # Check if this is Cerebras upstream needing transformation
        is_cerebras = "api.cerebras.ai" in upstream_url

        for chunk in response.iter_content(chunk_size=None):
            if chunk:
                if is_cerebras:
                    # Transform Cerebras SSE to ChatGPT format
                    parsed = parse_sse_chunk(chunk)
                    if parsed:
                        transformed = transform_cerebras_to_chatgpt(parsed)
                        if transformed:
                            yield transformed.encode('utf-8')
                else:
                    # Pass through ChatGPT chunks as-is
                    yield chunk
    except Exception as e:
        logger.error(f"Error during streaming: {e}")
        # ... error handling
```

#### Step 4: Testing
1. Test non-streaming Cerebras requests (already working)
2. Test streaming Cerebras requests with `codex exec --yolo`
3. Verify ChatGPT streaming still works (regression test)
4. Test stream completion events are sent correctly

### Edge Cases to Handle

1. **Partial SSE chunks**: Chunks may be split across TCP packets
   - Solution: Buffer incomplete chunks and combine with next chunk
2. **Multiple SSE events in one chunk**: One chunk may contain multiple `data:` lines
   - Solution: Parse and transform each event separately
3. **Non-SSE content**: Some responses may not be SSE format
   - Solution: Detect SSE format and fall back to pass-through
4. **Error responses**: Handle HTTP errors gracefully
   - Solution: Already handled by existing error logging

### Rollback Plan

If transformation causes issues:
1. Add environment variable `DISABLE_CEREBRAS_TRANSFORM=1`
2. Fall back to direct pass-through
3. Return clear error message to user about incompatibility

## Alternative: Use curl_cffi for Cerebras

**Consideration**: If SSE transformation proves too complex, consider using curl_cffi for Cerebras as well (since it already works for ChatGPT).

**Pros**:
- Leverage existing working code
- No format transformation needed

**Cons**:
- Cerebras doesn't have Cloudflare protection (doesn't need Chrome impersonation)
- Less efficient than httpx for simple HTTP requests
- Adds unnecessary complexity

## Success Criteria

1. ✅ `codex exec --yolo 'What is 2+2?'` completes successfully with Cerebras
2. ✅ No "stream disconnected" errors
3. ✅ Response content is displayed correctly
4. ✅ ChatGPT streaming still works (regression test)
5. ✅ Non-streaming Cerebras requests still work

## Timeline

- **Implementation**: 30-60 minutes (including testing)
- **Testing**: 15-30 minutes
- **Documentation**: 15 minutes

## Files to Modify

1. `src/codex_plus/llm_execution_middleware.py` - Add transformation logic
2. `tests/test_cerebras_streaming.py` - Add tests (new file)
3. `CLAUDE.md` - Document streaming transformation behavior
