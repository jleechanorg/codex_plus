# Dual-Proxy Validation Testing Strategy

## Overview

This document outlines the testing approach for validating Cerebras SSE response transformation by running two proxies side-by-side:

1. **Passthrough Proxy (Port 10000)** - Logs real ChatGPT request/response pairs without modification
2. **Cerebras Proxy (Port 10001)** - Transforms requests to Cerebras and reconstructs responses

## Architecture

```
┌─────────────┐
│  Codex CLI  │
└──────┬──────┘
       │
       ├─────────────────────────────────────────┐
       │                                         │
       ▼                                         ▼
┌──────────────────┐                    ┌──────────────────┐
│ Passthrough Proxy│                    │ Cerebras Proxy   │
│   (Port 10000)   │                    │   (Port 10001)   │
│                  │                    │                  │
│ LOGGING MODE ON  │                    │ CEREBRAS MODE ON │
│ No transformation│                    │ Full transform   │
└────────┬─────────┘                    └────────┬─────────┘
         │                                       │
         ▼                                       ▼
┌─────────────────┐                    ┌─────────────────┐
│ ChatGPT Backend │                    │ Cerebras API    │
│ (Real responses)│                    │ (SSE streaming) │
└─────────────────┘                    └─────────────────┘
```

## Test Workflow

### Phase 1: Setup Dual Proxies

```bash
# Terminal 1: Start passthrough proxy (logging mode)
CODEX_PLUS_LOGGING_MODE=true ./proxy.sh restart

# Terminal 2: Start Cerebras proxy on different port
# (Requires port configuration in proxy.sh)
PROXY_PORT=10001 CEREBRAS_API_KEY=xxx ./proxy.sh --cerebras restart

# Verify both are running
curl http://localhost:10000/health
curl http://localhost:10001/health
```

### Phase 2: Capture Reference Data

Run identical requests through both proxies and capture outputs:

```bash
# Test script: testing_integration/dual_proxy_test.sh

# 1. Send request to passthrough proxy (real ChatGPT)
OPENAI_BASE_URL=http://localhost:10000 codex "Write a hello world function" \
  > /tmp/chatgpt_output.txt

# 2. Send same request to Cerebras proxy
OPENAI_BASE_URL=http://localhost:10001 codex "Write a hello world function" \
  > /tmp/cerebras_output.txt

# 3. Compare outputs
diff /tmp/chatgpt_output.txt /tmp/cerebras_output.txt
```

### Phase 3: Validate Transformations

#### Request Validation
- Compare logged request bodies from both proxies
- Verify Cerebras proxy correctly transforms:
  - `input[]` → `messages[]`
  - Flat tools → nested `function` structure
  - Model name mapping
  - Endpoint transformation (/responses → /chat/completions)

#### Response Validation
- Parse logged SSE events from both proxies
- Verify event sequence matches:
  - `response.created` timing
  - `response.output_item.added` structure
  - `response.output_text.delta` content equivalence
  - `response.completed` final state

#### Tool Call Validation (Critical)
- Send requests with tool calls through both proxies
- Verify Cerebras proxy correctly transforms:
  - `tool_calls[].function.arguments` (SSE deltas)
  - `response.function_call.arguments.delta` events
  - Final tool execution equivalence

## Log Analysis

### Passthrough Proxy Logs
```
/tmp/codex_plus/chatgpt_responses/latest_response.txt  # Raw ChatGPT SSE
/tmp/codex_plus/cereb_conversion/request_payload.json  # Original request
```

### Cerebras Proxy Logs
```
/tmp/codex_plus/cerebras_debug/last_request.json       # Transformed request
/tmp/codex_plus/cerebras_responses/latest_response.txt # Raw Cerebras SSE (if added)
```

## Port Configuration

To run dual proxies, we need to support dynamic port configuration:

### Option 1: Environment Variable
```bash
# proxy.sh modification
PROXY_PORT=${PROXY_PORT:-10000}
uvicorn ... --port $PROXY_PORT
```

### Option 2: Command-line Flag
```bash
./proxy.sh --port 10001 --cerebras restart
```

## Test Cases

### 1. Simple Text Response
**Input**: "Say hello"
**Expected**: Both proxies produce equivalent text output

### 2. Streaming Response
**Input**: "Count to 10 slowly"
**Expected**: Both proxies stream at similar rate, same final content

### 3. Tool Calling
**Input**: Request using `mcp__` tools
**Expected**:
- Same tools executed
- Same arguments passed
- Same final results

### 4. Multi-turn Conversation
**Input**: Series of related questions
**Expected**: Context preserved identically in both proxies

## Validation Scripts

### `testing_integration/compare_proxies.py`
```python
#!/usr/bin/env python3
"""
Compare outputs from passthrough and Cerebras proxies
"""

import json
import sys
from pathlib import Path

def parse_sse_events(log_file):
    """Parse SSE log into structured events"""
    events = []
    with open(log_file, 'rb') as f:
        content = f.read().decode('utf-8', errors='ignore')
        for line in content.split('\n'):
            if line.startswith('data: '):
                try:
                    events.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass
    return events

def compare_events(chatgpt_events, cerebras_events):
    """Compare event sequences for equivalence"""
    # Check event count
    if len(chatgpt_events) != len(cerebras_events):
        print(f"❌ Event count mismatch: {len(chatgpt_events)} vs {len(cerebras_events)}")
        return False

    # Check event types match
    for i, (cg, cb) in enumerate(zip(chatgpt_events, cerebras_events)):
        if cg.get('type') != cb.get('type'):
            print(f"❌ Event {i} type mismatch: {cg.get('type')} vs {cb.get('type')}")
            return False

    print("✅ Event sequences match")
    return True

if __name__ == "__main__":
    chatgpt_log = Path("/tmp/codex_plus/chatgpt_responses/latest_response.txt")
    cerebras_log = Path("/tmp/codex_plus/cerebras_responses/latest_response.txt")

    chatgpt_events = parse_sse_events(chatgpt_log)
    cerebras_events = parse_sse_events(cerebras_log)

    if compare_events(chatgpt_events, cerebras_events):
        sys.exit(0)
    else:
        sys.exit(1)
```

## Implementation Checklist

- [ ] Add `PROXY_PORT` environment variable support to `proxy.sh`
- [ ] Add Cerebras response logging (similar to ChatGPT logging)
- [ ] Create `testing_integration/dual_proxy_test.sh` script
- [ ] Create `testing_integration/compare_proxies.py` validator
- [ ] Document expected vs actual differences (timestamps, IDs, etc.)
- [ ] Add automated test suite using pytest with dual proxy fixtures
- [ ] Create dashboard/report showing validation results

## Expected Differences (Acceptable)

These differences are expected and acceptable:

1. **Response IDs**: Different UUIDs/IDs from different services
2. **Timestamps**: Different creation times
3. **Model metadata**: Different model fingerprints
4. **Token counts**: Cerebras may count differently
5. **Minor formatting**: Extra/missing whitespace in content

## Blockers to Fix

These differences indicate bugs:

1. **Missing events**: Cerebras missing `response.created` or `output_item.added`
2. **Wrong event types**: `output_text.delta` vs `function_call.arguments.delta` mismatch
3. **Content differences**: Different final text or tool arguments
4. **Incomplete streaming**: Cerebras stops early or hangs
5. **Tool execution failures**: Tools work in ChatGPT but fail in Cerebras

## Success Criteria

✅ Dual-proxy validation passes when:

1. Both proxies produce equivalent final outputs for 20+ test cases
2. Event sequences match (type and order)
3. Tool calling works identically
4. Multi-turn conversations maintain same context
5. No content loss or corruption during transformation
6. Streaming completes successfully in both proxies

## Next Steps

1. ✅ Clarify `.codexplus` vs `.claude` directory structure (DONE)
2. ⏭️ Add port configuration to `proxy.sh`
3. ⏭️ Implement Cerebras response logging
4. ⏭️ Create comparison scripts
5. ⏭️ Run validation suite
6. ⏭️ Fix any discovered issues
7. ⏭️ Document findings and update transformation logic
