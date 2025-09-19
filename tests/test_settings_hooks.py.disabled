import json
import os
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from codex_plus.main import app
import codex_plus.hooks as hooks_mod


def write_file(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def write_settings(cfg: dict):
    p = Path(".codexplus/settings.json")
    write_file(p, json.dumps(cfg, indent=2))
    hooks_mod.hook_system._load_settings_hooks()
    return p


def make_client():
    return TestClient(app)


def mock_upstream():
    mresp = Mock()
    mresp.status_code = 200
    mresp.headers = {"content-type": "application/json"}
    mresp.iter_content.return_value = iter([b"{}"])
    return mresp


def cleanup_paths(paths):
    for p in paths:
        try:
            if Path(p).is_file():
                Path(p).unlink()
        except Exception:
            pass
    # Remove settings.json if present and empty hooks dir if created by tests
    try:
        sp = Path(".codexplus/settings.json")
        if sp.exists():
            sp.unlink()
    except Exception:
        pass


def test_user_prompt_submit_blocks(tmp_path):
    # Arrange: settings with a block-on-FOOBAR hook
    hook_path = Path(".codexplus/hooks/block_on_word.py")
    write_file(
        hook_path,
        """#!/usr/bin/env python3
import sys, json
d=json.load(sys.stdin)
prompt=str(d.get('prompt',''))
if 'FOOBAR' in prompt:
    print('Policy: FOOBAR not allowed', file=sys.stderr)
    sys.exit(2)
sys.exit(0)
""",
    )
    settings = {
        "hooks": {
            "UserPromptSubmit": [
                {"hooks": [{"type": "command", "command": f"python3 $CLAUDE_PROJECT_DIR/{hook_path}", "timeout": 2}]}
            ]
        }
    }
    write_settings(settings)

    client = make_client()
    payload = {
        "model": "gpt-x",
        "instructions": "Test",
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Tell me FOOBAR"}],
            }
        ],
    }

    with patch("curl_cffi.requests.Session") as mock_session_cls:
        mock_session = Mock()
        mock_session.request.return_value = mock_upstream()
        mock_session_cls.return_value = mock_session
        r = client.post("/responses", json=payload)
        assert r.status_code == 400
        assert "FOOBAR" in r.json().get("error", "") or "Policy" in r.json().get("error", "")
        # Upstream should not be called when blocked
        assert mock_session.request.call_count == 0

    cleanup_paths([hook_path])


def test_user_prompt_submit_additional_context_injected():
    # Arrange: hook that injects additionalContext
    hook_path = Path(".codexplus/hooks/add_context.py")
    write_file(
        hook_path,
        """#!/usr/bin/env python3
import json, sys
print(json.dumps({
  "hookSpecificOutput": {"hookEventName":"UserPromptSubmit", "additionalContext": "CTX-123"}
}))
sys.exit(0)
""",
    )
    settings = {
        "hooks": {
            "UserPromptSubmit": [
                {"hooks": [{"type": "command", "command": f"python3 $CLAUDE_PROJECT_DIR/{hook_path}", "timeout": 2}]}
            ]
        }
    }
    write_settings(settings)

    client = make_client()
    payload = {
        "model": "gpt-x",
        "instructions": "Test",
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "hello there"}],
            }
        ],
    }

    with patch("curl_cffi.requests.Session") as mock_session_cls:
        mock_session = Mock()
        mock_session.request.return_value = mock_upstream()
        mock_session_cls.return_value = mock_session
        r = client.post("/responses", json=payload)
        assert r.status_code == 200
        # Verify context was injected into upstream body
        args, kwargs = mock_session.request.call_args
        sent = json.loads(kwargs.get("data") or b"{}")
        # For codex format, we prepend marker to first input_text
        first = sent["input"][0]["content"][0]["text"]
        assert "CTX-123" in first

    cleanup_paths([hook_path])


def test_pretooluse_blocks_slash_command():
    # Arrange PreToolUse that blocks any SlashCommand
    marker = Path("/tmp/codex_plus_pretool_blocked")
    if marker.exists():
        marker.unlink()
    hook_path = Path(".codexplus/hooks/pretool_block.py")
    write_file(
        hook_path,
        f"""#!/usr/bin/env python3
import sys
# create a marker so we know this ran
open('{marker}', 'w').write('blocked')
sys.stderr.write('blocked by pretool')
sys.exit(2)
""",
    )
    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "SlashCommand/.*",
                    "hooks": [
                        {"type": "command", "command": f"python3 $CLAUDE_PROJECT_DIR/{hook_path}", "timeout": 2}
                    ],
                }
            ]
        }
    }
    write_settings(settings)

    client = make_client()
    payload = {
        "model": "gpt-x",
        "instructions": "Test",
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "/echo hi"}],
            }
        ],
    }

    with patch("curl_cffi.requests.Session") as mock_session_cls:
        mock_session = Mock()
        mock_session.request.return_value = mock_upstream()
        mock_session_cls.return_value = mock_session
        r = client.post("/responses", json=payload)
        assert r.status_code == 400
        assert marker.exists()
        assert mock_session.request.call_count == 0

    cleanup_paths([hook_path, marker])


def test_posttooluse_runs_after_response():
    # Arrange PostToolUse that writes a marker
    marker = Path("/tmp/codex_plus_posttool_marker")
    if marker.exists():
        marker.unlink()
    hook_path = Path(".codexplus/hooks/posttool_marker.py")
    write_file(
        hook_path,
        f"""#!/usr/bin/env python3
open('{marker}', 'w').write('ran')
""",
    )
    settings = {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "SlashCommand/.*",
                    "hooks": [
                        {"type": "command", "command": f"python3 $CLAUDE_PROJECT_DIR/{hook_path}", "timeout": 2}
                    ],
                }
            ]
        }
    }
    write_settings(settings)
    client = make_client()
    payload = {
        "model": "gpt-x",
        "instructions": "Test",
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "/echo hi"}],
            }
        ],
    }

    with patch("curl_cffi.requests.Session") as mock_session_cls:
        mock_session = Mock()
        mock_session.request.return_value = mock_upstream()
        mock_session_cls.return_value = mock_session
        r = client.post("/responses", json=payload)
        assert r.status_code == 200
        # PostToolUse hook should have created the marker
        assert marker.exists()

    cleanup_paths([hook_path, marker])


def test_session_start_end_hooks(tmp_path):
    # Arrange hooks that write markers
    start_marker = Path("/tmp/codex_plus_session_start")
    end_marker = Path("/tmp/codex_plus_session_end")
    for p in (start_marker, end_marker):
        if p.exists():
            p.unlink()
    hook_start = Path(".codexplus/hooks/session_start.py")
    hook_end = Path(".codexplus/hooks/session_end.py")
    write_file(hook_start, f"open('{start_marker}','w').write('start')\n")
    write_file(hook_end, f"open('{end_marker}','w').write('end')\n")
    settings = {
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": f"python3 $CLAUDE_PROJECT_DIR/{hook_start}", "timeout": 2}]}
            ],
            "SessionEnd": [
                {"hooks": [{"type": "command", "command": f"python3 $CLAUDE_PROJECT_DIR/{hook_end}", "timeout": 2}]}
            ],
        }
    }
    write_settings(settings)

    with make_client() as client:
        # On startup, SessionStart should run
        time.sleep(0.05)
        assert start_marker.exists()
        # Trigger one request
        with patch("curl_cffi.requests.Session") as mock_session_cls:
            mock_session = Mock(); mock_session.request.return_value = mock_upstream(); mock_session_cls.return_value = mock_session
            client.post("/responses", json={"model":"x","instructions":"","input": []})

    # After closing client (shutdown), SessionEnd should run
    time.sleep(0.05)
    assert end_marker.exists()

    cleanup_paths([hook_start, hook_end, start_marker, end_marker])


def test_stop_hook_runs_after_response():
    # Arrange Stop hook writes a marker
    marker = Path("/tmp/codex_plus_stop_marker")
    if marker.exists():
        marker.unlink()
    hook_path = Path(".codexplus/hooks/stop_marker.py")
    write_file(hook_path, f"open('{marker}','w').write('stop')\n")
    settings = {
        "hooks": {
            "Stop": [
                {"hooks": [{"type": "command", "command": f"python3 $CLAUDE_PROJECT_DIR/{hook_path}", "timeout": 2}]}
            ]
        }
    }
    write_settings(settings)
    client = make_client()
    with patch("curl_cffi.requests.Session") as mock_session_cls:
        mock_session = Mock(); mock_session.request.return_value = mock_upstream(); mock_session_cls.return_value = mock_session
        r = client.post("/responses", json={"model":"x","instructions":"","input": []})
        assert r.status_code == 200
        # Stop hook runs asynchronously; give it a moment
        for _ in range(20):
            if marker.exists():
                break
            time.sleep(0.01)
        assert marker.exists()

    cleanup_paths([hook_path, marker])


def test_notification_and_precompact_helpers():
    # Arrange two hooks that write markers
    notif_marker = Path("/tmp/codex_plus_notif_marker")
    compact_marker = Path("/tmp/codex_plus_precompact_marker")
    for p in (notif_marker, compact_marker):
        if p.exists():
            p.unlink()
    hook_notif = Path(".codexplus/hooks/notif.py")
    hook_precompact = Path(".codexplus/hooks/precompact.py")
    write_file(hook_notif, f"open('{notif_marker}','w').write('notif')\n")
    write_file(hook_precompact, f"open('{compact_marker}','w').write('precompact')\n")
    settings = {
        "hooks": {
            "Notification": [
                {"hooks": [{"type": "command", "command": f"python3 $CLAUDE_PROJECT_DIR/{hook_notif}", "timeout": 2}]}
            ],
            "PreCompact": [
                {"hooks": [{"type": "command", "command": f"python3 $CLAUDE_PROJECT_DIR/{hook_precompact}", "timeout": 2}]}
            ],
        }
    }
    write_settings(settings)

    # Call exported helpers directly
    from codex_plus.hooks import settings_notification, settings_pre_compact
    import anyio

    anyio.run(settings_notification, None, "Test notification")
    anyio.run(settings_pre_compact, None, "manual", "")

    assert notif_marker.exists()
    assert compact_marker.exists()

    cleanup_paths([hook_notif, hook_precompact, notif_marker, compact_marker])

