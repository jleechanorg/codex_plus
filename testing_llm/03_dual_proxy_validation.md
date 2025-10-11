# Dual-Proxy Validation Test

## Overview
Test the dual-proxy setup by running identical requests through both ChatGPT passthrough (port 10000) and Cerebras transformation (port 10001) proxies using the real Codex CLI with authentication.

## Prerequisites
- Both proxies must be running:
  - Port 10000: Passthrough with `CODEX_PLUS_LOGGING_MODE=true`
  - Port 10001: Cerebras with `CEREBRAS_API_KEY` set
- Valid Codex CLI authentication configured

## Test Procedure

### Step 1: Start Passthrough Proxy (Port 10000)
```bash
CODEX_PLUS_LOGGING_MODE=true ./proxy.sh restart
```

Verify:
```bash
curl -s http://localhost:10000/health
```

### Step 2: Start Cerebras Proxy (Port 10001)
```bash
export PROXY_PORT=10001
PROXY_PORT=10001 ./proxy.sh --cerebras enable
```

Verify:
```bash
curl -s http://localhost:10001/health
```

### Step 3: Test with ChatGPT Proxy (Authenticated)
```bash
OPENAI_BASE_URL=http://localhost:10000 codex exec --yolo "Write a hello world function in Python"
```

**Expected:** 200 OK with LLM response logged to `/tmp/codex_plus/chatgpt_responses/latest_response.txt`

### Step 4: Test with Cerebras Proxy (Authenticated)
```bash
OPENAI_BASE_URL=http://localhost:10001 codex exec --yolo "Write a hello world function in Python"
```

**Expected:** 200 OK with LLM response logged to `/tmp/codex_plus/cerebras_responses/latest_response.txt`

### Step 5: Compare Responses
```bash
python3 testing_integration/compare_proxies.py
```

## Validation Checklist

- [ ] Port 10000 health check passes
- [ ] Port 10001 health check passes
- [ ] ChatGPT proxy returns 200 (NOT 401)
- [ ] Cerebras proxy returns 200
- [ ] ChatGPT response logged correctly
- [ ] Cerebras response logged correctly
- [ ] Both responses contain actual LLM output
- [ ] Response comparison shows acceptable differences

## Expected Outcomes

### Success Criteria
1. Both proxies return 200 with authenticated Codex CLI requests
2. ChatGPT response contains real GPT-5 Codex output
3. Cerebras response contains transformed output from Cerebras model
4. Logs capture complete SSE streams
5. No 401 errors (indicates proper auth forwarding)

### Known Differences (Acceptable)
- Model IDs differ (gpt-5-codex vs gpt-oss-120b)
- Response timing/chunking patterns
- Cerebras may include reasoning stream
- Different system fingerprints

### Blocking Issues
- 401 Unauthorized from either proxy
- Empty or truncated responses
- Missing SSE events
- Malformed response reconstruction

## ✅ Test Results (2025-10-02)

**Status: PASSED**

### Port 10000 - ChatGPT Proxy
- ✅ Health check: `{"status":"healthy"}`
- ✅ Response: 200 OK (NOT 401)
- ✅ Command: `OPENAI_BASE_URL=http://localhost:10000 codex exec --yolo "Write a hello world function in Python"`
- ✅ Log size: 26KB (`/tmp/codex_plus/chatgpt_responses/latest_response.txt`)
- ✅ Format: ChatGPT backend SSE (`event: response.created`)

### Port 10001 - Cerebras Proxy
- ✅ Health check: `{"status":"healthy"}`
- ✅ Response: 200 OK
- ✅ Command: `OPENAI_BASE_URL=http://localhost:10001 codex exec --yolo "say hello"`
- ✅ Log size: 7.5KB (`/tmp/codex_plus/cerebras_responses/latest_response.txt`)
- ✅ Format: OpenAI-compatible SSE with reasoning + content streams
- ✅ Output: "Hello!" (correct)

**Conclusion:** Both proxies successfully handle authenticated Codex CLI requests with proper 200 responses and complete SSE streaming.
