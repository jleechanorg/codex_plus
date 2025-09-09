#!/usr/bin/env python3
import json
from pathlib import Path
from unittest.mock import patch, Mock

from fastapi.testclient import TestClient

from main import app
from main_sync_cffi import slash_middleware


def _make_payload(text: str) -> dict:
    return {
        "model": "gpt-5",
        "instructions": "Test",
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
            }
        ],
        "tools": [],
        "tool_choice": "auto",
        "parallel_tool_calls": True,
        "reasoning": False,
        "store": False,
        "stream": False,
    }


def test_expanded_request_proxies_with_streaming(tmp_path):
    # Create a simple command to trigger expansion
    cmd_dir = Path(".codexplus/commands")
    cmd_dir.mkdir(parents=True, exist_ok=True)
    (cmd_dir / "echo.md").write_text("Echo: $ARGUMENTS\n", encoding="utf-8")

    # Reload commands so the middleware picks up the newly created file
    try:
        slash_middleware._load_markdown_commands()  # type: ignore[attr-defined]
    except Exception:
        pass

    client = TestClient(app)

    # Mock upstream streaming response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/event-stream", "x-test": "ok"}
    mock_response.iter_content.return_value = iter([b"data: ok\n\n"])

    with patch("curl_cffi.requests.Session") as mock_session_cls:
        mock_session = Mock()
        mock_session.request.return_value = mock_response
        mock_session_cls.return_value = mock_session

        payload = _make_payload("/echo hello world")
        resp = client.post("/responses", json=payload)

        # Proxied with streaming
        assert resp.status_code == 200
        assert b"data: ok" in resp.content

        # Validate upstream call
        mock_session.request.assert_called_once()
        args, kwargs = mock_session.request.call_args
        # Positional: method, url
        assert args[0] in ("POST", "GET", "PUT", "DELETE", "PATCH")
        assert "/responses" in args[1]
        # Body sent upstream should be bytes
        sent_body = kwargs.get("data")
        assert isinstance(sent_body, (bytes, bytearray))

        # Response headers preserved (content-type and custom header)
        assert resp.headers.get("content-type") == "text/event-stream"
        assert resp.headers.get("x-test") == "ok"
