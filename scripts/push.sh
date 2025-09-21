#!/bin/bash
# Quick push script for Codex Plus development
# Adds, commits, and pushes changes with a timestamped message

# Ensure we are in the correct directory for git commands
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [[ -z "$PROJECT_ROOT" ]]; then
    echo "❌ Error: Not in a git repository. Please run this script from within the Codex Plus project."
    exit 1
fi

cd "$PROJECT_ROOT" || {
    echo "❌ Error: Could not change to project root: $PROJECT_ROOT"
    exit 1
}

# Generate timestamp
TIMESTAMP=$(TZ='America/Los_Angeles' date '+%Y-%m-%d %H:%M:%S %Z')

# Check if a commit message argument was provided
if [ "$#" -eq 0 ]; then
    # If no argument, create the default message
    COMMIT_MSG="update codex plus at ${TIMESTAMP}"
else
    # If an argument exists, combine it with the timestamp
    COMMIT_MSG="$* ${TIMESTAMP}"
fi

echo "🚀 Codex Plus: Staging all changes..."
git add .

# Use the dynamically created commit message
echo "📝 Committing with message: '${COMMIT_MSG}'..."
git commit -m "${COMMIT_MSG}"

echo "⬆️  Pushing changes to GitHub..."
if git push 2>/dev/null; then
    echo "✅ Push complete."
else
    echo "⚠️  Push failed - likely no git remote configured."
    echo "   To add a remote: git remote add origin <repository-url>"
    echo "   Changes have been committed locally."
fi

# Check if proxy needs restart after push
current_branch=$(git branch --show-current)
if [ "$current_branch" != "main" ]; then
    echo ""
    echo "💡 Development tip: If you modified proxy code, consider restarting:"
    echo "   ./proxy.sh restart"
else
    echo ""
    echo "ℹ️  Pushed to main branch - consider testing with:"
    echo "   ./proxy.sh status"
fi