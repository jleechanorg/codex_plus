#!/usr/bin/env python3
"""
Adapted tests for LLMExecutionMiddleware (replacing EnhancedSlashCommandMiddleware)
"""
import json

from codex_plus.llm_execution_middleware import LLMExecutionMiddleware, create_llm_execution_middleware


def make_codex_cli_payload(text: str) -> bytes:
    payload = {
        "model": "gpt-5",
        "instructions": "Test",
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": text}
                ],
            }
        ],
        "tools": [],
        "tool_choice": "auto",
        "parallel_tool_calls": True,
        "reasoning": False,
        "store": False,
        "stream": False,
    }
    return json.dumps(payload).encode("utf-8")


def test_injects_execution_instruction_when_slash_command_present():
    mw: LLMExecutionMiddleware = create_llm_execution_middleware("https://chatgpt.com/backend-api/codex")
    body = make_codex_cli_payload("/copilot analyze PR")
    data = json.loads(body)
    modified = mw.inject_execution_behavior(data)
    # System instruction should be injected (in messages or input text)
    if "messages" in modified:
        assert modified["messages"][0]["role"] == "system"
        assert "You are a slash command interpreter" in modified["messages"][0]["content"]
    else:
        # Codex input format: instruction prepended to input_text
        txt = modified["input"][0]["content"][0]["text"]
        assert txt.startswith("[SYSTEM:")


def test_no_injection_when_no_slash_command():
    mw: LLMExecutionMiddleware = create_llm_execution_middleware("https://chatgpt.com/backend-api/codex")
    body = make_codex_cli_payload("hello world")
    data = json.loads(body)
    modified = mw.inject_execution_behavior(data)
    # Should be identical when no slash command present
    assert modified == data


def test_multiple_slash_commands_detection():
    """Test the fix for multi-command parsing bug"""
    mw: LLMExecutionMiddleware = create_llm_execution_middleware("https://chatgpt.com/backend-api/codex")

    # Test cases that were failing before the fix
    test_cases = [
        ("/cmd1 arg /cmd2 arg", [("cmd1", "arg"), ("cmd2", "arg")]),
        ("/copilot /fixpr", [("copilot", ""), ("fixpr", "")]),
        ("/echo hello /test-args arg1 arg2", [("echo", "hello"), ("test-args", "arg1 arg2")]),
        ("/cmd1 some args /cmd2 /cmd3 final", [("cmd1", "some args"), ("cmd2", ""), ("cmd3", "final")])
    ]

    for text, expected in test_cases:
        commands = mw.detect_slash_commands(text)
        assert commands == expected, f"Failed for input '{text}': expected {expected}, got {commands}"
