#!/usr/bin/env python3
"""
Test the full LLM execution flow
Tests slash command processing through the middleware
"""
import pytest
import json
import asyncio
from unittest.mock import Mock, AsyncMock
from codex_plus.llm_execution_middleware import LLMExecutionMiddleware


class TestLLMExecutionFlow:
    """Test suite for LLM execution flow with proper assertions"""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance for testing"""
        return LLMExecutionMiddleware("https://chatgpt.com/backend-api/codex")

    def test_slash_command_detection(self, middleware):
        """Test that slash commands are properly detected"""
        test_cases = [
            ("/hello Claude", True),
            ("/test auth.py", True),
            ("/search TODO", True),
            ("regular message", False),
            ("", False),
        ]

        for command, expected in test_cases:
            if command is None:
                continue  # Skip None case as detect_slash_commands expects string

            result = middleware.detect_slash_commands(command)
            if expected:
                assert result, f"Expected slash command detection for: {command}"
                assert len(result) > 0, "Should detect at least one command"
            else:
                assert not result or len(result) == 0, f"Should not detect slash command for: {command}"

    def test_command_parsing(self, middleware):
        """Test that slash commands are parsed correctly"""
        test_cases = [
            ("/hello Claude", ("hello", "Claude")),
            ("/test auth.py", ("test", "auth.py")),
            ("/search TODO", ("search", "TODO")),
            ("/explain this code:\ndef foo(x):\n    return x * 2", ("explain", "this code:\ndef foo(x):\n    return x * 2"))
        ]

        for command, expected in test_cases:
            result = middleware.detect_slash_commands(command)

            assert result, f"Should detect slash command: {command}"
            command_name, args = result[0]
            expected_name, expected_args = expected

            assert command_name == expected_name, f"Command name mismatch for {command}"
            assert args == expected_args, f"Arguments mismatch for {command}"

    def test_middleware_initialization(self, middleware):
        """Test that middleware initializes correctly"""
        assert middleware.url_getter() == "https://chatgpt.com/backend-api/codex"
        assert hasattr(middleware, 'detect_slash_commands')
        assert hasattr(middleware, 'process_request')

    @pytest.mark.asyncio
    async def test_empty_payload_handling(self, middleware):
        """Test handling of empty or malformed payloads"""
        empty_texts = [
            "",
            "   ",  # whitespace only
            "no slash commands here"
        ]

        for text in empty_texts:
            try:
                result = middleware.detect_slash_commands(text)
                assert not result or len(result) == 0, "Empty text should not detect commands"
            except Exception as e:
                pytest.fail(f"Middleware should handle empty text gracefully, got: {e}")

    def test_special_characters_in_commands(self, middleware):
        """Test handling of special characters in slash commands"""
        test_cases = [
            "/search @TODO",
            "/test file-name.py",
            "/explain code with\nnewlines",
            "/command with spaces and symbols !@#$%"
        ]

        for command in test_cases:
            try:
                result = middleware.detect_slash_commands(command)
                assert result, f"Should detect command with special chars: {command}"
            except Exception as e:
                pytest.fail(f"Should handle special characters gracefully, got: {e}")


if __name__ == "__main__":
    # Allow direct execution for debugging
    pytest.main([__file__, "-v"])