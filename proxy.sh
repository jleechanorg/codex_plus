#!/bin/bash

# Codex-Plus Simple Proxy Control Script
# Usage: ./proxy.sh [enable|disable|status|restart]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$SCRIPT_DIR/venv"
PROXY_MODULE="main_sync_cffi"
# Runtime files under /tmp/codex_plus
RUNTIME_DIR="/tmp/codex_plus"
PID_FILE="$RUNTIME_DIR/proxy.pid"
LOG_FILE="$RUNTIME_DIR/proxy.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}🔍 M1 Proxy Status:${NC}"
    
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo -e "  ${GREEN}✅ Running${NC} (PID: $PID)"
            echo -e "  ${GREEN}📡 Proxy URL:${NC} http://localhost:10000"
            echo -e "  ${GREEN}🏥 Health Check:${NC} http://localhost:10000/health"
            echo -e "  ${GREEN}📝 Log:${NC} $LOG_FILE"
            echo -e "  ${GREEN}📊 Usage:${NC} OPENAI_BASE_URL=http://localhost:10000 codex"
            return 0
        else
            echo -e "  ${RED}❌ Not running${NC} (stale PID file)"
            rm -f "$PID_FILE"
            return 1
        fi
    else
        echo -e "  ${RED}❌ Not running${NC}"
        return 1
    fi
}

start_proxy() {
    echo -e "${BLUE}🚀 Starting M1 Simple Passthrough Proxy...${NC}"
    
    # Check if already running
    if print_status >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Proxy is already running${NC}"
        return 0
    fi
    
    # Ensure runtime directory exists
    mkdir -p "$RUNTIME_DIR"

    # Activate virtual environment and start proxy
    cd "$SCRIPT_DIR"
    if [ ! -d "$VENV_PATH" ]; then
        echo -e "${RED}❌ Virtual environment not found at $VENV_PATH${NC}"
        echo -e "${YELLOW}💡 Run: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt${NC}"
        return 1
    fi
    
    # Start proxy in background
    source "$VENV_PATH/bin/activate"
    cd "$SCRIPT_DIR"
    export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"
    nohup python -c "from codex_plus.$PROXY_MODULE import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=10000)" > "$LOG_FILE" 2>&1 &
    PID=$!
    echo "$PID" > "$PID_FILE"
    
    # Wait a moment and check if it started successfully
    sleep 2
    if kill -0 "$PID" 2>/dev/null; then
        echo -e "${GREEN}✅ Proxy started successfully${NC}"
        print_status
    else
        echo -e "${RED}❌ Failed to start proxy${NC}"
        echo -e "${YELLOW}📋 Check logs:${NC} tail -f $LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

stop_proxy() {
    echo -e "${BLUE}🛑 Stopping M1 Simple Passthrough Proxy...${NC}"
    
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            rm -f "$PID_FILE"
            echo -e "${GREEN}✅ Proxy stopped${NC}"
        else
            echo -e "${YELLOW}⚠️  Proxy was not running${NC}"
            rm -f "$PID_FILE"
        fi
    else
        echo -e "${YELLOW}⚠️  No PID file found, attempting to kill any running proxy processes${NC}"
        pkill -f "python.*$PROXY_MODULE" && echo -e "${GREEN}✅ Killed proxy processes${NC}" || echo -e "${YELLOW}⚠️  No proxy processes found${NC}"
    fi
}

restart_proxy() {
    echo -e "${BLUE}🔄 Restarting M1 Simple Passthrough Proxy...${NC}"
    stop_proxy
    sleep 1
    start_proxy
}

show_help() {
    echo -e "${BLUE}Codex-Plus Simple Proxy Control Script${NC}"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo -e "  ${GREEN}enable${NC}   Start the proxy server"
    echo -e "  ${GREEN}disable${NC}  Stop the proxy server"
    echo -e "  ${GREEN}status${NC}   Show proxy status"
    echo -e "  ${GREEN}restart${NC}  Restart the proxy server"
    echo -e "  ${GREEN}help${NC}     Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 enable                                    # Start proxy"
    echo "  $0 status                                    # Check status"
    echo "  OPENAI_BASE_URL=http://localhost:10000 codex  # Use with codex"
    echo "  $0 disable                                   # Stop proxy"
}

# Main command handling
case "${1:-enable}" in
    "enable"|"start")
        start_proxy
        ;;
    "disable"|"stop")
        stop_proxy
        ;;
    "status")
        print_status
        ;;
    "restart")
        restart_proxy
        ;;
    "help"|"-h"|"--help")
        show_help
        ;;
    *)
        echo -e "${RED}❌ Unknown command: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
