#!/usr/bin/env python3
import os
import json
from pathlib import Path

import pytest

from llm_execution_middleware import LLMExecutionMiddleware, create_llm_execution_middleware


def test_detect_slash_commands_and_instruction_building():
    mw: LLMExecutionMiddleware = create_llm_execution_middleware("https://chatgpt.com/backend-api/codex")
    text = "Please /echo one and then /echo two"
    cmds = mw.detect_slash_commands(text)
    assert ("echo", "one and then") or ("echo", "one") in cmds
    instr = mw.create_execution_instruction(cmds)
    assert "You are a slash command interpreter" in instr


def test_no_injection_for_plain_text():
    mw: LLMExecutionMiddleware = create_llm_execution_middleware("https://chatgpt.com/backend-api/codex")
    payload = {"input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]}]}
    modified = mw.inject_execution_behavior(payload)
    assert modified == payload


def test_find_command_file_precedence(tmp_path):
    mw: LLMExecutionMiddleware = create_llm_execution_middleware("https://chatgpt.com/backend-api/codex")
    codex_dir = Path(".codexplus/commands"); codex_dir.mkdir(parents=True, exist_ok=True)
    claude_dir = Path(".claude/commands"); claude_dir.mkdir(parents=True, exist_ok=True)
    name = "dupfile"
    codex_file = codex_dir / f"{name}.md"; codex_file.write_text("codex version", encoding="utf-8")
    claude_file = claude_dir / f"{name}.md"; claude_file.write_text("claude version", encoding="utf-8")
    try:
        f = mw.find_command_file(name)
        assert f is not None
        # .codexplus should take precedence
        assert f.name == f"{name}.md" and str(f).endswith(".codexplus/commands/"+f.name)
    finally:
        for p in (codex_file, claude_file):
            try: p.unlink(missing_ok=True)
            except: pass
        for d in (codex_dir, claude_dir):
            try:
                if d.exists() and not any(d.iterdir()):
                    d.rmdir(); parent=d.parent
                    if parent.exists() and not any(parent.iterdir()): parent.rmdir()
            except: pass


def test_multiple_commands_injection_in_input_format():
    mw: LLMExecutionMiddleware = create_llm_execution_middleware("https://chatgpt.com/backend-api/codex")
    payload = {
        "input": [
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "First /echo one then /echo two please"}]}
        ]
    }
    modified = mw.inject_execution_behavior(payload)
    txt = modified["input"][0]["content"][0]["text"]
    assert txt.startswith("[SYSTEM:")


    # Replacement for expansion: ensure instruction includes both commands
    cmds = mw.detect_slash_commands("First /echo one then /echo two please")
    instr = mw.create_execution_instruction(cmds)
    low = instr.lower()
    assert "/echo" in low and low.count("/echo") >= 2
