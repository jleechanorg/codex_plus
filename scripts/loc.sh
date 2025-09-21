#!/bin/bash
# Complete Code Statistics Script for Codex Plus
# Provides comprehensive analysis including git statistics and lines of code breakdown

# Check if help is requested
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    echo "Usage: $0 [date]"
    echo "  date: Optional date in YYYY-MM-DD format (defaults to 30 days ago)"
    echo "Examples:"
    echo "  ./loc.sh                    # Last 30 days"
    echo "  ./loc.sh 2025-06-01         # Since June 1st, 2025"
    exit 0
fi

# Parse date argument
SINCE_DATE="$1"

echo "🚀 Generating Complete Code Statistics for Codex Plus..."
echo "========================================================================"
echo

# Note: This script can be extended with git statistics analysis
# For now, focusing on lines of code breakdown

echo "📊 Lines of Code Breakdown (src/codex_plus directory)"
echo "========================================================================"

# Source directory for Codex Plus
SOURCE_DIR="src/codex_plus"

# Function to count lines in files
count_lines() {
    local pattern="$1"
    local files=$(find "$SOURCE_DIR" -type f -name "$pattern" ! -path "*/__pycache__/*" ! -path "*/.pytest_cache/*" 2>/dev/null)
    if [ -z "$files" ]; then
        echo "0"
    else
        echo "$files" | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}'
    fi
}

# Function to count test vs non-test lines
count_test_vs_nontest() {
    local ext="$1"
    local test_lines=$(find "$SOURCE_DIR" -type f -name "*.$ext" ! -path "*/__pycache__/*" ! -path "*/.pytest_cache/*" 2>/dev/null | grep -i test | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
    local nontest_lines=$(find "$SOURCE_DIR" -type f -name "*.$ext" ! -path "*/__pycache__/*" ! -path "*/.pytest_cache/*" 2>/dev/null | grep -v -i test | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')

    # Handle empty results
    test_lines=${test_lines:-0}
    nontest_lines=${nontest_lines:-0}

    echo "$test_lines $nontest_lines"
}

# File extensions to track
FILE_TYPES=("py" "js" "sh")

# Initialize totals
total_test_lines=0
total_nontest_lines=0
total_all_lines=0

# Calculate lines for each file type
echo "📈 Breakdown by File Type:"
echo "=========================="

for ext in "${FILE_TYPES[@]}"; do
    read test_count nontest_count <<< $(count_test_vs_nontest "$ext")
    total_lines=$((test_count + nontest_count))

    total_test_lines=$((total_test_lines + test_count))
    total_nontest_lines=$((total_nontest_lines + nontest_count))
    total_all_lines=$((total_all_lines + total_lines))

    if [[ $total_lines -gt 0 ]]; then
        printf "%-12s: %6d lines (%5d prod + %5d test)\n" "$ext files" "$total_lines" "$nontest_count" "$test_count"
    fi
done

echo ""
echo "📋 Summary:"
echo "==========="
echo "  Production Code: $total_nontest_lines lines"
echo "  Test Code:       $total_test_lines lines"
echo "  TOTAL CODEBASE:  $total_all_lines lines"

if [[ $total_all_lines -gt 0 ]]; then
    test_percentage=$(awk -v test="$total_test_lines" -v all="$total_all_lines" 'BEGIN {if (all > 0) printf "%.1f", test * 100 / all; else print "0"}')
    echo "  Test Ratio:      ${test_percentage}%"
fi

echo ""
echo "🎯 Code by Functionality:"
echo "========================="

# Count major functional areas (production only)
count_functional_area() {
    local pattern="$1"
    local name="$2"

    py_count=$(find . -name "*.py" -path "*$pattern*" ! -path "*/test*" ! -name "*test*.py" \
        | grep -v node_modules | grep -v .git | grep -v venv \
        | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}' || echo 0)

    sh_count=$(find . -name "*.sh" -path "*$pattern*" ! -path "*/test*" ! -name "*test*.sh" \
        | grep -v node_modules | grep -v .git | grep -v venv \
        | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}' || echo 0)

    total=$((py_count + sh_count))

    if [[ $total -gt 0 ]]; then
        printf "  %-20s: %6d lines (py:%5d sh:%4d)\n" "$name" "$total" "$py_count" "$sh_count"
    fi
}

# Major functional areas for Codex Plus
count_functional_area "src/codex_plus" "Core Proxy"
count_functional_area "scripts" "Development Scripts"
count_functional_area ".codexplus" "Extensions"
count_functional_area "tests" "Test Suite"

echo ""
echo "ℹ️  Analysis covers:"
echo "  • Python source files (.py)"
echo "  • Shell scripts (.sh)"
echo "  • Excludes: cache files, dependencies"