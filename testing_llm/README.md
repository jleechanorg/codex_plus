# LLM-Executable Test Suite for Codex Plus Hook System

This directory contains a comprehensive test suite designed to be executed by an LLM (Large Language Model) using `codex exec --yolo` or similar execution environments. Each test file validates different aspects of the Codex Plus proxy and hook system.

## Overview

The Codex Plus proxy is a FastAPI-based HTTP proxy that intercepts Codex CLI requests and adds power-user features including:
- **Hook System**: Pre-input, post-output, and event-driven hooks
- **Status Line**: Git-integrated status information
- **Settings Integration**: JSON-based hook configuration
- **Request Processing**: Streaming and non-streaming request handling

## Test Files

### 01. Basic Proxy Test (`01_basic_proxy_test.md`)
**Objective**: Verify proxy server startup and basic functionality
- Server health checks
- Request forwarding validation
- Log verification
- Git status line generation

**Prerequisites**: Python environment, dependencies installed

### 02. Hook Integration Test (`02_hook_integration.md`)
**Objective**: Test hook system loading and execution
- Python hook loading (.py files with YAML frontmatter)
- Settings-based hooks from JSON configuration
- Hook error handling and recovery
- Hook precedence and execution order

**Prerequisites**: Test 01 completed successfully

### 03. Streaming Test (`03_streaming_test.md`)
**Objective**: Validate streaming response handling
- Streaming request processing
- Hook integration with streaming
- Large request handling
- Concurrent streaming requests

**Prerequisites**: Tests 01-02 completed

### 04. Error Handling Test (`04_error_handling.md`)
**Objective**: Test system resilience and error recovery
- Upstream connection errors
- Malformed request handling
- Hook execution failures
- Resource exhaustion scenarios

**Prerequisites**: Tests 01-03 completed

### 05. Performance Test (`05_performance_test.md`)
**Objective**: Validate system performance under load
- Baseline performance metrics
- Concurrent request handling
- Memory usage monitoring
- Hook performance impact

**Prerequisites**: Tests 01-04 completed

### 06. End-to-End Test (`06_end_to_end.md`)
**Objective**: Comprehensive workflow testing
- Complete hook lifecycle
- Real-world usage scenarios
- System integration validation
- Final health verification

**Prerequisites**: All previous tests completed

## Usage Instructions

### Running Individual Tests

Each test file can be executed independently:

```bash
# Navigate to the test directory
cd /Users/jleechan/projects_other/codex_plus/test_llm/

# Execute a specific test (using LLM)
codex exec --yolo "Follow the step-by-step instructions in 01_basic_proxy_test.md"
```

### Running Complete Test Suite

Execute tests in sequence for comprehensive validation:

```bash
# Run all tests in order
for test_file in 01_basic_proxy_test.md 02_hook_integration.md 03_streaming_test.md 04_error_handling.md 05_performance_test.md 06_end_to_end.md; do
    echo "Executing $test_file..."
    codex exec --yolo "Follow all instructions in $test_file and report results"
    echo "Completed $test_file"
done
```

## Test Execution Requirements

### System Prerequisites
- **Python 3.8+** with virtual environment
- **Git repository** (for git-related functionality)
- **FastAPI and dependencies** installed (`pip install -r requirements.txt`)
- **curl_cffi** library (critical for proxy functionality)
- **Port 3000 available** for proxy server

### Environment Setup
```bash
# Navigate to project root
cd /Users/jleechan/projects_other/codex_plus

# Activate virtual environment
source venv/bin/activate  # or .\venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Verify proxy script is executable
chmod +x ./proxy.sh
```

### Execution Context
- Tests assume execution from project root directory
- Git repository should be in working state
- No other services should be using port 3000
- Sufficient disk space for logs and temporary files

## Key Features Being Tested

### Hook System Architecture
- **Python Hooks**: Files with YAML frontmatter inheriting from Hook class
- **Settings Hooks**: JSON-configured command hooks
- **Event Types**: UserPromptSubmit, PreToolUse, PostToolUse, Stop, SessionStart, SessionEnd
- **Hook Precedence**: .codexplus overrides .claude directories

### Request Processing Pipeline
1. **Incoming Request** → FastAPI route handler
2. **Pre-Input Hooks** → Request modification and validation
3. **Upstream Forwarding** → ChatGPT backend via curl_cffi
4. **Post-Output Hooks** → Response processing
5. **Status Line Generation** → Git status integration
6. **Cleanup** → Resource management and logging

### Configuration Hierarchy
1. **`.codexplus/settings.json`** (highest precedence)
2. **`.claude/settings.json`** (fallback)
3. **Environment variables** (CLAUDE_PROJECT_DIR, etc.)
4. **Default values** (hardcoded fallbacks)

## Expected Test Outcomes

### Success Indicators
- ✅ All health checks pass
- ✅ Hooks load and execute without errors
- ✅ Request/response processing works correctly
- ✅ Git integration functions properly
- ✅ Error conditions handled gracefully
- ✅ Performance meets baseline requirements
- ✅ System remains stable under load

### Common Failure Modes
- ❌ **curl_cffi missing**: Proxy cannot bypass Cloudflare
- ❌ **Port conflicts**: Another service using port 3000
- ❌ **Git issues**: Not in git repo or git commands failing
- ❌ **Permission errors**: Hook scripts not executable
- ❌ **JSON syntax**: Invalid settings.json configuration
- ❌ **Python path**: Import errors for hook modules

## Troubleshooting Guide

### Proxy Won't Start
```bash
# Check port availability
lsof -i :3000

# Verify dependencies
pip list | grep -E "(fastapi|curl_cffi|uvicorn)"

# Check logs
tail -f proxy.log
```

### Hooks Not Loading
```bash
# Check file permissions
ls -la .codexplus/hooks/ .claude/hooks/

# Verify YAML syntax
python3 -c "import yaml; yaml.safe_load(open('.codexplus/hooks/test_hook.py').read().split('---')[1])"

# Check JSON syntax
python3 -m json.tool .codexplus/settings.json
```

### Git Integration Issues
```bash
# Verify git repository
git status

# Check git commands
git rev-parse --show-toplevel
git branch --show-current
```

### Performance Issues
```bash
# Monitor resources
top -p $(cat proxy.pid)

# Check log levels
grep -c "DEBUG\|INFO\|ERROR" proxy.log

# Profile hook execution
grep "hook.*time\|hook.*processing" proxy.log
```

## Reporting Test Results

When executing tests via LLM, provide structured reporting:

### Test Result Format
```markdown
## Test: [Test Name]
**Status**: ✅ PASS / ❌ FAIL / ⚠️ PARTIAL

### Results Summary
- Total Steps: X/Y completed
- Critical Issues: [List any critical failures]
- Warnings: [List any warnings or minor issues]
- Performance Metrics: [If applicable]

### Evidence
- Log excerpts showing key functionality
- Command outputs demonstrating success
- Error messages (if any) with context

### Recommendations
- [Any suggested improvements or follow-up actions]
```

## Maintenance

### Updating Tests
- Keep tests synchronized with hook system changes
- Update expected results when new features are added
- Maintain compatibility with both `.codexplus` and `.claude` configurations

### Test Environment Cleanup
```bash
# Remove test artifacts
rm -f .codexplus/hooks/test_*.py
rm -f .codexplus/hooks/e2e_*.py
rm -f .codexplus/hooks/recovery_*.py

# Restore original settings (keep backups)
cp .codexplus/settings.json.backup .codexplus/settings.json

# Clean proxy state
./proxy.sh restart
```

## Integration with CI/CD

These tests can be integrated into automated testing pipelines:

```bash
# Example CI script
#!/bin/bash
set -e

echo "Starting Codex Plus Hook System Tests..."

# Setup
source venv/bin/activate
./proxy.sh enable

# Execute tests
for test in test_llm/*.md; do
    echo "Executing $(basename $test)..."
    # LLM execution logic here
    # codex exec --yolo "$(cat $test)"
done

# Cleanup
./proxy.sh disable

echo "All tests completed successfully"
```

---

**Note**: These tests are designed for execution by LLMs that can interpret markdown instructions and execute shell commands. Human testers can also follow the step-by-step instructions manually.