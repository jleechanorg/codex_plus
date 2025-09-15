#!/usr/bin/env python3
"""
Test hook for Notification event
Validates notification handling and user interaction
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

        # Log Notification event details
        timestamp = datetime.now().isoformat()
        session_id = payload.get("session_id", "unknown")
        message = payload.get("message", "")

        print(f"[Notification Hook] Notification received in session {session_id} at {timestamp}")
        print(f"[Notification Hook] Message: {message}")

        # Process different types of notifications
        notification_type = "general"
        if "permission" in message.lower():
            notification_type = "permission_request"
        elif "idle" in message.lower():
            notification_type = "idle_status"
        elif "waiting" in message.lower():
            notification_type = "waiting_status"

        print(f"[Notification Hook] Classified as: {notification_type}")

        # Return structured feedback
        feedback = {
            "hook_executed": True,
            "hook_type": "Notification",
            "notification_processed": True,
            "notification_type": notification_type,
            "message_length": len(message),
            "processing_timestamp": timestamp
        }

        print(json.dumps(feedback))

    except Exception as e:
        error_log = {
            "hook_type": "Notification",
            "error": str(e),
            "status": "failed"
        }
        print(f"[Notification Hook Error] {e}")
        print(json.dumps(error_log))

if __name__ == "__main__":
    main()