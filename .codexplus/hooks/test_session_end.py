#!/usr/bin/env python3
"""
Test hook for SessionEnd event
Validates session cleanup and final processing
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

        # Log SessionEnd event details
        timestamp = datetime.now().isoformat()
        session_id = payload.get("session_id", "unknown")
        reason = payload.get("reason", "unknown")
        cwd = payload.get("cwd", "")

        print(f"[SessionEnd Hook] Session {session_id} ending at {timestamp}")
        print(f"[SessionEnd Hook] End reason: {reason}")
        if cwd:
            print(f"[SessionEnd Hook] Working directory: {cwd}")

        # Analyze session end reason
        end_analysis = {
            "end_reason": reason,
            "is_normal_exit": reason == "exit",
            "is_forced_termination": reason in ["kill", "interrupt"],
            "is_error_exit": reason == "error"
        }

        # Simulate cleanup operations
        cleanup_operations = {
            "temp_files_cleaned": True,
            "resources_released": True,
            "logs_finalized": True,
            "session_archived": True
        }

        print(f"[SessionEnd Hook] End analysis: {json.dumps(end_analysis, indent=2)}")
        print(f"[SessionEnd Hook] Cleanup performed: {json.dumps(cleanup_operations, indent=2)}")

        # Return structured feedback
        feedback = {
            "hook_executed": True,
            "hook_type": "SessionEnd",
            "session_ended": True,
            "cleanup_completed": True,
            "end_analysis": end_analysis,
            "cleanup_operations": cleanup_operations,
            "termination_timestamp": timestamp
        }

        print(json.dumps(feedback))

    except Exception as e:
        error_log = {
            "hook_type": "SessionEnd",
            "error": str(e),
            "status": "failed"
        }
        print(f"[SessionEnd Hook Error] {e}")
        print(json.dumps(error_log))

if __name__ == "__main__":
    main()