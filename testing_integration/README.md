# Integration Tests for Codex Plus Proxy

This directory contains integration tests that verify the Codex Plus proxy behavior with real `codex` CLI execution.

## Overview

Integration tests validate:
- Proxy startup and configuration
- Logging passthrough mode functionality
- Payload modification detection
- Environment variable controls
- Request/response logging

## Prerequisites

### Required Tools

1. **Codex CLI**: The OpenAI Codex command-line interface
   ```bash
   npm install -g @openai/codex
   ```

2. **Python 3.9+**: For proxy server
   ```bash
   python3 --version
   ```

3. **Virtual Environment**: Proxy dependencies
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

### Environment Setup

Ensure you have:
- Valid Codex API credentials configured
- Network access to Codex API endpoints
- Port 10000 available for proxy

## Test Files

### `test_passthrough_proxy.sh`

Comprehensive integration test for logging passthrough mode.

**Tests Included:**

1. **Proxy Startup Test**
   - Verifies proxy starts with `--logging` flag
   - Confirms logging mode is active in status output

2. **Payload Passthrough Test**
   - Executes real `codex exec --yolo` commands
   - Checks request logs to ensure no modifications
   - Verifies no slash command injection
   - Verifies no status line injection

3. **Proxy Logging Test**
   - Validates logging mode activation messages
   - Confirms execution behavior injection is skipped

4. **Normal Mode Comparison**
   - Tests proxy without `--logging` flag
   - Ensures normal processing still works

5. **Environment Variable Test**
   - Tests `CODEX_PLUS_LOGGING_MODE=true` variable
   - Validates environment-based activation

**Usage:**

```bash
# Run all tests
./testing_integration/test_passthrough_proxy.sh

# View test artifacts
ls -la /tmp/codex_plus_integration_test/
```

**Test Artifacts:**

After execution, test artifacts are saved to `/tmp/codex_plus_integration_test/`:
- `proxy_start.log` - Proxy startup output
- `codex_output.log` - Codex CLI output
- `captured_request.json` - Actual request payload sent to upstream
- `proxy_tail.log` - Recent proxy log entries
- `normal_mode_request.json` - Request in normal mode for comparison

## Running Tests

### Quick Start

```bash
# Ensure you're in the project root
cd /path/to/codex_plus

# Run integration tests
./testing_integration/test_passthrough_proxy.sh
```

### Manual Testing

For manual verification:

```bash
# 1. Start proxy in logging mode
./proxy.sh --logging enable

# 2. Check status
./proxy.sh status

# 3. Run codex through proxy
OPENAI_BASE_URL=http://localhost:10000 codex exec --yolo 'echo "test"'

# 4. Inspect request log
cat /tmp/codex_plus/$(git branch --show-current)/request_payload.json

# 5. Stop proxy
./proxy.sh disable
```

## Expected Test Results

### Successful Test Output

```
╔════════════════════════════════════════════════════╗
║   CODEX PLUS LOGGING PASSTHROUGH MODE TESTS       ║
╚════════════════════════════════════════════════════╝

📦 Setting up test environment...
  ℹ️  Environment setup complete

Running integration tests...

🧪 TEST: Proxy starts successfully with --logging flag
  ✅ PASS: Proxy started successfully
  ✅ PASS: Logging mode is active and displayed in status

🧪 TEST: Payload is not modified by logging mode proxy
  ℹ️  Executing: codex exec --yolo 'echo "test passthrough"'
  ✅ PASS: Payload does not contain slash command modifications
  ✅ PASS: Payload does not contain status line modifications

🧪 TEST: Proxy logs indicate logging mode is active
  ✅ PASS: Proxy log shows 'Logging mode enabled'
  ✅ PASS: Proxy log confirms no execution behavior injection

🧪 TEST: Normal mode (without --logging) does modify payloads
  ✅ PASS: Normal mode active (no logging flag)
  ✅ PASS: Request logged in normal mode

🧪 TEST: CODEX_PLUS_LOGGING_MODE environment variable controls behavior
  ✅ PASS: Environment variable CODEX_PLUS_LOGGING_MODE=true activates logging mode

╔════════════════════════════════════════════════════╗
║   TEST RESULTS                                     ║
╚════════════════════════════════════════════════════╝

  Tests Run:    5
  Tests Passed: 10
  Tests Failed: 0

✅ ALL TESTS PASSED
```

## Debugging Failed Tests

### Common Issues

1. **Port 10000 already in use**
   ```bash
   # Check what's using the port
   lsof -i :10000

   # Stop existing proxy
   ./proxy.sh disable
   ```

2. **Codex CLI not found**
   ```bash
   # Install codex globally
   npm install -g @openai/codex

   # Verify installation
   which codex
   ```

3. **Request log not found**
   - Ensure proxy is actually processing requests
   - Check `/tmp/codex_plus/proxy.log` for errors
   - Verify OPENAI_BASE_URL is set correctly

4. **Timeout during codex exec**
   - Normal for slow API responses
   - Tests account for timeouts
   - Check network connectivity to Codex API

### Inspecting Test Artifacts

```bash
# View all test artifacts
ls -la /tmp/codex_plus_integration_test/

# Check captured request payload
jq '.' /tmp/codex_plus_integration_test/captured_request.json

# View proxy logs
tail -50 /tmp/codex_plus_integration_test/proxy_tail.log

# Compare normal vs logging mode
diff /tmp/codex_plus_integration_test/normal_mode_request.json \
     /tmp/codex_plus_integration_test/captured_request.json
```

## CI/CD Integration

These integration tests are designed to run in CI environments but may be skipped due to:
- Codex API credentials requirement
- External API dependencies
- Longer execution time

To run in CI:

```yaml
# Example GitHub Actions workflow
- name: Run Integration Tests
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  run: |
    ./testing_integration/test_passthrough_proxy.sh
  # Allow failures for now due to API dependencies
  continue-on-error: true
```

## Test Coverage

| Feature | Test Coverage |
|---------|--------------|
| Proxy startup with --logging | ✅ |
| Logging mode status display | ✅ |
| Payload passthrough verification | ✅ |
| No slash command injection | ✅ |
| No status line injection | ✅ |
| Logging mode messages | ✅ |
| Environment variable control | ✅ |
| Normal mode comparison | ✅ |

## Contributing

When adding new integration tests:

1. Follow the existing test helper pattern
2. Use descriptive test names
3. Clean up resources in trap handlers
4. Save test artifacts for debugging
5. Provide clear pass/fail messages
6. Update this README with new tests

## Related Documentation

- [proxy.sh](../proxy.sh) - Proxy control script
- [CLAUDE.md](../CLAUDE.md) - Architecture and usage
- [README.md](../README.md) - Project overview
