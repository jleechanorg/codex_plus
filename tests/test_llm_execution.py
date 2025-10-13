#!/usr/bin/env python3
"""
Test script for LLM execution middleware
Tests whether instructing the LLM to execute commands works better than expanding them
"""
import pytest
import json
import copy
from types import SimpleNamespace
from codex_plus.llm_execution_middleware import LLMExecutionMiddleware


class TestLLMExecutionMiddleware:
    """Test suite for LLM execution middleware with proper assertions"""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance for testing"""
        return LLMExecutionMiddleware("https://api.openai.com")

    def test_slash_command_detection(self, middleware):
        """Test that slash commands are properly detected and parsed"""
        test_cases = [
            ("/test auth.py", [("test", "auth.py")]),
            ("/search TODO", [("search", "TODO")]),
            ("/git status", [("git", "status")]),
            ("/explain /refactor code", [("explain", ""), ("refactor", "code")]),
            ("Run /test and then /lint", [("test", "and then"), ("lint", "")]),
        ]

        for text, expected in test_cases:
            detected = middleware.detect_slash_commands(text)
            assert detected == expected, f"Failed to detect commands in '{text}'. Expected {expected}, got {detected}"

    def test_execution_instruction_generation(self, middleware):
        """Test that execution instructions are generated correctly"""
        commands = [("test", "auth.py")]
        instruction = middleware.create_execution_instruction(commands)

        # Verify instruction contains key elements
        assert "slash command interpreter" in instruction.lower()
        assert "execution rules" in instruction.lower()
        assert "/test:" in instruction
        assert "auth.py" in instruction
        assert len(instruction) > 100, "Instruction should be substantial"

    def test_codex_format_request_modification(self, middleware):
        """Test request modification for Codex format"""
        codex_request = {
            "input": [{
                "type": "message",
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": "/test auth.py"
                }]
            }]
        }

        original = copy.deepcopy(codex_request)
        modified = middleware.inject_execution_behavior(codex_request)

        # Verify original request structure is preserved
        assert "input" in modified
        assert len(modified["input"]) == len(original["input"])

        # Verify modification occurred (content should be different)
        original_text = original["input"][0]["content"][0]["text"]
        modified_text = modified["input"][0]["content"][0]["text"]
        assert modified_text != original_text
        assert "[SYSTEM:" in modified_text

    def test_standard_format_request_modification(self, middleware):
        """Test request modification for standard messages format"""
        standard_request = {
            "messages": [
                {"role": "user", "content": "/search TODO in the codebase"}
            ]
        }

        original_count = len(standard_request["messages"])
        modified = middleware.inject_execution_behavior(copy.deepcopy(standard_request))

        # Verify system message was injected
        assert "messages" in modified
        assert len(modified["messages"]) == original_count + 1

        # Verify system message is first
        system_msg = modified["messages"][0]
        assert system_msg["role"] == "system"
        assert "slash command interpreter" in system_msg["content"].lower()

        # Verify original user message is preserved
        user_msg = modified["messages"][1]
        assert user_msg["role"] == "user"
        assert user_msg["content"] == "/search TODO in the codebase"

    def test_no_slash_commands_no_modification(self, middleware):
        """Test that requests without slash commands are not modified"""
        regular_request = {
            "messages": [
                {"role": "user", "content": "Hello, how are you?"}
            ]
        }

        original = copy.deepcopy(regular_request)
        modified = middleware.inject_execution_behavior(copy.deepcopy(regular_request))

        # Should be identical
        assert modified == original

    def test_empty_request_handling(self, middleware):
        """Test handling of empty or malformed requests"""
        empty_requests = [
            {},
            {"messages": []},
            {"input": []},
        ]

        for request in empty_requests:
            try:
                result = middleware.inject_execution_behavior(copy.deepcopy(request) if request else {})
                # Should not crash and should return the original request
                assert result == (request or {})
            except Exception as e:
                pytest.fail(f"Should handle empty request gracefully, got: {e}")

    def test_instruction_contains_execution_context(self, middleware):
        """Test that generated instructions contain proper execution context"""
        commands = [("help", ""), ("status", "project")]
        instruction = middleware.create_execution_instruction(commands)

        # Check for execution-specific keywords
        required_phrases = [
            "execution rules",
            "run step-by-step",
            "show actual output",
            "begin execution now"
        ]

        instruction_lower = instruction.lower()
        for phrase in required_phrases:
            assert phrase in instruction_lower, f"Instruction missing required phrase: '{phrase}'"

    def test_status_line_only_applies_to_latest_user_command(self, middleware):
        """Slash command detection should focus on the latest user message even with status line injection."""

        middleware.current_request = SimpleNamespace(
            state=SimpleNamespace(
                status_line="[Dir: repo | Local: branch | Remote: origin/branch | PR: none]"
            )
        )

        request_body = {
            "messages": [
                {"role": "system", "content": "system context"},
                {"role": "user", "content": "/fixpr"},
                {"role": "assistant", "content": "ack"},
                {"role": "user", "content": "/redgreen"},
            ]
        }

        modified = middleware.inject_execution_behavior(copy.deepcopy(request_body))

        system_msg = modified["messages"][0]
        assert system_msg["role"] == "system"
        assert "/redgreen" in system_msg["content"]
        assert "/fixpr" not in system_msg["content"]

        user_messages = [msg for msg in modified["messages"] if msg.get("role") == "user"]
        assert len(user_messages) == 2
        assert user_messages[0]["content"] == "/fixpr"
        assert user_messages[1]["content"].startswith("Display this status line first:")
        assert "/redgreen" in user_messages[1]["content"]


if __name__ == "__main__":
    # Allow direct execution for debugging
    pytest.main([__file__, "-v"])
