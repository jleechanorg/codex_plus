# Test: Simple Request

**Objective**: Test basic request/response through Cerebras proxy with transformation

**Category**: Small (< 30 seconds)

**Prerequisites**:
- Test 01 passed
- `OPENAI_BASE_URL=http://localhost:10000` set
- Cerebras API key valid

## Commands to Execute

### 1. Simple Echo Request
```bash
echo "What is 2+2? Answer with just the number." | \
  OPENAI_BASE_URL=http://localhost:10000 codex exec --yolo
```

**Expected**: Response containing "4"

### 2. Verify Request Was Transformed
```bash
# Check proxy logs for transformation
grep "transform_request\|Cerebras\|llama" /tmp/codex_plus/proxy.log | tail -5
```

**Expected**: Evidence of request transformation in logs

### 3. Check Cerebras API Was Called
```bash
# Look for upstream URL in logs
grep "api.cerebras.ai\|llama-3.3-70b" /tmp/codex_plus/proxy.log | tail -3
```

**Expected**: Logs show Cerebras API calls

## Validation Criteria

- [ ] Request completed successfully
- [ ] Response is coherent and correct ("4")
- [ ] Logs show request transformation
- [ ] Logs show Cerebras API was called (not ChatGPT)
- [ ] No errors or timeouts

## Evidence Requirements

**Save all outputs to**: `/tmp/codex_plus/cereb_conversion/test_evidence/02_simple_request/`

### Files to Create

1. **`command_output.txt`** - Full codex output and log excerpts

2. **`validation.json`**:
```json
{
  "test_name": "02_simple_request",
  "status": "PASS",
  "timestamp": "<ISO 8601>",
  "criteria": [
    {"name": "Request completed", "passed": true},
    {"name": "Correct response", "passed": true},
    {"name": "Transformation detected", "passed": true},
    {"name": "Cerebras API called", "passed": true},
    {"name": "No errors", "passed": true}
  ],
  "response_preview": "4",
  "transformation_evidence": "Found in logs"
}
```

3. **`summary.md`**:
```markdown
# Test: 02_simple_request

**Status**: ✅ PASS

## Test Flow
1. Sent simple math question through proxy
2. Proxy transformed Codex request → Cerebras format
3. Cerebras API processed request
4. Response returned correctly

## Response
> 4

## Transformation Evidence
- Logs show model mapping: gpt-5-codex → llama-3.3-70b
- Request sent to api.cerebras.ai
- Response format converted back

## Evidence Location
/tmp/codex_plus/cereb_conversion/test_evidence/02_simple_request/

## Timestamp
<ISO 8601>
```

## Execution Steps

1. Create evidence directory:
```bash
EVIDENCE_DIR="/tmp/codex_plus/cereb_conversion/test_evidence/02_simple_request"
mkdir -p "$EVIDENCE_DIR"
```

2. Execute request and capture output:
```bash
echo "What is 2+2? Answer with just the number." | \
  OPENAI_BASE_URL=http://localhost:10000 codex exec --yolo \
  > "$EVIDENCE_DIR/command_output.txt" 2>&1
```

3. Extract relevant log lines:
```bash
echo "\n=== Transformation Evidence ===" >> "$EVIDENCE_DIR/command_output.txt"
grep -A 2 -B 2 "transform_request\|Cerebras\|llama" /tmp/codex_plus/proxy.log | tail -10 \
  >> "$EVIDENCE_DIR/command_output.txt"
```

4. Verify Cerebras API was used:
```bash
echo "\n=== API Call Evidence ===" >> "$EVIDENCE_DIR/command_output.txt"
grep "api.cerebras.ai" /tmp/codex_plus/proxy.log | tail -5 \
  >> "$EVIDENCE_DIR/command_output.txt"
```

5. Create validation.json by checking:
   - Response contains "4"
   - No error messages in output
   - Logs show transformation
   - Logs show Cerebras API

6. Create summary.md with results

## Success Indicators

✅ **Test passes if**:
- Codex responds with correct answer
- Proxy logs show transformation logic
- Cerebras API endpoint appears in logs
- No authentication or connection errors

❌ **Test fails if**:
- Request times out
- Response is incorrect or incoherent
- Logs show ChatGPT API instead of Cerebras
- Any errors in output or logs
- Missing transformation evidence

## Troubleshooting

If test fails:
- Check `OPENAI_BASE_URL` is set correctly
- Verify Cerebras API key is valid
- Check proxy logs for transformation errors
- Ensure proxy started with `--cerebras` flag
