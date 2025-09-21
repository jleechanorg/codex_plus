#!/bin/bash
# GitHub Self-Hosted Runner Setup Script for Codex Plus
# Downloads, configures, and starts a GitHub Actions runner

set -e

# Configuration
RUNNER_DIR="$HOME/actions-runner"
RUNNER_VERSION="2.311.0"
LABELS="self-hosted,codex-plus,claude"

# Parse arguments
REPO_URL=""
RUNNER_TOKEN=""
NO_AUTO_INSTALL="false"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo)
            REPO_URL="$2"
            shift 2
            ;;
        --token)
            RUNNER_TOKEN="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--repo <repository-url>] [--token <runner-token>]"
            echo "  --repo: GitHub repository URL (e.g., https://github.com/user/repo)"
            echo "  --token: GitHub runner token"
            echo "  If repo not specified, will try to detect from git remote origin"
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

# If not set by argument, check environment variable
if [[ -z "$REPO_URL" && -n "$GITHUB_REPO_URL" ]]; then
    REPO_URL="$GITHUB_REPO_URL"
fi

# If still not set, try to get from git remote
if [[ -z "$REPO_URL" ]]; then
    if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        REPO_URL="$(git config --get remote.origin.url 2>/dev/null || echo '')"
        # Convert SSH to HTTPS format if needed
        if [[ "$REPO_URL" =~ ^git@github\.com:(.+)\.git$ ]]; then
            REPO_URL="https://github.com/${BASH_REMATCH[1]}"
        fi
    fi
fi

# If still not set, print error and exit
if [[ -z "$REPO_URL" ]]; then
    echo "❌ Repository URL not specified."
    echo "Please either:"
    echo "  1. Run from within a git repository with origin remote"
    echo "  2. Use --repo <repository-url> argument"
    echo "  3. Set GITHUB_REPO_URL environment variable"
    echo ""
    echo "Example: $0 --repo https://github.com/user/repo"
    exit 1
fi

echo "🚀 GitHub Runner Setup for Codex Plus"
echo "======================================"
echo ""

# Check operating system
OS="linux"
ARCH="x64"

case "$(uname -s)" in
    Linux*)     OS="linux" ;;
    Darwin*)    OS="osx" ;;
    MINGW*)     OS="win" ;;
    *)
        echo "❌ Unsupported operating system: $(uname -s)"
        echo "This script supports Linux, macOS, and Windows (Git Bash)"
        exit 1
        ;;
esac

case "$(uname -m)" in
    x86_64*)    ARCH="x64" ;;
    arm64*)     ARCH="arm64" ;;
    aarch64*)   ARCH="arm64" ;;
    *)
        echo "⚠️  Architecture $(uname -m) detected. Using x64 as default."
        ARCH="x64"
        ;;
esac

echo "✅ Detected: $OS-$ARCH"

# Check if runner directory already exists
if [[ -d "$RUNNER_DIR" ]]; then
    echo "⚠️  Runner directory already exists: $RUNNER_DIR"
    read -p "Remove existing directory and start fresh? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️  Removing existing runner directory..."
        rm -rf "$RUNNER_DIR"
        echo "✅ Removed existing directory"
    else
        echo "❌ Cannot proceed with existing directory. Please remove it manually."
        exit 1
    fi
fi

# Create runner directory
echo "📁 Creating runner directory: $RUNNER_DIR"
mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

# Download runner
RUNNER_PACKAGE="actions-runner-${OS}-${ARCH}-${RUNNER_VERSION}.tar.gz"
DOWNLOAD_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${RUNNER_PACKAGE}"

echo "⬇️  Downloading GitHub runner: $RUNNER_PACKAGE"
if command -v curl >/dev/null 2>&1; then
    curl -L "$DOWNLOAD_URL" -o "$RUNNER_PACKAGE"
elif command -v wget >/dev/null 2>&1; then
    wget "$DOWNLOAD_URL" -O "$RUNNER_PACKAGE"
else
    echo "❌ Neither curl nor wget found. Please install one of them."
    exit 1
fi

# Extract runner
echo "📦 Extracting runner..."
tar xzf "$RUNNER_PACKAGE"

# Configure runner
echo "⚙️  Configuring runner..."
echo "Repository: $REPO_URL"

# If token not provided, prompt for it
if [[ -z "$RUNNER_TOKEN" ]]; then
    echo ""
    echo "📋 To get a runner token:"
    echo "  1. Go to: ${REPO_URL}/settings/actions/runners"
    echo "  2. Click 'New self-hosted runner'"
    echo "  3. Copy the token from the configuration command"
    echo ""
    read -p "Enter runner token: " RUNNER_TOKEN
fi

if [[ -z "$RUNNER_TOKEN" ]]; then
    echo "❌ Runner token is required"
    exit 1
fi

# Configure the runner
./config.sh --url "$REPO_URL" --token "$RUNNER_TOKEN" --labels "$LABELS" --unattended

echo ""
echo "✅ Runner configured successfully!"

# Start runner
echo "🚀 Starting runner..."
echo "Note: This will run in the foreground. Use Ctrl+C to stop."
echo ""

# For Unix-like systems, offer to install as a service
if [[ "$OS" != "win" ]]; then
    read -p "Install as a system service? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "📋 Installing as service..."
        sudo ./svc.sh install
        sudo ./svc.sh start
        echo "✅ Service installed and started"
        echo "   Status: sudo ./svc.sh status"
        echo "   Stop: sudo ./svc.sh stop"
        echo "   Uninstall: sudo ./svc.sh uninstall"
    else
        echo "▶️  Starting runner in foreground mode..."
        ./run.sh
    fi
else
    echo "▶️  Starting runner..."
    ./run.cmd
fi

echo ""
echo "🎉 GitHub runner setup complete!"
echo "The runner is now ready to accept Codex Plus CI/CD jobs."