#!/usr/bin/env python3
"""
Test hook for PreCompact event
Validates compact operation preparation and context preservation
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

        # Log PreCompact event details
        timestamp = datetime.now().isoformat()
        session_id = payload.get("session_id", "unknown")
        trigger = payload.get("trigger", "unknown")
        custom_instructions = payload.get("custom_instructions", "")

        print(f"[PreCompact Hook] Compact operation triggered in session {session_id} at {timestamp}")
        print(f"[PreCompact Hook] Trigger type: {trigger}")
        if custom_instructions:
            print(f"[PreCompact Hook] Custom instructions: {custom_instructions[:100]}...")

        # Analyze compact trigger
        trigger_analysis = {
            "trigger_type": trigger,
            "is_manual": trigger == "manual",
            "is_automatic": trigger == "auto",
            "has_custom_instructions": bool(custom_instructions)
        }

        print(f"[PreCompact Hook] Trigger analysis: {json.dumps(trigger_analysis, indent=2)}")

        # Simulate context preservation preparation
        context_preservation = {
            "important_context_identified": True,
            "preservation_strategy": "automatic" if trigger == "auto" else "custom",
            "preparation_complete": True
        }

        # Return structured feedback
        feedback = {
            "hook_executed": True,
            "hook_type": "PreCompact",
            "compact_prepared": True,
            "trigger_analyzed": True,
            "trigger_analysis": trigger_analysis,
            "context_preservation": context_preservation,
            "preparation_timestamp": timestamp
        }

        print(json.dumps(feedback))

    except Exception as e:
        error_log = {
            "hook_type": "PreCompact",
            "error": str(e),
            "status": "failed"
        }
        print(f"[PreCompact Hook Error] {e}")
        print(json.dumps(error_log))

if __name__ == "__main__":
    main()