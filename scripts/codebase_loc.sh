#!/bin/bash
# Simple lines of code counter for Codex Plus
# Counts Python, JavaScript, and shell script files

find . -type f \( -name "*.py" -o -name "*.js" -o -name "*.sh" \) \
    ! -path "./venv/*" \
    ! -path "./node_modules/*" \
    ! -path "./.git/*" \
    -exec wc -l {} + | awk '{total += $1} END {print total}'