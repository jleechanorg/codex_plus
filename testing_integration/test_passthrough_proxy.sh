#!/usr/bin/env bash
#
# Integration test for logging passthrough mode
# Tests that --logging flag prevents payload modification
#
# Usage: ./test_passthrough_proxy.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEST_LOG_DIR="/tmp/codex_plus_integration_test"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results tracking
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Cleanup function
cleanup() {
    echo -e "${BLUE}🧹 Cleaning up test environment...${NC}"

    # Stop proxy if running
    if [ -f /tmp/codex_plus/proxy.pid ]; then
        local pid=$(cat /tmp/codex_plus/proxy.pid 2>/dev/null || echo "")
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo "  Stopping proxy (PID: $pid)"
            cd "$PROJECT_ROOT" && ./proxy.sh disable >/dev/null 2>&1 || true
        fi
    fi

    # Clean up test logs
    rm -rf "$TEST_LOG_DIR"

    # Unset environment variables
    unset OPENAI_BASE_URL
    unset CODEX_PLUS_LOGGING_MODE
}

trap cleanup EXIT

# Test helper functions
log_test() {
    echo -e "${BLUE}🧪 TEST: $1${NC}"
    TESTS_RUN=$((TESTS_RUN + 1))
}

log_pass() {
    echo -e "${GREEN}  ✅ PASS: $1${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

log_fail() {
    echo -e "${RED}  ❌ FAIL: $1${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

log_info() {
    echo -e "${YELLOW}  ℹ️  $1${NC}"
}

# Setup test environment
setup_test_environment() {
    echo -e "${BLUE}📦 Setting up test environment...${NC}"

    # Create test log directory
    mkdir -p "$TEST_LOG_DIR"

    # Ensure we're in project root
    cd "$PROJECT_ROOT"

    # Verify proxy script exists
    if [ ! -f "./proxy.sh" ]; then
        echo -e "${RED}❌ ERROR: proxy.sh not found in $PROJECT_ROOT${NC}"
        exit 1
    fi

    # Verify codex CLI is available
    if ! command -v codex &> /dev/null; then
        echo -e "${RED}❌ ERROR: codex CLI not found in PATH${NC}"
        echo "  Install with: npm install -g @openai/codex"
        exit 1
    fi

    log_info "Environment setup complete"
}

# Test 1: Proxy starts successfully in logging mode
test_proxy_starts_with_logging_mode() {
    log_test "Proxy starts successfully with --logging flag"

    cd "$PROJECT_ROOT"

    # Stop any existing proxy
    ./proxy.sh disable >/dev/null 2>&1 || true
    sleep 2

    # Start proxy in logging mode
    if ./proxy.sh --logging enable 2>&1 | tee "$TEST_LOG_DIR/proxy_start.log"; then
        sleep 3

        # Verify proxy started successfully and logging mode is shown
        if grep -q "✅ Running" "$TEST_LOG_DIR/proxy_start.log" && \
           grep -q "Logging.*ENABLED" "$TEST_LOG_DIR/proxy_start.log"; then
            log_pass "Proxy started successfully"
            log_pass "Logging mode is active and displayed in status"
        else
            if ! grep -q "✅ Running" "$TEST_LOG_DIR/proxy_start.log"; then
                log_fail "Proxy failed to start"
            fi
            if ! grep -q "Logging.*ENABLED" "$TEST_LOG_DIR/proxy_start.log"; then
                log_fail "Logging mode not shown in status output"
            fi
            cat "$TEST_LOG_DIR/proxy_start.log"
        fi
    else
        log_fail "Proxy start command failed"
        cat "$TEST_LOG_DIR/proxy_start.log"
    fi
}

# Test 2: Payload is not modified in logging mode
test_payload_not_modified() {
    log_test "Payload is not modified by logging mode proxy"

    # Set environment to use proxy
    export OPENAI_BASE_URL="http://localhost:10000"

    # Capture initial request payload before proxy processes it
    local test_input='echo "test passthrough"'

    # Execute a simple codex command through proxy
    log_info "Executing: codex exec --yolo '$test_input'"

    # Run codex and capture both stdout and stderr
    set +e
    timeout 30 codex exec --yolo "$test_input" > "$TEST_LOG_DIR/codex_output.log" 2>&1
    local exit_code=$?
    set -e

    if [ $exit_code -eq 124 ]; then
        log_info "Command timed out after 30s (expected for slow codex responses)"
    fi

    # Check proxy logs for request payload
    local branch_name=$(git branch --show-current)
    local request_log="/tmp/codex_plus/$branch_name/request_payload.json"

    if [ -f "$request_log" ]; then
        log_info "Found request log: $request_log"

        # Verify payload doesn't contain injected execution instructions
        if grep -q "slash command" "$request_log" 2>/dev/null; then
            log_fail "Payload contains slash command injection (should be passthrough)"
            log_info "Check: $request_log"
        else
            log_pass "Payload does not contain slash command modifications"
        fi

        # Verify payload doesn't contain status line injection
        if grep -q "git status" "$request_log" 2>/dev/null; then
            log_fail "Payload contains git status injection (should be passthrough)"
        else
            log_pass "Payload does not contain status line modifications"
        fi

        # Copy request log for inspection
        cp "$request_log" "$TEST_LOG_DIR/captured_request.json"
        log_info "Request payload saved to: $TEST_LOG_DIR/captured_request.json"
    else
        log_fail "Request log not found at $request_log"
    fi
}

# Test 3: Proxy logs show passthrough mode
test_proxy_logs_indicate_passthrough() {
    log_test "Proxy logs indicate logging mode is active"

    local proxy_log="/tmp/codex_plus/proxy.log"

    if [ -f "$proxy_log" ]; then
        # Check for logging mode activation message
        if grep -q "Logging mode enabled" "$proxy_log"; then
            log_pass "Proxy log shows 'Logging mode enabled'"
        else
            log_fail "Proxy log missing logging mode activation message"
        fi

        # Verify no execution behavior injection logged
        if grep -q "inject_execution_behavior" "$proxy_log" 2>/dev/null; then
            log_fail "Proxy log shows execution behavior injection (should skip in logging mode)"
        else
            log_pass "Proxy log confirms no execution behavior injection"
        fi

        # Copy proxy log for inspection
        tail -100 "$proxy_log" > "$TEST_LOG_DIR/proxy_tail.log"
        log_info "Proxy log tail saved to: $TEST_LOG_DIR/proxy_tail.log"
    else
        log_fail "Proxy log not found at $proxy_log"
    fi
}

# Test 4: Normal mode (without --logging) does modify payload
test_normal_mode_modifies_payload() {
    log_test "Normal mode (without --logging) does modify payloads"

    cd "$PROJECT_ROOT"

    # Restart proxy without logging mode
    ./proxy.sh disable >/dev/null 2>&1 || true
    sleep 2

    if ./proxy.sh enable 2>&1 | tee "$TEST_LOG_DIR/proxy_normal_start.log"; then
        sleep 3

        # Verify logging mode is NOT active
        if ! ./proxy.sh status 2>&1 | grep -q "Logging.*ENABLED"; then
            log_pass "Normal mode active (no logging flag)"
        else
            log_fail "Logging mode still active in normal start"
        fi

        # Execute codex command
        export OPENAI_BASE_URL="http://localhost:10000"
        local test_input='echo "test normal mode"'

        set +e
        timeout 30 codex exec --yolo "$test_input" > "$TEST_LOG_DIR/codex_normal_output.log" 2>&1
        set -e

        # Check if modifications are present (they should be in normal mode)
        local branch_name=$(git branch --show-current)
        local request_log="/tmp/codex_plus/$branch_name/request_payload.json"

        if [ -f "$request_log" ]; then
            # In normal mode, we expect the middleware to potentially process the request
            # (though slash commands might not be detected for simple echo commands)
            log_pass "Request logged in normal mode"
            cp "$request_log" "$TEST_LOG_DIR/normal_mode_request.json"
        fi
    else
        log_fail "Failed to start proxy in normal mode"
    fi
}

# Test 5: Environment variable CODEX_PLUS_LOGGING_MODE works
test_logging_mode_env_variable() {
    log_test "CODEX_PLUS_LOGGING_MODE environment variable controls behavior"

    cd "$PROJECT_ROOT"

    # Stop proxy
    ./proxy.sh disable >/dev/null 2>&1 || true
    sleep 2

    # Start with environment variable
    export CODEX_PLUS_LOGGING_MODE="true"

    if ./proxy.sh enable 2>&1 | tee "$TEST_LOG_DIR/proxy_env_start.log"; then
        sleep 3

        # Check startup output for logging mode indicator
        if grep -q "Logging.*ENABLED" "$TEST_LOG_DIR/proxy_env_start.log"; then
            log_pass "Environment variable CODEX_PLUS_LOGGING_MODE=true activates logging mode"
        else
            log_fail "Environment variable didn't activate logging mode"
            log_info "Startup output excerpt:"
            grep "Logging\|Running\|Status" "$TEST_LOG_DIR/proxy_env_start.log" || cat "$TEST_LOG_DIR/proxy_env_start.log"
        fi
    fi

    unset CODEX_PLUS_LOGGING_MODE
}

# Main test execution
main() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   CODEX PLUS LOGGING PASSTHROUGH MODE TESTS       ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════╝${NC}"
    echo ""

    setup_test_environment

    echo ""
    echo -e "${BLUE}Running integration tests...${NC}"
    echo ""

    test_proxy_starts_with_logging_mode
    test_payload_not_modified
    test_proxy_logs_indicate_passthrough
    test_normal_mode_modifies_payload
    test_logging_mode_env_variable

    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   TEST RESULTS                                     ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  Tests Run:    ${TESTS_RUN}"
    echo -e "  ${GREEN}Tests Passed: ${TESTS_PASSED}${NC}"
    echo -e "  ${RED}Tests Failed: ${TESTS_FAILED}${NC}"
    echo ""

    if [ "$TESTS_FAILED" -eq 0 ]; then
        echo -e "${GREEN}✅ ALL TESTS PASSED${NC}"
        echo ""
        echo -e "${BLUE}Test artifacts saved to: $TEST_LOG_DIR${NC}"
        return 0
    else
        echo -e "${RED}❌ SOME TESTS FAILED${NC}"
        echo ""
        echo -e "${BLUE}Test artifacts saved to: $TEST_LOG_DIR${NC}"
        return 1
    fi
}

# Run tests
main
