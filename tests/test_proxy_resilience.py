#!/usr/bin/env python3
"""
Regression tests for proxy resiliency features.

Covers:
1. Upstream retry/backoff handling for curl_cffi timeouts.
2. Graceful streaming failure signalling.
3. Status line subprocess robustness (BrokenPipe handling).
4. Background status task shutdown hygiene.
"""
import asyncio
import json
from types import MethodType, SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock

import pytest

from codex_plus.llm_execution_middleware import LLMExecutionMiddleware
from codex_plus.status_line_middleware import HookMiddleware
from codex_plus.hooks import HookSystem
from curl_cffi import requests as curl_requests


class DummyRequest:
    """Minimal FastAPI Request stand-in for middleware testing."""

    def __init__(self, body: bytes, headers: Optional[dict] = None, method: str = "POST"):
        self._body = body
        self.method = method
        self.headers = headers or {}
        self.state = SimpleNamespace()

    async def body(self) -> bytes:
        return self._body


async def read_streaming_response(response) -> bytes:
    """Collect the full body from a StreamingResponse for assertions."""

    body_parts: list[bytes] = []

    async for chunk in response.body_iterator:
        if chunk:
            body_parts.append(chunk)

    return b"".join(body_parts)


@pytest.mark.asyncio
async def test_upstream_timeout_retries_before_success(monkeypatch):
    """Middleware should retry once when the upstream request times out."""

    middleware = LLMExecutionMiddleware("https://chatgpt.com/backend-api/codex")

    class FakeResponse:
        def __init__(self, chunks):
            self._chunks = list(chunks)
            self.headers = {"content-type": "text/event-stream"}
            self.status_code = 200
            self.closed = False

        def iter_content(self, chunk_size=None):
            for chunk in self._chunks:
                yield chunk

        def close(self):
            self.closed = True

    class FakeSession:
        def __init__(self):
            self.calls = 0

        def request(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise curl_requests.exceptions.RequestException("timeout")
            return FakeResponse([b"data: ok\n\n"])

    monkeypatch.setattr(curl_requests, "Session", lambda impersonate=None: FakeSession())

    request_payload = json.dumps({"input": []}).encode()
    request = DummyRequest(
        body=request_payload,
        headers={"content-type": "application/json"},
    )

    response = await middleware.process_request(request, "responses")
    body = await read_streaming_response(response)

    assert b"data: ok" in body
    assert hasattr(middleware, "_session")
    assert getattr(middleware._session, "calls", 0) == 2  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_streaming_sends_error_event_when_upstream_stream_fails(monkeypatch):
    """Streaming generator should surface an SSE error event instead of crashing."""

    middleware = LLMExecutionMiddleware("https://chatgpt.com/backend-api/codex")

    class FailingResponse:
        def __init__(self):
            self.headers = {"content-type": "text/event-stream"}
            self.status_code = 200
            self.closed = False

        def iter_content(self, chunk_size=None):
            raise curl_requests.exceptions.RequestException("upstream stalled")

        def close(self):
            self.closed = True

    class FakeSession:
        def __init__(self):
            self.calls = 0

        def request(self, *args, **kwargs):
            self.calls += 1
            return FailingResponse()

    monkeypatch.setattr(curl_requests, "Session", lambda impersonate=None: FakeSession())

    request_payload = json.dumps({"input": []}).encode()
    request = DummyRequest(
        body=request_payload,
        headers={"content-type": "application/json"},
    )

    response = await middleware.process_request(request, "responses")
    body = await read_streaming_response(response)

    assert b'"code": "UPSTREAM_ERROR"' in body
    assert b"upstream stalled" in body


@pytest.mark.asyncio
async def test_run_status_line_handles_broken_pipe(monkeypatch):
    """Broken pipe during status line command should be handled gracefully."""

    hook_system = HookSystem(hooks_dirs=[])
    hook_system.status_line_cfg = {"command": "dummy-cmd", "timeout": 0.1}

    created_proc = {}

    class FakeProc:
        kill_calls = 0

        def __init__(self):
            self.killed = False
            self.returncode = None

        async def communicate(self, input=None):
            raise BrokenPipeError("test broken pipe")

        def kill(self):
            FakeProc.kill_calls += 1
            self.killed = True

        async def wait(self):
            self.returncode = -9

    async def fake_create_subprocess_exec(*args, **kwargs):
        proc = FakeProc()
        created_proc["proc"] = proc
        created_proc.setdefault("procs", []).append(proc)
        return proc

    monkeypatch.setattr(
        "codex_plus.hooks.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    monkeypatch.setattr(
        hook_system,
        "_git_status_line_fallback",
        AsyncMock(return_value="[Dir: repo | Local: main | Remote: origin/main | PR: none]"),
    )

    result = await hook_system.run_status_line()

    assert result.startswith("[Dir:")
    command_proc = created_proc["procs"][-1]
    assert command_proc.killed is True
    assert FakeProc.kill_calls == 1


@pytest.mark.asyncio
async def test_hook_middleware_stop_background_updates_cancels_task(monkeypatch):
    """Background status updater should shut down cleanly on request."""

    class DummyHookManager:
        async def run_status_line(self, working_directory=None):
            return "[Dir: dummy]"

    middleware = HookMiddleware(hook_manager=DummyHookManager())

    start_event = asyncio.Event()
    cancel_event = asyncio.Event()

    async def fake_loop(self):
        start_event.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cancel_event.set()
            raise

    middleware._background_update_loop = MethodType(fake_loop, middleware)  # type: ignore[attr-defined]

    await middleware.start_background_status_update()
    await asyncio.wait_for(start_event.wait(), timeout=0.2)

    await middleware.stop_background_status_update()

    assert cancel_event.is_set()
    assert middleware._cache_task is None or middleware._cache_task.done()
