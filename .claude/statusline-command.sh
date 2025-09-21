#!/bin/bash
# Claude Code statusline command
# Provides a comprehensive status line with user, host, directory, git info, and context

# Get basic info
user=$(whoami)
host=$(hostname -s)
pwd=$(pwd)

# Get git information if in a git repo
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    # Get current branch
    branch=$(git branch --show-current 2>/dev/null || echo "detached")
    
    # Get git status indicators
    git_status=""
    if [[ -n $(git status --porcelain 2>/dev/null) ]]; then
        git_status="*"  # Uncommitted changes
    fi
    
    # Get sync status with remote
    remote_status=""
    remote=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)
    if [[ -n "$remote" ]]; then
        ahead=$(git rev-list --count "$remote"..HEAD 2>/dev/null || echo "0")
        behind=$(git rev-list --count HEAD.."$remote" 2>/dev/null || echo "0")
        
        if [[ "$ahead" -gt 0 ]] && [[ "$behind" -gt 0 ]]; then
            remote_status=" ↕$ahead/$behind"
        elif [[ "$ahead" -gt 0 ]]; then
            remote_status=" ↑$ahead"
        elif [[ "$behind" -gt 0 ]]; then
            remote_status=" ↓$behind"
        fi
    fi
    
    git_info=" ($branch$git_status$remote_status)"
else
    git_info=""
fi

# Get Claude Code context info from stdin JSON
input=$(cat)
model_name=$(echo "$input" | jq -r '.model.display_name // "Claude"' 2>/dev/null || echo "Claude")
current_dir=$(echo "$input" | jq -r '.workspace.current_dir // ""' 2>/dev/null || echo "")
output_style=$(echo "$input" | jq -r '.output_style.name // ""' 2>/dev/null || echo "")

# Format the statusline with colors
printf "\033[1;32m%s@%s\033[0m:\033[1;34m%s\033[0m%s" "$user" "$host" "$(basename "$pwd")" "$git_info"

# Add model info if available
if [[ "$model_name" != "Claude" ]]; then
    printf " \033[1;33m[%s]\033[0m" "$model_name"
fi

# Add output style if not default
if [[ -n "$output_style" ]] && [[ "$output_style" != "default" ]]; then
    printf " \033[1;35m(%s)\033[0m" "$output_style"
fi

echo