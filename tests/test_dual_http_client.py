"""
Tests for dual HTTP client architecture (curl_cffi for ChatGPT, httpx for Cerebras)

This test suite validates that the proxy can:
1. Use curl_cffi for ChatGPT upstream (Cloudflare bypass)
2. Use httpx for Cerebras upstream (avoid Cloudflare blocking)
3. Maintain all transformation logic for Cerebras
4. Preserve authentication handling for both upstreams
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import Request
from fastapi.responses import StreamingResponse
import json


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
        request.state = Mock()

        with patch('src.codex_plus.llm_execution_middleware.requests.Session') as mock_session_class:
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

        # Mock request
        request = Mock(spec=Request)
        request.method = "POST"
        request.headers = {"content-type": "application/json"}
        request.body = AsyncMock(return_value=json.dumps({
            "model": "gpt-5-codex",
            "instructions": "test",
            "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]}]
        }).encode())
        request.state = Mock()

        with patch('src.codex_plus.llm_execution_middleware.httpx.stream') as mock_httpx_stream:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.iter_bytes = Mock(return_value=iter([b'{"response": "test"}\n']))
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            mock_httpx_stream.return_value = mock_response

            with patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'}):
                response = await middleware.process_request(request, "responses")

            # Verify httpx.stream was called (not curl_cffi)
            mock_httpx_stream.assert_called_once()
            # Verify no Chrome impersonation parameter
            call_kwargs = mock_httpx_stream.call_args[1]
            assert 'impersonate' not in call_kwargs

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
        request.state = Mock()

        with patch('src.codex_plus.llm_execution_middleware.httpx.stream') as mock_httpx_stream:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.iter_bytes = Mock(return_value=iter([b'{"response": "4"}\n']))
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            mock_httpx_stream.return_value = mock_response

            with patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'}):
                response = await middleware.process_request(request, "responses")

            # Extract the body that was sent
            call_kwargs = mock_httpx_stream.call_args[1]
            sent_body = json.loads(call_kwargs['content'])

            # Verify transformation was applied
            assert sent_body['model'] == 'llama-3.3-70b'  # Model mapped
            assert 'messages' in sent_body  # Messages format
            assert 'instructions' not in sent_body  # Codex format removed
            assert 'input' not in sent_body  # Codex format removed
            assert sent_body['tools'][0]['type'] == 'function'  # Tool format converted

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
        request.state = Mock()

        with patch('src.codex_plus.llm_execution_middleware.httpx.stream') as mock_httpx_stream:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.iter_bytes = Mock(return_value=iter([b'{"response": "test"}\n']))
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            mock_httpx_stream.return_value = mock_response

            with patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'}):
                response = await middleware.process_request(request, "responses")

            # Verify endpoint was transformed
            called_url = mock_httpx_stream.call_args[0][1]
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
        request.state = Mock()

        test_api_key = "sk-test-cerebras-key-12345"

        with patch('src.codex_plus.llm_execution_middleware.httpx.stream') as mock_httpx_stream:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.iter_bytes = Mock(return_value=iter([b'{"response": "test"}\n']))
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            mock_httpx_stream.return_value = mock_response

            with patch.dict('os.environ', {'OPENAI_API_KEY': test_api_key}):
                response = await middleware.process_request(request, "responses")

            # Verify Authorization header was added
            call_kwargs = mock_httpx_stream.call_args[1]
            assert 'headers' in call_kwargs
            assert 'Authorization' in call_kwargs['headers']
            assert call_kwargs['headers']['Authorization'] == f'Bearer {test_api_key}'

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
        request.state = Mock()

        with patch('src.codex_plus.llm_execution_middleware.requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/event-stream"}
            mock_response.iter_content = Mock(return_value=iter([b"data: test\n\n"]))
            mock_response.close = Mock()
            mock_session.request = Mock(return_value=mock_response)
            mock_session_class.return_value = mock_session

            response = await middleware.process_request(request, "responses")

            # Verify original headers were preserved (not replaced with Bearer)
            call_kwargs = mock_session.request.call_args[1]
            assert 'cookie' in call_kwargs['headers']
            assert call_kwargs['headers']['cookie'] == "session_token=abc123"

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
        request.state = Mock()

        with patch('src.codex_plus.llm_execution_middleware.httpx.stream') as mock_httpx_stream:
            mock_httpx_stream.side_effect = Exception("Connection timeout")

            with patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'}):
                response = await middleware.process_request(request, "responses")

            # Verify error response
            assert response.status_code == 500
            body = json.loads(response.body.decode())
            assert 'error' in body
            assert 'timeout' in body['error'].lower()


class TestHTTPClientSelection:
    """Test HTTP client selection logic"""

    def test_is_cerebras_upstream_detection(self):
        """Should correctly identify Cerebras upstream URLs"""
        from src.codex_plus.llm_execution_middleware import LLMExecutionMiddleware

        cerebras_urls = [
            "https://api.cerebras.ai/v1",
            "https://api.cerebras.ai/v1/chat/completions",
        ]

        for url in cerebras_urls:
            middleware = LLMExecutionMiddleware(url)
            assert middleware._is_cerebras_upstream(url), f"Failed to detect Cerebras URL: {url}"

    def test_is_not_cerebras_upstream(self):
        """Should correctly identify non-Cerebras upstream URLs"""
        from src.codex_plus.llm_execution_middleware import LLMExecutionMiddleware

        non_cerebras_urls = [
            "https://chatgpt.com/backend-api/codex",
            "https://api.openai.com/v1/chat/completions",
            "https://example.com/api",
        ]

        for url in non_cerebras_urls:
            middleware = LLMExecutionMiddleware(url)
            assert not middleware._is_cerebras_upstream(url), f"Incorrectly detected as Cerebras: {url}"


class TestStreamingResponseHandling:
    """Test streaming response handling for both clients"""

    @pytest.mark.asyncio
    async def test_curl_cffi_streaming_preserved(self):
        """curl_cffi streaming should work as before"""
        from src.codex_plus.llm_execution_middleware import LLMExecutionMiddleware

        middleware = LLMExecutionMiddleware("https://chatgpt.com/backend-api/codex")

        request = Mock(spec=Request)
        request.method = "POST"
        request.headers = {"content-type": "application/json"}
        request.body = AsyncMock(return_value=json.dumps({
            "model": "gpt-5-codex",
            "instructions": "test",
            "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]}]
        }).encode())
        request.state = Mock()

        chunks = [b"data: chunk1\n\n", b"data: chunk2\n\n", b"data: [DONE]\n\n"]

        with patch('src.codex_plus.llm_execution_middleware.requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/event-stream"}
            mock_response.iter_content = Mock(return_value=iter(chunks))
            mock_response.close = Mock()
            mock_session.request = Mock(return_value=mock_response)
            mock_session_class.return_value = mock_session

            response = await middleware.process_request(request, "responses")

            # Verify streaming response returned
            assert isinstance(response, StreamingResponse)
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_httpx_streaming_works(self):
        """httpx streaming should work for Cerebras"""
        from src.codex_plus.llm_execution_middleware import LLMExecutionMiddleware

        middleware = LLMExecutionMiddleware("https://api.cerebras.ai/v1")

        request = Mock(spec=Request)
        request.method = "POST"
        request.headers = {"content-type": "application/json"}
        request.body = AsyncMock(return_value=json.dumps({
            "model": "gpt-5-codex",
            "instructions": "test",
            "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]}],
            "stream": True
        }).encode())
        request.state = Mock()

        chunks = [b'data: {"delta": "test"}\n\n', b'data: [DONE]\n\n']

        with patch('src.codex_plus.llm_execution_middleware.httpx.stream') as mock_httpx_stream:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/event-stream"}
            mock_response.iter_bytes = Mock(return_value=iter(chunks))
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            mock_httpx_stream.return_value = mock_response

            with patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'}):
                response = await middleware.process_request(request, "responses")

            # Verify streaming response returned
            assert isinstance(response, StreamingResponse)
            assert response.status_code == 200
