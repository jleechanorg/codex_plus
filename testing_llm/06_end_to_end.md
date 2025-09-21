# 06 End-to-End Test

## Objective
Comprehensive end-to-end test of the complete hook system workflow including real-world usage scenarios.

## Prerequisites
- All previous tests completed successfully
- Proxy server running and healthy
- Git repository is in working state
- Development environment fully set up

## Test Steps

### 1. Complete Hook Lifecycle Test

```bash
# Create a comprehensive test hook that exercises all hook types
cat > .codexplus/hooks/e2e_test_hook.py << 'EOF'
---
name: e2e_test_hook
type: pre-input
priority: 30
enabled: true
description: Comprehensive end-to-end test hook
---

import asyncio
import logging
import json
from datetime import datetime
from codex_plus.hooks import Hook

logger = logging.getLogger(__name__)

class E2ETestHook(Hook):
    """End-to-end test hook that exercises all major functionality"""

    def __init__(self, name, config):
        super().__init__(name, config)
        self.request_count = 0

    async def pre_input(self, request, body):
        self.request_count += 1
        logger.info(f"E2E Hook: Processing request #{self.request_count}")

        # Test request modification
        if 'messages' in body and body['messages']:
            timestamp = datetime.now().strftime("%H:%M:%S")
            body['messages'][0]['content'] = f"[E2E-{timestamp}] {body['messages'][0]['content']}"
            logger.info("E2E Hook: Modified request content")

        # Test async processing
        await asyncio.sleep(0.01)  # Simulate async work

        # Test context injection
        if 'input' in body:
            for item in body['input']:
                if item.get('type') == 'message':
                    for content in item.get('content', []):
                        if content.get('type') == 'input_text':
                            original_text = content.get('text', '')
                            content['text'] = f"[E2E Context] {original_text}"
                            logger.info("E2E Hook: Injected context")
                            break
                    break

        return body

    async def post_output(self, response):
        logger.info(f"E2E Hook: Processing response type: {type(response).__name__}")
        # Don't modify streaming responses, just log
        return response

    async def pre_tool_use(self, request, tool_name, tool_args):
        logger.info(f"E2E Hook: Pre-tool use for {tool_name}")
        return tool_args

    async def stop(self, request, conversation_data):
        logger.info(f"E2E Hook: Conversation stopped, processed {self.request_count} requests")
        return conversation_data
EOF

chmod +x .codexplus/hooks/e2e_test_hook.py
```

### 2. Settings-Based Hook Integration Test

```bash
# Create comprehensive settings hooks for all events
python3 -c "
import json
from pathlib import Path

# Create comprehensive settings configuration
settings = {
    'hooks': {
        'UserPromptSubmit': [{
            'matcher': '*',
            'hooks': [{
                'type': 'command',
                'command': 'echo \"{\\\"event\\\": \\\"UserPromptSubmit\\\", \\\"timestamp\\\": \\\"\$(date)\\\"}\"',
                'timeout': 3
            }]
        }],
        'PreToolUse': [{
            'matcher': '*',
            'hooks': [{
                'type': 'command',
                'command': 'echo \"{\\\"event\\\": \\\"PreToolUse\\\", \\\"tool\\\": \\\"TOOL_NAME\\\"}\"',
                'timeout': 3
            }]
        }],
        'PostToolUse': [{
            'matcher': '*',
            'hooks': [{
                'type': 'command',
                'command': 'echo \"{\\\"event\\\": \\\"PostToolUse\\\", \\\"status\\\": \\\"completed\\\"}\"',
                'timeout': 3
            }]
        }],
        'Stop': [{
            'matcher': '*',
            'hooks': [{
                'type': 'command',
                'command': 'echo \"{\\\"event\\\": \\\"Stop\\\", \\\"final\\\": true}\"',
                'timeout': 3
            }]
        }]
    },
    'statusLine': {
        'type': 'command',
        'command': 'bash -c \"echo [E2E-Test: \$(git rev-parse --abbrev-ref HEAD) | \$(date +%H:%M:%S)]\"',
        'timeout': 5
    }
}

# Write to .codexplus/settings.json
settings_path = Path('.codexplus/settings.json')
settings_path.write_text(json.dumps(settings, indent=2))
print('Created comprehensive E2E settings configuration')
"

# Restart proxy to load all hooks and settings
./proxy.sh restart
sleep 5

# Verify all hooks loaded
grep -i "loaded.*hook\|settings hooks" proxy.log | tail -10
```

**Expected Result**:
- E2E test hook loaded successfully
- Settings hooks loaded for all events
- No loading errors in logs

### 3. Full Request Processing Pipeline Test

```bash
# Test complete request processing pipeline
echo "Testing complete request processing pipeline..."

# Make a request that exercises the full pipeline
curl -X POST http://localhost:10000/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dummy_token" \
  -d '{
    "input": [{
      "type": "message",
      "content": [{
        "type": "input_text",
        "text": "This is a comprehensive end-to-end test message"
      }]
    }],
    "stream": false
  }' -v

# Check that all hook stages executed
echo "Checking hook execution stages..."

# Check pre-input hook execution
grep -i "e2e hook.*processing request" proxy.log | tail -3

# Check settings hook execution
grep -i "UserPromptSubmit\|PreToolUse\|PostToolUse" proxy.log | tail -5

# Check context injection
grep -i "e2e hook.*injected context\|e2e hook.*modified" proxy.log | tail -3
```

**Expected Result**:
- All hook stages execute in correct order
- Request content is modified by hooks
- Settings-based hooks trigger appropriately
- No errors in pipeline processing

### 4. Status Line Integration Test

```bash
# Test status line integration with request processing
echo "Testing status line integration..."

# Trigger status line generation
python3 -c "
import sys
sys.path.append('src')
from codex_plus.hooks import hook_system
import asyncio

async def test_status_line_e2e():
    print('Testing custom E2E status line...')
    status = await hook_system.run_status_line()
    if status:
        print(f'Status Line: {status}')
        # Should show custom E2E format
        if 'E2E-Test:' in status:
            print('✓ Custom E2E status line working')
        else:
            print('⚠ Status line not using E2E format')
    else:
        print('✗ No status line generated')

asyncio.run(test_status_line_e2e())
"

# Check status line mode
python3 -c "
import sys
sys.path.append('src')
from codex_plus.hooks import hook_system

mode = hook_system.status_line_mode()
print(f'Status line mode: {mode}')
"

# Verify status line appears during request processing
curl -X POST http://localhost:10000/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dummy_token" \
  -d '{"input": [{"type": "message", "content": [{"type": "input_text", "text": "status line test"}]}]}' \
  -s > /dev/null

# Check for status line in logs
grep -i "git status line\|status line" proxy.log | tail -3
```

**Expected Result**:
- Custom E2E status line format works
- Status line appears during request processing
- Mode configuration is respected

### 5. Hook Error Recovery Test

```bash
# Test complete error recovery workflow
echo "Testing hook error recovery..."

# Create a partially failing hook setup
cat > .codexplus/hooks/recovery_test.py << 'EOF'
---
name: recovery_test
type: pre-input
priority: 1
enabled: true
---

from codex_plus.hooks import Hook
import random

class RecoveryTestHook(Hook):
    async def pre_input(self, request, body):
        # Fail randomly to test recovery
        if random.random() < 0.3:  # 30% failure rate
            raise Exception("Random test failure for recovery testing")

        # Add recovery marker if successful
        if 'messages' in body and body['messages']:
            body['messages'][0]['content'] = f"[RECOVERY-OK] {body['messages'][0]['content']}"

        return body
EOF

# Restart to load recovery test hook
./proxy.sh restart
sleep 3

# Make multiple requests to test recovery behavior
echo "Making multiple requests to test recovery..."
for i in {1..10}; do
    curl -X POST http://localhost:10000/responses \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer dummy_token" \
      -d "{\"input\": [{\"type\": \"message\", \"content\": [{\"type\": \"input_text\", \"text\": \"Recovery test $i\"}]}]}" \
      -s > /dev/null
    sleep 0.5
done

# Check recovery behavior
echo "Checking recovery behavior..."
recovery_successes=$(grep -c "RECOVERY-OK" proxy.log || echo "0")
recovery_failures=$(grep -c "error.*recovery_test" proxy.log || echo "0")

echo "Recovery test results:"
echo "  Successful recoveries: $recovery_successes"
echo "  Handled failures: $recovery_failures"

# Verify server is still responsive
curl -X POST http://localhost:10000/health
```

**Expected Result**:
- Some requests succeed with RECOVERY-OK marker
- Some requests fail with logged errors
- Server continues operating despite failures
- Other hooks continue to work

### 6. Real-World Workflow Simulation

```bash
# Simulate real development workflow
echo "Simulating real development workflow..."

# Simulate starting a coding session
python3 -c "
import sys
sys.path.append('src')
from codex_plus.hooks import settings_session_start
import asyncio

async def simulate_session_start():
    print('Simulating session start...')
    await settings_session_start(None, 'manual-test')
    print('Session start hooks completed')

asyncio.run(simulate_session_start())
"

# Simulate various development requests
dev_requests=(
    "How do I implement a REST API in Python?"
    "Show me how to write unit tests for this function"
    "Help me debug this error message"
    "Generate documentation for my class"
    "Refactor this code to improve performance"
)

for request in "${dev_requests[@]}"; do
    echo "Processing: $request"
    curl -X POST http://localhost:10000/responses \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer dummy_token" \
      -d "{\"input\": [{\"type\": \"message\", \"content\": [{\"type\": \"input_text\", \"text\": \"$request\"}]}]}" \
      -s > /dev/null
    sleep 1
done

# Simulate session end
python3 -c "
import sys
sys.path.append('src')
from codex_plus.hooks import settings_session_end
import asyncio

async def simulate_session_end():
    print('Simulating session end...')
    await settings_session_end(None, 'manual-test')
    print('Session end hooks completed')

asyncio.run(simulate_session_end())
"

# Check workflow processing
echo "Checking workflow processing..."
workflow_requests=$(grep -c "E2E Hook.*Processing request" proxy.log || echo "0")
echo "Processed development requests: $workflow_requests"
```

**Expected Result**:
- Session start/end hooks execute correctly
- All development requests processed through hooks
- Hook system handles varied request types
- No degradation in functionality over time

### 7. Integration with Git and Project Context

```bash
# Test git integration aspects
echo "Testing git and project context integration..."

# Check current git state
git_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
git_status=$(git status --porcelain 2>/dev/null | wc -l || echo "0")
echo "Current git branch: $git_branch"
echo "Modified files: $git_status"

# Test project context in hooks
python3 -c "
import os
import subprocess
print('Testing project context...')

# Test environment variables
claude_project_dir = os.environ.get('CLAUDE_PROJECT_DIR')
print(f'CLAUDE_PROJECT_DIR: {claude_project_dir}')

# Test git root detection
try:
    git_root = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip()
    print(f'Git root: {git_root}')
except:
    print('Git root: Not in git repository')

# Test hook system project awareness
import sys
sys.path.append('src')
from codex_plus.hooks import hook_system
print(f'Hook system session ID: {hook_system.session_id}')
"

# Make request and check project context usage
curl -X POST http://localhost:10000/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dummy_token" \
  -d '{"input": [{"type": "message", "content": [{"type": "input_text", "text": "Test project context integration"}]}]}' \
  -s > /dev/null

# Check for project context in logs
grep -i "project\|claude_project_dir" proxy.log | tail -3
```

**Expected Result**:
- Git integration works correctly
- Project context is available to hooks
- Environment variables set appropriately
- Session ID tracking works

### 8. Complete System Health Verification

```bash
# Comprehensive system health check after E2E testing
echo "Performing comprehensive system health check..."

# Check proxy health
echo "1. Proxy Health:"
curl -s http://localhost:10000/health | python3 -m json.tool

# Check process status
echo -e "\n2. Process Status:"
./proxy.sh status

# Check resource usage
echo -e "\n3. Resource Usage:"
PID=$(cat proxy.pid 2>/dev/null || pgrep -f "uvicorn.*main:app")
if [ -n "$PID" ]; then
    ps -o pid,rss,vsz,pcpu,time -p "$PID"
else
    echo "Process not found"
fi

# Check log health (no critical errors)
echo -e "\n4. Log Health:"
error_count=$(grep -ic "error\|exception\|traceback" proxy.log | tail -1)
warning_count=$(grep -ic "warning\|warn" proxy.log | tail -1)
info_count=$(grep -ic "info" proxy.log | tail -1)

echo "Log summary:"
echo "  Errors: $error_count"
echo "  Warnings: $warning_count"
echo "  Info messages: $info_count"

# Check hook system health
echo -e "\n5. Hook System Health:"
python3 -c "
import sys
sys.path.append('src')
from codex_plus.hooks import hook_system

print(f'Loaded hooks: {len(hook_system.hooks)}')
print(f'Settings hooks events: {len(hook_system.settings_hooks)}')
print(f'Status line configured: {bool(hook_system.status_line_cfg)}')

# List hook names
hook_names = [h.name for h in hook_system.hooks]
print(f'Hook names: {hook_names}')
"

# Final functionality test
echo -e "\n6. Final Functionality Test:"
final_response=$(curl -s -X POST http://localhost:10000/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dummy_token" \
  -d '{"input": [{"type": "message", "content": [{"type": "input_text", "text": "Final E2E health check"}]}]}')

if [ $? -eq 0 ]; then
    echo "✓ Final request processed successfully"
else
    echo "✗ Final request failed"
fi
```

**Expected Result**:
- All health checks pass
- Resource usage within reasonable limits
- Hook system fully operational
- No critical errors in logs
- Final functionality test succeeds

## Success Criteria Checklist

- [ ] Complete hook lifecycle works (pre-input → post-output)
- [ ] All hook events execute properly (UserPromptSubmit, PreToolUse, PostToolUse, Stop)
- [ ] Custom status line generation works
- [ ] Error recovery and resilience demonstrated
- [ ] Real-world workflow simulation successful
- [ ] Git and project context integration working
- [ ] System remains healthy after comprehensive testing
- [ ] No memory leaks or resource issues
- [ ] All hook types function correctly
- [ ] Settings-based and Python-based hooks both work

## Cleanup

```bash
# Remove all test hooks
rm -f .codexplus/hooks/e2e_test_hook.py
rm -f .codexplus/hooks/recovery_test.py

# Restore original settings
python3 -c "
import json
from pathlib import Path

# Restore minimal settings
settings = {
    'hooks': {
        'PostToolUse': [{
            'matcher': 'SlashCommand/.*',
            'hooks': [{
                'type': 'command',
                'command': 'python3 \$CLAUDE_PROJECT_DIR/.codexplus/hooks/posttool_marker.py',
                'timeout': 2
            }]
        }]
    }
}

settings_path = Path('.codexplus/settings.json')
settings_path.write_text(json.dumps(settings, indent=2))
print('Restored original settings')
"

# Final restart and verification
./proxy.sh restart
sleep 3

echo "E2E cleanup completed. Final verification:"
curl -s http://localhost:10000/health | python3 -m json.tool
./proxy.sh status
```

**Expected Result**:
- Clean removal of test hooks
- Original settings restored
- Proxy restarts successfully
- System returns to clean state

## Troubleshooting

**If E2E tests fail**:
- Check each component individually using previous tests
- Review proxy logs for detailed error messages
- Verify git repository state
- Check system resources and permissions

**If hook integration fails**:
- Verify hook file syntax and permissions
- Check JSON settings syntax
- Review import paths and Python environment
- Test hooks individually before integration

**If performance degrades during E2E**:
- Monitor system resources continuously
- Check for memory leaks in custom hooks
- Review log levels and output volume
- Consider hook complexity and async usage

**System health issues**:
- Restart proxy server: `./proxy.sh restart`
- Check disk space and memory
- Review process limits: `ulimit -a`
- Verify network connectivity to upstream services