# Codex CLI to Cerebras/OpenAI Request Format Transformation

## Executive Summary

This document analyzes the request/response format differences between Codex CLI and Cerebras/OpenAI-compatible APIs, providing a complete transformation specification for building a format converter.

**Key Insight**: Codex uses a custom `/responses` endpoint with nested message structures and proprietary fields, while Cerebras follows the standard OpenAI `/v1/chat/completions` format with simpler message objects.

---

## 1. Endpoint Differences

| Aspect | Codex CLI | Cerebras/OpenAI |
|--------|-----------|-----------------|
| **Endpoint** | `/responses` | `/v1/chat/completions` |
| **Base URL** | `https://chatgpt.com/backend-api/codex` | `https://api.cerebras.ai/v1` |
| **Authentication** | Session cookies/JWT in headers | API key in `Authorization: Bearer <key>` header |

---

## 2. Request Body Format Comparison

### 2.1 Side-by-Side Structure

#### Codex CLI Request Format
```json
{
  "model": "gpt-5-codex",
  "instructions": "<system prompt>",
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "actual message text"
        }
      ]
    }
  ],
  "tools": [
    {
      "type": "function",
      "name": "shell",
      "description": "...",
      "strict": false,
      "parameters": { ... }
    }
  ],
  "tool_choice": "auto",
  "parallel_tool_calls": false,
  "reasoning": {
    "effort": "high",
    "summary": "auto"
  },
  "store": false,
  "stream": true,
  "include": ["reasoning.encrypted_content"],
  "prompt_cache_key": "01999c01-7338-7800-9a15-c1e76bf3bdd1"
}
```

#### Cerebras/OpenAI Request Format
```json
{
  "model": "llama-3.3-70b",
  "messages": [
    {
      "role": "system",
      "content": "<system prompt>"
    },
    {
      "role": "user",
      "content": "actual message text"
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "shell",
        "description": "...",
        "parameters": { ... }
      }
    }
  ],
  "tool_choice": "auto",
  "stream": true,
  "temperature": 0.7,
  "max_tokens": 4096
}
```

### 2.2 Key Differences Summary

| Feature | Codex Format | OpenAI/Cerebras Format | Transformation Required |
|---------|--------------|------------------------|-------------------------|
| **System Prompt** | `instructions` field (top-level) | First message with `role: "system"` | ✅ Merge into messages array |
| **Messages** | `input` array with nested structure | `messages` array with flat structure | ✅ Flatten and rename |
| **Content Structure** | Array of `{type, text}` objects | Plain string | ✅ Extract text from objects |
| **Message Type** | Has `type: "message"` wrapper | No type wrapper | ✅ Remove wrapper |
| **Tools Structure** | Flat: `{type, name, description, parameters, strict}` | Nested: `{type, function: {name, description, parameters}}` | ✅ Restructure |
| **Reasoning** | `{effort, summary}` object | Not supported | ❌ Drop field |
| **Store** | Boolean flag | Not supported | ❌ Drop field |
| **Include** | Array of field paths | Not supported | ❌ Drop field |
| **Prompt Cache** | `prompt_cache_key` UUID | Not supported | ❌ Drop field |
| **Tool Choice** | `"auto"` or object | `"auto"`, `"none"`, or object | ✅ Compatible |
| **Parallel Tool Calls** | Boolean | Not always supported | ⚠️ Check Cerebras support |
| **Streaming** | Boolean | Boolean | ✅ Compatible |

---

## 3. Detailed Transformation Rules

### 3.1 Message Transformation

**Rule**: Convert `instructions` + `input` → `messages`

```python
def transform_messages(codex_request):
    """
    Transform Codex input/instructions to OpenAI messages format.

    Args:
        codex_request: Dict with 'instructions' and 'input' fields

    Returns:
        List of message objects in OpenAI format
    """
    messages = []

    # Step 1: Add system message from instructions
    if "instructions" in codex_request:
        messages.append({
            "role": "system",
            "content": codex_request["instructions"]
        })

    # Step 2: Transform input array
    for input_msg in codex_request.get("input", []):
        # Remove "type": "message" wrapper
        transformed_msg = {
            "role": input_msg["role"]
        }

        # Flatten content array to string
        content_parts = []
        for content_item in input_msg.get("content", []):
            if content_item.get("type") == "input_text":
                content_parts.append(content_item["text"])
            # Handle other content types if needed (images, etc.)

        # Join multiple content parts (usually just one)
        transformed_msg["content"] = "\n\n".join(content_parts)

        messages.append(transformed_msg)

    return messages
```

**Example**:

Input (Codex):
```json
{
  "instructions": "You are a helpful assistant.",
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": [
        {"type": "input_text", "text": "Hello!"}
      ]
    }
  ]
}
```

Output (OpenAI):
```json
{
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ]
}
```

### 3.2 Tools Transformation

**Rule**: Restructure flat tools to nested format

```python
def transform_tools(codex_tools):
    """
    Transform Codex tools format to OpenAI tools format.

    Args:
        codex_tools: List of Codex tool objects

    Returns:
        List of OpenAI-compatible tool objects
    """
    if not codex_tools:
        return None

    openai_tools = []

    for tool in codex_tools:
        # Codex format: {type, name, description, strict, parameters}
        # OpenAI format: {type, function: {name, description, parameters}}

        openai_tool = {
            "type": tool["type"],  # Usually "function"
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {})
            }
        }

        # Note: "strict" field is dropped (Codex-specific)
        # Cerebras may not support structured outputs enforcement

        openai_tools.append(openai_tool)

    return openai_tools
```

**Example**:

Input (Codex):
```json
{
  "tools": [
    {
      "type": "function",
      "name": "shell",
      "description": "Runs a shell command",
      "strict": false,
      "parameters": {
        "type": "object",
        "properties": {
          "command": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["command"]
      }
    }
  ]
}
```

Output (OpenAI):
```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "shell",
        "description": "Runs a shell command",
        "parameters": {
          "type": "object",
          "properties": {
            "command": {"type": "array", "items": {"type": "string"}}
          },
          "required": ["command"]
        }
      }
    }
  ]
}
```

### 3.3 Model Name Mapping

**Rule**: Map Codex model names to Cerebras models

```python
MODEL_MAPPING = {
    "gpt-5-codex": "llama-3.3-70b",  # Default Cerebras model
    "gpt-4-codex": "llama-3.1-70b",
    # Add more mappings as needed
}

def transform_model_name(codex_model):
    """
    Map Codex model names to Cerebras equivalents.

    Args:
        codex_model: Codex model identifier

    Returns:
        Cerebras model identifier
    """
    return MODEL_MAPPING.get(codex_model, "llama-3.3-70b")
```

### 3.4 Top-Level Fields

**Rule**: Preserve compatible fields, drop Codex-specific fields

```python
def transform_top_level_fields(codex_request):
    """
    Transform top-level request fields.

    Args:
        codex_request: Full Codex request dict

    Returns:
        Dict with OpenAI-compatible top-level fields
    """
    openai_request = {}

    # Fields to preserve directly
    preserve_fields = ["stream", "tool_choice"]
    for field in preserve_fields:
        if field in codex_request:
            openai_request[field] = codex_request[field]

    # Fields to drop (Codex-specific)
    # - reasoning: Extended thinking config
    # - store: Conversation storage flag
    # - include: Field inclusion directives
    # - prompt_cache_key: Caching optimization
    # - parallel_tool_calls: May not be supported by Cerebras

    # Add standard OpenAI parameters if not present
    if "temperature" not in codex_request:
        openai_request["temperature"] = 0.7

    if "max_tokens" not in codex_request:
        openai_request["max_tokens"] = 4096

    return openai_request
```

### 3.5 Complete Transformation Function

```python
def transform_codex_to_openai(codex_request):
    """
    Complete transformation from Codex to OpenAI/Cerebras format.

    Args:
        codex_request: Full Codex request dict

    Returns:
        OpenAI-compatible request dict
    """
    openai_request = {}

    # 1. Transform model name
    openai_request["model"] = transform_model_name(
        codex_request.get("model", "gpt-5-codex")
    )

    # 2. Transform messages (instructions + input → messages)
    openai_request["messages"] = transform_messages(codex_request)

    # 3. Transform tools
    if "tools" in codex_request:
        openai_request["tools"] = transform_tools(codex_request["tools"])

    # 4. Handle top-level fields
    top_level = transform_top_level_fields(codex_request)
    openai_request.update(top_level)

    return openai_request
```

---

## 4. Response Format Transformation

### 4.1 Non-Streaming Response

Both formats are largely compatible for non-streaming responses:

**OpenAI Response**:
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "llama-3.3-70b",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 20,
    "total_tokens": 30
  }
}
```

**Transformation Notes**:
- Codex may expect different `finish_reason` values
- Tool calls format should be compatible but verify structure
- Response ID format may differ (not critical)

### 4.2 Streaming Response

Both use Server-Sent Events (SSE) format:

**OpenAI Stream Chunk**:
```
data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"llama-3.3-70b","choices":[{"index":0,"delta":{"role":"assistant","content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"llama-3.3-70b","choices":[{"index":0,"delta":{"content":"!"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"llama-3.3-70b","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

**Transformation**: Minimal changes needed, primarily field mapping:
- `object`: `"chat.completion.chunk"` (standard)
- `choices[].delta`: Contains incremental content
- Final chunk has `finish_reason`

---

## 5. Edge Cases and Challenges

### 5.1 Multimodal Content

**Challenge**: Codex may send images or other media in content arrays.

**Example** (Codex):
```json
{
  "content": [
    {"type": "input_text", "text": "What's in this image?"},
    {"type": "image", "source": {"type": "base64", "data": "..."}}
  ]
}
```

**OpenAI Format**:
```json
{
  "content": [
    {"type": "text", "text": "What's in this image?"},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
  ]
}
```

**Note**: Cerebras may not support vision models. Check model capabilities.

### 5.2 Tool Call Responses

**Challenge**: Ensure tool call format in responses matches expected structure.

**OpenAI Tool Call** (in response):
```json
{
  "role": "assistant",
  "content": null,
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "shell",
        "arguments": "{\"command\": [\"ls\", \"-la\"]}"
      }
    }
  ]
}
```

**Verification Needed**: Confirm Codex expects same structure for tool calls.

### 5.3 Reasoning Field

**Challenge**: Codex's `reasoning` field enables extended thinking (chain-of-thought).

```json
{
  "reasoning": {
    "effort": "high",
    "summary": "auto"
  }
}
```

**Options**:
1. **Drop entirely**: Cerebras doesn't support this
2. **Emulate via system prompt**: Add instructions for step-by-step reasoning
3. **Use specialized model**: Some models have built-in reasoning capabilities

**Recommendation**: Drop the field and optionally enhance system prompt with reasoning instructions.

### 5.4 Parallel Tool Calls

**Challenge**: Codex supports `parallel_tool_calls: false` to force sequential execution.

**Cerebras Support**: Unclear if supported. Test behavior:
- If unsupported, parameter is ignored (model decides)
- May need to handle parallel calls in proxy layer

### 5.5 Prompt Caching

**Challenge**: Codex uses `prompt_cache_key` for performance optimization.

```json
{
  "prompt_cache_key": "01999c01-7338-7800-9a15-c1e76bf3bdd1"
}
```

**Cerebras Alternative**: Check if Cerebras supports:
- `seed` parameter for deterministic outputs
- Native caching mechanisms

---

## 6. Implementation Checklist

### Phase 1: Request Transformation
- [ ] Implement `transform_messages()` function
- [ ] Implement `transform_tools()` function
- [ ] Implement `transform_model_name()` function
- [ ] Implement `transform_codex_to_openai()` orchestrator
- [ ] Add unit tests for each transformation function

### Phase 2: Response Handling
- [ ] Test non-streaming response compatibility
- [ ] Test streaming response (SSE) compatibility
- [ ] Verify tool call response format
- [ ] Handle error responses appropriately

### Phase 3: Edge Cases
- [ ] Handle multimodal content (if needed)
- [ ] Test parallel vs sequential tool calls
- [ ] Implement fallback for unsupported features
- [ ] Add logging for dropped fields

### Phase 4: Integration
- [ ] Add transformation middleware to proxy
- [ ] Implement model name configuration
- [ ] Add Cerebras API key handling
- [ ] Test end-to-end with real Codex CLI requests

---

## 7. Sample Code: Complete Transformer Class

```python
from typing import Dict, List, Any, Optional
import json

class CodexToCerebrasTransformer:
    """Transforms Codex CLI requests to Cerebras/OpenAI format."""

    MODEL_MAPPING = {
        "gpt-5-codex": "llama-3.3-70b",
        "gpt-4-codex": "llama-3.1-70b",
    }

    def __init__(self, default_model: str = "llama-3.3-70b"):
        self.default_model = default_model

    def transform_request(self, codex_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform complete Codex request to OpenAI format.

        Args:
            codex_request: Codex CLI request dict

        Returns:
            OpenAI/Cerebras compatible request dict
        """
        openai_request = {}

        # Model
        openai_request["model"] = self._transform_model(
            codex_request.get("model")
        )

        # Messages
        openai_request["messages"] = self._transform_messages(
            codex_request.get("instructions"),
            codex_request.get("input", [])
        )

        # Tools
        if "tools" in codex_request:
            openai_request["tools"] = self._transform_tools(
                codex_request["tools"]
            )

        # Tool choice
        if "tool_choice" in codex_request:
            openai_request["tool_choice"] = codex_request["tool_choice"]

        # Streaming
        if "stream" in codex_request:
            openai_request["stream"] = codex_request["stream"]

        # Standard parameters
        openai_request.setdefault("temperature", 0.7)
        openai_request.setdefault("max_tokens", 4096)

        return openai_request

    def _transform_model(self, codex_model: Optional[str]) -> str:
        """Map Codex model to Cerebras model."""
        if not codex_model:
            return self.default_model
        return self.MODEL_MAPPING.get(codex_model, self.default_model)

    def _transform_messages(
        self,
        instructions: Optional[str],
        input_messages: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Transform instructions + input to messages array."""
        messages = []

        # Add system message from instructions
        if instructions:
            messages.append({
                "role": "system",
                "content": instructions
            })

        # Transform input messages
        for msg in input_messages:
            transformed = {
                "role": msg["role"]
            }

            # Flatten content array
            content_parts = []
            for content_item in msg.get("content", []):
                if content_item.get("type") == "input_text":
                    content_parts.append(content_item["text"])
                # TODO: Handle other content types (images, etc.)

            transformed["content"] = "\n\n".join(content_parts)
            messages.append(transformed)

        return messages

    def _transform_tools(
        self,
        codex_tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Transform tools to OpenAI format."""
        openai_tools = []

        for tool in codex_tools:
            openai_tool = {
                "type": tool["type"],
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {})
                }
            }
            openai_tools.append(openai_tool)

        return openai_tools

# Usage example
if __name__ == "__main__":
    # Load sample Codex request
    with open("/tmp/codex_plus/cereb_conversion/request_payload.json") as f:
        codex_request = json.load(f)

    # Transform
    transformer = CodexToCerebrasTransformer()
    cerebras_request = transformer.transform_request(codex_request)

    # Display
    print(json.dumps(cerebras_request, indent=2))
```

---

## 8. Testing Strategy

### 8.1 Unit Tests

```python
import pytest
from transformer import CodexToCerebrasTransformer

def test_message_transformation():
    """Test basic message transformation."""
    transformer = CodexToCerebrasTransformer()
    codex_request = {
        "instructions": "You are helpful.",
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Hello"}
                ]
            }
        ]
    }

    result = transformer.transform_request(codex_request)

    assert len(result["messages"]) == 2
    assert result["messages"][0]["role"] == "system"
    assert result["messages"][0]["content"] == "You are helpful."
    assert result["messages"][1]["role"] == "user"
    assert result["messages"][1]["content"] == "Hello"

def test_tools_transformation():
    """Test tools format transformation."""
    transformer = CodexToCerebrasTransformer()
    codex_request = {
        "tools": [
            {
                "type": "function",
                "name": "test_tool",
                "description": "A test",
                "strict": false,
                "parameters": {"type": "object"}
            }
        ]
    }

    result = transformer.transform_request(codex_request)

    assert "tools" in result
    assert result["tools"][0]["type"] == "function"
    assert "function" in result["tools"][0]
    assert result["tools"][0]["function"]["name"] == "test_tool"
    assert "strict" not in result["tools"][0]

def test_model_mapping():
    """Test model name mapping."""
    transformer = CodexToCerebrasTransformer()
    codex_request = {"model": "gpt-5-codex"}

    result = transformer.transform_request(codex_request)

    assert result["model"] == "llama-3.3-70b"
```

### 8.2 Integration Tests

```python
def test_real_codex_request():
    """Test with actual Codex CLI request payload."""
    import json

    with open("/tmp/codex_plus/cereb_conversion/request_payload.json") as f:
        codex_request = json.load(f)

    transformer = CodexToCerebrasTransformer()
    cerebras_request = transformer.transform_request(codex_request)

    # Validate required fields
    assert "model" in cerebras_request
    assert "messages" in cerebras_request
    assert len(cerebras_request["messages"]) > 0

    # Validate dropped fields
    assert "instructions" not in cerebras_request
    assert "input" not in cerebras_request
    assert "reasoning" not in cerebras_request
    assert "store" not in cerebras_request
    assert "include" not in cerebras_request
    assert "prompt_cache_key" not in cerebras_request
```

---

## 9. Deployment Considerations

### 9.1 Performance

- **Transformation Overhead**: Minimal (< 1ms for typical requests)
- **Memory**: Message concatenation may increase memory for large conversations
- **Caching**: Lost prompt caching may impact performance (test with Cerebras alternatives)

### 9.2 Error Handling

```python
class TransformationError(Exception):
    """Raised when request transformation fails."""
    pass

def safe_transform(codex_request: Dict) -> Dict:
    """Transform with error handling."""
    try:
        transformer = CodexToCerebrasTransformer()
        return transformer.transform_request(codex_request)
    except KeyError as e:
        raise TransformationError(f"Missing required field: {e}")
    except Exception as e:
        raise TransformationError(f"Transformation failed: {e}")
```

### 9.3 Logging

```python
import logging

logger = logging.getLogger(__name__)

def transform_with_logging(codex_request: Dict) -> Dict:
    """Transform with detailed logging."""
    logger.info("Starting transformation")
    logger.debug(f"Input: {json.dumps(codex_request, indent=2)}")

    transformer = CodexToCerebrasTransformer()
    result = transformer.transform_request(codex_request)

    logger.info("Transformation complete")
    logger.debug(f"Output: {json.dumps(result, indent=2)}")

    # Log dropped fields
    dropped = set(codex_request.keys()) - set(result.keys())
    if dropped:
        logger.warning(f"Dropped Codex-specific fields: {dropped}")

    return result
```

---

## 10. Summary

### Transformation Pipeline

1. **Endpoint**: `/responses` → `/v1/chat/completions`
2. **Messages**: `instructions` + `input[]` → `messages[]` (flatten content, add system message)
3. **Tools**: Flat structure → Nested in `function` object (drop `strict` field)
4. **Model**: Map Codex model names → Cerebras model names
5. **Fields**: Drop `reasoning`, `store`, `include`, `prompt_cache_key`
6. **Preserve**: `stream`, `tool_choice`, standard parameters

### Key Challenges

1. **Reasoning field**: No direct equivalent in Cerebras (drop or emulate)
2. **Parallel tool calls**: Verify Cerebras support
3. **Prompt caching**: Lost optimization (test performance impact)
4. **Multimodal content**: May need special handling for images
5. **Authentication**: Session cookies → API key

### Next Steps

1. Implement transformer class with unit tests
2. Add middleware to proxy for request/response transformation
3. Test with real Codex CLI requests
4. Monitor performance and error rates
5. Document model capability differences (e.g., vision, reasoning)
