"""
TDD Tests for Codex to Cerebras Request Transformer

These tests should FAIL initially (Red phase), then pass after implementation (Green phase).
"""
import pytest
import json
from pathlib import Path


# Import the transformer (will fail until implemented)
try:
    from codex_plus.cerebras_transformer import CodexToCerebrasTransformer
except ImportError:
    CodexToCerebrasTransformer = None


@pytest.fixture
def sample_codex_request():
    """Load real Codex request from captured payload"""
    request_file = Path("/tmp/codex_plus/cereb_conversion/request_payload.json")
    if request_file.exists():
        with open(request_file, 'r') as f:
            return json.load(f)
    # Minimal fallback if file doesn't exist
    return {
        "model": "gpt-5-codex",
        "instructions": "You are a helpful assistant.",
        "input": [{
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "Hello"}]
        }],
        "tools": [{
            "type": "function",
            "name": "test_tool",
            "description": "A test tool",
            "strict": False,
            "parameters": {"type": "object", "properties": {}}
        }],
        "reasoning": {"effort": "high"},
        "store": False,
        "stream": True
    }


@pytest.fixture
def transformer():
    """Create transformer instance"""
    if CodexToCerebrasTransformer is None:
        pytest.skip("CodexToCerebrasTransformer not implemented yet")
    return CodexToCerebrasTransformer()


class TestMessageTransformation:
    """Test message structure transformation"""

    def test_instructions_becomes_system_message(self, transformer, sample_codex_request):
        """Test that instructions field becomes system message in messages array"""
        result = transformer.transform_request(sample_codex_request)

        assert "messages" in result
        assert len(result["messages"]) > 0
        assert result["messages"][0]["role"] == "system"
        assert result["messages"][0]["content"] == sample_codex_request["instructions"]

    def test_input_array_flattened(self, transformer, sample_codex_request):
        """Test that input array is flattened to messages"""
        result = transformer.transform_request(sample_codex_request)

        # Should have system message + user messages from input
        expected_count = 1 + len(sample_codex_request["input"])
        assert len(result["messages"]) == expected_count

    def test_content_text_extracted(self, transformer):
        """Test that nested content structure is flattened to plain string"""
        codex_request = {
            "model": "gpt-5-codex",
            "instructions": "System prompt",
            "input": [{
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Part 1"},
                    {"type": "input_text", "text": "Part 2"}
                ]
            }]
        }

        result = transformer.transform_request(codex_request)

        user_msg = result["messages"][1]  # After system message
        assert user_msg["role"] == "user"
        # Should concatenate multiple text parts
        assert "Part 1" in user_msg["content"]
        assert "Part 2" in user_msg["content"]

    def test_message_type_wrapper_removed(self, transformer):
        """Test that 'type: message' wrapper is removed"""
        codex_request = {
            "model": "gpt-5-codex",
            "instructions": "System",
            "input": [{
                "type": "message",  # This should be removed
                "role": "user",
                "content": [{"type": "input_text", "text": "Hello"}]
            }]
        }

        result = transformer.transform_request(codex_request)

        # Result messages should not have "type" field
        for msg in result["messages"]:
            assert "type" not in msg


class TestToolTransformation:
    """Test tool format transformation"""

    def test_tools_nested_under_function(self, transformer):
        """Test that tools are restructured with nested function"""
        codex_request = {
            "model": "gpt-5-codex",
            "instructions": "System",
            "input": [],
            "tools": [{
                "type": "function",
                "name": "get_weather",
                "description": "Get weather",
                "strict": False,
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}}
                }
            }]
        }

        result = transformer.transform_request(codex_request)

        assert "tools" in result
        assert len(result["tools"]) == 1

        tool = result["tools"][0]
        assert tool["type"] == "function"
        assert "function" in tool  # Should be nested
        assert tool["function"]["name"] == "get_weather"
        assert tool["function"]["description"] == "Get weather"
        assert tool["function"]["parameters"] == codex_request["tools"][0]["parameters"]

    def test_strict_field_dropped(self, transformer):
        """Test that 'strict' field is removed from tools"""
        codex_request = {
            "model": "gpt-5-codex",
            "instructions": "System",
            "input": [],
            "tools": [{
                "type": "function",
                "name": "tool",
                "description": "desc",
                "strict": False,
                "parameters": {}
            }]
        }

        result = transformer.transform_request(codex_request)

        tool = result["tools"][0]
        # 'strict' should not appear anywhere in transformed tool
        assert "strict" not in tool
        assert "strict" not in tool.get("function", {})


class TestFieldFiltering:
    """Test that unsupported fields are dropped"""

    def test_reasoning_field_dropped(self, transformer, sample_codex_request):
        """Test that reasoning field is removed"""
        result = transformer.transform_request(sample_codex_request)
        assert "reasoning" not in result

    def test_store_field_dropped(self, transformer, sample_codex_request):
        """Test that store field is removed"""
        result = transformer.transform_request(sample_codex_request)
        assert "store" not in result

    def test_include_field_dropped(self, transformer):
        """Test that include field is removed"""
        codex_request = {
            "model": "gpt-5-codex",
            "instructions": "System",
            "input": [],
            "include": ["reasoning.encrypted_content"]
        }

        result = transformer.transform_request(codex_request)
        assert "include" not in result

    def test_prompt_cache_key_dropped(self, transformer):
        """Test that prompt_cache_key is removed"""
        codex_request = {
            "model": "gpt-5-codex",
            "instructions": "System",
            "input": [],
            "prompt_cache_key": "some-uuid"
        }

        result = transformer.transform_request(codex_request)
        assert "prompt_cache_key" not in result

    def test_compatible_fields_preserved(self, transformer, sample_codex_request):
        """Test that compatible fields are kept"""
        result = transformer.transform_request(sample_codex_request)

        # These should be preserved
        assert "stream" in result
        assert result["stream"] == sample_codex_request["stream"]

        if "tool_choice" in sample_codex_request:
            assert "tool_choice" in result

        if "parallel_tool_calls" in sample_codex_request:
            assert "parallel_tool_calls" in result


class TestModelMapping:
    """Test model name transformation"""

    def test_codex_model_mapped_to_cerebras(self, transformer):
        """Test that gpt-5-codex is mapped to appropriate Cerebras model"""
        codex_request = {
            "model": "gpt-5-codex",
            "instructions": "System",
            "input": []
        }

        result = transformer.transform_request(codex_request)

        # Should be mapped to a Cerebras model
        assert result["model"] != "gpt-5-codex"
        # Check that it's a valid Cerebras model name
        assert "llama" in result["model"].lower() or "qwen" in result["model"].lower()


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_input_array(self, transformer):
        """Test handling of empty input array"""
        codex_request = {
            "model": "gpt-5-codex",
            "instructions": "System",
            "input": []  # Empty
        }

        result = transformer.transform_request(codex_request)

        # Should have at least system message
        assert len(result["messages"]) >= 1
        assert result["messages"][0]["role"] == "system"

    def test_missing_instructions(self, transformer):
        """Test handling when instructions field is missing"""
        codex_request = {
            "model": "gpt-5-codex",
            # instructions missing
            "input": [{
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Hello"}]
            }]
        }

        result = transformer.transform_request(codex_request)

        # Should still work, just no system message
        assert "messages" in result

    def test_multimodal_content_handling(self, transformer):
        """Test handling of non-text content types"""
        codex_request = {
            "model": "gpt-5-codex",
            "instructions": "System",
            "input": [{
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Look at this"},
                    {"type": "image", "data": "base64..."}  # Non-text content
                ]
            }]
        }

        # For now, should handle gracefully (may skip or error)
        # Implementation decision: skip non-text or preserve?
        result = transformer.transform_request(codex_request)
        assert "messages" in result

    def test_malformed_input_handles_gracefully(self, transformer):
        """Test that minimal input is handled gracefully with defaults"""
        codex_request = {
            "model": "gpt-5-codex",
            # Missing instructions and input - should still work
        }

        result = transformer.transform_request(codex_request)

        # Should still produce valid output with defaults
        assert "model" in result
        assert "messages" in result
        assert "temperature" in result
        assert "max_tokens" in result


class TestEndToEndTransformation:
    """Integration tests for complete transformation"""

    def test_full_transformation_with_real_data(self, transformer, sample_codex_request):
        """Test complete transformation with real captured Codex request"""
        result = transformer.transform_request(sample_codex_request)

        # Validate overall structure
        assert "model" in result
        assert "messages" in result
        assert isinstance(result["messages"], list)
        assert len(result["messages"]) > 0

        # Validate no Codex-specific fields remain
        assert "instructions" not in result
        assert "input" not in result
        assert "reasoning" not in result
        assert "store" not in result

        # Validate tools if present
        if "tools" in result:
            for tool in result["tools"]:
                assert "function" in tool
                assert "strict" not in tool

        print("\n=== Transformed Request ===")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
