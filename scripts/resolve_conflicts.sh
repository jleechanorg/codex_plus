#!/bin/bash
# Simple script to resolve conflicts for current PR in Codex Plus
# Usage: ./resolve_conflicts.sh

echo "🔄 Auto-resolving conflicts for current branch..."

# Get current branch and PR number
CURRENT_BRANCH=$(git branch --show-current)
PR_NUMBER=$(gh pr view --json number --jq '.number' 2>/dev/null || echo "")

if [ -z "$PR_NUMBER" ]; then
    echo "❌ Not in a PR branch or no PR found"
    echo "💡 Make sure you have GitHub CLI installed and are in a branch with an open PR"
    exit 1
fi

echo "📍 Branch: $CURRENT_BRANCH"
echo "📋 PR: #$PR_NUMBER"

# Check if auto-resolution script exists
AUTO_RESOLVE_SCRIPT="scripts/auto_resolve_conflicts.sh"
if [ -f "$AUTO_RESOLVE_SCRIPT" ]; then
    echo "🔧 Using auto-resolution script..."
    chmod +x "$AUTO_RESOLVE_SCRIPT"
    ./"$AUTO_RESOLVE_SCRIPT" "$PR_NUMBER"
else
    echo "⚠️  Auto-resolution script not found at $AUTO_RESOLVE_SCRIPT"
    echo "📝 Manual conflict resolution steps:"
    echo "   1. git fetch origin"
    echo "   2. git merge origin/main"
    echo "   3. Resolve conflicts manually"
    echo "   4. git add ."
    echo "   5. git commit"
    echo "   6. git push"
fi