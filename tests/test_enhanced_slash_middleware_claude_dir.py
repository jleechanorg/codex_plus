#!/usr/bin/env python3
import os
from pathlib import Path

from codex_plus.llm_execution_middleware import create_llm_execution_middleware


def write_cmd(path: Path, name: str, description: str = "Test cmd") -> Path:
    cmd_dir = path
    cmd_dir.mkdir(parents=True, exist_ok=True)
    cmd_file = cmd_dir / f"{name}.md"
    cmd_file.write_text(f"---\ndescription: {description}\n---\n\nBody\n", encoding="utf-8")
    return cmd_file


def test_find_command_file_from_claude_directory(tmp_path):
    # Create a .claude/commands/testcmd.md file under repo root
    claude_cmds = Path(".claude/commands")
    created = write_cmd(claude_cmds, "testcmd", description="From .claude")

    try:
        mw = create_llm_execution_middleware("https://chatgpt.com/backend-api/codex")
        f = mw.find_command_file("testcmd")
        assert f is not None
        assert f.name == "testcmd.md"
        assert ".claude/commands" in str(f)
    finally:
        # Cleanup created file
        try:
            created.unlink(missing_ok=True)
            # remove directory if empty
            if not any(claude_cmds.iterdir()):
                claude_cmds.rmdir()
                parent = claude_cmds.parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
        except Exception:
            pass


def test_claude_overrides_codexplus_when_duplicate():
    codexplus_cmds = Path(".codexplus/commands")
    claude_cmds = Path(".claude/commands")
    same = "dup"
    codex_file = write_cmd(codexplus_cmds, same, description="From .codexplus")
    claude_file = write_cmd(claude_cmds, same, description="From .claude override")

    try:
        mw = create_llm_execution_middleware("https://chatgpt.com/backend-api/codex")
        f = mw.find_command_file(same)
        # .codexplus should take precedence in LLMExecutionMiddleware
        assert f is not None and ".codexplus/commands" in str(f)
    finally:
        for f in (codex_file, claude_file):
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass
        for d in (codexplus_cmds, claude_cmds):
            try:
                if d.exists() and not any(d.iterdir()):
                    d.rmdir()
                    parent = d.parent
                    if parent.exists() and not any(parent.iterdir()):
                        parent.rmdir()
            except Exception:
                pass


def test_home_codexplus_used_when_local_missing(monkeypatch, tmp_path):
    """Commands in ~/.codexplus/commands resolve even if repo lacks them."""
    fake_home = tmp_path / "home"
    cmd_dir = fake_home / ".codexplus" / "commands"
    created = write_cmd(cmd_dir, "homecmd", description="From home .codexplus")
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    try:
        mw = create_llm_execution_middleware("https://chatgpt.com/backend-api/codex")
        resolved = mw.find_command_file("homecmd")
        assert resolved is not None
        assert str(cmd_dir) in str(resolved)
    finally:
        created.unlink(missing_ok=True)
        # cleanup test directories we created under the fake home
        current = cmd_dir
        while current != fake_home and current.exists() and not any(current.iterdir()):
            current.rmdir()
            current = current.parent


def test_local_codexplus_precedence_over_home(monkeypatch, tmp_path):
    """Local .codexplus/commands outranks ~/.codexplus/commands."""
    local_dir = Path(".codexplus/commands")
    local_dir.mkdir(parents=True, exist_ok=True)
    local_file = write_cmd(local_dir, "priority", description="Local win")

    fake_home = tmp_path / "home"
    home_cmd_dir = fake_home / ".codexplus" / "commands"
    home_file = write_cmd(home_cmd_dir, "priority", description="Home fallback")
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    try:
        mw = create_llm_execution_middleware("https://chatgpt.com/backend-api/codex")
        resolved = mw.find_command_file("priority")
        assert resolved is not None
        assert str(local_dir) in str(resolved)
    finally:
        local_file.unlink(missing_ok=True)
        if not any(local_dir.iterdir()):
            local_dir.rmdir()
        home_file.unlink(missing_ok=True)
        current = home_cmd_dir
        while current != fake_home and current.exists() and not any(current.iterdir()):
            current.rmdir()
            current = current.parent
