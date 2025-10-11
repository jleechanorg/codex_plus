# Test: Streaming Response

**Objective**: Validate streaming response handling through Cerebras proxy

**Category**: Medium (30-60 seconds)

**Prerequisites**:
- Tests 01-02 passed
- Streaming supported by Cerebras
- Proxy handles SSE format

## Commands to Execute

### 1. Simple Streaming Request
```bash
echo "Count from 1 to 5, one number per line." | \
  OPENAI_BASE_URL=http://localhost:10000 codex exec --yolo
```

**Expected**: Progressive output, numbers appear sequentially

### 2. Verify Streaming in Logs
```bash
grep "stream.*true\|streaming\|SSE" /tmp/codex_plus/proxy.log | tail -10
```

**Expected**: Evidence of streaming request handling

## Validation Criteria

- [ ] Response streams progressively (not all at once)
- [ ] All expected content received (numbers 1-5)
- [ ] No broken chunks or incomplete responses
- [ ] Proxy logs show streaming mode
- [ ] No stream interruption errors

## Evidence Requirements

**Save to**: `/tmp/codex_plus/cereb_conversion/test_evidence/03_streaming_response/`

### Files

1. **`command_output.txt`** - Full streaming output with timestamps

2. **`validation.json`**:
```json
{
  "test_name": "03_streaming_response",
  "status": "PASS",
  "timestamp": "<ISO 8601>",
  "criteria": [
    {"name": "Progressive streaming", "passed": true},
    {"name": "Complete response", "passed": true},
    {"name": "No broken chunks", "passed": true},
    {"name": "Streaming detected in logs", "passed": true},
    {"name": "No interruptions", "passed": true}
  ],
  "streaming_evidence": "Found in logs"
}
```

3. **`summary.md`** - Report with streaming observations

## Execution Steps

1. Create evidence directory:
```bash
EVIDENCE_DIR="/tmp/codex_plus/cereb_conversion/test_evidence/03_streaming_response"
mkdir -p "$EVIDENCE_DIR"
```

2. Execute streaming request:
```bash
echo "Count from 1 to 5, one number per line." | \
  OPENAI_BASE_URL=http://localhost:10000 codex exec --yolo \
  > "$EVIDENCE_DIR/command_output.txt" 2>&1
```

3. Check streaming evidence in logs:
```bash
echo "\n=== Streaming Evidence ===" >> "$EVIDENCE_DIR/command_output.txt"
grep "stream" /tmp/codex_plus/proxy.log | tail -10 \
  >> "$EVIDENCE_DIR/command_output.txt"
```

4. Validate response completeness

5. Create validation.json and summary.md

## Success Indicators

✅ **Pass if**:
- Response arrives progressively
- All content received
- Logs confirm streaming mode

❌ **Fail if**:
- Response arrives all at once
- Incomplete or truncated output
- Stream errors in logs
