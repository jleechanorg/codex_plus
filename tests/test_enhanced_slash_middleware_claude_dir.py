#!/usr/bin/env python3
import os
from pathlib import Path

from enhanced_slash_middleware import create_enhanced_slash_command_middleware


def write_cmd(path: Path, name: str, description: str = "Test cmd") -> Path:
    cmd_dir = path
    cmd_dir.mkdir(parents=True, exist_ok=True)
    cmd_file = cmd_dir / f"{name}.md"
    cmd_file.write_text(f"---\ndescription: {description}\n---\n\nBody\n", encoding="utf-8")
    return cmd_file


def test_loads_commands_from_claude_directory(tmp_path):
    # Create a .claude/commands/testcmd.md file under repo root
    claude_cmds = Path(".claude/commands")
    created = write_cmd(claude_cmds, "testcmd", description="From .claude")

    try:
        mw = create_enhanced_slash_command_middleware()
        # Should have loaded the command
        cmd = mw.registry.get("testcmd")
        assert cmd is not None and cmd.source == "markdown"
        assert cmd.description == "From .claude"
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
        mw = create_enhanced_slash_command_middleware()
        cmd = mw.registry.get(same)
        assert cmd is not None
        # Because we register .codexplus first and .claude second, .claude should override
        assert cmd.description == "From .claude override"
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

