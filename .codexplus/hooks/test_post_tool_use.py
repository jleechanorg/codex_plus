#!/usr/bin/env python3
"""
Test hook for PostToolUse event
Validates tool execution results and provides feedback
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

        # Log PostToolUse event details
        timestamp = datetime.now().isoformat()
        session_id = payload.get("session_id", "unknown")
        tool_name = payload.get("tool_name", "unknown")
        tool_args = payload.get("tool_args", {})
        tool_response = payload.get("tool_response", {})

        print(f"[PostToolUse Hook] Tool {tool_name} completed in session {session_id} at {timestamp}")
        print(f"[PostToolUse Hook] Tool response status: {tool_response.get('status_code', 'unknown')}")

        # Analyze tool execution results
        execution_successful = tool_response.get("status_code", 0) in [200, 201, 204]

        # Generate feedback for Claude
        feedback_message = ""
        if tool_name == "Bash":
            feedback_message = "Command executed successfully. Consider checking output for any warnings."
        elif tool_name in ["Write", "Edit"]:
            feedback_message = "File modification completed. Remember to test changes."
        elif tool_name == "Read":
            feedback_message = "File read operation completed successfully."
        else:
            feedback_message = f"Tool {tool_name} executed successfully."

        # Return structured feedback
        feedback = {
            "hook_executed": True,
            "hook_type": "PostToolUse",
            "tool_name": tool_name,
            "execution_successful": execution_successful,
            "feedback": feedback_message,
            "analysis_timestamp": timestamp
        }

        print(json.dumps(feedback))

    except Exception as e:
        error_log = {
            "hook_type": "PostToolUse",
            "error": str(e),
            "status": "failed"
        }
        print(f"[PostToolUse Hook Error] {e}")
        print(json.dumps(error_log))

if __name__ == "__main__":
    main()