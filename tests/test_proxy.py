# test_proxy.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
import json

# Import the proxy app (to be created)
from main import app
from main_sync_cffi import slash_middleware

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_llm_session():
    # Ensure the LLM middleware recreates its session inside each test's patch context
    try:
        if hasattr(slash_middleware, "_session"):
            delattr(slash_middleware, "_session")  # type: ignore[attr-defined]
    except Exception:
        pass
    yield

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
        # Mock upstream response for curl_cffi
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"test": "response"}'
        mock_response.iter_content.return_value = [b'{"test": "response"}']
        
        with patch('curl_cffi.requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session.request.return_value = mock_response
            mock_session_class.return_value = mock_session
            
            # Make request to proxy
            if method == "GET":
                response = client.get(path)
            elif method == "POST":
                response = client.post(path, json={"test": "data"})
            
            # Verify forwarding behavior
            if expected_forward:
                # Should forward to upstream API
                mock_session.request.assert_called_once()
                called_url = mock_session.request.call_args[0][1]  # Second positional arg is URL
                assert called_url.startswith("https://chatgpt.com"), f"Expected forwarding to ChatGPT API, got {called_url}"
                assert path in called_url
                assert response.status_code == 200
            else:
                # Should NOT forward (local handling)
                mock_session_class.assert_not_called()
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
        # Mock streaming response for curl_cffi
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": content_type}
        mock_response.iter_content.return_value = [response_data]
        
        with patch('curl_cffi.requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session.request.return_value = mock_response
            mock_session_class.return_value = mock_session
            
            # Make request that should be streamed
            response = client.post("/v1/chat/completions", json={"stream": True})
            
            # Verify streaming behavior
            mock_session.request.assert_called_once()
            assert response.status_code == 200
            
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
        # Mock error response from upstream for curl_cffi
        mock_response = Mock()
        mock_response.status_code = error_status
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = error_message
        mock_response.iter_content.return_value = [error_message.encode()]
        
        with patch('curl_cffi.requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session.request.return_value = mock_response
            mock_session_class.return_value = mock_session
            
            # Make request to proxy
            response = client.post("/v1/chat/completions", json={"test": "data"})
            
            # Verify error passthrough
            mock_session.request.assert_called_once()
            assert response.status_code == error_status
            assert error_message in response.text
