#!/bin/bash
# Simple Lines of Code Counter for Codex Plus
# Focuses on production vs test code breakdown

echo "📊 Lines of Code Count - Codex Plus"
echo "===================================="

# Function to count lines with proper exclusions
count_files() {
    local ext="$1"
    local test_filter="$2"

    if [[ "$test_filter" == "test" ]]; then
        find . -name "*.$ext" \( -path "*/test*" -o -name "*test*.$ext" \) \
            | grep -v node_modules | grep -v .git | grep -v venv | grep -v __pycache__ \
            | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}' || echo 0
    else
        find . -name "*.$ext" ! -path "*/test*" ! -name "*test*.$ext" \
            | grep -v node_modules | grep -v .git | grep -v venv | grep -v __pycache__ \
            | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}' || echo 0
    fi
}

# Overall language totals
echo "🐍 Python (.py):"
py_prod=$(count_files "py" "prod")
py_test=$(count_files "py" "test")
echo "  Production: ${py_prod:-0} lines"
echo "  Test:       ${py_test:-0} lines"

echo "📜 Shell Scripts (.sh):"
sh_prod=$(count_files "sh" "prod")
sh_test=$(count_files "sh" "test")
echo "  Production: ${sh_prod:-0} lines"
echo "  Test:       ${sh_test:-0} lines"

echo "🌟 JavaScript (.js):"
js_prod=$(count_files "js" "prod")
js_test=$(count_files "js" "test")
echo "  Production: ${js_prod:-0} lines"
echo "  Test:       ${js_test:-0} lines"

# Summary
echo ""
echo "📋 Summary:"
total_prod=$((${py_prod:-0} + ${sh_prod:-0} + ${js_prod:-0}))
total_test=$((${py_test:-0} + ${sh_test:-0} + ${js_test:-0}))
total_all=$((total_prod + total_test))

echo "  Production Code: $total_prod lines"
echo "  Test Code:       $total_test lines"
echo "  TOTAL CODEBASE:  $total_all lines"

if [[ $total_all -gt 0 ]]; then
    test_percentage=$(awk -v test="$total_test" -v all="$total_all" 'BEGIN {if (all > 0) printf "%.1f", test * 100 / all; else print "0"}')
    echo "  Test Coverage:   ${test_percentage}%"
fi

echo ""
echo "🎯 Production Code by Component:"
echo "==============================="

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

    js_count=$(find . -name "*.js" -path "*$pattern*" ! -path "*/test*" ! -name "*test*.js" \
        | grep -v node_modules | grep -v .git | grep -v venv \
        | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}' || echo 0)

    total=$((py_count + sh_count + js_count))

    if [[ $total -gt 0 ]]; then
        printf "  %-20s: %6d lines (py:%5d sh:%4d js:%4d)\n" "$name" "$total" "$py_count" "$sh_count" "$js_count"
    fi
}

# Major functional areas for Codex Plus
count_functional_area "src/codex_plus" "Core Proxy Engine"
count_functional_area "scripts" "Development Tools"
count_functional_area ".codexplus" "Command Extensions"
count_functional_area "infrastructure" "Deployment"

echo ""
echo "ℹ️  Exclusions:"
echo "  • Virtual environment (venv/)"
echo "  • Node modules, git files"
echo "  • Temporary and cache files"