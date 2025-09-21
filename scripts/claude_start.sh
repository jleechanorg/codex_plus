#!/bin/bash
# Enhanced Claude Code startup script for Codex Plus
# Starts the proxy and launches Claude Code with appropriate settings

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse command line arguments
FORCE_CLEAN=false
MODE=""
REMAINING_ARGS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--clean)
            FORCE_CLEAN=true
            shift
            ;;
        -d|--default)
            MODE="default"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            REMAINING_ARGS+=("$1")
            shift
            ;;
    esac
done

# Show help function
show_help() {
    cat << 'EOF'
claude_start.sh - Start Codex Plus proxy and Claude Code

USAGE
    ./claude_start.sh [options] [claude_args...]

OPTIONS
    -c, --clean     Force clean start (stop existing proxy)
    -d, --default   Use default settings
    -h, --help      Show this help

EXAMPLES
    ./claude_start.sh                    # Start with default settings
    ./claude_start.sh --clean            # Clean restart
    ./claude_start.sh "help me code"     # Start with initial prompt
EOF
}

# Restore remaining arguments for Claude
set -- "${REMAINING_ARGS[@]}"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}🚀 Starting Codex Plus...${NC}"

# Check if proxy is already running
if [ -f "/tmp/codex_plus_proxy.pid" ]; then
    PID=$(cat "/tmp/codex_plus_proxy.pid")
    if kill -0 "$PID" 2>/dev/null; then
        if [ "$FORCE_CLEAN" = true ]; then
            echo -e "${YELLOW}🔄 Stopping existing proxy...${NC}"
            "$PROJECT_ROOT/proxy.sh" disable
            sleep 2
        else
            echo -e "${GREEN}✅ Proxy already running (PID: $PID)${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Stale PID file found, cleaning up...${NC}"
        rm -f "/tmp/codex_plus_proxy.pid"
    fi
fi

# Start proxy if not running
if ! pgrep -f "codex_plus.*main" > /dev/null; then
    echo -e "${BLUE}🔧 Starting Codex Plus proxy...${NC}"
    if ! "$PROJECT_ROOT/proxy.sh" enable; then
        echo -e "${RED}❌ Failed to start proxy${NC}"
        exit 1
    fi

    # Wait for proxy to be ready
    echo -e "${BLUE}⏳ Waiting for proxy to be ready...${NC}"
    for i in {1..10}; do
        if curl -s http://localhost:10000/health > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Proxy is ready${NC}"
            break
        fi
        if [ $i -eq 10 ]; then
            echo -e "${RED}❌ Proxy failed to start properly${NC}"
            exit 1
        fi
        sleep 1
    done
fi

# Check MCP servers
echo -e "${BLUE}🔍 Checking MCP servers...${NC}"
if [ -f "$SCRIPT_DIR/claude_mcp.sh" ]; then
    if ! "$SCRIPT_DIR/claude_mcp.sh" --test; then
        echo -e "${YELLOW}⚠️  MCP servers may not be properly configured${NC}"
    fi
fi

# Set environment variable to use proxy
export OPENAI_BASE_URL=http://localhost:10000

# Start Claude Code
echo -e "${GREEN}🎯 Starting Claude Code with proxy...${NC}"
echo -e "${BLUE}Environment: OPENAI_BASE_URL=$OPENAI_BASE_URL${NC}"

# Execute Claude with arguments (if any)
if [ $# -gt 0 ]; then
    echo -e "${BLUE}📝 Initial prompt: $*${NC}"
    exec claude "$@"
else
    exec claude
fi