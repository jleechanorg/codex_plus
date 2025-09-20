# 03 Streaming Test

## Objective
Test that streaming responses work correctly without context overflow and that hooks don't interfere with streaming.

## Prerequisites
- Proxy server is running
- Basic proxy functionality tested (test 01)
- Hook system loaded (test 02)

## Test Steps

### 1. Test Streaming Response Handling

```bash
# Test with a streaming request (expect 401 but should handle streaming correctly)
curl -X POST http://localhost:3000/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dummy_token" \
  -d '{
    "input": [{
      "type": "message",
      "content": [{
        "type": "input_text",
        "text": "This is a streaming test"
      }]
    }],
    "stream": true
  }' -v --no-buffer
```

**Expected Result**:
- Connection established
- Request properly forwarded upstream
- May get 401 (expected without valid auth)
- No errors about streaming in proxy logs

### 2. Check Pre-Input Hook Processing on /responses

```bash
# Check that pre-input hooks are applied to /responses endpoint
grep -i "pre-input hooks applied" proxy.log | tail -3

# Check for request body modification logs
grep -i "request body modified" proxy.log | tail -3
```

**Expected Result**:
- Log entries showing pre-input hooks were applied
- Evidence of request processing on /responses endpoint

### 3. Test Status Line During Streaming

```bash
# Start a background request to trigger status line
(curl -X POST http://localhost:3000/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dummy_token" \
  -d '{
    "input": [{
      "type": "message",
      "content": [{"type": "input_text", "text": "test"}]
    }]
  }' > /dev/null 2>&1 &)

# Check for status line in logs
sleep 2
grep -i "git status line" proxy.log | tail -3

# Check for hook middleware execution
grep -i "hook middleware" proxy.log | tail -3
```

**Expected Result**:
- Status line generated during request processing
- No interference between streaming and status line generation

### 4. Test Large Request Handling

```bash
# Create a large request to test context limits
python3 -c "
import json
import requests

# Create a large message to test context handling
large_text = 'This is a test message. ' * 1000  # ~25KB

payload = {
    'input': [{
        'type': 'message',
        'content': [{'type': 'input_text', 'text': large_text}]
    }]
}

try:
    response = requests.post(
        'http://localhost:3000/responses',
        json=payload,
        headers={'Authorization': 'Bearer dummy_token'},
        timeout=10
    )
    print(f'Response status: {response.status_code}')
    print(f'Response length: {len(response.text)} chars')
except Exception as e:
    print(f'Request handling: {e}')
"
```

**Expected Result**:
- Request processed without errors
- Response status code (likely 401 but connection successful)
- No context overflow errors in proxy logs

### 5. Test Concurrent Streaming Requests

```bash
# Test multiple concurrent requests
python3 -c "
import concurrent.futures
import requests
import json

def make_request(i):
    payload = {
        'input': [{
            'type': 'message',
            'content': [{'type': 'input_text', 'text': f'Concurrent test {i}'}]
        }]
    }
    try:
        response = requests.post(
            'http://localhost:3000/responses',
            json=payload,
            headers={'Authorization': 'Bearer dummy_token'},
            timeout=5
        )
        return f'Request {i}: {response.status_code}'
    except Exception as e:
        return f'Request {i}: Error - {e}'

# Make 5 concurrent requests
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(make_request, i) for i in range(5)]
    results = [f.result() for f in concurrent.futures.as_completed(futures)]

for result in results:
    print(result)
"
```

**Expected Result**:
- All 5 requests complete
- Status codes returned (likely 401 but no connection errors)
- No deadlocks or hanging requests

### 6. Test Hook Execution with Streaming

```bash
# Check that hooks run even with streaming responses
grep -A 5 -B 5 "Processing.*responses" proxy.log | tail -15

# Check for hook execution during request processing
grep -i "hook.*executed\|hook.*applied" proxy.log | tail -5
```

**Expected Result**:
- Hooks execute normally even with streaming endpoints
- No interference between hooks and streaming

### 7. Monitor Memory Usage During Streaming

```bash
# Monitor proxy process during streaming test
PID=$(cat proxy.pid 2>/dev/null || pgrep -f "uvicorn.*main:app")

if [ -n "$PID" ]; then
    echo "Monitoring proxy PID: $PID"

    # Start background streaming test
    python3 -c "
import requests
import time
import threading

def stream_test():
    for i in range(10):
        try:
            requests.post(
                'http://localhost:3000/responses',
                json={'input': [{'type': 'message', 'content': [{'type': 'input_text', 'text': f'Stream test {i}' * 100}]}]},
                headers={'Authorization': 'Bearer dummy_token'},
                timeout=2
            )
            time.sleep(0.5)
        except:
            pass

# Start streaming test
threading.Thread(target=stream_test, daemon=True).start()
time.sleep(5)
print('Streaming test completed')
" &

    # Monitor memory usage
    for i in {1..10}; do
        ps -o pid,rss,vsz,pcpu -p "$PID" 2>/dev/null || echo "Process not found"
        sleep 1
    done
else
    echo "Proxy PID not found"
fi
```

**Expected Result**:
- Memory usage remains stable (no major leaks)
- Process continues running
- CPU usage reasonable during streaming

## Success Criteria Checklist

- [ ] Streaming requests are handled correctly
- [ ] Pre-input hooks process /responses endpoint
- [ ] Status line generation works during streaming
- [ ] Large requests don't cause context overflow
- [ ] Concurrent requests work without deadlocks
- [ ] Hooks execute normally with streaming responses
- [ ] Memory usage remains stable during streaming
- [ ] No streaming-related errors in proxy logs

## Cleanup

```bash
# Kill any background processes
pkill -f "curl.*responses" 2>/dev/null || true

# Check proxy is still running
./proxy.sh status
```

## Troubleshooting

**If streaming fails**:
- Check curl_cffi is installed: `pip list | grep curl-cffi`
- Verify FastAPI streaming setup in main.py
- Check for blocking operations in hooks

**If memory usage grows**:
- Check for unclosed connections in logs
- Verify StreamingResponse objects are properly handled
- Look for hook memory leaks

**If concurrent requests fail**:
- Check FastAPI async configuration
- Verify no synchronous blocking in hooks
- Monitor file descriptor limits: `ulimit -n`

**If hooks interfere with streaming**:
- Check hook execution doesn't consume stream content
- Verify hooks use async/await properly
- Ensure post-output hooks skip StreamingResponse objects