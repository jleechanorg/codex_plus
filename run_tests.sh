#!/bin/bash
# Centralized test runner for both local development and CI
# Supports: ./run_tests.sh (local) and ./run_tests.sh --ci (GitHub Actions)

set -e  # Exit on any error

# Parse command line arguments
CI_MODE=false
if [[ "$1" == "--ci" ]]; then
    CI_MODE=true
fi

if [ "$CI_MODE" = true ]; then
    echo "🤖 Codex Plus CI Test Runner"
    echo "============================"
    echo "Running in GitHub Actions CI mode..."
else
    echo "🧪 Codex Plus Local Test Runner"
    echo "================================"
    echo "Simulating GitHub CI environment locally..."
fi
echo

# Check if we're in the right directory
if [ ! -f "requirements.txt" ]; then
    echo "❌ Error: requirements.txt not found. Are you in the project root?"
    exit 1
fi

# Check Python version
echo "🐍 Checking Python version..."
python_version=$(python --version 2>&1 | cut -d' ' -f2)
echo "Python version: $python_version"

# Check for Python 3.11+ (like CI)
required_version="3.11"
if python -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)"; then
    echo "✅ Python version is 3.11+"
else
    echo "⚠️  Warning: CI uses Python 3.11, you have $python_version"
fi

echo

# Install system dependencies (Linux simulation)
echo "📦 Checking system dependencies..."
echo "Note: CI installs libcurl4-openssl-dev (curl_cffi dependency)"
if command -v curl >/dev/null 2>&1; then
    echo "✅ curl is available"
else
    echo "⚠️  Warning: curl not found - may affect curl_cffi"
fi

echo

# Check virtual environment
echo "🔍 Checking virtual environment..."
if [ -n "$VIRTUAL_ENV" ]; then
    echo "✅ Virtual environment active: $VIRTUAL_ENV"
else
    echo "⚠️  Warning: No virtual environment detected"
    echo "   Consider running: source venv/bin/activate"
fi

echo

# Install dependencies (only in local mode, CI already installs them)
if [ "$CI_MODE" = false ]; then
    echo "📦 Installing/upgrading Python dependencies..."
    python -m pip install --upgrade pip

    if [ -f requirements.txt ]; then
        echo "Installing requirements.txt..."
        pip install -r requirements.txt
    else
        echo "❌ Error: requirements.txt not found"
        exit 1
    fi

    # Install pytest (like CI)
    echo "Installing pytest..."
    pip install pytest pytest-xdist pytest-timeout
else
    echo "📦 Using CI-installed dependencies..."
fi

echo

# Set environment variables (like CI)
echo "🌍 Setting CI environment variables..."
export NO_NETWORK='1'
echo "✅ NO_NETWORK=1 (simulating CI network restrictions)"

echo

# Run tests
echo "🧪 Running tests..."

if [ "$CI_MODE" = true ]; then
    # CI mode: Use exact same command as GitHub Actions
    echo "Command: pytest -q --tb=short --timeout=60 -m \"not slow and not integration\" -n auto --dist=worksteal --ignore=tests/claude/commands/test_orchestrate_integration.py --maxfail=5"
    echo
    pytest -q --tb=short --timeout=60 -m "not slow and not integration" \
           -n auto --dist=worksteal \
           --ignore=tests/claude/commands/test_orchestrate_integration.py \
           --maxfail=5
else
    # Local mode: More conservative approach
    echo "Command: pytest -q --tb=short --maxfail=3"
    echo "Timeout: 10 minutes (practical timeout)"
    echo

    # Run with practical timeout and better output
    echo "Running fast tests first..."
    pytest tests/claude/hooks/ -q --tb=short

    echo
    echo "Running main test suite..."
    # Use timeout if available (Linux/macOS)
    if command -v timeout >/dev/null 2>&1; then
        # Linux timeout - 10 minutes instead of 15
        timeout 600 pytest -q --tb=short --maxfail=3
    elif command -v gtimeout >/dev/null 2>&1; then
        # macOS timeout (if coreutils installed)
        gtimeout 600 pytest -q --tb=short --maxfail=3
    else
        # No timeout available, run normally with fail-fast
        echo "(No timeout command available, running with fail-fast)"
        pytest -q --tb=short --maxfail=3
    fi
fi

test_exit_code=$?

echo
if [ $test_exit_code -eq 0 ]; then
    echo "✅ All tests passed! 🎉"
    echo "✅ Your code is ready for CI"
else
    echo "❌ Tests failed with exit code: $test_exit_code"
    echo "❌ Fix failing tests before pushing to CI"
    exit $test_exit_code
fi

echo
echo "🏁 Test run complete!"
echo "This simulates the GitHub CI environment from .github/workflows/tests.yml"