# Dual-Proxy Implementation Issues

## Issue #1: Proxy Script Process Management Conflict

### Problem
The `proxy.sh` script cannot run two proxy instances simultaneously because:

1. **Global Process Killing**: The script kills ALL python processes matching the proxy module pattern
   ```bash
   # Line ~280 in proxy.sh
   pkill -f "python.*$PROXY_MODULE"
   ```

2. **Single PID File**: Uses a single PID file `/tmp/codex_plus/proxy.pid`
   - Starting a second proxy overwrites this file
   - Stopping one proxy kills both instances

3. **Port Checking Logic**: Checks for processes on "default" port (10000)
   - Even with `PROXY_PORT=10001`, still kills port 10000 processes

### Impact
- Cannot run passthrough (10000) and Cerebras (10001) proxies simultaneously
- Dual-proxy validation testing requires manual intervention
- Test script `dual_proxy_test.sh` cannot work as designed

### Solution Options

#### Option 1: Port-Specific PID Files (Recommended)
```bash
# Use port-specific PID file
PID_FILE="$RUNTIME_DIR/proxy_${PROXY_PORT}.pid"
LOCK_FILE="$RUNTIME_DIR/proxy_${PROXY_PORT}.lock"

# Only kill processes on THIS port
if lsof -ti:$PROXY_PORT >/dev/null 2>&1; then
    kill $(lsof -ti:$PROXY_PORT)
fi
```

**Pros**: Clean isolation, supports N proxies
**Cons**: Requires refactoring proxy.sh

#### Option 2: Background uvicorn (Simpler)
```bash
# Start second proxy directly
export PYTHONPATH=src
PROXY_PORT=10001 \
CODEX_PLUS_UPSTREAM_URL="https://api.cerebras.ai/v1" \
CODEX_PLUS_PROVIDER_MODE="cerebras" \
nohup python -c "..." > /tmp/cerebras_proxy.log 2>&1 &
```

**Pros**: Works now, no script changes
**Cons**: No management, manual cleanup

#### Option 3: Separate Test Script
Create `start_dual_proxies.sh` specifically for testing:
```bash
#!/bin/bash
# Start passthrough on 10000
CODEX_PLUS_LOGGING_MODE=true ./proxy.sh enable

# Start Cerebras manually on 10001
export PYTHONPATH=src
PROXY_PORT=10001 uvicorn ... &
echo $! > /tmp/cerebras_proxy.pid
```

**Pros**: Keeps proxy.sh simple
**Cons**: Duplication, maintenance burden

### Recommendation
Implement **Option 1** - port-specific PID files. This provides:
- ✅ Clean multi-instance support
- ✅ Proper process isolation
- ✅ Works with existing test scripts
- ✅ Future-proof for N proxy instances

### Implementation Tasks
- [ ] Add port-specific PID/lock file logic to proxy.sh
- [ ] Update process killing to target specific port only
- [ ] Test dual-proxy startup/shutdown
- [ ] Update test scripts to use new logic
- [ ] Document multi-instance usage

## Issue #2: Test Script Environment Variables

### Problem
Test script uses inline environment variables:
```bash
PROXY_PORT=10001 ./proxy.sh --cerebras enable  # Fails: command not found
```

Bash requires `export` for subprocess visibility.

### Solution
```bash
export PROXY_PORT=10001
./proxy.sh --cerebras enable
```

### Status
- ✅ Documented in dual_proxy_test.sh
- ⚠️  Still fails due to Issue #1 (process killing)

## Workaround for Current Testing

Until Issue #1 is fixed, use manual approach:

```bash
# Terminal 1: Passthrough proxy
CODEX_PLUS_LOGGING_MODE=true ./proxy.sh restart

# Terminal 2: Cerebras proxy (manual)
export PYTHONPATH=src PROXY_PORT=10001
export CODEX_PLUS_UPSTREAM_URL="https://api.cerebras.ai/v1"
export CODEX_PLUS_PROVIDER_MODE="cerebras"

python -c "
from codex_plus.main_sync_cffi import app
import uvicorn
uvicorn.run(app, host='127.0.0.1', port=10001)
"

# Terminal 3: Run test
./testing_integration/dual_proxy_test.sh
```

## Next Steps

1. **Short-term**: Use manual workaround for validation
2. **Medium-term**: Implement Option 1 (port-specific PID files)
3. **Long-term**: Consider containerization (Docker Compose) for isolation
