#!/usr/bin/env python3
"""
Hook Metadata:
name: add-context
type: UserPromptSubmit
priority: 50
enabled: true
"""
import json, sys
print(json.dumps({
  "hookSpecificOutput": {"hookEventName":"UserPromptSubmit", "additionalContext": "CTX-123"}
}))
sys.exit(0)
