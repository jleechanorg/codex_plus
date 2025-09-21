#!/bin/bash
# Schedule a Claude conversation with Git and branch context for Codex Plus
set -euo pipefail

# Source bashrc to ensure PATH and environment variables are loaded
[[ -f ~/.bashrc ]] && source ~/.bashrc

# Check for correct number of arguments
if [ "$#" -lt 1 ] || [ "$#" -gt 3 ]; then
  echo "Usage: $0 <time-HH:MM> [branch-name] [--continue]"
  echo "If a branch name is not specified, the script uses the current git branch."
  echo "Use --continue to resume the previous conversation instead of starting fresh."
  exit 1
fi

SCHEDULE_TIME="$1"
USE_CONTINUE=false

# Check if --continue flag is present (can be 2nd or 3rd argument)
for arg in "$@"; do
  if [[ "$arg" == "--continue" ]]; then
    USE_CONTINUE=true
    break
  fi
done

# Ensure the time is in HH:MM 24-hour format
if ! [[ "$SCHEDULE_TIME" =~ ^([01]?[0-9]|2[0-3]):[0-5][0-9]$ ]]; then
  echo "Error: time must be in HH:MM 24-hour format"
  exit 1
fi

# Parse arguments to get branch name
REMOTE_BRANCH=""
if [ "$#" -ge 2 ]; then
  if [[ "$2" != "--continue" ]]; then
    REMOTE_BRANCH="$2"
  elif [ "$#" -ge 3 ] && [[ "$3" != "--continue" ]]; then
    REMOTE_BRANCH="$3"
  fi
fi

# Resolve branch if not provided
if [ -z "$REMOTE_BRANCH" ]; then
  REMOTE_BRANCH=$(git symbolic-ref --quiet --short HEAD 2>/dev/null || git branch --show-current || git rev-parse --abbrev-ref HEAD 2>/dev/null)
fi
if [ -z "$REMOTE_BRANCH" ] || [ "$REMOTE_BRANCH" = "HEAD" ]; then
  echo "Error: Could not determine current branch (detached HEAD?). Please specify a branch name."
  exit 1
fi

# Gather context for the branch
echo "Gathering context for Codex Plus branch: $REMOTE_BRANCH"

# Check for an open PR on this branch
PR_INFO=""
if command -v gh >/dev/null 2>&1; then
  PR_INFO=$(gh pr list --head "$REMOTE_BRANCH" --state open --json number,title,url 2>/dev/null | jq -r '.[] | "PR #\(.number): \(.title)"' 2>/dev/null || echo "")
fi

# Check for scratchpad file
SCRATCHPAD_INFO=""
SCRATCHPAD_FILE="roadmap/scratchpad_${REMOTE_BRANCH}.md"
if [ -f "$SCRATCHPAD_FILE" ]; then
  SCRATCHPAD_INFO=$(head -n 10 "$SCRATCHPAD_FILE" 2>/dev/null | grep -E "(Goal:|Task:|Current:|Status:)" | head -n 3 | tr '\n' ' ' || echo "")
fi

# Get recent commit messages from the current branch
DEFAULT_BRANCH="main"
RECENT_COMMITS=$(git log --oneline -3 origin/"$DEFAULT_BRANCH".."$REMOTE_BRANCH" 2>/dev/null | sed 's/^/  /' || echo "")

# Check for TODO file
TODO_INFO=""
TODO_FILE="TODO_${REMOTE_BRANCH}.md"
if [ -f "$TODO_FILE" ]; then
  TODO_INFO=$(head -n 5 "$TODO_FILE" 2>/dev/null | tr '\n' ' ' || echo "")
fi

# Build comprehensive context message
BRANCH_MESSAGE="Resume work on Codex Plus branch: $REMOTE_BRANCH"

if [ -n "$PR_INFO" ]; then
  BRANCH_MESSAGE="$BRANCH_MESSAGE. Active $PR_INFO"
fi

if [ -n "$SCRATCHPAD_INFO" ]; then
  BRANCH_MESSAGE="$BRANCH_MESSAGE. Context: $SCRATCHPAD_INFO"
fi

if [ -n "$TODO_INFO" ]; then
  BRANCH_MESSAGE="$BRANCH_MESSAGE. TODO: $TODO_INFO"
fi

if [ -n "$RECENT_COMMITS" ]; then
  BRANCH_MESSAGE="$BRANCH_MESSAGE. Recent commits:$'\n'$RECENT_COMMITS"
fi

# Add final instruction
BRANCH_MESSAGE="$BRANCH_MESSAGE$'\n\n'Please review conversation history and continue working on the Codex Plus proxy development."

# Scheduling logic
CURRENT_SECONDS=$(date +%s)

# Cross-platform compatible date handling
if [[ "$OSTYPE" == "darwin"* ]] || [[ "$OSTYPE" == "freebsd"* ]]; then
  # macOS/BSD date syntax
  TARGET_SECONDS=$(date -j -f "%H:%M" "$SCHEDULE_TIME" "+%s" 2>/dev/null)
  if [ $? -ne 0 ]; then
    echo "Error: Invalid time format for macOS/BSD date command"
    exit 1
  fi
else
  # GNU/Linux date syntax
  TARGET_SECONDS=$(date -d "$SCHEDULE_TIME" +%s 2>/dev/null)
  if [ $? -ne 0 ]; then
    echo "Error: Invalid time format for GNU/Linux date command"
    exit 1
  fi
fi

# If target time is in the past (same day), schedule for tomorrow
if [ $TARGET_SECONDS -le $CURRENT_SECONDS ]; then
  if [[ "$OSTYPE" == "darwin"* ]] || [[ "$OSTYPE" == "freebsd"* ]]; then
    TARGET_SECONDS=$(date -v+1d -j -f "%H:%M" "$SCHEDULE_TIME" "+%s")
  else
    TARGET_SECONDS=$(date -d "tomorrow $SCHEDULE_TIME" +%s)
  fi
fi

WAIT_SECONDS=$((TARGET_SECONDS - CURRENT_SECONDS))

echo "Scheduling Claude conversation for $SCHEDULE_TIME"
echo "Waiting $WAIT_SECONDS seconds..."

# Wait until the scheduled time
sleep $WAIT_SECONDS

# Launch Claude
echo "Starting Claude with Codex Plus context..."

# Set environment to use Codex Plus proxy
export OPENAI_BASE_URL=http://localhost:10000

# Launch Claude with appropriate flags
if [ "$USE_CONTINUE" = true ]; then
  claude --continue "$BRANCH_MESSAGE"
else
  claude "$BRANCH_MESSAGE"
fi