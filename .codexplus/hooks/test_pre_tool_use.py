#!/usr/bin/env python3
"""
Test hook for PreToolUse event
Validates tool execution gating and parameter validation
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

        # Log PreToolUse event details
        timestamp = datetime.now().isoformat()
        session_id = payload.get("session_id", "unknown")
        tool_name = payload.get("tool_name", "unknown")
        tool_args = payload.get("tool_args", {})

        print(f"[PreToolUse Hook] Tool {tool_name} about to execute in session {session_id} at {timestamp}")
        print(f"[PreToolUse Hook] Tool args: {json.dumps(tool_args, indent=2)}")

        # Simulate tool validation (allow all tools for testing)
        allow_execution = True

        # Special handling for dangerous tools (just logging, not blocking)
        if tool_name in ["Bash", "Write", "Edit"]:
            print(f"[PreToolUse Hook] Monitoring potentially impactful tool: {tool_name}")

        # Return structured feedback
        feedback = {
            "hook_executed": True,
            "hook_type": "PreToolUse",
            "tool_validated": True,
            "tool_name": tool_name,
            "allow_execution": allow_execution,
            "validation_timestamp": timestamp
        }

        # Exit code 0 = allow, exit code 2 = block (we're allowing all for testing)
        print(json.dumps(feedback))
        sys.exit(0)

    except Exception as e:
        error_log = {
            "hook_type": "PreToolUse",
            "error": str(e),
            "status": "failed"
        }
        print(f"[PreToolUse Hook Error] {e}")
        print(json.dumps(error_log))
        sys.exit(1)

if __name__ == "__main__":
    main()