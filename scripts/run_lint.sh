#!/bin/bash
# Comprehensive Python Linting Script for Codex Plus
# Runs Ruff, isort, mypy, and Bandit for complete code quality analysis

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
TARGET_DIR="${1:-src/codex_plus}"
FIX_MODE="${2:-false}"  # Pass 'fix' as second argument to auto-fix issues

echo -e "${BLUE}🔍 Running comprehensive Python linting on: ${TARGET_DIR}${NC}"
echo "=================================================="

# Ensure we're in the project root
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$PROJECT_ROOT"

# Ensure we're in virtual environment
if [[ "${VIRTUAL_ENV:-}" == "" ]] && [[ -f "venv/bin/activate" ]]; then
    echo -e "${YELLOW}⚠️  Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Function to run a linter with proper error handling
run_linter() {
    local tool_name="$1"
    local command="$2"
    local emoji="$3"

    echo -e "\n${BLUE}${emoji} Running ${tool_name}...${NC}"
    echo "Command: $command"

    if eval "$command"; then
        echo -e "${GREEN}✅ ${tool_name}: PASSED${NC}"
        return 0
    else
        echo -e "${RED}❌ ${tool_name}: FAILED${NC}"
        return 1
    fi
}

# Track overall status
overall_status=0

# 1. Ruff - Linting
echo -e "\n${BLUE}📋 STEP 1: Ruff (Linting)${NC}"
if [[ "$FIX_MODE" == "fix" ]]; then
    ruff_cmd="ruff check $TARGET_DIR --fix"
else
    ruff_cmd="ruff check $TARGET_DIR"
fi

if ! run_linter "Ruff Linting" "$ruff_cmd" "📋"; then
    overall_status=1
fi

# Ruff formatting
echo -e "\n${BLUE}🎨 STEP 1b: Ruff (Formatting)${NC}"
if [[ "$FIX_MODE" == "fix" ]]; then
    ruff_format_cmd="ruff format $TARGET_DIR"
else
    ruff_format_cmd="ruff format $TARGET_DIR --diff"
fi

if ! run_linter "Ruff Formatting" "$ruff_format_cmd" "🎨"; then
    overall_status=1
fi

# 2. isort - Import Sorting (if available)
echo -e "\n${BLUE}📚 STEP 2: isort (Import Sorting)${NC}"
if command -v isort >/dev/null 2>&1; then
    if [[ "$FIX_MODE" == "fix" ]]; then
        isort_cmd="isort $TARGET_DIR"
    else
        isort_cmd="isort $TARGET_DIR --check-only --diff"
    fi

    if ! run_linter "isort" "$isort_cmd" "📚"; then
        overall_status=1
    fi
else
    echo -e "${YELLOW}⚠️  isort not available, skipping import sorting${NC}"
fi

# 3. mypy - Static Type Checking (if available)
echo -e "\n${BLUE}🔬 STEP 3: mypy (Type Checking)${NC}"
if command -v mypy >/dev/null 2>&1; then
    mypy_cmd="mypy $TARGET_DIR --ignore-missing-imports"

    if ! run_linter "mypy" "$mypy_cmd" "🔬"; then
        overall_status=1
    fi
else
    echo -e "${YELLOW}⚠️  mypy not available, skipping type checking${NC}"
fi

# 4. Bandit - Security Analysis (if available)
echo -e "\n${BLUE}🛡️  STEP 4: Bandit (Security Scanning)${NC}"
if command -v bandit >/dev/null 2>&1; then
    bandit_cmd="bandit -r $TARGET_DIR -f txt"

    if ! run_linter "Bandit" "$bandit_cmd" "🛡️"; then
        overall_status=1
    fi
else
    echo -e "${YELLOW}⚠️  bandit not available, skipping security analysis${NC}"
fi

# Summary
echo -e "\n=================================================="
if [[ $overall_status -eq 0 ]]; then
    echo -e "${GREEN}🎉 ALL AVAILABLE LINTING CHECKS PASSED!${NC}"
    echo -e "${GREEN}✅ All configured linting tools successful${NC}"
else
    echo -e "${RED}❌ SOME LINTING CHECKS FAILED${NC}"
    echo -e "${YELLOW}💡 Run with 'fix' argument to auto-fix some issues:${NC}"
    echo -e "${YELLOW}   ./scripts/run_lint.sh $TARGET_DIR fix${NC}"
fi

echo -e "\n${BLUE}📊 Linting Summary:${NC}"
echo "  • Target: $TARGET_DIR"
echo "  • Mode: $([ "$FIX_MODE" == "fix" ] && echo "Auto-fix enabled" || echo "Check-only")"
echo "  • Tools: Ruff (lint+format), isort, mypy, Bandit"

exit $overall_status