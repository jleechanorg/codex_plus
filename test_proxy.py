# test_proxy.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
import httpx
import json

# Import the proxy app (to be created)
from main import app

client = TestClient(app)

# Test Matrix 1: Core Request Interception
class TestSimplePassthroughProxy:
    """Test suite for M1 Simple Passthrough Proxy implementation"""
    
    # Matrix 1: Core Request Interception (RED - failing tests)
    @pytest.mark.parametrize("method,path,expected_forward", [
        ("GET", "/v1/models", True),
        ("POST", "/v1/chat/completions", True),
        ("POST", "/v1/embeddings", True),
        ("GET", "/health", False),  # Special case - not forwarded
    ])
    def test_request_forwarding(self, method, path, expected_forward):
        """Test that requests are properly forwarded to upstream API"""
        # Mock upstream response
        mock_upstream = AsyncMock()
        mock_upstream.status_code = 200
        mock_upstream.headers = {"content-type": "application/json"}
        async def mock_aiter_raw():
            yield b'{"test": "response"}'
        mock_upstream.aiter_raw = mock_aiter_raw
        mock_upstream.aclose = AsyncMock()
        
        with patch('httpx.AsyncClient.stream') as mock_stream:
            mock_stream.return_value.__aenter__.return_value = mock_upstream
            
            # Make request to proxy
            if method == "GET":
                response = client.get(path)
            elif method == "POST":
                response = client.post(path, json={"test": "data"})
            
            # Verify forwarding behavior
            if expected_forward:
                # Should forward to upstream API
                mock_stream.assert_called_once()
                called_url = mock_stream.call_args[0][1]  # Second positional argument is URL
                assert called_url.startswith("https://api.openai.com"), f"Expected forwarding to OpenAI API, got {called_url}"
                assert path in called_url
                assert response.status_code == 200
            else:
                # Should NOT forward (local handling)
                mock_stream.assert_not_called()
                assert response.status_code == 200
                assert "healthy" in response.json().get("status", "")

    # Matrix 2: Streaming Response Types (Fixed - working tests)
    @pytest.mark.parametrize("content_type,response_data", [
        ("application/json", b'{"object": "test"}'),
        ("text/event-stream", b'data: {"object": "test"}\n\n'),
        ("application/octet-stream", b"binary data"),
    ])
    def test_response_streaming(self, content_type, response_data):
        """Test that different response types are properly streamed"""
        # Mock streaming response with proper async iterator
        mock_upstream = AsyncMock()
        mock_upstream.status_code = 200
        mock_upstream.headers = {"content-type": content_type}
        
        # Create async iterator for raw bytes
        async def mock_aiter_raw():
            yield response_data
        mock_upstream.aiter_raw = mock_aiter_raw
        mock_upstream.aclose = AsyncMock()
        
        with patch('httpx.AsyncClient.stream') as mock_stream:
            mock_stream.return_value.__aenter__.return_value = mock_upstream
            
            # Make request that should be streamed
            response = client.post("/v1/chat/completions", json={"stream": True})
            
            # Verify streaming behavior
            mock_stream.assert_called_once()
            assert response.status_code == 200
            assert content_type in response.headers["content-type"]
            
            # Verify content is preserved
            assert response_data in response.content

    # Matrix 4: Error Conditions (RED - failing tests)
    @pytest.mark.parametrize("error_status,error_message", [
        (401, "Unauthorized"),
        (404, "Not Found"),
        (429, "Rate limit exceeded"),
        (500, "Internal server error"),
    ])
    def test_error_passthrough(self, error_status, error_message):
        """Test that error responses are properly passed through"""
        # Mock error response from upstream
        mock_upstream = AsyncMock()
        mock_upstream.status_code = error_status
        mock_upstream.headers = {"content-type": "application/json"}
        async def mock_aiter_raw():
            yield error_message.encode()
        mock_upstream.aiter_raw = mock_aiter_raw
        mock_upstream.aclose = AsyncMock()
        
        with patch('httpx.AsyncClient.stream') as mock_stream:
            mock_stream.return_value.__aenter__.return_value = mock_upstream
            
            # Make request to proxy
            response = client.post("/v1/chat/completions", json={"test": "data"})
            
            # Verify error passthrough
            mock_stream.assert_called_once()
            assert response.status_code == error_status
            assert error_message in response.text