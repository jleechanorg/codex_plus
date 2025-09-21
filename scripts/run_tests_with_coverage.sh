#!/bin/bash
# Coverage Test Runner Script for Codex Plus
# Runs all test_*.py files with comprehensive coverage analysis
#
# Usage:
#   ./run_tests_with_coverage.sh                   # All tests with coverage (HTML report included)
#   ./run_tests_with_coverage.sh --no-html         # Generate text report only (skip HTML)

# Auto-detect Python interpreter
PYTHON_CMD="python3"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

print_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Get project root
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$PROJECT_ROOT"

# Source directory for Codex Plus
SOURCE_DIR="src/codex_plus"

print_status "Using source directory: $SOURCE_DIR"

# Check if source directory exists
if [ ! -d "$SOURCE_DIR" ]; then
    print_error "Source directory '$SOURCE_DIR' not found. Please run this script from the project root."
    exit 1
fi

# Parse command line arguments
generate_html=true  # Default to generating HTML

for arg in "$@"; do
    case $arg in
        --no-html)
            generate_html=false
            ;;
        *)
            print_warning "Unknown argument: $arg"
            ;;
    esac
done

# Create coverage output directory
PROJECT_NAME="codex_plus"
COVERAGE_DIR="/tmp/${PROJECT_NAME}/coverage"
mkdir -p "$COVERAGE_DIR"

print_status "🧪 Running tests with coverage analysis for Codex Plus..."
print_status "HTML output will be saved to: $COVERAGE_DIR"

# Try to activate virtual environment
if [[ -f "venv/bin/activate" ]]; then
    print_status "Activating virtual environment..."
    source venv/bin/activate
else
    print_warning "No virtual environment found. Using system Python."
fi

# Check if coverage is installed
print_status "Checking coverage installation..."

if ! python -c "import coverage" 2>/dev/null; then
    print_warning "Coverage tool not found. Installing..."
    if ! pip install coverage; then
        print_error "Failed to install coverage"
        exit 1
    fi
    print_success "Coverage installed successfully"
else
    print_status "Coverage already installed"
fi

# Find all test files
test_files=()
while IFS= read -r -d '' file; do
    test_files+=("$file")
done < <(find ./tests -name "test_*.py" -type f \
    ! -path "./venv/*" \
    ! -path "./node_modules/*" \
    -print0 2>/dev/null)

# Check if any test files exist
if [ ${#test_files[@]} -eq 0 ]; then
    print_warning "No test files found in ./tests/"
    exit 0
fi

print_status "Found ${#test_files[@]} test file(s) for coverage analysis"
echo

# Start timing
start_time=$(date +%s)
print_status "⏱️  Starting coverage analysis at $(date)"

# Clear any previous coverage data
coverage erase

# Initialize counters
total_tests=0
passed_tests=0
failed_tests=0
failed_test_files=()

# Check if pytest is available and use it, otherwise run individual test files
if command -v pytest >/dev/null 2>&1 && [ -f "pytest.ini" ]; then
    print_status "Using pytest for test execution"

    if coverage run --source=src/codex_plus -m pytest tests/ -v; then
        print_success "All tests passed with pytest"
        passed_tests=${#test_files[@]}
        total_tests=${#test_files[@]}
    else
        print_error "Some tests failed with pytest"
        failed_tests=${#test_files[@]}
        total_tests=${#test_files[@]}
    fi
else
    print_status "Using individual test file execution"

    # Run tests sequentially with coverage
    for test_file in "${test_files[@]}"; do
        if [ -f "$test_file" ]; then
            total_tests=$((total_tests + 1))
            echo -n "[$total_tests/${#test_files[@]}] Running: $test_file ... "

            if coverage run --append --source=src/codex_plus "$test_file" >/dev/null 2>&1; then
                passed_tests=$((passed_tests + 1))
                print_success "PASSED"
            else
                failed_tests=$((failed_tests + 1))
                failed_test_files+=("$test_file")
                print_error "FAILED"
            fi
        fi
    done
fi

echo

# Generate coverage reports
print_status "📊 Generating coverage reports..."

# Text report (always generated)
print_status "Generating text coverage report..."
coverage report --show-missing > "$COVERAGE_DIR/coverage.txt" 2>/dev/null
coverage report --show-missing

# HTML report (optional)
if [ "$generate_html" = true ]; then
    print_status "Generating HTML coverage report..."
    if coverage html -d "$COVERAGE_DIR" >/dev/null 2>&1; then
        print_success "HTML report generated: $COVERAGE_DIR/index.html"

        # Try to open in browser on macOS
        if [[ "$OSTYPE" == "darwin"* ]]; then
            print_status "Opening coverage report in browser..."
            open "$COVERAGE_DIR/index.html" 2>/dev/null || true
        fi
    else
        print_error "Failed to generate HTML report"
    fi
fi

# Calculate execution time
end_time=$(date +%s)
execution_time=$((end_time - start_time))

# Summary
echo
print_status "📋 Test Execution Summary"
echo "   Total tests run: $total_tests"
echo "   Passed: $passed_tests"
echo "   Failed: $failed_tests"
echo "   Execution time: ${execution_time}s"

if [ $failed_tests -gt 0 ]; then
    echo
    print_error "Failed test files:"
    for failed_file in "${failed_test_files[@]}"; do
        echo "   • $failed_file"
    done
fi

# Get coverage percentage
coverage_percent=$(coverage report --format=total 2>/dev/null || echo "unknown")
if [ "$coverage_percent" != "unknown" ]; then
    echo "   Coverage: ${coverage_percent}%"

    # Color-code coverage percentage
    if [ "$coverage_percent" -ge 80 ]; then
        print_success "Good coverage: ${coverage_percent}%"
    elif [ "$coverage_percent" -ge 60 ]; then
        print_warning "Moderate coverage: ${coverage_percent}%"
    else
        print_error "Low coverage: ${coverage_percent}%"
    fi
fi

print_status "⏱️  Coverage analysis completed at $(date)"

# Exit with appropriate code
if [ $failed_tests -eq 0 ]; then
    exit 0
else
    exit 1
fi