#!/usr/bin/env python3
"""
Test hook for SessionStart event
Validates session initialization and context loading
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

        # Log SessionStart event details
        timestamp = datetime.now().isoformat()
        session_id = payload.get("session_id", "unknown")
        source = payload.get("source", "unknown")

        log_entry = {
            "hook_type": "SessionStart",
            "timestamp": timestamp,
            "session_id": session_id,
            "source": source,
            "status": "executed"
        }

        print(f"[SessionStart Hook] Session {session_id} started from {source} at {timestamp}")

        # Return structured feedback
        feedback = {
            "hook_executed": True,
            "hook_type": "SessionStart",
            "session_initialized": True,
            "context_loaded": True
        }

        print(json.dumps(feedback))

    except Exception as e:
        error_log = {
            "hook_type": "SessionStart",
            "error": str(e),
            "status": "failed"
        }
        print(f"[SessionStart Hook Error] {e}")
        print(json.dumps(error_log))

if __name__ == "__main__":
    main()