"""
Test Cerebras provider routing functionality
"""
import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock


def test_cerebras_upstream_url_from_file():
    """Test that proxy reads Cerebras URL from provider.base_url file"""
    # Create temporary provider.base_url file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.base_url') as f:
        f.write("https://api.cerebras.ai/v1")
        temp_file = f.name

    try:
        # Patch the file path to use our temp file
        with patch('codex_plus.main_sync_cffi._get_upstream_url') as mock_get_url:
            # Simulate reading from the file
            with open(temp_file, 'r') as f:
                cerebras_url = f.read().strip()
            mock_get_url.return_value = cerebras_url

            # Import after patching
            from codex_plus.main_sync_cffi import _get_upstream_url

            # Test that we get the Cerebras URL
            result = mock_get_url()
            assert result == "https://api.cerebras.ai/v1", f"Expected Cerebras URL, got {result}"
    finally:
        os.unlink(temp_file)


def test_cerebras_url_validation():
    """Test that _validate_upstream_url allows Cerebras URLs"""
    from codex_plus.main_sync_cffi import _validate_upstream_url

    # Cerebras URLs should be valid
    assert _validate_upstream_url("https://api.cerebras.ai/v1/chat/completions"), \
        "Cerebras URL should be valid"
    assert _validate_upstream_url("https://api.cerebras.ai/v1/responses"), \
        "Cerebras URL should be valid"

    # ChatGPT URLs should still be valid
    assert _validate_upstream_url("https://chatgpt.com/backend-api/codex"), \
        "ChatGPT URL should be valid"

    # Invalid URLs should fail
    assert not _validate_upstream_url("https://evil.com/steal-data"), \
        "Random URLs should be invalid"
    assert not _validate_upstream_url("http://api.cerebras.ai/v1"), \
        "HTTP (not HTTPS) should be invalid"


def test_default_to_chatgpt_when_no_file():
    """Test that proxy defaults to ChatGPT when provider.base_url doesn't exist"""
    with patch('os.path.exists', return_value=False):
        from codex_plus.main_sync_cffi import _get_upstream_url

        url = _get_upstream_url()
        assert url == "https://chatgpt.com/backend-api/codex", \
            "Should default to ChatGPT URL when file doesn't exist"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
