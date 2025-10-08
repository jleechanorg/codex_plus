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
ERROR_LOG_FILE="$RUNTIME_DIR/proxy.err"
LOCK_FILE="$RUNTIME_DIR/proxy.lock"
BASE_URL_FILE="$RUNTIME_DIR/provider.base_url"
LAUNCHD_STDOUT_LOG="$RUNTIME_DIR/launchd.out"
LAUNCHD_STDERR_LOG="$RUNTIME_DIR/launchd.err"
LAUNCHD_ENV_FILE="$RUNTIME_DIR/launchd.env"

if [ -n "${CODEX_PROXY_RUNTIME_DIR:-}" ]; then
    RUNTIME_DIR="$CODEX_PROXY_RUNTIME_DIR"
    PID_FILE="$RUNTIME_DIR/proxy.pid"
    LOG_FILE="$RUNTIME_DIR/proxy.log"
    ERROR_LOG_FILE="$RUNTIME_DIR/proxy.err"
    LOCK_FILE="$RUNTIME_DIR/proxy.lock"
    BASE_URL_FILE="$RUNTIME_DIR/provider.base_url"
    LAUNCHD_STDOUT_LOG="$RUNTIME_DIR/launchd.out"
    LAUNCHD_STDERR_LOG="$RUNTIME_DIR/launchd.err"
    LAUNCHD_ENV_FILE="$RUNTIME_DIR/launchd.env"
fi
# Autostart configuration
AUTOSTART_LABEL="com.codex.plus.proxy"
LAUNCH_AGENT_PATH="$HOME/Library/LaunchAgents/$AUTOSTART_LABEL.plist"
LAUNCHD_SCRIPT="$SCRIPT_DIR/scripts/proxy_launchd.sh"
CRONTAB_ENTRY="@reboot cd $SCRIPT_DIR && ./proxy.sh enable"

# Provider configuration
PROVIDER_MODE="openai"
FORCE_RESTART="false"
DEFAULT_UPSTREAM_URL="https://chatgpt.com/backend-api/codex"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse global flags (currently only --cerebras and --logging)
POSITIONAL_ARGS=()
LOGGING_MODE="false"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --cerebras)
            PROVIDER_MODE="cerebras"
            shift
            ;;
        --logging)
            LOGGING_MODE="true"
            shift
            ;;
        --)
            shift
            POSITIONAL_ARGS+=("$@")
            break
            ;;
        *)
            POSITIONAL_ARGS+=("$1")
            shift
            ;;
    esac
done

if [ ${#POSITIONAL_ARGS[@]} -eq 0 ]; then
    POSITIONAL_ARGS=("enable")
fi

set -- "${POSITIONAL_ARGS[@]}"

COMMAND="${1:-enable}"
if [ "$PROVIDER_MODE" = "cerebras" ] && { [ "$COMMAND" = "enable" ] || [ "$COMMAND" = "start" ]; }; then
    FORCE_RESTART="true"
fi

configure_provider_environment() {
    if [ "$PROVIDER_MODE" = "cerebras" ]; then
        local sourced_env=false
        if [ -z "${CEREBRAS_API_KEY:-}" ] || [ -z "${CEREBRAS_BASE_URL:-}" ] || [ -z "${CEREBRAS_MODEL:-}" ]; then
            if [ -f "$HOME/.bashrc" ]; then
                local bashrc_exports
                bashrc_exports=$(bash -ic '
                    source ~/.bashrc >/dev/null 2>&1
                    printf "export CEREBRAS_API_KEY=%q\\n" "$CEREBRAS_API_KEY"
                    printf "export CEREBRAS_BASE_URL=%q\\n" "$CEREBRAS_BASE_URL"
                    printf "export CEREBRAS_MODEL=%q\\n" "$CEREBRAS_MODEL"
                ' 2>/dev/null || true)
                if [ -n "$bashrc_exports" ]; then
                    eval "$bashrc_exports"
                    sourced_env=true
                fi
            fi
        fi

        local missing_vars=()
        for var in CEREBRAS_API_KEY CEREBRAS_BASE_URL CEREBRAS_MODEL; do
            if [ -z "${!var:-}" ]; then
                missing_vars+=("$var")
            fi
        done

        if [ "${#missing_vars[@]}" -gt 0 ]; then
            if [ "$sourced_env" = true ]; then
                echo -e "${YELLOW}ℹ️  Loaded ~/.bashrc but Cerebras variables are still missing${NC}" >&2
            else
                echo -e "${YELLOW}ℹ️  Cerebras variables not set; add them to ~/.bashrc or export beforehand${NC}" >&2
            fi
            echo -e "${RED}❌ Missing required Cerebras environment variable(s): ${missing_vars[*]}${NC}" >&2
            echo -e "${YELLOW}💡 Export CEREBRAS_API_KEY, CEREBRAS_BASE_URL, and CEREBRAS_MODEL before starting in Cerebras mode${NC}" >&2
            return 1
        fi

        export CODEX_PLUS_PROVIDER_MODE="cerebras"
        export OPENAI_API_KEY="$CEREBRAS_API_KEY"
        export OPENAI_BASE_URL="$CEREBRAS_BASE_URL"
        export OPENAI_MODEL="$CEREBRAS_MODEL"
        printf '%s\n' "$CEREBRAS_BASE_URL" > "$BASE_URL_FILE"
        echo -e "${BLUE}🌐 Cerebras mode enabled - proxy will use Cerebras credentials${NC}"
    else
        export CODEX_PLUS_PROVIDER_MODE="openai"
        printf '%s\n' "$DEFAULT_UPSTREAM_URL" > "$BASE_URL_FILE"
    fi
    echo "$PROVIDER_MODE" > "$RUNTIME_DIR/provider.mode"
}

get_upstream_url() {
    if [ -f "$BASE_URL_FILE" ]; then
        local upstream
        read -r upstream < "$BASE_URL_FILE" 2>/dev/null || upstream=""
        if [ -n "$upstream" ]; then
            printf '%s' "$upstream"
            return
        fi
    fi
    printf '%s' "$DEFAULT_UPSTREAM_URL"
}

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

    # Clean up logging mode state file
    if [ -f "$RUNTIME_DIR/logging.mode" ]; then
        rm -f "$RUNTIME_DIR/logging.mode"
    fi

}

prepare_runtime_paths() {
    mkdir -p "$RUNTIME_DIR"
    chmod 755 "$RUNTIME_DIR"

    for log_path in "$LOG_FILE" "$ERROR_LOG_FILE" "$LAUNCHD_STDOUT_LOG" "$LAUNCHD_STDERR_LOG"; do
        if [ ! -f "$log_path" ]; then
            touch "$log_path"
        fi
        chmod 644 "$log_path" 2>/dev/null || true
    done
}

persist_launchd_environment() {
    local env_file="$LAUNCHD_ENV_FILE"
    local tmp_file="${env_file}.tmp"

    mkdir -p "$RUNTIME_DIR"

    cat /dev/null > "$tmp_file"

    local provider_value="${CODEX_PLUS_PROVIDER_MODE:-$PROVIDER_MODE}"
    if [ -n "$provider_value" ]; then
        printf 'CODEX_PLUS_PROVIDER_MODE=%q\n' "$provider_value" >> "$tmp_file"
    fi

    if [ "${CODEX_PLUS_LOGGING_MODE:-false}" = "true" ]; then
        printf 'CODEX_PLUS_LOGGING_MODE=true\n' >> "$tmp_file"
    fi

    for var in OPENAI_API_KEY OPENAI_BASE_URL OPENAI_MODEL CEREBRAS_API_KEY CEREBRAS_BASE_URL CEREBRAS_MODEL; do
        if [ -n "${!var:-}" ]; then
            printf '%s=%q\n' "$var" "${!var}" >> "$tmp_file"
        fi
    done

    chmod 600 "$tmp_file" 2>/dev/null || true
    mv "$tmp_file" "$env_file"
}

clear_launchd_environment() {
    rm -f "$LAUNCHD_ENV_FILE"
}

PORT_GUARD_EXIT_CODE=""
PORT_GUARD_OUTPUT=""

run_port_guard() {
    if [ -n "${CODEX_PROXY_GUARD_STATE:-}" ]; then
        case "$CODEX_PROXY_GUARD_STATE" in
            owned_by_proxy) PORT_GUARD_EXIT_CODE=0 ;;
            free) PORT_GUARD_EXIT_CODE=10 ;;
            occupied_other) PORT_GUARD_EXIT_CODE=20 ;;
            unknown) PORT_GUARD_EXIT_CODE=30 ;;
            *) PORT_GUARD_EXIT_CODE=30 ;;
        esac
        PORT_GUARD_OUTPUT="{\"state\": \"${CODEX_PROXY_GUARD_STATE}\"}"
        return 0
    fi

    local python_cmd=("python3")
    if [ -n "${PYTHON:-}" ]; then
        python_cmd=("${PYTHON}")
    elif ! command -v python3 >/dev/null 2>&1; then
        python_cmd=("python")
    fi

    local env_pythonpath="$SCRIPT_DIR/src"
    if [ -n "${PYTHONPATH:-}" ]; then
        env_pythonpath="$env_pythonpath:$PYTHONPATH"
    fi

    PORT_GUARD_OUTPUT=$(PYTHONPATH="$env_pythonpath" "${python_cmd[@]}" -m codex_plus.port_guard \
        --port 10000 \
        --health-url "http://127.0.0.1:10000/health" \
        --health-timeout 1.0 \
        --expect codex_plus \
        --expect main_sync_cffi \
        --expect uvicorn \
        --json 2>/dev/null)
    PORT_GUARD_EXIT_CODE=$?
    if [ -z "$PORT_GUARD_OUTPUT" ]; then
        PORT_GUARD_OUTPUT="{\"state\": \"unknown\"}"
    fi
    case "$PORT_GUARD_EXIT_CODE" in
        0|10|20|30) :;;
        *) PORT_GUARD_EXIT_CODE=30 ;;
    esac
}

print_status() {
    echo -e "${BLUE}🔍 M1 Proxy Status:${NC}"

    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE" 2>/dev/null)
        if validate_pid "$pid"; then
            echo -e "  ${GREEN}✅ Running${NC} (PID: $pid)"
            echo -e "  ${GREEN}📡 Proxy URL:${NC} http://localhost:10000"
            echo -e "  ${GREEN}🏥 Health Check:${NC} http://localhost:10000/health"
            echo -e "  ${GREEN}📝 Log:${NC} $LOG_FILE"
            echo -e "  ${GREEN}🛠️ Error Log:${NC} $ERROR_LOG_FILE"
            if [ -f "$RUNTIME_DIR/provider.mode" ]; then
                local provider
                provider=$(cat "$RUNTIME_DIR/provider.mode" 2>/dev/null)
                if [ -n "$provider" ]; then
                    local provider_display
                    provider_display=$(printf '%s' "$provider" | tr '[:lower:]' '[:upper:]')
                    echo -e "  ${GREEN}🌐 Mode:${NC} $provider_display"
                fi
            fi
            # Check both environment variable and persisted file
            if [ -f "$RUNTIME_DIR/logging.mode" ] || [ "${CODEX_PLUS_LOGGING_MODE:-false}" = "true" ]; then
                echo -e "  ${BLUE}📝 Logging:${NC} ENABLED (passthrough only)"
            fi
            echo -e "  ${GREEN}📊 Upstream:${NC} $(get_upstream_url)"
            return 0
        else
            # Only clean up stale resources if PID validation fails
            cleanup_stale_resources
            echo -e "  ${RED}❌ Not running${NC} (cleaned up stale resources)"
            return 1
        fi
    else
        # Only clean up if no PID file exists
        cleanup_stale_resources
        echo -e "  ${RED}❌ Not running${NC}"
        return 1
    fi
}

start_proxy() {
    echo -e "${BLUE}🚀 Starting M1 Simple Passthrough Proxy...${NC}"

    prepare_runtime_paths

    local os_name
    os_name=$(uname -s)

    local lock_timeout=10

    if [ -f "$LOCK_FILE" ]; then
        local lock_pid=$(cat "$LOCK_FILE" 2>/dev/null)
        if [[ "$lock_pid" =~ ^[0-9]+$ ]] && ! kill -0 "$lock_pid" 2>/dev/null; then
            echo -e "${YELLOW}🧹 Removing stale lock file (PID $lock_pid no longer running)${NC}"
            rm -f "$LOCK_FILE"
        fi
    fi

    local lock_acquired=false
    for ((i=0; i<lock_timeout; i++)); do
        if (set -C; echo $$ > "$LOCK_FILE") 2>/dev/null; then
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

    local startup_success=false
    trap 'if [ "${startup_success:-false}" != true ]; then rm -f "$LOCK_FILE"; fi' EXIT

    if [ "${FORCE_RESTART}" = "true" ]; then
        echo -e "${YELLOW}♻️  Force restart requested (${PROVIDER_MODE} mode) - continuing${NC}"
    else
        run_port_guard
        case "${PORT_GUARD_EXIT_CODE:-}" in
            0)
                echo -e "${YELLOW}⚠️  Proxy already running on port 10000; skipping start${NC}"
                startup_success=true
                rm -f "$LOCK_FILE"
                trap - EXIT
                return 0
                ;;
            20)
                echo -e "${RED}❌ Port 10000 is in use by another process; refusing to start${NC}"
                echo -e "${YELLOW}ℹ️  Port guard details:${NC} ${PORT_GUARD_OUTPUT}"
                rm -f "$LOCK_FILE"
                trap - EXIT
                return 1
                ;;
            30)
                echo -e "${YELLOW}⚠️  Unable to determine port ownership; continuing with startup${NC}"
                ;;
            *)
                :
                ;;
        esac
    fi

    echo -e "${YELLOW}🔄 Checking for existing proxy processes...${NC}"

    for attempt in 1 2 3; do
        local existing_pids=$(lsof -ti :10000 2>/dev/null)
        if [ -z "$existing_pids" ]; then
            break
        fi

        echo -e "${YELLOW}⚡ Attempt $attempt: Killing proxy processes: $existing_pids${NC}"

        if [ "$attempt" -le 2 ]; then
            kill $existing_pids 2>/dev/null
        else
            kill -9 $existing_pids 2>/dev/null
        fi

        sleep 2
    done

    pkill -f "uvicorn.*codex_plus" 2>/dev/null || true

    if lsof -i :10000 >/dev/null 2>&1; then
        echo -e "${YELLOW}🔨 Force killing all processes on port 10000...${NC}"
        lsof -ti :10000 2>/dev/null | xargs -r kill -9 2>/dev/null
        sleep 3

        if lsof -i :10000 >/dev/null 2>&1; then
            echo -e "${RED}❌ Failed to stop existing proxy on port 10000${NC}"
            lsof -i :10000
            return 1
        fi
    fi

    echo -e "${GREEN}✅ Port 10000 is now available${NC}"

    cd "$SCRIPT_DIR" || {
        echo -e "${RED}❌ Failed to change to script directory${NC}"
        return 1
    }

    if [ ! -d "$VENV_PATH" ]; then
        echo -e "${RED}❌ Virtual environment not found at $VENV_PATH${NC}"
        echo -e "${YELLOW}💡 Run: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt${NC}"
        return 1
    fi

    if ! configure_provider_environment; then
        return 1
    fi

    if [ "$LOGGING_MODE" = "true" ] || [ "${CODEX_PLUS_LOGGING_MODE:-false}" = "true" ]; then
        export CODEX_PLUS_LOGGING_MODE="true"
        echo "true" > "$RUNTIME_DIR/logging.mode"
    else
        unset CODEX_PLUS_LOGGING_MODE
        rm -f "$RUNTIME_DIR/logging.mode"
    fi

    if [ "$os_name" = "Darwin" ]; then
        persist_launchd_environment
        ensure_launchd_script
        install_launchd

        local startup_timeout=10
        local observed_pid=""

        for ((i=0; i<startup_timeout; i++)); do
            sleep 1
            if [ -z "$observed_pid" ] && [ -f "$PID_FILE" ]; then
                observed_pid=$(cat "$PID_FILE" 2>/dev/null || true)
            fi
            if [ -n "$observed_pid" ] && validate_pid "$observed_pid"; then
                if curl -s -f http://localhost:10000/health >/dev/null 2>&1; then
                    startup_success=true
                    break
                elif [ $i -eq $((startup_timeout-1)) ]; then
                    echo -e "${YELLOW}⚠️  Process started but health check failed${NC}"
                fi
            fi
            echo -e "${YELLOW}⏳ Waiting for launchd service to be ready ($((i+1))/$startup_timeout)...${NC}"
        done

        if [ "$startup_success" = true ]; then
            rm -f "$LOCK_FILE"
            trap - EXIT
            echo -e "${GREEN}✅ Proxy started successfully under launchd${NC}"
            echo -e "${BLUE}🔍 M1 Proxy Status:${NC}"
            if [ -z "$observed_pid" ] && [ -f "$PID_FILE" ]; then
                observed_pid=$(cat "$PID_FILE" 2>/dev/null || true)
            fi
            if [ -n "$observed_pid" ]; then
                echo -e "  ${GREEN}✅ Running${NC} (PID: $observed_pid)"
            else
                echo -e "  ${GREEN}✅ Running${NC}"
            fi
            echo -e "  ${GREEN}📡 Proxy URL:${NC} http://localhost:10000"
            echo -e "  ${GREEN}🏥 Health Check:${NC} http://localhost:10000/health"
            echo -e "  ${GREEN}📝 Log:${NC} $LOG_FILE"
            echo -e "  ${GREEN}🛠️ Error Log:${NC} $ERROR_LOG_FILE"
            if [ -f "$RUNTIME_DIR/logging.mode" ] || [ "${CODEX_PLUS_LOGGING_MODE:-false}" = "true" ]; then
                echo -e "  ${BLUE}📝 Logging:${NC} ENABLED (passthrough only)"
            fi
            echo -e "  ${GREEN}📊 Upstream:${NC} $(get_upstream_url)"
            return 0
        else
            echo -e "${RED}❌ Failed to start proxy via launchd${NC}"
            echo -e "${YELLOW}📋 Check logs for details:${NC} tail -f $ERROR_LOG_FILE"
            launchctl stop "$AUTOSTART_LABEL" >/dev/null 2>&1 || true
            launchctl unload "$LAUNCH_AGENT_PATH" >/dev/null 2>&1 || true
            rm -f "$PID_FILE"
            rm -f "$LOCK_FILE"
            trap - EXIT
            return 1
        fi
    fi

    source "$VENV_PATH/bin/activate" || {
        echo -e "${RED}❌ Failed to activate virtual environment${NC}"
        return 1
    }

    export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"

    nohup python -c "
import sys, os
try:
    from codex_plus.$PROXY_MODULE import app
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=10000, log_level='info')
except Exception as e:
    print(f'STARTUP_ERROR: {e}', file=sys.stderr)
    sys.exit(1)
" >> "$LOG_FILE" 2>> "$ERROR_LOG_FILE" &

    local pid=$!
    echo "$pid" > "$PID_FILE"

    local startup_timeout=10

    for ((i=0; i<startup_timeout; i++)); do
        sleep 1
        if validate_pid "$pid"; then
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
        trap - EXIT
        rm -f "$LOCK_FILE"
        echo -e "${GREEN}✅ Proxy started successfully and is responding${NC}"
        echo -e "${BLUE}🔍 M1 Proxy Status:${NC}"
        echo -e "  ${GREEN}✅ Running${NC} (PID: $pid)"
        echo -e "  ${GREEN}📡 Proxy URL:${NC} http://localhost:10000"
        echo -e "  ${GREEN}🏥 Health Check:${NC} http://localhost:10000/health"
        echo -e "  ${GREEN}📝 Log:${NC} $LOG_FILE"
        echo -e "  ${GREEN}🛠️ Error Log:${NC} $ERROR_LOG_FILE"
        if [ -f "$RUNTIME_DIR/logging.mode" ] || [ "${CODEX_PLUS_LOGGING_MODE:-false}" = "true" ]; then
            echo -e "  ${BLUE}📝 Logging:${NC} ENABLED (passthrough only)"
        fi
        echo -e "  ${GREEN}📊 Upstream:${NC} $(get_upstream_url)"
        return 0
    else
        echo -e "${RED}❌ Failed to start proxy or service is not responding${NC}"
        echo -e "${YELLOW}📋 Check logs for details:${NC} tail -f $ERROR_LOG_FILE"

        if validate_pid "$pid"; then
            kill -TERM "$pid" 2>/dev/null
            sleep 2
            kill -KILL "$pid" 2>/dev/null
        fi
        rm -f "$PID_FILE"
        rm -f "$LOCK_FILE"
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

    # Clean up lock files and logging mode state
    rm -f "$RUNTIME_DIR/proxy.lock"
    rm -f "$RUNTIME_DIR/logging.mode"

    # Ensure launchd won't immediately restart the proxy
    if [ "$(uname -s)" = "Darwin" ]; then
        if [ -f "$LAUNCH_AGENT_PATH" ]; then
            if launchctl list "$AUTOSTART_LABEL" >/dev/null 2>&1; then
                echo -e "${YELLOW}🛑 Stopping launchd job ${AUTOSTART_LABEL}${NC}"
                launchctl stop "$AUTOSTART_LABEL" >/dev/null 2>&1 || true
            fi
            echo -e "${YELLOW}🔌 Unloading launchd agent to prevent automatic restarts${NC}"
            launchctl unload "$LAUNCH_AGENT_PATH" >/dev/null 2>&1 || true
        fi
        clear_launchd_environment
    fi
}

restart_proxy() {
    echo -e "${BLUE}🔄 Restarting M1 Simple Passthrough Proxy...${NC}"
    stop_proxy
    sleep 1
    start_proxy
}

ensure_launchd_script() {
    mkdir -p "$(dirname "$LAUNCHD_SCRIPT")"
    cat <<EOF > "$LAUNCHD_SCRIPT"
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$SCRIPT_DIR"
VENV_PATH="$VENV_PATH"
RUNTIME_DIR="$RUNTIME_DIR"
PID_FILE="$PID_FILE"
LOG_FILE="$LOG_FILE"
ERROR_LOG_FILE="$ERROR_LOG_FILE"
LAUNCHD_ENV_FILE="$LAUNCHD_ENV_FILE"
PROXY_MODULE="$PROXY_MODULE"

mkdir -p "$RUNTIME_DIR"
if [ ! -f "$LOG_FILE" ]; then
  touch "$LOG_FILE"
fi
if [ ! -f "$ERROR_LOG_FILE" ]; then
  touch "$ERROR_LOG_FILE"
fi
chmod 644 "$LOG_FILE" "$ERROR_LOG_FILE" 2>/dev/null || true

unset CODEX_PLUS_LOGGING_MODE
if [ -f "$LAUNCHD_ENV_FILE" ]; then
  set -a
  source "$LAUNCHD_ENV_FILE"
  set +a
fi

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

echo $$ > "$PID_FILE"

exec python -c "
import sys, os
try:
    from codex_plus.$PROXY_MODULE import app
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=10000, log_level='info')
except Exception as e:
    print(f'STARTUP_ERROR: {e}', file=sys.stderr)
    sys.exit(1)
" >> "$LOG_FILE" 2>> "$ERROR_LOG_FILE"
EOF
    chmod +x "$LAUNCHD_SCRIPT"
}

install_launchd() {
    if [ ! -f "$LAUNCHD_ENV_FILE" ]; then
        persist_launchd_environment
    fi
    prepare_runtime_paths
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
    <string>$LAUNCHD_STDOUT_LOG</string>
    <key>StandardErrorPath</key>
    <string>$LAUNCHD_STDERR_LOG</string>
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
    clear_launchd_environment
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
    echo "Usage: $0 [--cerebras] [--logging] [command]"
    echo ""
    echo "Options:"
    echo -e "  ${GREEN}--cerebras${NC}  Use Cerebras credentials (requires CEREBRAS_API_KEY, CEREBRAS_BASE_URL, CEREBRAS_MODEL)"
    echo -e "  ${GREEN}--logging${NC}   Enable logging-only mode (passthrough without modification)"
    echo ""
    echo "Commands:"
    echo -e "  ${GREEN}enable${NC}   Start the proxy server"
    echo -e "  ${GREEN}disable${NC}  Stop the proxy server"
    echo -e "  ${GREEN}start${NC}    Alias for enable"
    echo -e "  ${GREEN}stop${NC}     Alias for disable"
    echo -e "  ${GREEN}status${NC}   Show proxy status"
    echo -e "  ${GREEN}restart${NC}  Restart the proxy server"
    echo -e "  ${GREEN}autostart${NC} [enable|disable|status|ensure]"
    echo -e "             Manage automatic startup (default: enable)"
    echo -e "  ${GREEN}help${NC}     Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 enable                                    # Start proxy"
    echo "  $0 status                                    # Check status"
    echo "  $0 --cerebras                                # Start proxy using Cerebras environment"
    echo "  $0 --cerebras enable                          # Equivalent explicit command"
    echo "  OPENAI_BASE_URL=http://localhost:10000 codex  # Use with codex"
    echo "  $0 disable                                   # Stop proxy"
}

# Main command handling
case "$COMMAND" in
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
