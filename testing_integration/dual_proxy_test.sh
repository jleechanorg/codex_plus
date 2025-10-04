#!/bin/bash

# Dual-Proxy Validation Test
# Runs the same request through both passthrough and Cerebras proxies and compares outputs

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🔬 Dual-Proxy Validation Test${NC}"
echo -e "================================\n"

# Test request
TEST_PROMPT="${1:-Write a hello world function in Python}"

echo -e "${BLUE}📝 Test Prompt:${NC} $TEST_PROMPT\n"

# Step 1: Ensure passthrough proxy is running
echo -e "${BLUE}Step 1: Check passthrough proxy (port 10000)${NC}"
if ! curl -s -f http://localhost:10000/health >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Passthrough proxy not running, starting...${NC}"
    cd "$PROJECT_ROOT"
    CODEX_PLUS_LOGGING_MODE=true ./proxy.sh restart
    sleep 3
fi

if curl -s -f http://localhost:10000/health >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Passthrough proxy ready on port 10000${NC}\n"
else
    echo -e "${RED}❌ Failed to start passthrough proxy${NC}"
    exit 1
fi

# Step 2: Ensure Cerebras proxy is running on different port
echo -e "${BLUE}Step 2: Check Cerebras proxy (port 10001)${NC}"

# Check required Cerebras environment variables
if [ -z "${CEREBRAS_API_KEY:-}" ] || [ -z "${CEREBRAS_MODEL:-}" ]; then
    echo -e "${RED}❌ Missing Cerebras configuration${NC}"
    echo -e "   Set CEREBRAS_API_KEY and CEREBRAS_MODEL environment variables"
    exit 1
fi

# Stop any existing process on 10001
if lsof -ti:10001 >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Stopping existing process on port 10001${NC}"
    kill $(lsof -ti:10001) 2>/dev/null || true
    sleep 2
fi

# Start Cerebras proxy on port 10001
echo -e "${YELLOW}🚀 Starting Cerebras proxy on port 10001...${NC}"
cd "$PROJECT_ROOT"

# Export required variables for subprocess
export PROXY_PORT=10001
export CEREBRAS_API_KEY
export CEREBRAS_MODEL
export CEREBRAS_BASE_URL="${CEREBRAS_BASE_URL:-https://api.cerebras.ai/v1}"

# Start proxy in background
PROXY_PORT=10001 ./proxy.sh --cerebras enable

# Wait for Cerebras proxy to be ready
for i in {1..10}; do
    if curl -s -f http://localhost:10001/health >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Cerebras proxy ready on port 10001${NC}\n"
        break
    fi
    sleep 1
    if [ $i -eq 10 ]; then
        echo -e "${RED}❌ Cerebras proxy failed to start${NC}"
        exit 1
    fi
done

# Step 3: Send request to passthrough proxy
echo -e "${BLUE}Step 3: Send request to passthrough proxy${NC}"

# Create simple test request
REQUEST_JSON=$(cat <<EOF
{
    "model": "gpt-5-codex",
    "input": [{
        "type": "message",
        "role": "user",
        "content": [{"type": "input_text", "text": "$TEST_PROMPT"}]
    }],
    "stream": true
}
EOF
)

echo "$REQUEST_JSON" | curl -s -X POST http://localhost:10000/responses \
    -H "Content-Type: application/json" \
    -d @- > /tmp/passthrough_output.txt

if [ -s /tmp/passthrough_output.txt ]; then
    echo -e "${GREEN}✅ Received response from passthrough proxy${NC}"
    echo -e "   Saved to /tmp/passthrough_output.txt\n"
else
    echo -e "${RED}❌ No response from passthrough proxy${NC}"
    exit 1
fi

# Step 4: Send same request to Cerebras proxy
echo -e "${BLUE}Step 4: Send request to Cerebras proxy${NC}"

echo "$REQUEST_JSON" | curl -s -X POST http://localhost:10001/responses \
    -H "Content-Type: application/json" \
    -d @- > /tmp/cerebras_output.txt

if [ -s /tmp/cerebras_output.txt ]; then
    echo -e "${GREEN}✅ Received response from Cerebras proxy${NC}"
    echo -e "   Saved to /tmp/cerebras_output.txt\n"
else
    echo -e "${RED}❌ No response from Cerebras proxy${NC}"
    exit 1
fi

# Step 5: Compare responses
echo -e "${BLUE}Step 5: Compare responses${NC}"

if command -v python3 &> /dev/null; then
    python3 "$SCRIPT_DIR/compare_proxies.py"
    COMPARISON_RESULT=$?
else
    echo -e "${YELLOW}⚠️  Python3 not found, skipping automated comparison${NC}"
    echo -e "${BLUE}Manual comparison:${NC}"
    echo -e "  diff /tmp/passthrough_output.txt /tmp/cerebras_output.txt"
    COMPARISON_RESULT=0
fi

# Cleanup: Stop Cerebras proxy
echo -e "\n${BLUE}Cleanup: Stop Cerebras proxy${NC}"
if lsof -ti:10001 >/dev/null 2>&1; then
    kill $(lsof -ti:10001) 2>/dev/null || true
    echo -e "${GREEN}✅ Cerebras proxy stopped${NC}"
fi

# Final result
echo -e "\n================================"
if [ $COMPARISON_RESULT -eq 0 ]; then
    echo -e "${GREEN}✅ DUAL-PROXY TEST PASSED${NC}"
    exit 0
else
    echo -e "${RED}❌ DUAL-PROXY TEST FAILED${NC}"
    exit 1
fi
