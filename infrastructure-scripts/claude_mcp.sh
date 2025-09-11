#!/bin/bash
echo "🚀 Installing MCP Servers with Enhanced Reliability..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Synchronization for parallel processing
STATS_LOCK_FILE="/tmp/claude_mcp_stats.lock"

# Function to safely update stats counters with file locking
update_stats() {
    local stat_type="$1"
    local name="$2"
    local result="$3"
    
    # Use flock for atomic updates without creating a subshell
    {
        flock -x 200
        case "$stat_type" in
            "TOTAL")
                TOTAL_SERVERS=$((TOTAL_SERVERS + 1))
                ;;
            "SUCCESS")
                SUCCESSFUL_INSTALLS=$((SUCCESSFUL_INSTALLS + 1))
                INSTALL_RESULTS["$name"]="$result"
                ;;
            "FAILURE")
                FAILED_INSTALLS=$((FAILED_INSTALLS + 1))
                INSTALL_RESULTS["$name"]="$result"
                ;;
        esac
    } 200>"$STATS_LOCK_FILE"
}

# Set up logging
LOG_FILE="/tmp/claude_mcp_$(date +%Y%m%d_%H%M%S).log"
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
NODE_PATH=$(which node)
NPX_PATH=$(which npx)

if [ -z "$NODE_PATH" ] || [ -z "$NPX_PATH" ]; then
    echo -e "${RED}❌ Node.js or NPX not found. Please install Node.js first.${NC}"
    exit 1
fi

echo -e "${BLUE}📍 Node path: $NODE_PATH${NC}"
echo -e "${BLUE}📍 NPX path: $NPX_PATH${NC}"

# Check Node.js version and warn about compatibility
NODE_VERSION=$(node --version)
echo -e "${BLUE}📍 Node version: $NODE_VERSION${NC}"
log_with_timestamp "Node.js version: $NODE_VERSION"

# Check for major version compatibility
NODE_MAJOR=$(echo "$NODE_VERSION" | sed 's/v\([0-9]*\).*/\1/')
if [ "$NODE_MAJOR" -lt 20 ]; then
    echo -e "${YELLOW}⚠️ WARNING: Node.js $NODE_VERSION detected. MCP servers recommend Node 20+${NC}"
    echo -e "${YELLOW}   Some packages may show engine warnings but should still work${NC}"
    log_with_timestamp "WARNING: Node.js version $NODE_VERSION is below recommended v20+"
else
    echo -e "${GREEN}✅ Node.js version compatible with MCP servers${NC}"
fi

# Check npm permissions and suggest alternatives
echo -e "${BLUE}🔍 Checking npm global installation permissions...${NC}"
if npm list -g --depth=0 >/dev/null 2>&1; then
    echo -e "${GREEN}✅ NPM global permissions look good${NC}"
    USE_GLOBAL=true
else
    echo -e "${YELLOW}⚠️ Global npm permissions may be restricted${NC}"
    echo -e "${YELLOW}   Will use npx direct installation method${NC}"
    USE_GLOBAL=false
fi

# Track installation results
declare -A INSTALL_RESULTS
TOTAL_SERVERS=0
SUCCESSFUL_INSTALLS=0
FAILED_INSTALLS=0
CURRENT_STEP=0

# Parallel processing configuration
MAX_PARALLEL_JOBS=3
declare -A PARALLEL_PIDS
declare -A PARALLEL_RESULTS

# Server installation queue for parallel processing
declare -a SERVER_QUEUE

# Function to check if npm package exists
package_exists() {
    local package="$1"
    npm view "$package" version >/dev/null 2>&1
}

# Function to install npm package with permission-aware method
install_package() {
    local package="$1"
    log_with_timestamp "Attempting to install package: $package"

    if [ "$USE_GLOBAL" = true ]; then
        echo -e "${BLUE}  📦 Installing $package globally...${NC}"
        # Capture detailed error output
        local install_output
        install_output=$(npm install -g "$package" 2>&1)
        local exit_code=$?

        if [ $exit_code -eq 0 ]; then
            echo -e "${GREEN}  ✅ Package $package installed globally${NC}"
            log_with_timestamp "SUCCESS: Package $package installed globally"
            return 0
        else
            echo -e "${YELLOW}  ⚠️ Global installation failed, trying alternative methods...${NC}"
            log_error_details "npm install -g" "$package" "$install_output"

            # Check if it's a permission error
            if echo "$install_output" | grep -q "EACCES\|permission denied"; then
                echo -e "${YELLOW}  🔧 Permission issue detected - switching to npx-only mode${NC}"
                log_with_timestamp "Permission error detected, using npx-only approach"
                USE_GLOBAL=false
                return 0  # Continue with npx approach
            else
                echo -e "${RED}  📋 Install error: $install_output${NC}"
                return 1
            fi
        fi
    else
        echo -e "${BLUE}  📦 Using npx direct execution (no global install needed)${NC}"
        log_with_timestamp "Using npx direct execution for $package"
        return 0
    fi
}

# Function to test if MCP server works
test_mcp_server() {
    local name="$1"
    echo -e "${BLUE}  🧪 Testing server $name...${NC}"

    # Try to get server info (this will fail if server can't start)
    if timeout 5s claude mcp list | grep -q "^$name:"; then
        echo -e "${GREEN}  ✅ Server $name is responding${NC}"
        return 0
    else
        echo -e "${YELLOW}  ⚠️ Server $name added but may need configuration${NC}"
        return 1
    fi
}

# Function to cleanup failed server installation
cleanup_failed_server() {
    local name="$1"
    echo -e "${YELLOW}  🧹 Cleaning up failed installation of $name...${NC}"
    claude mcp remove "$name" >/dev/null 2>&1 || true
}

# Function to display current step with dynamic counting
display_step() {
    local title="$1"
    CURRENT_STEP=$((CURRENT_STEP + 1))
    echo -e "\n${BLUE}[$CURRENT_STEP] $title${NC}"
}

# Function to check MCP server in parallel
check_server_parallel() {
    local name="$1"
    local check_file="/tmp/mcp_check_$name.status"
    
    {
        if claude mcp list 2>/dev/null | grep -q "^$name:.*✓ Connected"; then
            echo "CONNECTED" > "$check_file"
        else
            echo "DISCONNECTED" > "$check_file"
        fi
    } &
    
    PARALLEL_PIDS["$name"]=$!
}

# Function to wait for parallel checks and collect results
collect_parallel_results() {
    local timeout_seconds=10
    
    for name in "${!PARALLEL_PIDS[@]}"; do
        local pid=${PARALLEL_PIDS["$name"]}
        local check_file="/tmp/mcp_check_$name.status"
        
        # Each process gets individual timeout calculation
        local process_start_time=$(date +%s)
        local elapsed=0
        while kill -0 "$pid" 2>/dev/null && [ $elapsed -lt $timeout_seconds ]; do
            sleep 0.1
            elapsed=$(( $(date +%s) - process_start_time ))
        done
        
        # Kill if still running
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
        
        # Read result
        if [ -f "$check_file" ]; then
            PARALLEL_RESULTS["$name"]=$(cat "$check_file")
            rm -f "$check_file"
        else
            PARALLEL_RESULTS["$name"]="TIMEOUT"
        fi
    done
    
    # Clear PID tracking (reinitialize associative array correctly)
    unset PARALLEL_PIDS
    declare -A PARALLEL_PIDS
}

# Enhanced function to add MCP server with full error checking
add_mcp_server() {
    local name="$1"
    local package="$2"
    shift 2
    local args="$@"

    update_stats "TOTAL" "$name" ""
    echo -e "${BLUE}  🔧 Setting up $name...${NC}"
    log_with_timestamp "Setting up MCP server: $name (package: $package)"

    # Check if server already exists
    if server_already_exists "$name"; then
        echo -e "${GREEN}  ✅ Server $name already exists, skipping installation${NC}"
        log_with_timestamp "Server $name already exists, skipping"
        update_stats "SUCCESS" "$name" "ALREADY_EXISTS"
        return 0
    fi

    # Check if package exists in npm registry
    echo -e "${BLUE}  🔍 Checking if package $package exists in npm registry...${NC}"
    local registry_check
    registry_check=$(npm view "$package" version 2>&1)
    local registry_exit_code=$?

    if [ $registry_exit_code -ne 0 ]; then
        echo -e "${RED}  ❌ Package $package not found in npm registry${NC}"
        log_error_details "npm view" "$package" "$registry_check"
        INSTALL_RESULTS["$name"]="PACKAGE_NOT_FOUND"
        FAILED_INSTALLS=$((FAILED_INSTALLS + 1))
        return 1
    else
        echo -e "${GREEN}  ✅ Package $package exists (version: $(echo "$registry_check" | head -1))${NC}"
        log_with_timestamp "Package $package exists in registry"
    fi

    # Check if package is installed globally (only if using global mode)
    if [ "$USE_GLOBAL" = true ]; then
        echo -e "${BLUE}  🔍 Checking global npm installation...${NC}"
        local global_check
        global_check=$(npm list -g "$package" 2>&1)
        local global_exit_code=$?

        if [ $global_exit_code -ne 0 ]; then
            echo -e "${YELLOW}  📦 Package $package not installed globally, installing...${NC}"
            log_with_timestamp "Package $package not installed globally, attempting installation"
            if ! install_package "$package"; then
                # If global install failed due to permissions, continue with npx
                if [ "$USE_GLOBAL" = false ]; then
                    echo -e "${BLUE}  🔄 Continuing with npx direct execution${NC}"
                else
                    INSTALL_RESULTS["$name"]="INSTALL_FAILED"
                    FAILED_INSTALLS=$((FAILED_INSTALLS + 1))
                    return 1
                fi
            fi
        else
            echo -e "${GREEN}  ✅ Package $package already installed globally${NC}"
            log_with_timestamp "Package $package already installed globally"
            echo "Global package check: $global_check" >> "$LOG_FILE"
        fi
    else
        echo -e "${BLUE}  🔄 Using npx direct execution - no global installation required${NC}"
        log_with_timestamp "Using npx direct execution for $package"
    fi

    # Remove existing server if present
    claude mcp remove "$name" >/dev/null 2>&1 || true

    # Add server with error checking
    echo -e "${BLUE}  🔗 Adding MCP server $name...${NC}"
    log_with_timestamp "Attempting to add MCP server: $name"

    # Capture detailed error output from claude mcp add
    local add_output
    add_output=$(claude mcp add --scope user "$name" "$NPX_PATH" "$package" $args 2>&1)
    local add_exit_code=$?

    if [ $add_exit_code -eq 0 ]; then
        echo -e "${GREEN}  ✅ Successfully added $name${NC}"
        log_with_timestamp "Successfully added MCP server: $name"

        # Test if server actually works
        sleep 1  # Give server time to initialize
        if test_mcp_server "$name"; then
            INSTALL_RESULTS["$name"]="SUCCESS"
            SUCCESSFUL_INSTALLS=$((SUCCESSFUL_INSTALLS + 1))
        else
            INSTALL_RESULTS["$name"]="NEEDS_CONFIG"
            SUCCESSFUL_INSTALLS=$((SUCCESSFUL_INSTALLS + 1))  # Still count as success
        fi
    else
        echo -e "${RED}  ❌ Failed to add $name to Claude MCP${NC}"
        log_error_details "claude mcp add" "$name" "$add_output"
        echo -e "${RED}  📋 Add error: $add_output${NC}"
        cleanup_failed_server "$name"
        INSTALL_RESULTS["$name"]="ADD_FAILED"
        FAILED_INSTALLS=$((FAILED_INSTALLS + 1))
        return 1
    fi
}

# GitHub Token Configuration (for private repository access)
# Uses centralized token loading system for better maintainability
#
# Generate tokens at:
# - GitHub: https://github.com/settings/tokens (scopes: repo, read:org, read:user)
# - Perplexity: https://www.perplexity.ai/settings/api
#
# NOTE: This script uses GitHub's NEW official MCP server (github/github-mcp-server)
# which is HTTP-based and hosted remotely, replacing the old deprecated npm package

# Load centralized token helper
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOKEN_HELPER="$SCRIPT_DIR/scripts/load_tokens.sh"

if [ -f "$TOKEN_HELPER" ]; then
    echo -e "${BLUE}📋 Loading tokens using centralized helper...${NC}"
    log_with_timestamp "Using centralized token helper: $TOKEN_HELPER"

    # Source the token helper to load functions and tokens
    source "$TOKEN_HELPER"

    # Load tokens
    if load_tokens; then
        log_with_timestamp "Tokens loaded successfully via centralized helper"

        # Ensure tokens are properly exported for use in this script
        # The load_tokens function may not export variables to parent shell properly
        if [ -f "$HOME/.token" ]; then
            source "$HOME/.token" 2>/dev/null || true
            export GITHUB_PERSONAL_ACCESS_TOKEN="$GITHUB_TOKEN"
        fi
    else
        echo -e "${RED}❌ Failed to load tokens via centralized helper${NC}"
        echo -e "${YELLOW}💡 Run '$TOKEN_HELPER create' to create template token file${NC}"
        echo -e "${YELLOW}💡 Run '$TOKEN_HELPER help' for more options${NC}"
        log_with_timestamp "ERROR: Token loading failed, aborting for security"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️ Centralized token helper not found, falling back to legacy method${NC}"
    log_with_timestamp "WARNING: Token helper not found at $TOKEN_HELPER, using fallback"

    # Fallback to legacy token loading
    HOME_TOKEN_FILE="$HOME/.token"
    if [ -f "$HOME_TOKEN_FILE" ]; then
        echo -e "${GREEN}✅ Loading tokens from $HOME_TOKEN_FILE${NC}"
        source "$HOME_TOKEN_FILE"
        export GITHUB_PERSONAL_ACCESS_TOKEN="$GITHUB_TOKEN"
    else
        echo -e "${RED}❌ No token file found${NC}"
        echo -e "${YELLOW}💡 Create ~/.token file with your tokens${NC}"
        exit 1
    fi
fi

# Ensure GITHUB_PERSONAL_ACCESS_TOKEN is exported for compatibility
export GITHUB_PERSONAL_ACCESS_TOKEN

# Function to check environment requirements
check_github_requirements() {
    if [ "$GITHUB_TOKEN_LOADED" = true ]; then
        echo -e "${GREEN}✅ GitHub token loaded - GitHub remote server will have full access${NC}"

        # Test token validity using the centralized helper
        echo -e "${BLUE}  🔍 Testing GitHub token validity...${NC}"
        if test_github_token; then
            echo -e "${BLUE}  📡 Using GitHub's NEW official remote MCP server${NC}"
            echo -e "${BLUE}  🔗 Server URL: https://api.githubcopilot.com/mcp/${NC}"
        fi
    elif [ -n "$GITHUB_PERSONAL_ACCESS_TOKEN" ]; then
        echo -e "${YELLOW}⚠️ GitHub token found but not validated by centralized helper${NC}"
        echo -e "${YELLOW}   Server will work for public repositories${NC}"
        echo -e "${YELLOW}   For private repos, ensure token has required scopes${NC}"
    else
        echo -e "${YELLOW}⚠️ No GitHub token found${NC}"
        echo -e "${YELLOW}   Server will work for public repositories only${NC}"
        echo -e "${YELLOW}   For private repos, add GITHUB_TOKEN to ~/.token file${NC}"
    fi
}

# Enhanced MCP server checking with parallel health checks
echo -e "${BLUE}🔍 Checking existing MCP installations and health status...${NC}"
log_with_timestamp "Checking existing MCP servers with parallel health checks"

EXISTING_SERVERS=""
if EXISTING_SERVERS=$(claude mcp list 2>&1); then
    EXISTING_COUNT=$(echo "$EXISTING_SERVERS" | grep -E "^[a-zA-Z].*:" | wc -l)
    echo -e "${GREEN}✅ Found $EXISTING_COUNT existing MCP servers${NC}"
    log_with_timestamp "Found $EXISTING_COUNT existing MCP servers"

    if [ "$EXISTING_COUNT" -gt 0 ]; then
        echo -e "${BLUE}📋 Running parallel health checks on existing servers...${NC}"
        
        # Extract server names and start parallel health checks
        SERVER_NAMES=($(echo "$EXISTING_SERVERS" | grep -E "^[a-zA-Z].*:" | cut -d':' -f1))
        
        # Start parallel health checks (limited to MAX_PARALLEL_JOBS)
        check_count=0
        for server_name in "${SERVER_NAMES[@]}"; do
            if [ $check_count -ge $MAX_PARALLEL_JOBS ]; then
                # Wait for some checks to complete before starting more
                collect_parallel_results
                check_count=0
            fi
            check_server_parallel "$server_name"
            check_count=$((check_count + 1))
        done
        
        # Wait for remaining checks to complete
        collect_parallel_results
        
        # Display results
        echo -e "${BLUE}📋 Server health status:${NC}"
        for server_name in "${SERVER_NAMES[@]}"; do
            status="${PARALLEL_RESULTS["$server_name"]:-"UNKNOWN"}"
            case "$status" in
                "CONNECTED")
                    echo -e "  ${GREEN}✓${NC} $server_name"
                    ;;
                "DISCONNECTED")
                    echo -e "  ${RED}✗${NC} $server_name"
                    ;;
                "TIMEOUT")
                    echo -e "  ${YELLOW}⏱${NC} $server_name (timeout)"
                    ;;
                *)
                    echo -e "  ${YELLOW}?${NC} $server_name (unknown)"
                    ;;
            esac
        done
        
        echo "$EXISTING_SERVERS" >> "$LOG_FILE"
    fi
else
    echo -e "${YELLOW}⚠️ Could not get MCP server list: $EXISTING_SERVERS${NC}"
    log_error_details "claude mcp list" "N/A" "$EXISTING_SERVERS"
fi
echo ""

# Function to check if MCP server already exists
server_already_exists() {
    local name="$1"
    echo "$EXISTING_SERVERS" | grep -q "^$name:"
}

# Check environment requirements
echo -e "${BLUE}🔍 Checking environment requirements...${NC}"
check_github_requirements
echo ""

# Define server installation batches for parallel processing
# Group servers that can be installed concurrently without conflicts
declare -A BATCH_1=(
    ["sequential-thinking"]="@modelcontextprotocol/server-sequential-thinking"
    ["playwright-mcp"]="@playwright/mcp"
    ["context7"]="@upstash/context7-mcp"
)

declare -A BATCH_2=(
    ["puppeteer-server"]="@modelcontextprotocol/server-puppeteer"
    ["gemini-cli-mcp"]="@yusukedev/gemini-cli-mcp"
    ["ddg-search"]="@oevortex/ddg_search"
)

# Function to install server batch in parallel
install_batch_parallel() {
    local -n batch_ref=$1
    local batch_name="$2"
    
    echo -e "${BLUE}🚀 Installing $batch_name in parallel...${NC}"
    log_with_timestamp "Starting parallel installation of $batch_name"
    
    # Start installations in parallel
    for server_name in "${!batch_ref[@]}"; do
        local package="${batch_ref[$server_name]}"
        {
            local result_file="/tmp/install_${server_name}.result"
            if add_mcp_server "$server_name" "$package" > "/tmp/install_${server_name}.log" 2>&1; then
                echo "SUCCESS" > "$result_file"
            else
                echo "FAILED" > "$result_file"
            fi
        } &
        
        PARALLEL_PIDS["$server_name"]=$!
        log_with_timestamp "Started parallel installation of $server_name (PID: ${PARALLEL_PIDS[$server_name]})"
    done
    
    # Wait for all installations to complete
    echo -e "${BLUE}  ⏳ Waiting for $batch_name installations to complete...${NC}"
    
    for server_name in "${!batch_ref[@]}"; do
        local pid="${PARALLEL_PIDS[$server_name]}"
        local result_file="/tmp/install_${server_name}.result"
        local log_file="/tmp/install_${server_name}.log"
        
        # Wait for this installation
        if wait "$pid"; then
            local result="$(cat "$result_file" 2>/dev/null || echo "UNKNOWN")"
            if [ "$result" = "SUCCESS" ]; then
                echo -e "${GREEN}  ✓ $server_name completed successfully${NC}"
                log_with_timestamp "Parallel installation SUCCESS: $server_name"
            else
                echo -e "${RED}  ✗ $server_name failed${NC}"
                log_with_timestamp "Parallel installation FAILED: $server_name"
                # Show error details
                if [ -f "$log_file" ]; then
                    echo -e "${RED}    Error details: $(tail -1 "$log_file")${NC}"
                fi
            fi
        else
            echo -e "${RED}  ✗ $server_name process failed${NC}"
            log_with_timestamp "Parallel installation PROCESS_FAILED: $server_name"
        fi
        
        # Cleanup temp files
        rm -f "$result_file" "$log_file"
    done
    
    # Clear parallel tracking (reinitialize associative array correctly)
    unset PARALLEL_PIDS
    declare -A PARALLEL_PIDS
    
    echo -e "${GREEN}✅ $batch_name installation batch completed${NC}"
}

# Core MCP Servers Installation
echo -e "${BLUE}📊 Installing Core MCP Servers with Parallel Processing...${NC}"

display_step "Setting up GitHub MCP Server (Official Remote)..."
# GitHub released a new official MCP server that replaces @modelcontextprotocol/server-github
# The new server is HTTP-based and hosted by GitHub for better reliability and features
echo -e "${BLUE}🔧 Setting up github-server (NEW Official Remote HTTP Server)...${NC}"

if server_already_exists "github-server"; then
    echo -e "${GREEN}  ✅ Server github-server already exists, skipping installation${NC}"
    log_with_timestamp "Server github-server already exists, skipping"
    INSTALL_RESULTS["github-server"]="ALREADY_EXISTS"
    SUCCESSFUL_INSTALLS=$((SUCCESSFUL_INSTALLS + 1))
else
    echo -e "${BLUE}  🔗 Adding GitHub official remote MCP server...${NC}"
    log_with_timestamp "Adding GitHub official remote MCP server"

    # Remove any old deprecated GitHub server first
    claude mcp remove "github-server" >/dev/null 2>&1 || true

    # Add the new official GitHub HTTP MCP server
    add_output=$(claude mcp add-json --scope user "github-server" '{"type": "http", "url": "https://api.githubcopilot.com/mcp/", "authorization_token": "Bearer '"$GITHUB_PERSONAL_ACCESS_TOKEN"'"}' 2>&1)
    add_exit_code=$?

    if [ $add_exit_code -eq 0 ]; then
        echo -e "${GREEN}  ✅ Successfully added GitHub remote MCP server${NC}"
        log_with_timestamp "Successfully added GitHub remote MCP server"
        INSTALL_RESULTS["github-server"]="SUCCESS"
        SUCCESSFUL_INSTALLS=$((SUCCESSFUL_INSTALLS + 1))
    else
        echo -e "${RED}  ❌ Failed to add GitHub remote MCP server${NC}"
        log_error_details "claude mcp add-json" "github-server" "$add_output"
        echo -e "${RED}  📋 Add error: $add_output${NC}"
        INSTALL_RESULTS["github-server"]="ADD_FAILED"
        FAILED_INSTALLS=$((FAILED_INSTALLS + 1))
    fi
fi

display_step "Installing Batch 1 Servers (Parallel)..."
install_batch_parallel BATCH_1 "Batch 1"

display_step "Setting up Memory MCP Server..."
# Create memory data directory in user's home
mkdir -p ~/.cache/mcp-memory
echo -e "${BLUE}  📁 Memory data directory: ~/.cache/mcp-memory/${NC}"

# Configure memory server with custom data path
MEMORY_PATH="$HOME/.cache/mcp-memory/memory.json"
echo -e "${BLUE}  📁 Memory file path: $MEMORY_PATH${NC}"

# Remove existing memory server to reconfigure
claude mcp remove "memory-server" -s user >/dev/null 2>&1 || true

# Add memory server with environment variable configuration
echo -e "${BLUE}  🔗 Adding memory server with custom configuration...${NC}"
add_output=$(claude mcp add --scope user "memory-server" "$NPX_PATH" "@modelcontextprotocol/server-memory" --env "MEMORY_FILE_PATH=$MEMORY_PATH" 2>&1)
add_exit_code=$?

if [ $add_exit_code -eq 0 ]; then
    echo -e "${GREEN}  ✅ Successfully configured memory server with custom path${NC}"
    log_with_timestamp "Successfully added memory server with custom path: $MEMORY_PATH"
else
    echo -e "${YELLOW}  ⚠️ Environment variable method failed, trying fallback...${NC}"
    log_with_timestamp "Environment variable method failed: $add_output"

    # Fallback: use standard add but create a symlink or wrapper script
    echo -e "${BLUE}  🔄 Using fallback configuration method...${NC}"

    # Create wrapper script that sets the environment variable
    WRAPPER_SCRIPT="$HOME/.cache/mcp-memory/memory-server-wrapper.sh"
    cat > "$WRAPPER_SCRIPT" << 'EOF'
#!/bin/bash
export MEMORY_FILE_PATH="$HOME/.cache/mcp-memory/memory.json"
exec npx @modelcontextprotocol/server-memory "$@"
EOF
    chmod +x "$WRAPPER_SCRIPT"

    # Add server using the wrapper script
    fallback_output=$(claude mcp add --scope user "memory-server" "$WRAPPER_SCRIPT" 2>&1)
    fallback_exit_code=$?

    if [ $fallback_exit_code -eq 0 ]; then
        echo -e "${GREEN}  ✅ Successfully added memory server with wrapper script${NC}"
        log_with_timestamp "Successfully added memory server with wrapper script"
    else
        echo -e "${RED}  ❌ Both methods failed for memory server${NC}"
        log_error_details "claude mcp add wrapper" "memory-server" "$fallback_output"
        echo -e "${YELLOW}  💡 You may need to manually configure the memory server${NC}"
    fi
fi

display_step "Installing Batch 2 Servers (Parallel)..."
install_batch_parallel BATCH_2 "Batch 2"

display_step "Setting up Web Search MCP Servers..."
echo -e "${BLUE}📋 Installing both free DuckDuckGo and premium Perplexity search servers${NC}"

# Remove existing web search servers to avoid conflicts
claude mcp remove "web-search-duckduckgo" >/dev/null 2>&1 || true
claude mcp remove "perplexity-ask" >/dev/null 2>&1 || true
claude mcp remove "ddg-search" >/dev/null 2>&1 || true

# DuckDuckGo is now installed in Batch 2
echo -e "${BLUE}  → DuckDuckGo Web Search (Free) - installed in Batch 2${NC}"
echo -e "${GREEN}✅ DuckDuckGo search - completely free, no API key needed${NC}"
echo -e "${BLUE}📋 Features: Web search, content fetching, privacy-focused${NC}"

# Install Perplexity search server (premium, requires API key)
echo -e "\n${BLUE}  → Perplexity AI Search (Premium)...${NC}"
if [ -n "$PERPLEXITY_API_KEY" ]; then
    echo -e "${GREEN}✅ Perplexity API key found - installing premium search server${NC}"
    echo -e "${BLUE}📋 Features: AI-powered search, real-time web research, advanced queries${NC}"

    # Add Perplexity server with API key
    echo -e "${BLUE}    🔧 Installing Perplexity search server...${NC}"
    add_output=$(claude mcp add --scope user "perplexity-ask" "npx" "server-perplexity-ask" --env "PERPLEXITY_API_KEY=$PERPLEXITY_API_KEY" 2>&1)
    add_exit_code=$?

    if [ $add_exit_code -eq 0 ]; then
        echo -e "${GREEN}    ✅ Successfully added Perplexity search server${NC}"
        log_with_timestamp "Successfully added Perplexity search server with API key"
        INSTALL_RESULTS["perplexity-ask"]="SUCCESS"
        SUCCESSFUL_INSTALLS=$((SUCCESSFUL_INSTALLS + 1))
    else
        echo -e "${RED}    ❌ Failed to add Perplexity search server${NC}"
        log_error_details "claude mcp add perplexity" "perplexity-ask" "$add_output"
        INSTALL_RESULTS["perplexity-ask"]="ADD_FAILED"
        FAILED_INSTALLS=$((FAILED_INSTALLS + 1))
    fi
else
    echo -e "${YELLOW}⚠️ Perplexity API key not found - skipping premium server${NC}"
    echo -e "${YELLOW}💡 Perplexity server provides AI-powered search with real-time web research${NC}"
    echo -e "${YELLOW}💡 Add PERPLEXITY_API_KEY to ~/.token file to enable${NC}"
    log_with_timestamp "Perplexity API key not found, skipping premium server installation"
fi

# Optional: Notion Server (if available)
display_step "Setting up Filesystem MCP Server..."
TOTAL_SERVERS=$((TOTAL_SERVERS + 1))
echo -e "${BLUE}  📁 Configuring filesystem access for projects directory...${NC}"
log_with_timestamp "Setting up MCP server: filesystem (package: @modelcontextprotocol/server-filesystem)"

# Check if server already exists
if server_already_exists "filesystem"; then
    echo -e "${GREEN}  ✅ Server filesystem already exists, skipping installation${NC}"
    log_with_timestamp "Server filesystem already exists, skipping"
    INSTALL_RESULTS["filesystem"]="ALREADY_EXISTS"
    SUCCESSFUL_INSTALLS=$((SUCCESSFUL_INSTALLS + 1))
else
    # Remove existing filesystem server to reconfigure with proper directory access
    claude mcp remove "filesystem" >/dev/null 2>&1 || true

    # Add filesystem server with proper directory configuration
    echo -e "${BLUE}  🔗 Adding filesystem server with /home/$USER/projects access...${NC}"
    add_output=$(claude mcp add --scope user "filesystem" "$NPX_PATH" "@modelcontextprotocol/server-filesystem" "/home/$USER/projects" 2>&1)
    add_exit_code=$?

    if [ $add_exit_code -eq 0 ]; then
        echo -e "${GREEN}  ✅ Successfully configured filesystem server with project directory access${NC}"
        log_with_timestamp "Successfully added filesystem server with /home/$USER/projects access"
        INSTALL_RESULTS["filesystem"]="SUCCESS"
        SUCCESSFUL_INSTALLS=$((SUCCESSFUL_INSTALLS + 1))
    else
        echo -e "${RED}  ❌ Failed to add filesystem server${NC}"
        log_error_details "claude mcp add filesystem" "filesystem" "$add_output"
        INSTALL_RESULTS["filesystem"]="ADD_FAILED"
        FAILED_INSTALLS=$((FAILED_INSTALLS + 1))
    fi
fi

display_step "Checking for Notion MCP Server..."
if package_exists "@notionhq/notion-mcp-server"; then
    add_mcp_server "notion-server" "@notionhq/notion-mcp-server"
elif package_exists "@makenotion/notion-mcp-server"; then
    add_mcp_server "notion-server" "@makenotion/notion-mcp-server"
else
    echo -e "${YELLOW}  ⚠️ Notion MCP server package not found, skipping...${NC}"
fi


display_step "Setting up React MCP Server..."
TOTAL_SERVERS=$((TOTAL_SERVERS + 1))
echo -e "${BLUE}  ⚛️ Configuring React MCP server for React development...${NC}"
log_with_timestamp "Setting up MCP server: react-mcp (local: react-mcp/index.js)"

# Check if server already exists
if server_already_exists "react-mcp"; then
    echo -e "${GREEN}  ✅ Server react-mcp already exists, skipping installation${NC}"
    log_with_timestamp "Server react-mcp already exists, skipping"
    INSTALL_RESULTS["react-mcp"]="ALREADY_EXISTS"
    SUCCESSFUL_INSTALLS=$((SUCCESSFUL_INSTALLS + 1))
else
    # Get the absolute path to the react-mcp directory
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REACT_MCP_PATH="$SCRIPT_DIR/react-mcp/index.js"
    
    # Check if react-mcp directory exists
    if [ -f "$REACT_MCP_PATH" ]; then
        echo -e "${GREEN}  ✅ Found React MCP server at: $REACT_MCP_PATH${NC}"
        log_with_timestamp "Found React MCP server at: $REACT_MCP_PATH"
        
        # Ensure dependencies are installed without using 'cd'
        if [ -f "${SCRIPT_DIR}/react-mcp/package.json" ]; then
            if [ ! -d "${SCRIPT_DIR}/react-mcp/node_modules" ]; then
                echo -e "${BLUE}  📦 Installing react-mcp dependencies...${NC}"
                
                # Check for package-lock.json before using npm ci
                if [ -f "${SCRIPT_DIR}/react-mcp/package-lock.json" ]; then
                    dep_output=$(npm --prefix "${SCRIPT_DIR}/react-mcp" ci 2>&1)
                else
                    echo -e "${YELLOW}  ⚠️ No package-lock.json found, using npm install instead${NC}"
                    dep_output=$(npm --prefix "${SCRIPT_DIR}/react-mcp" install 2>&1)
                fi
                
                dep_exit=$?
                if [ $dep_exit -ne 0 ]; then
                    echo -e "${RED}  ❌ Failed to install react-mcp dependencies${NC}"
                    log_error_details "npm dependency installation (react-mcp)" "react-mcp" "$dep_output"
                    update_stats "FAILURE" "react-mcp" "INSTALL_FAILED"
                    # Skip server addition - dependency failure is critical
                    echo -e "${YELLOW}  ⚠️ Skipping react-mcp server addition due to dependency failure${NC}"
                    REACT_MCP_SKIP=true
                else
                    echo -e "${GREEN}  ✅ Dependencies installed for react-mcp${NC}"
                    REACT_MCP_SKIP=false
                fi
            else
                REACT_MCP_SKIP=false
            fi
        else
            REACT_MCP_SKIP=false
        fi
        
        # Only add server if dependencies were successful
        if [ "$REACT_MCP_SKIP" != "true" ]; then
            # Remove existing react-mcp server to reconfigure
            claude mcp remove "react-mcp" >/dev/null 2>&1 || true

            # Add React MCP server using discovered Node binary with absolute path
            echo -e "${BLUE}  🔗 Adding React MCP server...${NC}"
            log_with_timestamp "Attempting to add React MCP server"

            add_output=$(claude mcp add --scope user "react-mcp" "$NODE_PATH" "$REACT_MCP_PATH" 2>&1)
            add_exit_code=$?

            if [ $add_exit_code -eq 0 ]; then
            echo -e "${GREEN}  ✅ Successfully configured React MCP server${NC}"
            echo -e "${BLUE}  📋 Server info:${NC}"
            echo -e "     • Path: $REACT_MCP_PATH"
            echo -e "     • Available tools: Create React apps, run dev servers, file operations, package management"
            echo -e "     • Features: React project management, terminal commands, process tracking"
            log_with_timestamp "Successfully added React MCP server"
            INSTALL_RESULTS["react-mcp"]="SUCCESS"
            SUCCESSFUL_INSTALLS=$((SUCCESSFUL_INSTALLS + 1))
        else
            echo -e "${RED}  ❌ Failed to add React MCP server${NC}"
            log_error_details "claude mcp add react-mcp" "react-mcp" "$add_output"
            INSTALL_RESULTS["react-mcp"]="ADD_FAILED"
            FAILED_INSTALLS=$((FAILED_INSTALLS + 1))
        fi
        fi  # Close the REACT_MCP_SKIP check
    else
        echo -e "${RED}  ❌ React MCP server not found at expected path: $REACT_MCP_PATH${NC}"
        echo -e "${YELLOW}  💡 Run 'git submodule update --init --recursive' to initialize submodules${NC}"
        log_with_timestamp "ERROR: React MCP server not found at $REACT_MCP_PATH"
        INSTALL_RESULTS["react-mcp"]="DEPENDENCY_MISSING"
        FAILED_INSTALLS=$((FAILED_INSTALLS + 1))
    fi
fi

display_step "Setting up Serena MCP Server..."
TOTAL_SERVERS=$((TOTAL_SERVERS + 1))
echo -e "${BLUE}  🧠 Configuring Serena MCP server for semantic code analysis...${NC}"
log_with_timestamp "Setting up MCP server: serena (uvx: git+https://github.com/oraios/serena)"

# Pre-flight check: Ensure uvx is available
echo -e "${BLUE}  🔍 Checking uvx availability...${NC}"
if ! command -v uvx >/dev/null 2>&1; then
    echo -e "${RED}  ❌ 'uvx' not found - required for Serena MCP server${NC}"
    echo -e "${YELLOW}  💡 Install uvx with: pip install uv${NC}"
    log_with_timestamp "ERROR: uvx not found, skipping Serena MCP server installation"
    INSTALL_RESULTS["serena"]="DEPENDENCY_MISSING"
    FAILED_INSTALLS=$((FAILED_INSTALLS + 1))
    TOTAL_SERVERS=$((TOTAL_SERVERS - 1))  # Correct count since we're not installing
else
    echo -e "${GREEN}  ✅ uvx found: $(uvx --version 2>/dev/null || echo "available")${NC}"
    log_with_timestamp "uvx dependency check passed"

    # Check if server already exists
    if server_already_exists "serena"; then
    echo -e "${GREEN}  ✅ Server serena already exists, skipping installation${NC}"
    log_with_timestamp "Server serena already exists, skipping"
    INSTALL_RESULTS["serena"]="ALREADY_EXISTS"
    SUCCESSFUL_INSTALLS=$((SUCCESSFUL_INSTALLS + 1))
else
    # Remove existing serena server to reconfigure
    claude mcp remove "serena" >/dev/null 2>&1 || true

    # Add Serena MCP server using uvx with git repository
    echo -e "${BLUE}  🔗 Adding Serena MCP server via uvx...${NC}"
    log_with_timestamp "Attempting to add Serena MCP server via uvx"

    # Use add-json for uvx configuration
    add_output=$(claude mcp add-json --scope user "serena" '{"command":"uvx","args":["--from","git+https://github.com/oraios/serena","serena","start-mcp-server"]}' 2>&1)
    add_exit_code=$?

    if [ $add_exit_code -eq 0 ]; then
        echo -e "${GREEN}  ✅ Successfully configured Serena MCP server${NC}"
        echo -e "${BLUE}  📋 Server info:${NC}"
        echo -e "     • Repository: https://github.com/oraios/serena"
        echo -e "     • Available tools: Semantic code analysis, file operations, memory system"
        echo -e "     • Dashboard: http://127.0.0.1:24282/dashboard/index.html"
        echo -e "     • Configuration: ~/.serena/serena_config.yml"
        log_with_timestamp "Successfully added Serena MCP server via uvx"
        INSTALL_RESULTS["serena"]="SUCCESS"
        SUCCESSFUL_INSTALLS=$((SUCCESSFUL_INSTALLS + 1))
    else
        echo -e "${RED}  ❌ Failed to add Serena MCP server${NC}"
        log_error_details "claude mcp add-json serena" "serena" "$add_output"
        INSTALL_RESULTS["serena"]="ADD_FAILED"
        FAILED_INSTALLS=$((FAILED_INSTALLS + 1))
    fi
    fi
fi

# Final verification and results
echo -e "\n${BLUE}✅ Verifying final installation...${NC}"
MCP_LIST=$(claude mcp list 2>/dev/null)
ACTUAL_SERVERS=$(echo "$MCP_LIST" | grep -E "^[a-zA-Z].*:" | wc -l)

echo -e "\n${GREEN}📋 Installation Results Summary:${NC}"
echo -e "${GREEN}=================================${NC}"
echo -e "${BLUE}Total servers attempted: $TOTAL_SERVERS${NC}"
echo -e "${GREEN}Successful installations: $SUCCESSFUL_INSTALLS${NC}"
echo -e "${RED}Failed installations: $FAILED_INSTALLS${NC}"
echo -e "${BLUE}Currently active servers: $ACTUAL_SERVERS${NC}"

echo -e "\n${BLUE}📊 Detailed Results:${NC}"
for server in "${!INSTALL_RESULTS[@]}"; do
    result="${INSTALL_RESULTS[$server]}"
    case "$result" in
        "SUCCESS")
            echo -e "${GREEN}  ✅ $server: Installed and working${NC}"
            ;;
        "NEEDS_CONFIG")
            echo -e "${YELLOW}  ⚠️ $server: Installed but may need configuration${NC}"
            ;;
        "ALREADY_EXISTS")
            echo -e "${BLUE}  ℹ️ $server: Already existed, skipped installation${NC}"
            ;;
        "PACKAGE_NOT_FOUND")
            echo -e "${RED}  ❌ $server: Package not found in npm registry${NC}"
            ;;
        "INSTALL_FAILED")
            echo -e "${RED}  ❌ $server: Failed to install npm package${NC}"
            ;;
        "ADD_FAILED")
            echo -e "${RED}  ❌ $server: Failed to add to Claude MCP${NC}"
            ;;
        "DEPENDENCY_MISSING")
            echo -e "${RED}  ❌ $server: Required dependency not found${NC}"
            ;;
    esac
done

echo -e "\n${BLUE}🔍 Current MCP Server List:${NC}"
echo "$MCP_LIST"

# Final logging summary
log_with_timestamp "Installation completed: $SUCCESSFUL_INSTALLS successful, $FAILED_INSTALLS failed"
echo -e "\n${BLUE}📝 Detailed log saved to: $LOG_FILE${NC}"
echo -e "${BLUE}💡 To view log: cat $LOG_FILE${NC}"

if [ "$SUCCESSFUL_INSTALLS" -gt 0 ]; then
    echo -e "\n${GREEN}🎉 MCP servers installed successfully!${NC}"
    if [ "$FAILED_INSTALLS" -gt 0 ]; then
        echo -e "${YELLOW}⚠️ Some servers failed to install. Check the detailed results above or log file.${NC}"
        echo -e "${YELLOW}💡 Log file: $LOG_FILE${NC}"
    fi
    exit 0
else
    echo -e "\n${RED}❌ No servers were successfully installed. Please check the errors above.${NC}"
    echo -e "${RED}💡 Check the detailed log: $LOG_FILE${NC}"
    exit 1
fi
