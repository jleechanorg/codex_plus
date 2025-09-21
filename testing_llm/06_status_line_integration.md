# Status Line Integration Test

This test validates that the Codex Plus proxy correctly injects git status information into the conversation output, making it visible to users during `codex exec` sessions.

## Test Objective

Verify that the status line appears in the actual conversation output when using `codex exec --yolo` with the proxy enabled.

## Environment Setup

```bash
# Ensure proxy is running on port 10001 (updated port)
cd /Users/jleechan/projects_other/codex_plus
source venv/bin/activate
PYTHONPATH=src uvicorn src.codex_plus.main:app --host 127.0.0.1 --port 10001 --log-level info &

# Verify proxy health
curl -s http://localhost:10001/health
# Expected: {"status":"healthy"}

# Configure environment for testing
export OPENAI_BASE_URL=http://localhost:10001
```

## Test Execution

### Test 1: Basic Status Line Injection

```bash
# Execute a simple command and verify status line appears
OPENAI_BASE_URL=http://localhost:10001 codex exec --yolo "echo 'status line test'"
```

**Expected Output:**
- Status line should appear at the beginning of Claude's response
- Format: `[Dir: codex_plus | Local: docs/comprehensive-update (synced) | Remote: origin/docs/comprehensive-update | PR: none]`
- Should be followed by the command execution and results

### Test 2: Status Line Format Validation

The status line should contain:
- **Dir**: Repository name (e.g., `codex_plus`)
- **Local**: Current branch with sync status (e.g., `docs/comprehensive-update (synced)`)
- **Remote**: Remote tracking branch (e.g., `origin/docs/comprehensive-update`)
- **PR**: Pull request status (e.g., `none` or PR number)

### Test 3: Multiple Requests Consistency

```bash
# Run multiple commands to ensure status line appears consistently
OPENAI_BASE_URL=http://localhost:10001 codex exec --yolo "ls -la"
OPENAI_BASE_URL=http://localhost:10001 codex exec --yolo "pwd"
OPENAI_BASE_URL=http://localhost:10001 codex exec --yolo "git status"
```

**Expected:**
- Status line should appear in every response
- Status information should be current and accurate

## Implementation Details

### Request-Level Injection Approach

The status line is injected at the request level rather than response level:

1. **Status Line Generation**: `HookMiddleware.get_status_line()` generates git status
2. **Request Modification**: Status line injected as system instruction in `inject_execution_behavior()`
3. **Claude Integration**: Claude receives instruction to include status line in response
4. **Conversation Output**: Status line appears as natural conversation content

### Key Components

- **Status Line Middleware**: `src/codex_plus/status_line_middleware.py`
- **LLM Execution Middleware**: `src/codex_plus/llm_execution_middleware.py`
- **Hook System**: `src/codex_plus/hooks.py`

## Success Criteria

✅ **Status line appears in conversation output**
- Status line is visible in `codex exec` terminal output
- Appears at the beginning of Claude's response
- Format matches expected git status format

✅ **Accurate git information**
- Repository name matches current directory
- Branch information is current
- Sync status reflects actual git state

✅ **Consistent injection**
- Status line appears on every request
- No duplication or missing status lines
- Performance impact is minimal

## Troubleshooting

### Status Line Not Appearing

1. **Check proxy health**: `curl http://localhost:10001/health`
2. **Verify environment variable**: `echo $OPENAI_BASE_URL`
3. **Check proxy logs**: Look for "📌 Will inject status line:" messages
4. **Git repository validation**: Ensure running in valid git repository

### Incorrect Status Information

1. **Git status check**: Run `git status` manually to compare
2. **Branch validation**: Verify current branch with `git branch --show-current`
3. **Remote tracking**: Check remote with `git remote -v`

## Test Results

**Test Date**: 2025-09-20
**Proxy Version**: M4 Enhanced Features
**Test Status**: ✅ PASSED

**Sample Output:**
```
[2025-09-21T03:42:50] codex

[Dir: codex_plus | Local: docs/comprehensive-update (synced) | Remote: origin/docs/comprehensive-update | PR: none]Command ran: `echo 'testing new status line injection'` → `testing new status line injection`
```

**Key Achievement:**
- Status line successfully appears in conversation output
- Request-level injection approach works correctly
- User can see git status context during conversations
- Integration with Codex CLI is seamless and non-intrusive