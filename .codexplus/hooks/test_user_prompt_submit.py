#!/usr/bin/env python3
"""
Test hook for UserPromptSubmit event
Validates prompt processing and context injection
"""
from shared_utils import HookRunner
from typing import Dict, Any


class UserPromptSubmitHook(HookRunner):
    """Hook for UserPromptSubmit events with context injection"""

    def __init__(self):
        super().__init__("UserPromptSubmit")

    def process_hook(self, payload: Dict[str, Any], common_fields: Dict[str, str]) -> Dict[str, Any]:
        """Process UserPromptSubmit event and inject context"""
        session_id = common_fields["session_id"]
        timestamp = common_fields["timestamp"]
        prompt = payload.get("prompt", "")[:100]  # First 100 chars

        self.log_message(f"Prompt submitted in session {session_id} at {timestamp}")
        self.log_message(f"Prompt preview: {prompt}...")

        # Simulate context injection
        additional_context = f"[TEST CONTEXT] Added by UserPromptSubmit hook at {timestamp}"

        return {
            "hook_executed": True,
            "hook_type": "UserPromptSubmit",
            "prompt_processed": True,
            "additionalContext": additional_context,
            "context_injected": True
        }


def main():
    hook = UserPromptSubmitHook()
    hook.run()


if __name__ == "__main__":
    main()