#!/usr/bin/env python3
import json, sys
print(json.dumps({
  "hookSpecificOutput": {"hookEventName":"UserPromptSubmit", "additionalContext": "CTX-123"}
}))
sys.exit(0)
