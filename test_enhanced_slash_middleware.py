#!/usr/bin/env python3
"""
Focused tests for EnhancedSlashCommandMiddleware
"""
import json
import pytest

from enhanced_slash_middleware import create_enhanced_slash_command_middleware


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


def test_process_request_body_updates_content_length_on_change():
    mw = create_enhanced_slash_command_middleware()
    body = make_codex_cli_payload("/copilot-codex analyze PR")
    headers = {"content-type": "application/json", "content-length": str(len(body))}

    new_body, new_headers = mw.process_request_body(body, headers)

    # Body should be modified and Content-Length updated
    assert new_body != body
    assert new_headers.get("content-length") == str(len(new_body))


def test_process_request_body_passthrough_when_no_command():
    mw = create_enhanced_slash_command_middleware()
    body = make_codex_cli_payload("hello world")
    headers = {"content-type": "application/json", "content-length": str(len(body))}

    new_body, new_headers = mw.process_request_body(body, headers)

    # No changes expected
    assert new_body == body
    # Headers remain unchanged
    assert new_headers == headers
