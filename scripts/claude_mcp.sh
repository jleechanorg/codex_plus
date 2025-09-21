#!/usr/bin/env bash
# Requires bash 4+ for associative arrays
# MCP Server Installation Script for Codex Plus

# Proper error handling - using safe_exit function instead of global set -e
# Note: set -e conflicts with safe_exit and graceful error handling patterns

# Check for test mode
TEST_MODE=false
if [ "$1" == "--test" ]; then
    TEST_MODE=true
fi

# Safe exit that won't kill the parent shell if sourced
safe_exit() {
  local code="${1:-0}"
  # If the script is sourced, 'return' is available; else 'return' errors and we use fallback exit
  return "$code" 2>/dev/null || {
    # Fallback exit for non-sourced execution
    builtin exit "$code"
  }
}

# Check bash version for associative array support
if [ "${BASH_VERSINFO[0]}" -lt 4 ]; then
    echo "❌ Error: This script requires bash 4.0 or higher for associative array support"
    echo "   Current bash version: ${BASH_VERSION}"
    echo "   Install newer bash: brew install bash (macOS) or update your system"
    safe_exit 1
fi

# Detect operating system for enhanced cross-platform compatibility
OS_TYPE="$(uname -s)"
case "$OS_TYPE" in
    Linux*)     MACHINE=Linux;;
    Darwin*)    MACHINE=Mac;;
    CYGWIN*)    MACHINE=Cygwin;;
    MINGW*)     MACHINE=MinGw;;
    MSYS*)      MACHINE=Git;;
    *)          MACHINE="UNKNOWN:$OS_TYPE"
esac

echo "🔍 Detected platform: $MACHINE ($OS_TYPE)"

# In test mode, exit early with success
if [ "$TEST_MODE" = true ]; then
    echo "🧪 Test mode: Exiting early with success"
    exit 0
fi

echo "🚀 Installing MCP Servers for Codex Plus..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Set up logging
LOG_FILE="/tmp/codex_plus_mcp_$(date +%Y%m%d_%H%M%S).log"
echo "📝 Logging to: $LOG_FILE"

# Function to log with timestamp
log_with_timestamp() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to log errors with details
log_error_details() {
    local operation="$1"
    local package="$2"
    local error_output="$3"

    log_with_timestamp "ERROR: $operation failed for $package"
    log_with_timestamp "Error details: $error_output"
    echo "Error details: $error_output" >> "$LOG_FILE"
}

# Get Node and NPX paths
NODE_PATH=$(which node 2>/dev/null)
NPX_PATH=$(which npx 2>/dev/null)

if [ -z "$NODE_PATH" ] || [ -z "$NPX_PATH" ]; then
    echo -e "${RED}❌ Node.js and npm are required but not found${NC}"
    echo "Please install Node.js from https://nodejs.org/"
    safe_exit 1
fi

echo "✅ Node.js found at: $NODE_PATH"
echo "✅ NPX found at: $NPX_PATH"

# Installation counters
TOTAL_SERVERS=0
SUCCESSFUL_INSTALLS=0
FAILED_INSTALLS=0
declare -A INSTALL_RESULTS

# Define MCP servers to install (adapted for development environment)
declare -A MCP_SERVERS=(
    ["@modelcontextprotocol/server-filesystem"]="Filesystem access"
    ["@modelcontextprotocol/server-github"]="GitHub integration"
    ["@modelcontextprotocol/server-web-search"]="Web search capabilities"
    ["@modelcontextprotocol/server-brave-search"]="Brave search"
    ["@modelcontextprotocol/server-postgres"]="PostgreSQL database"
)

# Function to install MCP server
install_mcp_server() {
    local package_name="$1"
    local description="$2"

    echo -e "${BLUE}📦 Installing $package_name${NC}"
    echo "   Description: $description"

    TOTAL_SERVERS=$((TOTAL_SERVERS + 1))

    # Attempt installation with timeout
    local install_output
    install_output=$(npx -y "$package_name" --help 2>&1)
    local install_exit_code=$?

    if [ $install_exit_code -eq 0 ]; then
        echo -e "${GREEN}✅ Successfully installed $package_name${NC}"
        SUCCESSFUL_INSTALLS=$((SUCCESSFUL_INSTALLS + 1))
        INSTALL_RESULTS["$package_name"]="✅ Success"
        log_with_timestamp "SUCCESS: Installed $package_name"
    else
        echo -e "${RED}❌ Failed to install $package_name${NC}"
        FAILED_INSTALLS=$((FAILED_INSTALLS + 1))
        INSTALL_RESULTS["$package_name"]="❌ Failed"
        log_error_details "Installation" "$package_name" "$install_output"
    fi

    echo ""
}

# Install servers sequentially for better reliability
for package in "${!MCP_SERVERS[@]}"; do
    install_mcp_server "$package" "${MCP_SERVERS[$package]}"
done

# Generate installation summary
echo -e "${CYAN}📊 Installation Summary:${NC}"
echo "   Total servers: $TOTAL_SERVERS"
echo "   Successful: $SUCCESSFUL_INSTALLS"
echo "   Failed: $FAILED_INSTALLS"
echo ""

if [ $SUCCESSFUL_INSTALLS -gt 0 ]; then
    echo -e "${GREEN}✅ Successfully installed servers:${NC}"
    for package in "${!INSTALL_RESULTS[@]}"; do
        if [[ "${INSTALL_RESULTS[$package]}" == *"Success"* ]]; then
            echo "   • $package"
        fi
    done
    echo ""
fi

if [ $FAILED_INSTALLS -gt 0 ]; then
    echo -e "${RED}❌ Failed installations:${NC}"
    for package in "${!INSTALL_RESULTS[@]}"; do
        if [[ "${INSTALL_RESULTS[$package]}" == *"Failed"* ]]; then
            echo "   • $package"
        fi
    done
    echo ""
    echo -e "${YELLOW}💡 Check the log file for detailed error information: $LOG_FILE${NC}"
fi

# Exit with appropriate code
if [ $FAILED_INSTALLS -eq 0 ]; then
    echo -e "${GREEN}🎉 All MCP servers installed successfully!${NC}"
    safe_exit 0
else
    echo -e "${YELLOW}⚠️  Some installations failed. See log for details.${NC}"
    safe_exit 1
fi