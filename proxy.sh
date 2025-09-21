#!/bin/bash

# 🚨🚨🚨 CRITICAL PROXY CONTROL SCRIPT - HANDLE WITH EXTREME CARE 🚨🚨🚨
#
# ⚠️  THIS SCRIPT MANAGES THE CORE CODEX PROXY SERVICE ⚠️
#
# 🔒 PROTECTED COMPONENTS (DO NOT MODIFY):
# - PROXY_MODULE variable (must remain "main_sync_cffi")
# - Python module imports and uvicorn startup command
# - Port 10000 configuration for Codex compatibility
# - Process management and PID handling
#
# ✅ SAFE TO MODIFY:
# - Log file locations and formatting
# - Status display messages and colors
# - Health check functionality
# - Process cleanup logic
#
# ❌ CRITICAL WARNINGS:
# - DO NOT change the proxy module name
# - DO NOT modify the port (must be 10000)
# - DO NOT alter the Python startup command structure
# - DO NOT remove curl_cffi or chrome124 impersonation
#
# Breaking these rules WILL prevent Codex from connecting to the proxy.

# Codex-Plus Simple Proxy Control Script
# Usage: ./proxy.sh [enable|disable|status|restart]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$SCRIPT_DIR/venv"
# 🔒 CRITICAL: This module name MUST NOT be changed - contains curl_cffi proxy logic
PROXY_MODULE="main_sync_cffi"
# Runtime files under /tmp/codex_plus
RUNTIME_DIR="/tmp/codex_plus"
PID_FILE="$RUNTIME_DIR/proxy.pid"
LOG_FILE="$RUNTIME_DIR/proxy.log"
# Autostart configuration
AUTOSTART_LABEL="com.codex.plus.proxy"
LAUNCH_AGENT_PATH="$HOME/Library/LaunchAgents/$AUTOSTART_LABEL.plist"
LAUNCHD_SCRIPT="$SCRIPT_DIR/scripts/proxy_launchd.sh"
CRONTAB_ENTRY="@reboot cd $SCRIPT_DIR && ./proxy.sh enable"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

validate_pid() {
    local pid="$1"
    # Check if PID is numeric and process exists
    if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
        # Additional check: verify it's actually our proxy process
        if ps -p "$pid" -o command= | grep -q "$PROXY_MODULE"; then
            return 0
        else
            echo -e "${YELLOW}⚠️  PID $pid exists but is not our proxy process${NC}" >&2
            return 1
        fi
    else
        return 1
    fi
}

cleanup_stale_resources() {
    # Clean up stale PID files and lock files
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE" 2>/dev/null)
        if ! validate_pid "$pid"; then
            echo -e "${YELLOW}🧹 Cleaning up stale PID file${NC}"
            rm -f "$PID_FILE"
        fi
    fi

    # Clean up any orphaned proxy processes
    local orphaned_pids=$(pgrep -f "python.*$PROXY_MODULE" | grep -v "$$" || true)
    if [ -n "$orphaned_pids" ]; then
        echo -e "${YELLOW}🧹 Found orphaned proxy processes: $orphaned_pids${NC}"
        echo "$orphaned_pids" | xargs -r kill -TERM 2>/dev/null || true
        sleep 2
        echo "$orphaned_pids" | xargs -r kill -KILL 2>/dev/null || true
    fi
}

print_status() {
    echo -e "${BLUE}🔍 M1 Proxy Status:${NC}"

    # Clean up stale resources first
    cleanup_stale_resources

    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE" 2>/dev/null)
        if validate_pid "$pid"; then
            echo -e "  ${GREEN}✅ Running${NC} (PID: $pid)"
            echo -e "  ${GREEN}📡 Proxy URL:${NC} http://localhost:10000"
            echo -e "  ${GREEN}🏥 Health Check:${NC} http://localhost:10000/health"
            echo -e "  ${GREEN}📝 Log:${NC} $LOG_FILE"
            echo -e "  ${GREEN}📊 Usage:${NC} OPENAI_BASE_URL=http://localhost:10000 codex"
            return 0
        else
            echo -e "  ${RED}❌ Not running${NC} (cleaned up stale resources)"
            return 1
        fi
    else
        echo -e "  ${RED}❌ Not running${NC}"
        return 1
    fi
}

start_proxy() {
    echo -e "${BLUE}🚀 Starting M1 Simple Passthrough Proxy...${NC}"

    # Create a lock file to prevent concurrent starts
    local lock_file="$RUNTIME_DIR/proxy.lock"
    local lock_timeout=10

    # Try to acquire lock with timeout
    local lock_acquired=false
    for ((i=0; i<lock_timeout; i++)); do
        if (set -C; echo $$ > "$lock_file") 2>/dev/null; then
            lock_acquired=true
            break
        fi
        echo -e "${YELLOW}⏳ Waiting for lock (attempt $((i+1))/$lock_timeout)...${NC}"
        sleep 1
    done

    if [ "$lock_acquired" = false ]; then
        echo -e "${RED}❌ Failed to acquire lock after ${lock_timeout}s${NC}"
        return 1
    fi

    # Ensure lock is released on exit
    trap 'rm -f "$lock_file"' EXIT

    # Check if already running (after acquiring lock)
    if print_status >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Proxy is already running${NC}"
        return 0
    fi

    # Ensure runtime directory exists with proper permissions
    mkdir -p "$RUNTIME_DIR"
    chmod 755 "$RUNTIME_DIR"

    # Validate environment
    cd "$SCRIPT_DIR" || {
        echo -e "${RED}❌ Failed to change to script directory${NC}"
        return 1
    }

    if [ ! -d "$VENV_PATH" ]; then
        echo -e "${RED}❌ Virtual environment not found at $VENV_PATH${NC}"
        echo -e "${YELLOW}💡 Run: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt${NC}"
        return 1
    fi

    # Check if port 10000 is available
    if lsof -i :10000 >/dev/null 2>&1; then
        echo -e "${RED}❌ Port 10000 is already in use${NC}"
        lsof -i :10000
        return 1
    fi

    # Start proxy in background with enhanced error handling
    source "$VENV_PATH/bin/activate" || {
        echo -e "${RED}❌ Failed to activate virtual environment${NC}"
        return 1
    }

    export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"

    # 🚨🚨🚨 CRITICAL PROXY STARTUP COMMAND - DO NOT MODIFY 🚨🚨🚨
    # ⚠️ This command starts the curl_cffi proxy with Cloudflare bypass ⚠️
    # ❌ FORBIDDEN: Changing module, host, port, or import structure
    nohup python -c "
import sys, os
try:
    from codex_plus.$PROXY_MODULE import app
    import uvicorn
    # 🔒 PROTECTED: Port 10000 required for Codex compatibility
    uvicorn.run(app, host='127.0.0.1', port=10000, log_level='info')
except Exception as e:
    print(f'STARTUP_ERROR: {e}', file=sys.stderr)
    sys.exit(1)
" > "$LOG_FILE" 2>&1 &

    local pid=$!
    echo "$pid" > "$PID_FILE"

    # Enhanced startup verification with multiple checks
    local startup_timeout=10
    local startup_success=false

    for ((i=0; i<startup_timeout; i++)); do
        sleep 1
        if validate_pid "$pid"; then
            # Additional check: verify the service is actually responding
            if curl -s -f http://localhost:10000/health >/dev/null 2>&1; then
                startup_success=true
                break
            elif [ $i -eq $((startup_timeout-1)) ]; then
                echo -e "${YELLOW}⚠️  Process started but health check failed${NC}"
            fi
        else
            echo -e "${RED}❌ Process failed to start or died during startup${NC}"
            break
        fi
        echo -e "${YELLOW}⏳ Waiting for service to be ready ($((i+1))/$startup_timeout)...${NC}"
    done

    if [ "$startup_success" = true ]; then
        echo -e "${GREEN}✅ Proxy started successfully and is responding${NC}"
        print_status
        return 0
    else
        echo -e "${RED}❌ Failed to start proxy or service is not responding${NC}"
        echo -e "${YELLOW}📋 Check logs for details:${NC} tail -f $LOG_FILE"

        # Clean up failed start
        if validate_pid "$pid"; then
            kill -TERM "$pid" 2>/dev/null
            sleep 2
            kill -KILL "$pid" 2>/dev/null
        fi
        rm -f "$PID_FILE"
        return 1
    fi
}

stop_proxy() {
    echo -e "${BLUE}🛑 Stopping M1 Simple Passthrough Proxy...${NC}"

    local graceful_timeout=10
    local force_timeout=5

    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE" 2>/dev/null)
        if validate_pid "$pid"; then
            echo -e "${YELLOW}📤 Sending SIGTERM to process $pid...${NC}"

            # Send SIGTERM for graceful shutdown
            kill -TERM "$pid" 2>/dev/null

            # Wait for graceful shutdown
            local stopped=false
            for ((i=0; i<graceful_timeout; i++)); do
                if ! validate_pid "$pid"; then
                    stopped=true
                    break
                fi
                sleep 1
                echo -e "${YELLOW}⏳ Waiting for graceful shutdown ($((i+1))/$graceful_timeout)...${NC}"
            done

            if [ "$stopped" = false ]; then
                echo -e "${YELLOW}⚠️  Graceful shutdown timeout, sending SIGKILL...${NC}"
                kill -KILL "$pid" 2>/dev/null

                # Wait for force kill
                for ((i=0; i<force_timeout; i++)); do
                    if ! validate_pid "$pid"; then
                        stopped=true
                        break
                    fi
                    sleep 1
                    echo -e "${YELLOW}⏳ Waiting for force kill ($((i+1))/$force_timeout)...${NC}"
                done
            fi

            if [ "$stopped" = true ]; then
                echo -e "${GREEN}✅ Proxy stopped successfully${NC}"
                rm -f "$PID_FILE"
            else
                echo -e "${RED}❌ Failed to stop process $pid${NC}"
                return 1
            fi
        else
            echo -e "${YELLOW}⚠️  PID file exists but process is not running${NC}"
            rm -f "$PID_FILE"
        fi
    else
        echo -e "${YELLOW}⚠️  No PID file found${NC}"
    fi

    # Clean up any remaining proxy processes as fallback
    local remaining_pids=$(pgrep -f "python.*$PROXY_MODULE" | grep -v "$$" || true)
    if [ -n "$remaining_pids" ]; then
        echo -e "${YELLOW}🧹 Cleaning up remaining proxy processes: $remaining_pids${NC}"
        echo "$remaining_pids" | xargs -r kill -TERM 2>/dev/null || true
        sleep 2
        echo "$remaining_pids" | xargs -r kill -KILL 2>/dev/null || true
        echo -e "${GREEN}✅ Cleaned up remaining processes${NC}"
    fi

    # Clean up lock files
    rm -f "$RUNTIME_DIR/proxy.lock"
}

restart_proxy() {
    echo -e "${BLUE}🔄 Restarting M1 Simple Passthrough Proxy...${NC}"
    stop_proxy
    sleep 1
    start_proxy
}

ensure_launchd_script() {
    if [ -x "$LAUNCHD_SCRIPT" ]; then
        return 0
    fi
    echo -e "${YELLOW}⚠️  Launchd helper script missing, creating $LAUNCHD_SCRIPT${NC}"
    mkdir -p "$(dirname "$LAUNCHD_SCRIPT")"
    cat <<'EOF' > "$LAUNCHD_SCRIPT"
#!/bin/bash
# Launchd-friendly proxy runner that keeps the uvicorn process in the foreground
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="$SCRIPT_DIR/venv"

if [ ! -d "$VENV_PATH" ]; then
  echo "Virtualenv missing at $VENV_PATH" >&2
  exit 1
fi

cd "$SCRIPT_DIR"
source "$VENV_PATH/bin/activate"
EXTRA_PYTHONPATH="$SCRIPT_DIR/src"
if [ -n "${PYTHONPATH:-}" ]; then
  export PYTHONPATH="$EXTRA_PYTHONPATH:$PYTHONPATH"
else
  export PYTHONPATH="$EXTRA_PYTHONPATH"
fi

exec python -c "
import sys
from codex_plus.main_sync_cffi import app
import uvicorn
uvicorn.run(app, host='127.0.0.1', port=10000, log_level='info')
"
EOF
    chmod +x "$LAUNCHD_SCRIPT"
}

install_launchd() {
    ensure_launchd_script
    mkdir -p "$(dirname "$LAUNCH_AGENT_PATH")"
    cat <<EOF > "$LAUNCH_AGENT_PATH"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>$AUTOSTART_LABEL</string>
    <key>ProgramArguments</key>
    <array>
      <string>$LAUNCHD_SCRIPT</string>
    </array>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/codex_plus/launchd.out</string>
    <key>StandardErrorPath</key>
    <string>/tmp/codex_plus/launchd.err</string>
    <key>EnvironmentVariables</key>
    <dict>
      <key>PATH</key>
      <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
  </dict>
</plist>
EOF
    launchctl unload "$LAUNCH_AGENT_PATH" >/dev/null 2>&1 || true
    launchctl load "$LAUNCH_AGENT_PATH"
    launchctl start "$AUTOSTART_LABEL" >/dev/null 2>&1 || true
    echo -e "${GREEN}✅ LaunchAgent installed at $LAUNCH_AGENT_PATH${NC}"
}

remove_launchd() {
    if [ -f "$LAUNCH_AGENT_PATH" ]; then
        launchctl unload "$LAUNCH_AGENT_PATH" >/dev/null 2>&1 || true
        rm -f "$LAUNCH_AGENT_PATH"
        echo -e "${GREEN}✅ LaunchAgent removed${NC}"
    else
        echo -e "${YELLOW}ℹ️  No LaunchAgent plist found${NC}"
    fi
}

status_launchd() {
    if [ ! -f "$LAUNCH_AGENT_PATH" ]; then
        echo -e "${YELLOW}ℹ️  LaunchAgent not configured${NC}"
        return 1
    fi
    if launchctl list "$AUTOSTART_LABEL" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ LaunchAgent loaded (${AUTOSTART_LABEL})${NC}"
        return 0
    fi
    echo -e "${YELLOW}⚠️  LaunchAgent plist exists but is not loaded${NC}"
    return 1
}

install_cron() {
    local cron_tmp
    cron_tmp=$(mktemp)
    { crontab -l 2>/dev/null || true; } > "$cron_tmp"
    if grep -Fq "$CRONTAB_ENTRY" "$cron_tmp"; then
        echo -e "${YELLOW}ℹ️  Crontab entry already present${NC}"
        rm -f "$cron_tmp"
        return 0
    fi
    printf "%s\n" "$CRONTAB_ENTRY" >> "$cron_tmp"
    crontab "$cron_tmp"
    rm -f "$cron_tmp"
    echo -e "${GREEN}✅ Crontab autostart installed${NC}"
}

remove_cron() {
    local cron_tmp
    cron_tmp=$(mktemp)
    { crontab -l 2>/dev/null || true; } | grep -Fv "$CRONTAB_ENTRY" > "$cron_tmp"
    crontab "$cron_tmp"
    rm -f "$cron_tmp"
    echo -e "${GREEN}✅ Crontab autostart removed (if it was present)${NC}"
}

status_cron() {
    if crontab -l 2>/dev/null | grep -Fq "$CRONTAB_ENTRY"; then
        echo -e "${GREEN}✅ Crontab autostart configured${NC}"
        return 0
    fi
    echo -e "${YELLOW}ℹ️  Crontab autostart not configured${NC}"
    return 1
}

handle_autostart() {
    local action="${1:-enable}"
    local os_name
    os_name=$(uname -s)
    case "$os_name" in
        Darwin)
            case "$action" in
                enable|ensure) install_launchd ;;
                disable) remove_launchd ;;
                status) status_launchd ;;
                *) echo -e "${RED}❌ Unknown autostart action: $action${NC}"; return 1 ;;
            esac
            ;;
        Linux)
            case "$action" in
                enable|ensure) install_cron ;;
                disable) remove_cron ;;
                status) status_cron ;;
                *) echo -e "${RED}❌ Unknown autostart action: $action${NC}"; return 1 ;;
            esac
            ;;
        *)
            echo -e "${RED}❌ Autostart not supported on $os_name${NC}"
            return 1
            ;;
    esac
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
    echo -e "  ${GREEN}autostart${NC} [enable|disable|status]"
    echo -e "             Manage automatic startup (default: enable)"
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
    "autostart")
        handle_autostart "$2"
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
