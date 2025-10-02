#!/usr/bin/env bash
#
# Quick smoke test for passthrough proxy
# Tests basic functionality without full codex execution
#
# Usage: ./smoke_test.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 Codex Plus Proxy Smoke Test${NC}"
echo ""

cd "$PROJECT_ROOT"

# Test 1: Proxy can start with logging mode
echo -e "${BLUE}Test 1: Starting proxy with --logging flag...${NC}"
./proxy.sh disable >/dev/null 2>&1 || true
sleep 1

if ./proxy.sh --logging enable 2>&1 | grep -q "Starting"; then
    echo -e "${GREEN}✅ Proxy started successfully${NC}"
    sleep 2
else
    echo -e "${RED}❌ Failed to start proxy${NC}"
    exit 1
fi

# Test 2: Status shows logging mode
echo -e "${BLUE}Test 2: Checking proxy status...${NC}"
if ./proxy.sh status | grep -q "Logging: ENABLED"; then
    echo -e "${GREEN}✅ Logging mode is active${NC}"
else
    echo -e "${RED}❌ Logging mode not shown in status${NC}"
    ./proxy.sh status
    exit 1
fi

# Test 3: Health endpoint works
echo -e "${BLUE}Test 3: Testing health endpoint...${NC}"
if curl -sf http://localhost:10000/health | grep -q "healthy"; then
    echo -e "${GREEN}✅ Health endpoint responding${NC}"
else
    echo -e "${RED}❌ Health endpoint not responding${NC}"
    exit 1
fi

# Test 4: Environment variable is set
echo -e "${BLUE}Test 4: Checking environment variable...${NC}"
./proxy.sh stop >/dev/null 2>&1 || true
sleep 1

export CODEX_PLUS_LOGGING_MODE="true"
./proxy.sh enable >/dev/null 2>&1
sleep 2

if grep -q "Logging mode enabled" /tmp/codex_plus/proxy.log 2>/dev/null; then
    echo -e "${GREEN}✅ Environment variable controls logging mode${NC}"
else
    echo -e "${RED}❌ Environment variable not working${NC}"
    tail -20 /tmp/codex_plus/proxy.log
    exit 1
fi

# Cleanup
./proxy.sh disable >/dev/null 2>&1 || true
unset CODEX_PLUS_LOGGING_MODE

echo ""
echo -e "${GREEN}✅ All smoke tests passed!${NC}"
