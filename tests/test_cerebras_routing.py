"""Tests for Cerebras provider routing helpers."""

import os
import tempfile
from unittest.mock import patch

import pytest


def test_cerebras_upstream_url_from_file():
    """_get_upstream_url should read a provider file when present."""
    from codex_plus.main_sync_cffi import _get_upstream_url

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".base_url") as handle:
        handle.write("https://api.cerebras.ai/v1")
        provider_path = handle.name

    try:
        with patch.dict(os.environ, {"CODEXPLUS_PROVIDER_BASE_URL_FILE": provider_path}, clear=False):
            assert _get_upstream_url() == "https://api.cerebras.ai/v1"
    finally:
        os.unlink(provider_path)


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
    """Fallback to ChatGPT URL if no overrides are configured."""
    from codex_plus.main_sync_cffi import _get_upstream_url

    with patch.dict(
        os.environ,
        {
            "CODEXPLUS_PROVIDER_BASE_URL_FILE": "/non-existent-path/base_url",
            "CODEX_PLUS_UPSTREAM_URL": "",
        },
        clear=False,
    ):
        url = _get_upstream_url()
        assert url == "https://chatgpt.com/backend-api/codex"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
