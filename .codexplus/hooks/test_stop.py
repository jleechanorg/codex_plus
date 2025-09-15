#!/usr/bin/env python3
"""
Test hook for Stop event
Validates conversation completion and cleanup
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

        # Log Stop event details
        timestamp = datetime.now().isoformat()
        session_id = payload.get("session_id", "unknown")
        transcript_path = payload.get("transcript_path", "")

        print(f"[Stop Hook] Conversation completed in session {session_id} at {timestamp}")
        if transcript_path:
            print(f"[Stop Hook] Transcript saved to: {transcript_path}")

        # Simulate conversation analysis
        conversation_stats = {
            "completion_time": timestamp,
            "session_duration": "estimated",
            "cleanup_performed": True
        }

        print(f"[Stop Hook] Conversation analysis: {json.dumps(conversation_stats, indent=2)}")

        # Return structured feedback
        feedback = {
            "hook_executed": True,
            "hook_type": "Stop",
            "conversation_completed": True,
            "cleanup_performed": True,
            "transcript_available": bool(transcript_path),
            "completion_timestamp": timestamp,
            "conversation_stats": conversation_stats
        }

        print(json.dumps(feedback))

    except Exception as e:
        error_log = {
            "hook_type": "Stop",
            "error": str(e),
            "status": "failed"
        }
        print(f"[Stop Hook Error] {e}")
        print(json.dumps(error_log))

if __name__ == "__main__":
    main()