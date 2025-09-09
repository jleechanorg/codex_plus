#!/usr/bin/env python3
import os
import json
from pathlib import Path

import pytest

from enhanced_slash_middleware import create_enhanced_slash_command_middleware
from enhanced_slash_middleware import HybridCommandDef


def test_handles_empty_body_returns_same():
    mw = create_enhanced_slash_command_middleware()
    body = b"not-json"
    headers = {"content-type": "application/json"}
    new_body, new_headers = mw.process_request_body(body, headers)
    assert new_body == body
    assert new_headers == headers


def test_passthrough_when_no_slash_command():
    mw = create_enhanced_slash_command_middleware()
    payload = {"input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]}]}
    body = json.dumps(payload).encode("utf-8")
    headers = {"content-type": "application/json", "content-length": str(len(body))}
    new_body, new_headers = mw.process_request_body(body, headers)
    assert new_body == body
    assert new_headers == headers


def test_markdown_frontmatter_description_and_substitution(tmp_path):
    # Create a command in .codexplus/commands
    cmd_dir = Path(".codexplus/commands")
    cmd_dir.mkdir(parents=True, exist_ok=True)
    cmd_file = cmd_dir / "sample.md"
    cmd_file.write_text(
        """---
description: Sample description
---

Args: $ARGUMENTS; first=$1 second=$2 default=${name:defaultName}
""",
        encoding="utf-8",
    )

    try:
        mw = create_enhanced_slash_command_middleware()
        # Description from frontmatter is registered
        cmd_def = mw.registry.get("sample")
        assert cmd_def is not None
        assert cmd_def.description == "Sample description"

        # Execute slash command and verify substitution
        out = mw._execute_command("/sample foo bar")
        assert out is not None
        assert "Args: foo bar; first=foo second=bar default=defaultName" in out
    finally:
        try:
            cmd_file.unlink(missing_ok=True)
        except Exception:
            pass
        # Clean up empty dirs
        try:
            if cmd_dir.exists() and not any(cmd_dir.iterdir()):
                cmd_dir.rmdir()
                parent = cmd_dir.parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
        except Exception:
            pass


def test_unknown_command_returns_message():
    mw = create_enhanced_slash_command_middleware()
    out = mw._execute_command("/doesnotexist foo")
    assert "Unknown command" in out


def test_builtin_handler_error_handling():
    mw = create_enhanced_slash_command_middleware()
    # Register a builtin that raises
    def boom(_):
        raise RuntimeError("boom")

    mw.registry.register(HybridCommandDef(
        name="boom",
        description="Boom",
        source="builtin",
        handler=boom,
    ))

    out = mw._execute_command("/boom arg1")
    assert "Error executing command /boom" in out or "Error executing command" in out


def test_quoted_arguments_parsing_and_substitution(tmp_path):
    # Create a command in .codexplus/commands
    cmd_dir = Path(".codexplus/commands")
    cmd_dir.mkdir(parents=True, exist_ok=True)
    cmd_file = cmd_dir / "qargs.md"
    cmd_file.write_text(
        """---
description: Quoted args test
---

Got: $ARGUMENTS | first=$1 | second=$2
""",
        encoding="utf-8",
    )

    try:
        mw = create_enhanced_slash_command_middleware()
        out = mw._execute_command('/qargs "fix all tests" --verbose')
        assert "Got: fix all tests --verbose" in out
        assert "first=fix all tests" in out
        assert "second=--verbose" in out
    finally:
        try:
            cmd_file.unlink(missing_ok=True)
        except Exception:
            pass
        # Clean up if empty
        try:
            if cmd_dir.exists() and not any(cmd_dir.iterdir()):
                cmd_dir.rmdir()
                parent = cmd_dir.parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
        except Exception:
            pass
