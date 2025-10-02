"""Tests for dual HTTP client architecture (curl_cffi for ChatGPT, httpx for Cerebras).

This test suite validates that the proxy can:
1. Use curl_cffi for ChatGPT upstream (Cloudflare bypass)
2. Use httpx for Cerebras upstream (avoid Cloudflare blocking)
3. Maintain all transformation logic for Cerebras
4. Preserve authentication handling for both upstreams
"""

import json
from types import SimpleNamespace
from typing import Iterable, List
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import Request


class DummyResponse:
    """Simple async-compatible response for httpx.AsyncClient.stream tests."""

    def __init__(self, chunks: Iterable[bytes], status_code: int = 200, headers=None):
        self._chunks: List[bytes] = list(chunks)
        self.status_code = status_code
        self.headers = headers or {"content-type": "application/json"}
        self.request = Mock()
        self.closed = False

    def iter_content(self, chunk_size=None):
        """Support ChatGPT path iteration (synchronous)."""
        return iter(self._chunks)

    def aiter_bytes(self):
        """Return async iterator for Cerebras streaming path."""

        async def generator():
            for chunk in self._chunks:
                yield chunk

        return generator()

    async def aclose(self):
        self.closed = True

    async def aread(self):
        return b"".join(self._chunks)

    def close(self):
        self.closed = True


class DummyStream:
    """Async context manager mimicking httpx stream."""

    def __init__(self, response: DummyResponse):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc, tb):
        await self.response.aclose()
        return False


class TestDualHTTPClient:
    """Test dual HTTP client selection based on upstream"""

    @pytest.mark.asyncio
    async def test_chatgpt_upstream_uses_curl_cffi(self):
        """ChatGPT upstream should use curl_cffi with Chrome impersonation"""
        from src.codex_plus.llm_execution_middleware import LLMExecutionMiddleware

        middleware = LLMExecutionMiddleware("https://chatgpt.com/backend-api/codex")

        # Mock request
        request = Mock(spec=Request)
        request.method = "POST"
        request.headers = {"content-type": "application/json"}
        request.body = AsyncMock(return_value=json.dumps({
            "model": "gpt-5-codex",
            "instructions": "test",
            "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]}]
        }).encode())
        request.state = SimpleNamespace()

        with patch('curl_cffi.requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/event-stream"}
            mock_response.iter_content = Mock(return_value=iter([b"data: test\n\n"]))
            mock_response.close = Mock()
            mock_session.request = Mock(return_value=mock_response)
            mock_session_class.return_value = mock_session

            response = await middleware.process_request(request, "responses")

            # Verify curl_cffi session was created with Chrome impersonation
            mock_session_class.assert_called_once_with(impersonate="chrome124")
            # Verify curl_cffi request method was called
            assert mock_session.request.called

    @pytest.mark.asyncio
    async def test_cerebras_upstream_uses_httpx(self):
        """Cerebras upstream should use httpx without impersonation"""
        from src.codex_plus.llm_execution_middleware import LLMExecutionMiddleware

        middleware = LLMExecutionMiddleware("https://api.cerebras.ai/v1")

        request = Mock(spec=Request)
        request.method = "POST"
        request.headers = {"content-type": "application/json"}
        request.body = AsyncMock(return_value=json.dumps({
            "model": "gpt-5-codex",
            "instructions": "test",
            "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]}]
        }).encode())
        request.state = SimpleNamespace()

        with patch('src.codex_plus.llm_execution_middleware.httpx.AsyncClient') as mock_client_cls:
            mock_client = Mock()
            mock_client.stream.return_value = DummyStream(DummyResponse([b'{"response": "test"}\n']))
            mock_client_cls.return_value = mock_client

            with patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'}, clear=False):
                response = await middleware.process_request(request, "responses")

            mock_client.stream.assert_called_once()
            call_kwargs = mock_client.stream.call_args.kwargs
            assert call_kwargs["headers"]["Authorization"].endswith("test_key")
            payload = json.loads(call_kwargs["content"].decode())
            assert payload["model"] != "gpt-5-codex"

    @pytest.mark.asyncio
    async def test_cerebras_request_transformation_still_applied(self):
        """Cerebras requests should still be transformed even with httpx"""
        from src.codex_plus.llm_execution_middleware import LLMExecutionMiddleware

        middleware = LLMExecutionMiddleware("https://api.cerebras.ai/v1")

        request = Mock(spec=Request)
        request.method = "POST"
        request.headers = {"content-type": "application/json"}
        original_body = {
            "model": "gpt-5-codex",
            "instructions": "You are a helpful assistant",
            "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "What is 2+2?"}]}],
            "tools": [{"name": "calculator", "parameters": {"type": "object"}}]
        }
        request.body = AsyncMock(return_value=json.dumps(original_body).encode())
        request.state = SimpleNamespace()

        with patch('src.codex_plus.llm_execution_middleware.httpx.AsyncClient') as mock_client_cls:
            mock_client = Mock()
            mock_client.stream.return_value = DummyStream(DummyResponse([b'{"response": "4"}\n']))
            mock_client_cls.return_value = mock_client

            with patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'}, clear=False):
                response = await middleware.process_request(request, "responses")

            sent_body = json.loads(mock_client.stream.call_args.kwargs["content"].decode())
            assert sent_body["model"] != "gpt-5-codex"
            assert "instructions" not in sent_body
            assert "input" not in sent_body
            assert sent_body["tools"][0]["type"] == "function"

    @pytest.mark.asyncio
    async def test_cerebras_endpoint_transformation(self):
        """Cerebras endpoint should be transformed to /v1/chat/completions"""
        from src.codex_plus.llm_execution_middleware import LLMExecutionMiddleware

        middleware = LLMExecutionMiddleware("https://api.cerebras.ai/v1")

        request = Mock(spec=Request)
        request.method = "POST"
        request.headers = {"content-type": "application/json"}
        request.body = AsyncMock(return_value=json.dumps({
            "model": "gpt-5-codex",
            "instructions": "test",
            "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]}]
        }).encode())
        request.state = SimpleNamespace()

        with patch('src.codex_plus.llm_execution_middleware.httpx.AsyncClient') as mock_client_cls:
            mock_client = Mock()
            mock_client.stream.return_value = DummyStream(DummyResponse([b'{"response": "test"}\n']))
            mock_client_cls.return_value = mock_client

            with patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'}, clear=False):
                response = await middleware.process_request(request, "responses")

            called_url = mock_client.stream.call_args.args[1]
            assert called_url.endswith('/v1/chat/completions')
            assert 'responses' not in called_url

    @pytest.mark.asyncio
    async def test_cerebras_authentication_added(self):
        """Cerebras requests should include Bearer token authentication"""
        from src.codex_plus.llm_execution_middleware import LLMExecutionMiddleware

        middleware = LLMExecutionMiddleware("https://api.cerebras.ai/v1")

        request = Mock(spec=Request)
        request.method = "POST"
        request.headers = {"content-type": "application/json"}
        request.body = AsyncMock(return_value=json.dumps({
            "model": "gpt-5-codex",
            "instructions": "test",
            "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]}]
        }).encode())
        request.state = SimpleNamespace()

        test_api_key = "cerebras-test-key"

        with patch('src.codex_plus.llm_execution_middleware.httpx.AsyncClient') as mock_client_cls:
            mock_client = Mock()
            mock_client.stream.return_value = DummyStream(DummyResponse([b'{"response": "test"}\n']))
            mock_client_cls.return_value = mock_client

            with patch.dict('os.environ', {'OPENAI_API_KEY': test_api_key}, clear=False):
                response = await middleware.process_request(request, "responses")

            headers = mock_client.stream.call_args.kwargs["headers"]
            assert headers["Authorization"] == f'Bearer {test_api_key}'

    @pytest.mark.asyncio
    async def test_chatgpt_preserves_session_cookies(self):
        """ChatGPT requests should preserve session authentication (not Bearer)"""
        from src.codex_plus.llm_execution_middleware import LLMExecutionMiddleware

        middleware = LLMExecutionMiddleware("https://chatgpt.com/backend-api/codex")

        request = Mock(spec=Request)
        request.method = "POST"
        request.headers = {
            "content-type": "application/json",
            "cookie": "session_token=abc123",
            "authorization": "Bearer chatgpt_token"
        }
        request.body = AsyncMock(return_value=json.dumps({
            "model": "gpt-5-codex",
            "instructions": "test",
            "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]}]
        }).encode())
        request.state = SimpleNamespace()

        with patch('curl_cffi.requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/event-stream"}
            mock_response.iter_content = Mock(return_value=iter([b"data: test\n\n"]))
            mock_response.close = Mock()
            mock_session.request = Mock(return_value=mock_response)
            mock_session_class.return_value = mock_session

            response = await middleware.process_request(request, "responses")

            call_kwargs = mock_session.request.call_args.kwargs
            assert call_kwargs['headers']['cookie'] == "session_token=abc123"
            assert 'Authorization' not in call_kwargs['headers'] or call_kwargs['headers']['Authorization'] == "Bearer chatgpt_token"

    @pytest.mark.asyncio
    async def test_error_handling_httpx_path(self):
        """HTTPx path should handle errors gracefully"""
        from src.codex_plus.llm_execution_middleware import LLMExecutionMiddleware

        middleware = LLMExecutionMiddleware("https://api.cerebras.ai/v1")

        request = Mock(spec=Request)
        request.method = "POST"
        request.headers = {"content-type": "application/json"}
        request.body = AsyncMock(return_value=json.dumps({
            "model": "gpt-5-codex",
            "instructions": "test",
            "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]}]
        }).encode())
        request.state = SimpleNamespace()

        error_response = DummyResponse([b'{"error": "bad"}'], status_code=404)

        with patch('src.codex_plus.llm_execution_middleware.httpx.AsyncClient') as mock_client_cls:
            mock_client = Mock()
            mock_client.stream.return_value = DummyStream(error_response)
            mock_client_cls.return_value = mock_client

            with patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'}, clear=False):
                response = await middleware.process_request(request, "responses")

            assert mock_client.stream.called
            assert response.status_code == 404

