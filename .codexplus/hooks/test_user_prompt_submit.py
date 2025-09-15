#!/usr/bin/env python3
"""
Test hook for UserPromptSubmit event
Validates prompt processing and context injection
"""
import json
import sys
from datetime import datetime

def main():
    try:
        # Read hook payload from stdin
        input_data = sys.stdin.read().strip()
        if not input_data:
            return

        payload = json.loads(input_data)

        # Log UserPromptSubmit event details
        timestamp = datetime.now().isoformat()
        session_id = payload.get("session_id", "unknown")
        prompt = payload.get("prompt", "")[:100]  # First 100 chars

        print(f"[UserPromptSubmit Hook] Prompt submitted in session {session_id} at {timestamp}")
        print(f"[UserPromptSubmit Hook] Prompt preview: {prompt}...")

        # Simulate context injection
        additional_context = f"[TEST CONTEXT] Added by UserPromptSubmit hook at {timestamp}"

        # Return structured feedback with context
        feedback = {
            "hook_executed": True,
            "hook_type": "UserPromptSubmit",
            "prompt_processed": True,
            "additionalContext": additional_context,
            "context_injected": True
        }

        print(json.dumps(feedback))

    except Exception as e:
        error_log = {
            "hook_type": "UserPromptSubmit",
            "error": str(e),
            "status": "failed"
        }
        print(f"[UserPromptSubmit Hook Error] {e}")
        print(json.dumps(error_log))

if __name__ == "__main__":
    main()