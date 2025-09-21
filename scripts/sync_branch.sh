#!/bin/bash
# Synchronize local Git branch with remote branch for Codex Plus development

# Function to display error messages and exit
error_exit() {
    echo "Error: $1" >&2
    exit 1
}

# Function to display info messages
info_message() {
    echo "Info: $1"
}

# Get current branch
CURRENT_BRANCH=$(git branch --show-current)
if [ -z "$CURRENT_BRANCH" ]; then
    error_exit "Could not determine current branch"
fi

# Parse arguments
LOCAL_BRANCH="${1:-$CURRENT_BRANCH}"
REMOTE_BRANCH="${2:-$LOCAL_BRANCH}"
REMOTE_NAME="${3:-origin}"

info_message "Synchronizing branches:"
echo "  Local:  $LOCAL_BRANCH"
echo "  Remote: $REMOTE_NAME/$REMOTE_BRANCH"

# Ensure we're in a git repository
if ! git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    error_exit "Not inside a Git repository"
fi

# Store original branch to return to later
ORIGINAL_BRANCH="$CURRENT_BRANCH"

# Fetch latest changes from remote
info_message "Fetching latest changes from $REMOTE_NAME..."
if ! git fetch "$REMOTE_NAME"; then
    error_exit "Failed to fetch from $REMOTE_NAME"
fi

# Check if local branch exists
if ! git show-ref --verify --quiet "refs/heads/$LOCAL_BRANCH"; then
    info_message "Local branch '$LOCAL_BRANCH' doesn't exist. Creating from $REMOTE_NAME/$REMOTE_BRANCH..."
    if ! git checkout -b "$LOCAL_BRANCH" "$REMOTE_NAME/$REMOTE_BRANCH"; then
        error_exit "Failed to create local branch '$LOCAL_BRANCH'"
    fi
else
    # Switch to the local branch
    info_message "Switching to local branch '$LOCAL_BRANCH'..."
    if ! git checkout "$LOCAL_BRANCH"; then
        error_exit "Failed to checkout local branch '$LOCAL_BRANCH'"
    fi

    # Check if remote branch exists
    if git show-ref --verify --quiet "refs/remotes/$REMOTE_NAME/$REMOTE_BRANCH"; then
        info_message "Pulling changes from $REMOTE_NAME/$REMOTE_BRANCH..."
        if ! git pull "$REMOTE_NAME" "$REMOTE_BRANCH"; then
            error_exit "Failed to pull from $REMOTE_NAME/$REMOTE_BRANCH"
        fi
    else
        info_message "Remote branch '$REMOTE_NAME/$REMOTE_BRANCH' doesn't exist"
    fi
fi

# Set upstream tracking
info_message "Setting upstream tracking to $REMOTE_NAME/$REMOTE_BRANCH..."
if ! git branch --set-upstream-to="$REMOTE_NAME/$REMOTE_BRANCH" "$LOCAL_BRANCH"; then
    error_exit "Failed to set upstream tracking"
fi

# Push local changes if any
if [ -n "$(git log --oneline $REMOTE_NAME/$REMOTE_BRANCH..$LOCAL_BRANCH 2>/dev/null)" ]; then
    info_message "Local commits found. Pushing to $REMOTE_NAME/$REMOTE_BRANCH..."
    if ! git push "$REMOTE_NAME" "$LOCAL_BRANCH:$REMOTE_BRANCH"; then
        error_exit "Failed to push to $REMOTE_NAME/$REMOTE_BRANCH"
    fi
else
    info_message "No local commits to push"
fi

# Return to original branch if different
if [ "$ORIGINAL_BRANCH" != "$LOCAL_BRANCH" ]; then
    info_message "Returning to original branch '$ORIGINAL_BRANCH'..."
    git checkout "$ORIGINAL_BRANCH"
fi

echo "✅ Branch synchronization complete!"
echo "   Local '$LOCAL_BRANCH' is now synced with $REMOTE_NAME/$REMOTE_BRANCH"