# 05 Performance Test

## Objective
Test proxy performance under basic load conditions and verify the system remains responsive.

## Prerequisites
- Proxy server is running
- All previous tests passed
- System has sufficient resources for load testing

## Test Steps

### 1. Baseline Performance Test

```bash
# Test single request latency
echo "Testing baseline request latency..."
curl -X POST http://localhost:10000/health \
  -w "Connect: %{time_connect}s\nTTFB: %{time_starttransfer}s\nTotal: %{time_total}s\n" \
  -o /dev/null -s

# Test with JSON processing
curl -X POST http://localhost:10000/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dummy_token" \
  -d '{"input": [{"type": "message", "content": [{"type": "input_text", "text": "baseline test"}]}]}' \
  -w "Connect: %{time_connect}s\nTTFB: %{time_starttransfer}s\nTotal: %{time_total}s\n" \
  -o /dev/null -s
```

**Expected Result**:
- Health endpoint: < 50ms total time
- JSON processing: < 500ms total time (includes upstream timeout)
- Consistent response times across multiple runs

### 2. Concurrent Request Load Test

```bash
# Test concurrent requests handling
python3 -c "
import concurrent.futures
import requests
import time
import statistics

def make_request(request_id):
    start = time.time()
    try:
        response = requests.post(
            'http://localhost:10000/responses',
            json={
                'input': [{
                    'type': 'message',
                    'content': [{'type': 'input_text', 'text': f'Load test request {request_id}'}]
                }]
            },
            headers={'Authorization': 'Bearer dummy_token'},
            timeout=5
        )
        end = time.time()
        return {
            'id': request_id,
            'status': response.status_code,
            'time': end - start,
            'success': True
        }
    except Exception as e:
        end = time.time()
        return {
            'id': request_id,
            'error': str(e),
            'time': end - start,
            'success': False
        }

# Test with 10 concurrent requests
print('Starting concurrent load test with 10 requests...')
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    start_time = time.time()
    futures = [executor.submit(make_request, i) for i in range(10)]
    results = [f.result() for f in concurrent.futures.as_completed(futures)]
    total_time = time.time() - start_time

# Analyze results
successful = [r for r in results if r['success']]
failed = [r for r in results if not r['success']]
times = [r['time'] for r in successful]

print(f'Total test time: {total_time:.2f}s')
print(f'Successful requests: {len(successful)}/10')
print(f'Failed requests: {len(failed)}')

if times:
    print(f'Average response time: {statistics.mean(times):.2f}s')
    print(f'Min response time: {min(times):.2f}s')
    print(f'Max response time: {max(times):.2f}s')

if failed:
    print('Failed request errors:')
    for f in failed[:3]:  # Show first 3 failures
        print(f'  Request {f[\"id\"]}: {f.get(\"error\", \"Unknown error\")}')
"
```

**Expected Result**:
- At least 8/10 requests should succeed
- Average response time < 2 seconds
- No server crashes or deadlocks
- Reasonable resource usage

### 3. Memory Usage Under Load

```bash
# Monitor memory usage during load
PID=$(cat proxy.pid 2>/dev/null || pgrep -f "uvicorn.*main:app")

if [ -n "$PID" ]; then
    echo "Monitoring memory usage for PID: $PID"

    # Get baseline memory
    echo "Baseline memory usage:"
    ps -o pid,rss,vsz,pcpu -p "$PID"
    baseline_rss=$(ps -o rss= -p "$PID" | tr -d ' ')

    # Start load test in background
    python3 -c "
import requests
import time
import threading

def load_generator():
    for i in range(20):
        try:
            requests.post(
                'http://localhost:10000/responses',
                json={
                    'input': [{
                        'type': 'message',
                        'content': [{'type': 'input_text', 'text': f'Memory test {i}' * 50}]
                    }]
                },
                headers={'Authorization': 'Bearer dummy_token'},
                timeout=3
            )
            time.sleep(0.2)
        except:
            pass

# Start load generator
thread = threading.Thread(target=load_generator)
thread.start()
thread.join()
print('Load test completed')
" &

    # Monitor during load
    echo "Memory during load test:"
    for i in {1..15}; do
        ps -o pid,rss,vsz,pcpu -p "$PID" 2>/dev/null || break
        sleep 1
    done

    wait  # Wait for background load test

    # Check final memory
    echo "Final memory usage:"
    ps -o pid,rss,vsz,pcpu -p "$PID"
    final_rss=$(ps -o rss= -p "$PID" 2>/dev/null | tr -d ' ')

    if [ -n "$baseline_rss" ] && [ -n "$final_rss" ]; then
        memory_growth=$((final_rss - baseline_rss))
        echo "Memory growth: ${memory_growth}KB"

        # Alert if memory grew significantly
        if [ "$memory_growth" -gt 50000 ]; then  # 50MB
            echo "WARNING: Significant memory growth detected"
        fi
    fi
else
    echo "Proxy process not found"
fi
```

**Expected Result**:
- Memory usage remains stable or grows minimally
- No memory leaks (RSS should not grow continuously)
- CPU usage remains reasonable (< 50% sustained)

### 4. Hook Performance Impact

```bash
# Measure hook processing overhead
echo "Testing hook performance impact..."

# First, create a performance test hook
cat > .codexplus/hooks/perf_test.py << 'EOF'
---
name: perf_test
type: pre-input
priority: 50
enabled: true
---

import time
import logging
from codex_plus.hooks import Hook

logger = logging.getLogger(__name__)

class PerfTestHook(Hook):
    async def pre_input(self, request, body):
        start = time.time()
        # Simulate some processing
        await asyncio.sleep(0.001)  # 1ms delay
        end = time.time()
        logger.info(f"PerfTestHook processing time: {(end-start)*1000:.2f}ms")
        return body
EOF

# Restart to load performance hook
./proxy.sh restart
sleep 3

# Test with and without hooks
python3 -c "
import requests
import time
import json
from pathlib import Path

def measure_request_time():
    start = time.time()
    try:
        response = requests.post(
            'http://localhost:10000/responses',
            json={'input': [{'type': 'message', 'content': [{'type': 'input_text', 'text': 'perf test'}]}]},
            headers={'Authorization': 'Bearer dummy_token'},
            timeout=5
        )
        end = time.time()
        return end - start
    except:
        return None

# Measure with hooks enabled
times_with_hooks = []
for i in range(5):
    t = measure_request_time()
    if t:
        times_with_hooks.append(t)
    time.sleep(0.1)

if times_with_hooks:
    avg_with_hooks = sum(times_with_hooks) / len(times_with_hooks)
    print(f'Average request time with hooks: {avg_with_hooks:.3f}s')
else:
    print('No successful requests with hooks')
"

# Check hook execution times in logs
grep -i "perftesthook processing time" proxy.log | tail -5
```

**Expected Result**:
- Hook processing time < 10ms per hook
- Total request time increase < 100ms due to hooks
- Hooks don't significantly impact performance

### 5. Status Line Performance

```bash
# Test status line generation performance
echo "Testing status line performance..."

python3 -c "
import sys
sys.path.append('src')
from codex_plus.hooks import hook_system
import asyncio
import time

async def benchmark_status_line():
    times = []
    for i in range(10):
        start = time.time()
        status = await hook_system.run_status_line()
        end = time.time()
        times.append(end - start)

    if times:
        avg_time = sum(times) / len(times)
        max_time = max(times)
        min_time = min(times)
        print(f'Status line generation:')
        print(f'  Average: {avg_time:.3f}s')
        print(f'  Min: {min_time:.3f}s')
        print(f'  Max: {max_time:.3f}s')

        if avg_time > 1.0:  # Warn if > 1 second
            print('  WARNING: Status line generation is slow')

asyncio.run(benchmark_status_line())
"
```

**Expected Result**:
- Status line generation < 500ms average
- Consistent timing across runs
- No significant performance degradation

### 6. Large Payload Handling

```bash
# Test with various payload sizes
echo "Testing large payload handling..."

python3 -c "
import requests
import time

payload_sizes = [1, 10, 100, 1000]  # KB

for size_kb in payload_sizes:
    # Create payload of specified size
    content = 'x' * (size_kb * 1024)
    payload = {
        'input': [{
            'type': 'message',
            'content': [{'type': 'input_text', 'text': content}]
        }]
    }

    start = time.time()
    try:
        response = requests.post(
            'http://localhost:10000/responses',
            json=payload,
            headers={'Authorization': 'Bearer dummy_token'},
            timeout=10
        )
        end = time.time()
        print(f'{size_kb}KB payload: {end-start:.3f}s (status: {response.status_code})')
    except Exception as e:
        end = time.time()
        print(f'{size_kb}KB payload: {end-start:.3f}s (error: {type(e).__name__})')
"
```

**Expected Result**:
- Smaller payloads (1-10KB) process quickly (< 1s)
- Larger payloads handled without crashes
- Response time scales reasonably with payload size

### 7. Resource Cleanup Test

```bash
# Test that resources are properly cleaned up
echo "Testing resource cleanup..."

# Check file descriptors before load
initial_fd_count=$(lsof -p $(cat proxy.pid 2>/dev/null || pgrep -f "uvicorn.*main:app") 2>/dev/null | wc -l)
echo "Initial file descriptors: $initial_fd_count"

# Generate load
python3 -c "
import requests
import concurrent.futures

def make_request(i):
    try:
        requests.post(
            'http://localhost:10000/responses',
            json={'input': [{'type': 'message', 'content': [{'type': 'input_text', 'text': f'cleanup test {i}'}]}]},
            headers={'Authorization': 'Bearer dummy_token'},
            timeout=2
        )
    except:
        pass

# Make 30 concurrent requests
with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
    futures = [executor.submit(make_request, i) for i in range(30)]
    [f.result() for f in concurrent.futures.as_completed(futures)]

print('Load generation completed')
"

# Wait for cleanup
sleep 5

# Check file descriptors after load
final_fd_count=$(lsof -p $(cat proxy.pid 2>/dev/null || pgrep -f "uvicorn.*main:app") 2>/dev/null | wc -l)
echo "Final file descriptors: $final_fd_count"

# Calculate change
fd_change=$((final_fd_count - initial_fd_count))
echo "File descriptor change: $fd_change"

if [ "$fd_change" -gt 50 ]; then
    echo "WARNING: Potential file descriptor leak detected"
else
    echo "Resource cleanup appears normal"
fi
```

**Expected Result**:
- File descriptor count returns close to baseline after load
- No significant resource leaks
- Process remains stable

## Success Criteria Checklist

- [ ] Baseline response times acceptable (< 50ms health, < 500ms JSON)
- [ ] Handles 10 concurrent requests with > 80% success rate
- [ ] Memory usage remains stable under load
- [ ] Hook processing overhead < 10ms per hook
- [ ] Status line generation < 500ms
- [ ] Large payloads handled without crashes
- [ ] No significant resource leaks after load testing
- [ ] Server remains responsive after all tests

## Cleanup

```bash
# Remove performance test hook
rm -f .codexplus/hooks/perf_test.py

# Restart to clean state
./proxy.sh restart

# Verify clean startup
sleep 3
curl http://localhost:10000/health
```

**Expected Result**:
- Clean restart successful
- Normal performance restored
- Health check passes

## Troubleshooting

**If performance is poor**:
- Check system resources: `top`, `free -m`, `df -h`
- Monitor network latency to upstream
- Review hook complexity and async usage
- Check for blocking operations in hooks

**If memory usage grows**:
- Look for unclosed connections or streams
- Check hook implementations for memory leaks
- Monitor garbage collection: `import gc; gc.collect()`

**If concurrent requests fail**:
- Check FastAPI worker configuration
- Verify async/await usage throughout codebase
- Monitor file descriptor limits: `ulimit -n`
- Check for deadlocks in hook execution

**Performance degradation troubleshooting**:
- Profile hook execution times
- Check git command performance (status line)
- Monitor upstream response times
- Review log levels (excessive logging can impact performance)