# 02 Hook Integration Test

## Objective
Test that the hook system is properly loaded and executing hooks correctly.

## Prerequisites
- Proxy server is running (from test 01)
- `.codexplus/settings.json` and `.claude/settings.json` exist
- Hook scripts are executable

## Test Steps

### 1. Verify Hook System Loading

```bash
# Check if hooks are loaded in the logs
grep -i "loaded.*hook" proxy.log | tail -10

# Check for settings hooks loading
grep -i "settings hooks" proxy.log | tail -5
```

**Expected Result**:
- Log entries showing "Loaded X hooks"
- Log entries showing "Loaded settings hooks for events: [...]"
- No hook loading errors

### 2. Test Python Hooks (.py files with YAML frontmatter)

```bash
# Create a simple test hook
mkdir -p .codexplus/hooks/

cat > .codexplus/hooks/test_hook.py << 'EOF'
---
name: test_hook
type: pre-input
priority: 50
enabled: true
description: Simple test hook for validation
---

import logging
from codex_plus.hooks import Hook

logger = logging.getLogger(__name__)

class TestHook(Hook):
    """Simple test hook for validation"""

    async def pre_input(self, request, body):
        logger.info(f"TestHook: Processing request to {request.url.path}")
        # Add a marker to show hook executed
        if 'messages' in body and body['messages']:
            body['messages'][0]['content'] = f"[TEST_HOOK_MARKER] {body['messages'][0]['content']}"
        return body
EOF

chmod +x .codexplus/hooks/test_hook.py
```

### 3. Restart Proxy to Load New Hook

```bash
# Restart proxy to load new hook
./proxy.sh restart

# Wait a moment for startup
sleep 3

# Check if new hook was loaded
grep -i "test_hook" proxy.log | tail -3
```

**Expected Result**:
- Log entry showing "Loaded hook: test_hook from .codexplus/hooks"
- No errors during hook loading

### 4. Test Settings-Based Hooks

```bash
# Test that settings hooks are configured
python3 -c "
import json
from pathlib import Path

# Check .codexplus/settings.json
codex_settings = Path('.codexplus/settings.json')
if codex_settings.exists():
    cfg = json.loads(codex_settings.read_text())
    print('Codex settings hooks:', list(cfg.get('hooks', {}).keys()))

# Check .claude/settings.json
claude_settings = Path('.claude/settings.json')
if claude_settings.exists():
    cfg = json.loads(claude_settings.read_text())
    print('Claude settings hooks:', list(cfg.get('hooks', {}).keys()))
"
```

**Expected Result**:
- List of configured hook events (UserPromptSubmit, PreToolUse, PostToolUse, etc.)
- Both .codexplus and .claude settings should be shown

### 5. Test Status Line Hook

```bash
# Trigger status line generation manually
python3 -c "
import sys
sys.path.append('src')
from codex_plus.hooks import hook_system
import asyncio

async def test_status_line():
    status = await hook_system.run_status_line()
    if status:
        print('Status line:', status)
    else:
        print('Status line: None')

asyncio.run(test_status_line())
"
```

**Expected Result**:
- Status line showing current git branch, sync status, repo name
- Format like: `[Dir: codex_plus | Local: hooks-restore (ahead 1) | Remote: origin/main | PR: none]`

### 6. Test Hook Event Execution

```bash
# Create a test hook script
cat > .codexplus/hooks/test_notification.py << 'EOF'
#!/usr/bin/env python3
import json
import sys

# Read JSON input
data = json.load(sys.stdin)
print(f"Notification hook received: {data.get('hook_event_name')}", file=sys.stderr)

# Return success
sys.exit(0)
EOF

chmod +x .codexplus/hooks/test_notification.py

# Test the hook manually
echo '{"hook_event_name": "Notification", "message": "test"}' | python3 .codexplus/hooks/test_notification.py
```

**Expected Result**:
- Message printed to stderr: "Notification hook received: Notification"
- Script exits with code 0

### 7. Test Hook System Error Handling

```bash
# Create a failing hook to test error handling
cat > .codexplus/hooks/failing_hook.py << 'EOF'
---
name: failing_hook
type: pre-input
priority: 99
enabled: true
---

from codex_plus.hooks import Hook

class FailingHook(Hook):
    async def pre_input(self, request, body):
        raise Exception("Test failure")
        return body
EOF

# Restart to load failing hook
./proxy.sh restart
sleep 3

# Check error handling in logs
grep -i "error.*failing_hook" proxy.log | tail -3
```

**Expected Result**:
- Error logged about failing_hook
- Other hooks should still continue to work
- Server should remain running

## Success Criteria Checklist

- [ ] Hook system loads without errors
- [ ] Python hooks (.py files) are loaded correctly
- [ ] Settings-based hooks are loaded from JSON files
- [ ] Status line generation works
- [ ] Test hooks execute and modify requests
- [ ] Hook error handling works (failures don't crash server)
- [ ] Both .codexplus and .claude hook directories are scanned
- [ ] Hook precedence works (.codexplus overrides .claude)

## Cleanup

```bash
# Remove test hooks
rm -f .codexplus/hooks/test_hook.py
rm -f .codexplus/hooks/test_notification.py
rm -f .codexplus/hooks/failing_hook.py

# Restart proxy to clear test hooks
./proxy.sh restart
```

## Troubleshooting

**If hooks aren't loading**:
- Check file permissions: `ls -la .codexplus/hooks/ .claude/hooks/`
- Verify YAML frontmatter syntax in .py files
- Check JSON syntax in settings.json files

**If Python hooks fail**:
- Check that files inherit from Hook class correctly
- Verify import path: `from codex_plus.hooks import Hook`
- Check PYTHONPATH includes src directory

**If settings hooks fail**:
- Validate JSON syntax: `python3 -m json.tool .codexplus/settings.json`
- Check script permissions: `ls -la .codexplus/hooks/ .claude/hooks/`
- Verify command paths in settings are correct