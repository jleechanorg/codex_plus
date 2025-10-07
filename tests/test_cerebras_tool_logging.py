import json
from pathlib import Path

import pytest

from codex_plus import cerebras_tool_output_logger as tool_logger


@pytest.mark.asyncio
async def test_record_tool_outputs_writes_redacted_snapshot(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(tool_logger, "LOG_DIR", tmp_path)

    payload = {"tool_outputs": [{"tool_call_id": "call_1", "output": "ok"}]}

    result_path = await tool_logger.record_tool_outputs(
        path="responses/resp_123/tool_outputs",
        body_bytes=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "topsecret", "X-Test": "value"},
    )

    assert result_path is not None
    assert result_path.exists()

    recorded = json.loads(result_path.read_text("utf-8"))
    assert recorded["path"] == "responses/resp_123/tool_outputs"
    assert recorded["body"] == payload
    assert "Authorization" not in recorded["headers"]
    assert recorded["headers"]["X-Test"] == "value"


@pytest.mark.asyncio
async def test_record_tool_outputs_ignores_invalid_json(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(tool_logger, "LOG_DIR", tmp_path)

    result_path = await tool_logger.record_tool_outputs(
        path="responses/resp_123/tool_outputs",
        body_bytes=b"not-json",
        headers={},
    )

    assert result_path is None
    assert not any(tmp_path.iterdir())

