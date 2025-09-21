# 04 Error Handling Test

## Objective
Test that the proxy handles various error conditions gracefully without crashing or losing functionality.

## Prerequisites
- Proxy server is running
- Hook system loaded
- Previous tests completed successfully

## Test Steps

### 1. Test Upstream Connection Errors

```bash
# Test behavior when upstream is unreachable (simulate network issue)
# First, check normal behavior
curl -X POST http://localhost:10000/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dummy_token" \
  -d '{"input": [{"type": "message", "content": [{"type": "input_text", "text": "test"}]}]}' \
  -w "Response time: %{time_total}s\nHTTP code: %{http_code}\n" \
  --connect-timeout 5

# Check proxy logs for connection handling
grep -i "connection\|timeout\|error" proxy.log | tail -5
```

**Expected Result**:
- Proxy attempts connection to upstream
- Error is handled gracefully (no crash)
- Appropriate error response returned to client
- Proxy continues running

### 2. Test Malformed JSON Requests

```bash
# Test with invalid JSON
curl -X POST http://localhost:10000/responses \
  -H "Content-Type: application/json" \
  -d '{"invalid": json, syntax}' \
  -w "\nHTTP code: %{http_code}\n"

# Test with empty body
curl -X POST http://localhost:10000/responses \
  -H "Content-Type: application/json" \
  -d '' \
  -w "\nHTTP code: %{http_code}\n"

# Check logs for JSON parsing
grep -i "json\|parse\|decode" proxy.log | tail -5
```

**Expected Result**:
- Invalid JSON handled without crash
- Appropriate error responses returned
- Logs show JSON decode errors (but no crashes)
- Server continues operating

### 3. Test Hook Execution Errors

```bash
# Create a hook that raises an exception
cat > .codexplus/hooks/error_hook.py << 'EOF'
---
name: error_hook
type: pre-input
priority: 10
enabled: true
---

from codex_plus.hooks import Hook

class ErrorHook(Hook):
    async def pre_input(self, request, body):
        raise ValueError("Intentional test error")
        return body
EOF

# Restart proxy to load error hook
./proxy.sh restart
sleep 3

# Make request to trigger hook error
curl -X POST http://localhost:10000/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dummy_token" \
  -d '{"input": [{"type": "message", "content": [{"type": "input_text", "text": "trigger error"}]}]}'

# Check error handling in logs
grep -i "error.*error_hook\|exception.*error_hook" proxy.log | tail -3
```

**Expected Result**:
- Hook error is caught and logged
- Request continues processing with other hooks
- Server doesn't crash
- Error logged with traceback

### 4. Test Settings Hook Command Failures

```bash
# Create failing command hook script
cat > .codexplus/hooks/failing_command.py << 'EOF'
#!/usr/bin/env python3
import sys
import json

# Read stdin
data = json.load(sys.stdin)

# Intentionally fail
print("This command failed", file=sys.stderr)
sys.exit(1)
EOF

chmod +x .codexplus/hooks/failing_command.py

# Add to settings
python3 -c "
import json
from pathlib import Path

settings_path = Path('.codexplus/settings.json')
if settings_path.exists():
    settings = json.loads(settings_path.read_text())
else:
    settings = {}

# Add failing hook to UserPromptSubmit
settings.setdefault('hooks', {})
settings['hooks'].setdefault('UserPromptSubmit', [])
settings['hooks']['UserPromptSubmit'].append({
    'matcher': '*',
    'hooks': [{
        'type': 'command',
        'command': 'python3 \$CLAUDE_PROJECT_DIR/.codexplus/hooks/failing_command.py',
        'timeout': 2
    }]
})

settings_path.write_text(json.dumps(settings, indent=2))
print('Added failing command hook')
"

# Restart to reload settings
./proxy.sh restart
sleep 3

# Trigger the failing hook
curl -X POST http://localhost:10000/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dummy_token" \
  -d '{"input": [{"type": "message", "content": [{"type": "input_text", "text": "test failing hook"}]}]}'

# Check command hook error handling
grep -i "hook.*fail\|command.*fail" proxy.log | tail -5
```

**Expected Result**:
- Command hook failure is logged
- Request processing continues
- No server crash
- Error details in logs

### 5. Test File System Errors

```bash
# Test with missing hook directory
mv .codexplus/hooks .codexplus/hooks_backup 2>/dev/null || true

# Restart to test missing directory handling
./proxy.sh restart
sleep 3

# Check logs for missing directory handling
grep -i "hooks directory.*not exist" proxy.log | tail -3

# Restore hooks directory
mv .codexplus/hooks_backup .codexplus/hooks 2>/dev/null || true
```

**Expected Result**:
- Missing directory logged but not treated as error
- Server starts successfully
- No crash when hooks directory missing

### 6. Test Resource Exhaustion Scenarios

```bash
# Test with very large request body
python3 -c "
import requests
import json

# Create a 5MB request
large_content = 'x' * (5 * 1024 * 1024)  # 5MB
payload = {
    'input': [{
        'type': 'message',
        'content': [{'type': 'input_text', 'text': large_content}]
    }]
}

try:
    response = requests.post(
        'http://localhost:10000/responses',
        json=payload,
        headers={'Authorization': 'Bearer dummy_token'},
        timeout=10
    )
    print(f'Large request status: {response.status_code}')
except requests.exceptions.RequestException as e:
    print(f'Large request handled with: {type(e).__name__}')
except Exception as e:
    print(f'Large request error: {e}')
"

# Check proxy memory usage after large request
PID=$(cat proxy.pid 2>/dev/null || pgrep -f "uvicorn.*main:app")
if [ -n "$PID" ]; then
    ps -o pid,rss,vsz -p "$PID"
fi
```

**Expected Result**:
- Large request handled without crashing server
- Memory usage reasonable after request
- Proper error handling if request too large

### 7. Test Git Command Failures

```bash
# Temporarily break git access to test status line error handling
mv .git .git_backup 2>/dev/null || true

# Trigger status line generation
python3 -c "
import sys
sys.path.append('src')
from codex_plus.hooks import hook_system
import asyncio

async def test_status_line_error():
    try:
        status = await hook_system.run_status_line()
        print(f'Status with broken git: {status}')
    except Exception as e:
        print(f'Status line error handling: {e}')

asyncio.run(test_status_line_error())
"

# Restore git
mv .git_backup .git 2>/dev/null || true
```

**Expected Result**:
- Git failures handled gracefully
- Fallback behavior or appropriate error handling
- No server crash when git commands fail

### 8. Test Process Recovery

```bash
# Check that proxy recovers from various errors
./proxy.sh status

# Make several error-triggering requests
for i in {1..3}; do
    curl -X POST http://localhost:10000/responses \
      -H "Content-Type: application/json" \
      -d "{invalid json $i}" \
      --connect-timeout 2 &
done

wait

# Verify server is still running
sleep 2
./proxy.sh status

# Test normal request still works
curl -X POST http://localhost:10000/health
```

**Expected Result**:
- Server survives multiple error conditions
- Status shows server still running
- Health endpoint still responds
- Normal functionality restored

## Success Criteria Checklist

- [ ] Upstream connection errors handled gracefully
- [ ] Malformed JSON requests don't crash server
- [ ] Hook execution errors are caught and logged
- [ ] Settings hook command failures are handled
- [ ] Missing directories/files handled appropriately
- [ ] Large requests handled without memory issues
- [ ] Git command failures don't crash server
- [ ] Server recovers from multiple error conditions
- [ ] Normal functionality continues after errors
- [ ] All errors properly logged with details

## Cleanup

```bash
# Remove test error hooks
rm -f .codexplus/hooks/error_hook.py
rm -f .codexplus/hooks/failing_command.py

# Restore original settings
python3 -c "
import json
from pathlib import Path

settings_path = Path('.codexplus/settings.json')
if settings_path.exists():
    settings = json.loads(settings_path.read_text())
    # Remove test failing hooks
    if 'hooks' in settings and 'UserPromptSubmit' in settings['hooks']:
        settings['hooks']['UserPromptSubmit'] = [
            h for h in settings['hooks']['UserPromptSubmit']
            if 'failing_command.py' not in str(h)
        ]
    settings_path.write_text(json.dumps(settings, indent=2))
    print('Cleaned up test settings')
"

# Restart proxy to clean state
./proxy.sh restart

# Verify health
curl http://localhost:10000/health
```

**Expected Result**:
- Clean restart successful
- Health check passes
- Normal operation restored

## Troubleshooting

**If server crashes during tests**:
- Check proxy logs for detailed error messages
- Verify system resources (memory, disk space)
- Check for infinite loops in hook code

**If error handling fails**:
- Review FastAPI exception handling configuration
- Check async/await usage in error handling code
- Verify logging configuration is correct

**If recovery tests fail**:
- Check process management in proxy.sh
- Verify PID file handling
- Test manual server restart: `./proxy.sh disable && ./proxy.sh enable`