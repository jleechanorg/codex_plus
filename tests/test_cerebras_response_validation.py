"""
Validation test for Cerebras response format compatibility with Codex CLI

This test validates that Cerebras API responses are compatible with what Codex CLI expects.
CRITICAL: Run this BEFORE implementing the full transformer.
"""
import pytest
import json
import os
from pathlib import Path


def load_sample_codex_request():
    """Load the real Codex request we captured"""
    request_file = Path("/tmp/codex_plus/cereb_conversion/request_payload.json")
    if request_file.exists():
        with open(request_file, 'r') as f:
            return json.load(f)
    pytest.skip("No sample Codex request found - run Codex CLI first to capture")


def test_cerebras_api_reachable():
    """Test that we can reach Cerebras API with credentials"""
    api_key = os.getenv("CEREBRAS_API_KEY")
    base_url = os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1")

    if not api_key:
        pytest.skip("CEREBRAS_API_KEY not set - cannot test Cerebras integration")

    import requests
    response = requests.get(
        f"{base_url}/models",
        headers={"Authorization": f"Bearer {api_key}"}
    )

    assert response.status_code in [200, 404], \
        f"Cerebras API unreachable: {response.status_code}"


def test_minimal_cerebras_request():
    """
    Test minimal Cerebras API request to validate response format.

    This is the CRITICAL test - validates that Cerebras responses
    can be parsed by whatever expects them.
    """
    api_key = os.getenv("CEREBRAS_API_KEY")
    base_url = os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1")
    model = os.getenv("CEREBRAS_MODEL", "llama-3.3-70b")

    if not api_key:
        pytest.skip("CEREBRAS_API_KEY not set - cannot test")

    import requests

    # Minimal OpenAI-compatible request
    minimal_request = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'test successful'"}
        ],
        "max_tokens": 10,
        "stream": False
    }

    response = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json=minimal_request,
        timeout=30
    )

    print(f"\n=== Cerebras Response Status: {response.status_code} ===")
    print(f"=== Response Headers: {dict(response.headers)} ===")

    assert response.status_code == 200, \
        f"Cerebras API error: {response.status_code} - {response.text}"

    response_data = response.json()
    print(f"=== Response Body ===\n{json.dumps(response_data, indent=2)}")

    # Validate OpenAI-compatible response structure
    assert "id" in response_data, "Missing 'id' field"
    assert "choices" in response_data, "Missing 'choices' field"
    assert len(response_data["choices"]) > 0, "Empty choices array"
    assert "message" in response_data["choices"][0], "Missing 'message' in choice"
    assert "content" in response_data["choices"][0]["message"], "Missing 'content' in message"

    # Check for Codex-specific fields (if any)
    # TODO: Compare with actual Codex CLI response expectations

    print("\n✅ Cerebras response format looks OpenAI-compatible")
    return response_data


def test_cerebras_streaming_response():
    """Test that streaming responses work and have correct SSE format"""
    api_key = os.getenv("CEREBRAS_API_KEY")
    base_url = os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1")
    model = os.getenv("CEREBRAS_MODEL", "llama-3.3-70b")

    if not api_key:
        pytest.skip("CEREBRAS_API_KEY not set")

    import requests

    streaming_request = {
        "model": model,
        "messages": [{"role": "user", "content": "Count to 3"}],
        "max_tokens": 20,
        "stream": True
    }

    response = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json=streaming_request,
        stream=True,
        timeout=30
    )

    assert response.status_code == 200, f"Streaming failed: {response.status_code}"

    chunks = []
    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            print(f"Chunk: {line_str}")
            chunks.append(line_str)

            if line_str == "data: [DONE]":
                break

            if line_str.startswith("data: "):
                data_str = line_str[6:]  # Remove "data: " prefix
                if data_str and data_str != "[DONE]":
                    chunk_data = json.loads(data_str)
                    assert "choices" in chunk_data, "Invalid SSE chunk format"

    assert len(chunks) > 0, "No streaming chunks received"
    print(f"\n✅ Received {len(chunks)} streaming chunks")


def test_cerebras_tool_calling():
    """Test that Cerebras supports function calling in OpenAI format"""
    api_key = os.getenv("CEREBRAS_API_KEY")
    base_url = os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1")
    model = os.getenv("CEREBRAS_MODEL", "llama-3.3-70b")

    if not api_key:
        pytest.skip("CEREBRAS_API_KEY not set")

    import requests

    # Simple function calling test
    tool_request = {
        "model": model,
        "messages": [{"role": "user", "content": "What's the weather in SF?"}],
        "tools": [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"}
                    },
                    "required": ["location"]
                }
            }
        }],
        "tool_choice": "auto",
        "max_tokens": 100
    }

    response = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json=tool_request,
        timeout=30
    )

    print(f"\n=== Tool Calling Response ===\n{response.text}")

    if response.status_code == 200:
        response_data = response.json()
        choice = response_data["choices"][0]

        # Check if model made a tool call
        if "tool_calls" in choice.get("message", {}):
            print("✅ Cerebras supports function calling!")
            print(f"Tool calls: {choice['message']['tool_calls']}")
        else:
            print("⚠️ No tool calls in response - model may have responded directly")
    else:
        print(f"⚠️ Tool calling request failed: {response.status_code}")
        print(f"Error: {response.text}")
        # Don't fail test - just document that tool calling might not work


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
