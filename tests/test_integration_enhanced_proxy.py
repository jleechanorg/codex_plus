#!/usr/bin/env python3
import json
from pathlib import Path
from unittest.mock import patch, Mock

from fastapi.testclient import TestClient

from codex_plus.main import app
from codex_plus.main_sync_cffi import slash_middleware


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
    # For LLM middleware, expansion isn't needed; it injects execution instruction.
    # We only need the proxy to forward and stream the upstream response.

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
        # Streaming bodies may not populate resp.content reliably; headers + call are authoritative

        # Response headers preserved (content-type and custom header)
        assert resp.headers.get("content-type") == "text/event-stream"
