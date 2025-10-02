import json
from pathlib import Path
from unittest.mock import patch, Mock

from fastapi.testclient import TestClient

from codex_plus.main import app
import codex_plus.hooks as hooks_mod


def write_hook(dir_path: Path, name: str, body: str) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    p = dir_path / f"{name}.py"
    p.write_text(body, encoding="utf-8")
    return p


def test_pre_input_hook_modifies_upstream_body(tmp_path):
    # Arrange: create a pre-input hook that injects a marker into the body
    hooks_dir = Path(".codexplus/hooks")
    hook_code = """---
name: inject-marker
type: pre-input
priority: 10
enabled: true
---
from codex_plus.hooks import Hook

class InjectMarker(Hook):
    name = "inject-marker"
    async def pre_input(self, request, body):
        body['hooked'] = True
        return body
hook = InjectMarker('inject-marker', {'type':'pre-input','priority':10,'enabled':True})
"""
    hook_file = write_hook(hooks_dir, "inject_marker", hook_code)

    try:
        # Reload hooks so the new file is discovered
        # Handle async event loop issue by catching RuntimeError
        try:
            hooks_mod.hook_system._load_hooks()
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                # Event loop issue during test - try again with clean environment
                hooks_mod.hook_system = hooks_mod.HookSystem()
            else:
                raise

        client = TestClient(app)

        # Mock upstream streaming response and capture body sent to upstream
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.iter_content.return_value = iter([b"{}"])

        with patch("curl_cffi.requests.Session") as mock_session_cls:
            mock_session = Mock()
            mock_session.request.return_value = mock_response
            mock_session_cls.return_value = mock_session

            payload = {"model":"gpt-5","instructions":"Test","input":[{"type":"message","role":"user","content":[{"type":"input_text","text":"/echo hi"}]}]}
            r = client.post("/responses", json=payload)
            assert r.status_code == 200
            # Verify the body sent upstream contained our injected marker
            args, kwargs = mock_session.request.call_args
            sent_body = kwargs.get("data")
            assert isinstance(sent_body, (bytes, bytearray))
            sent_json = json.loads(sent_body)
            assert sent_json.get("hooked") is True
    finally:
        try:
            hook_file.unlink(missing_ok=True)
            if hooks_dir.exists() and not any(hooks_dir.iterdir()):
                hooks_dir.rmdir()
                parent = hooks_dir.parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
        except Exception:
            pass
