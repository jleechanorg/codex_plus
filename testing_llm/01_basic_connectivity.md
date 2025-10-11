# Test: Basic Connectivity

**Objective**: Verify Cerebras proxy server is running and responsive

**Category**: Small (< 30 seconds)

**Prerequisites**:
- Proxy started with `./proxy.sh --cerebras`
- Port 10000 available
- Cerebras credentials configured

## Commands to Execute

### 1. Check Proxy Health
```bash
curl -s http://localhost:10000/health
```

**Expected**: HTTP 200 with JSON response containing health status

### 2. Verify Proxy Process
```bash
ps aux | grep "uvicorn.*codex_plus" | grep -v grep
```

**Expected**: Process running on port 10000

### 3. Check Proxy Logs
```bash
tail -n 5 /tmp/codex_plus/proxy.log
```

**Expected**: No ERROR lines, should see INFO messages

## Validation Criteria

- [ ] Health endpoint returns HTTP 200
- [ ] Response contains valid JSON
- [ ] Proxy process is running
- [ ] No errors in recent logs
- [ ] Proxy responds within 1 second

## Evidence Requirements

**Save all outputs to**: `/tmp/codex_plus/cereb_conversion/test_evidence/01_basic_connectivity/`

### Files to Create

1. **`command_output.txt`** - Full output of all commands
2. **`validation.json`** - Structured validation results:
```json
{
  "test_name": "01_basic_connectivity",
  "status": "PASS",
  "timestamp": "<ISO 8601 timestamp>",
  "criteria": [
    {"name": "Health endpoint responds", "passed": true},
    {"name": "Valid JSON response", "passed": true},
    {"name": "Proxy process running", "passed": true},
    {"name": "No errors in logs", "passed": true},
    {"name": "Response time < 1s", "passed": true}
  ],
  "errors": []
}
```

3. **`summary.md`** - Human-readable report:
```markdown
# Test: 01_basic_connectivity

**Status**: ✅ PASS

## Results
- Health check: OK
- Proxy process: Running (PID: XXXXX)
- Logs: Clean, no errors

## Evidence Location
/tmp/codex_plus/cereb_conversion/test_evidence/01_basic_connectivity/

## Timestamp
<ISO 8601 timestamp>
```

## Execution Steps

1. Create evidence directory:
```bash
mkdir -p /tmp/codex_plus/cereb_conversion/test_evidence/01_basic_connectivity
```

2. Run health check and save output:
```bash
curl -s -w "\nHTTP_CODE:%{http_code}\nTIME:%{time_total}\n" \
  http://localhost:10000/health \
  > /tmp/codex_plus/cereb_conversion/test_evidence/01_basic_connectivity/command_output.txt 2>&1
```

3. Check proxy process:
```bash
ps aux | grep "uvicorn.*codex_plus" | grep -v grep \
  >> /tmp/codex_plus/cereb_conversion/test_evidence/01_basic_connectivity/command_output.txt 2>&1
```

4. Check logs:
```bash
tail -n 10 /tmp/codex_plus/proxy.log \
  >> /tmp/codex_plus/cereb_conversion/test_evidence/01_basic_connectivity/command_output.txt 2>&1
```

5. Create validation.json based on results

6. Create summary.md with pass/fail status

## Success Indicators

✅ **Test passes if**:
- All validation criteria are true
- Evidence files created successfully
- No exceptions or crashes

❌ **Test fails if**:
- Health endpoint unreachable
- Proxy not running
- Errors in logs
- Missing evidence files
