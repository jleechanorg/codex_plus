"""
Codex to OpenAI-Compatible Request Format Transformer

Transforms Codex CLI requests to OpenAI-compatible format (Cerebras, gpt-oss, DeepSeek, etc.).
Based on specification in docs/codex_to_cerebras_transformation.md
"""
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class TransformationError(Exception):
    """Raised when request transformation fails"""
    pass


class CodexToCerebrasTransformer:
    """
    Transforms Codex CLI requests to Cerebras/OpenAI format.

    Key transformations:
    - instructions + input[] → messages[]
    - Flat tools → nested under 'function'
    - Drop unsupported fields (reasoning, store, include, prompt_cache_key, strict)
    - Map model names
    """

    # Model name mapping - use explicit Cerebras equivalents when known, otherwise
    # fall back to the configured default model (env override or class default).
    MODEL_MAP: Dict[str, str] = {
        "gpt-5-codex": "llama-3.3-70b",
        "gpt-4.1-codex": "llama-3.1-70b",
        "gpt-4-codex": "llama-3.1-70b",
        "gpt-4.1-mini": "llama-3.1-8b",
    }

    def __init__(self, default_model: str = None):
        """
        Initialize transformer.

        Args:
            default_model: Default Cerebras model to use if mapping not found.
                          If None, reads from CEREBRAS_MODEL env var or defaults to llama-3.3-70b
        """
        import os
        if default_model is None:
            # Read from environment variable, default to gpt-oss-120b (OpenAI's open-source model)
            default_model = os.getenv("CEREBRAS_MODEL", "gpt-oss-120b")
        
        self.default_model = default_model
        logger.info(f"🔧 Using Cerebras model: {self.default_model}")

    def transform_request(self, codex_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform complete Codex request to Cerebras format.

        Args:
            codex_request: Codex CLI request payload

        Returns:
            Cerebras/OpenAI compatible request payload

        Raises:
            TransformationError: If transformation fails
        """
        try:
            cerebras_request = {}

            # 1. Transform model name
            model = self._map_model(codex_request.get("model", "gpt-5-codex"))
            cerebras_request["model"] = model

            # 2. Transform messages (instructions + input → messages)
            cerebras_request["messages"] = self._transform_messages(
                codex_request.get("instructions", ""),
                codex_request.get("input", [])
            )

            # 3. Transform tools when present. Keep metadata even if the target
            # model may not execute tool calls so downstream layers can decide.
            if "tools" in codex_request and codex_request["tools"]:
                cerebras_request["tools"] = self._transform_tools(codex_request["tools"])

                if "tool_choice" in codex_request:
                    cerebras_request["tool_choice"] = codex_request["tool_choice"]

                if "parallel_tool_calls" in codex_request:
                    cerebras_request["parallel_tool_calls"] = codex_request["parallel_tool_calls"]

                if not self._model_supports_tools(model):
                    logger.warning(
                        f"⚠️  {model} may not support function calling; keeping tool metadata for compatibility"
                    )
                else:
                    logger.info(f"✅ Tools included - {model} supports function calling")

            # 4. Copy compatible fields only
            compatible_fields = ["stream", "temperature", "max_tokens"]
            for field in compatible_fields:
                if field in codex_request:
                    cerebras_request[field] = codex_request[field]

            # 5. Add defaults for optional fields
            if "temperature" not in cerebras_request:
                cerebras_request["temperature"] = 0.7
            if "max_tokens" not in cerebras_request:
                cerebras_request["max_tokens"] = 4096

            # Note: Explicitly dropping Cerebras-unsupported fields that cause 400 errors:
            # - frequency_penalty (not supported by Cerebras)
            # - logit_bias (not supported by Cerebras)
            # - presence_penalty (not supported by Cerebras)
            # - service_tier (not supported by Cerebras)
            # Also dropping Codex-specific fields:
            # - reasoning, store, include, prompt_cache_key, strict

            logger.debug(f"Transformed request: {len(cerebras_request['messages'])} messages, "
                        f"{len(cerebras_request.get('tools', []))} tools")

            return cerebras_request

        except Exception as e:
            raise TransformationError(f"Failed to transform request: {e}") from e

    def _map_model(self, codex_model: str) -> str:
        """
        Map Codex model name to Cerebras model name.

        Args:
            codex_model: Codex model name (e.g., "gpt-5-codex")

        Returns:
            Cerebras model name (e.g., "qwen-3-coder-480b")
        """
        # For now, all models map to the configured default model
        # This is typically set from CEREBRAS_MODEL env var
        mapped_model = self.MODEL_MAP.get(codex_model)
        if mapped_model:
            logger.debug(f"Mapping {codex_model} → {mapped_model}")
            return mapped_model

        logger.debug(f"Mapping {codex_model} → {self.default_model} (default)")
        return self.default_model

    def _model_supports_tools(self, model: str) -> bool:
        """
        Check if a model supports function calling (tools).

        Args:
            model: Model name

        Returns:
            True if model supports tools, False otherwise
        """
        # Models that support function calling:
        # - llama models (llama-3.3-70b, etc.)
        # - gpt-oss models (gpt-oss-120b, gpt-oss-20b)
        # - Some qwen coder models expose function calling for compatibility
        return (
            model.startswith("llama")
            or model.startswith("gpt-oss")
            or model.startswith("qwen")
        )

    def _transform_messages(self, instructions: str, input_array: List[Dict]) -> List[Dict]:
        """
        Transform Codex instructions + input to OpenAI messages format.

        Codex format:
            instructions: "System prompt"
            input: [{type: "message", role: "user", content: [{type: "input_text", text: "..."}]}]

        OpenAI format:
            messages: [{role: "system", content: "..."}, {role: "user", content: "..."}]

        Args:
            instructions: System instructions from Codex
            input_array: Array of Codex input messages

        Returns:
            List of OpenAI-formatted messages
        """
        messages = []

        # 1. Add system message from instructions
        if instructions:
            messages.append({
                "role": "system",
                "content": instructions
            })

        # 2. Transform each input message
        for input_msg in input_array or []:
            msg_type = input_msg.get("type")

            if msg_type == "message":
                transformed_msg = {
                    "role": input_msg.get("role", "user")
                }

                # Flatten content array to string
                content = self._extract_content(input_msg.get("content", []))
                if content:
                    transformed_msg["content"] = content

                # Preserve tool_call_id for tool responses
                if "tool_call_id" in input_msg:
                    transformed_msg["tool_call_id"] = input_msg["tool_call_id"]

                messages.append(transformed_msg)

            elif msg_type == "function_call":
                tool_call_id = input_msg.get("call_id") or input_msg.get("id")
                function_name = input_msg.get("name")
                arguments = input_msg.get("arguments", "")
                if not isinstance(arguments, str):
                    # Ensure arguments are serialized as string per OpenAI schema
                    import json as _json
                    try:
                        arguments = _json.dumps(arguments)
                    except Exception:
                        arguments = str(arguments)

                tool_call = {
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": function_name,
                        "arguments": arguments or "{}"
                    }
                }

                messages.append({
                    "role": "assistant",
                    "tool_calls": [tool_call]
                })

            elif msg_type == "function_call_output":
                messages.append({
                    "role": "tool",
                    "tool_call_id": input_msg.get("call_id"),
                    "content": input_msg.get("output", "")
                })

            elif msg_type == "reasoning":
                reasoning_text = self._extract_reasoning_summary(input_msg)
                if reasoning_text:
                    messages.append({
                        "role": "assistant",
                        "content": reasoning_text,
                        "name": "reasoning"
                    })

            else:
                # Preserve unknown message types as assistant commentary for transparency
                fallback_content = self._extract_content(input_msg.get("content", []))
                if fallback_content:
                    messages.append({
                        "role": input_msg.get("role", "assistant"),
                        "content": fallback_content
                    })

        return messages

    def _extract_content(self, content_array: List[Dict]) -> str:
        """
        Extract text content from Codex content array.

        Codex content format:
            [{type: "input_text", text: "Part 1"}, {type: "input_text", text: "Part 2"}]

        OpenAI content format:
            "Part 1\n\nPart 2"

        Args:
            content_array: Array of content objects

        Returns:
            Concatenated text content
        """
        text_parts = []

        for content_item in content_array:
            text = content_item.get("text")
            if text:
                text_parts.append(text)
            # Ignore other types (image, etc.) for now
            # TODO: Handle multimodal content if Cerebras supports it

        return "\n\n".join(text_parts)

    def _transform_tools(self, codex_tools: List[Dict]) -> List[Dict]:
        """
        Transform Codex tools to OpenAI format.

        Codex format:
            {type: "function", name: "...", description: "...", strict: false, parameters: {...}}

        OpenAI format:
            {type: "function", function: {name: "...", description: "...", parameters: {...}}}

        Args:
            codex_tools: List of Codex tool definitions

        Returns:
            List of OpenAI-formatted tools
        """
        openai_tools = []

        for codex_tool in codex_tools:
            openai_tool = {
                "type": codex_tool.get("type", "function")
            }

            # Nest tool properties under "function" key
            function_def = {
                "name": codex_tool["name"],
                "description": codex_tool.get("description", ""),
                "parameters": codex_tool.get("parameters", {})
            }

            openai_tool["function"] = function_def

            # Note: "strict" field is intentionally dropped (Codex-specific)

            openai_tools.append(openai_tool)

        return openai_tools

    def _extract_reasoning_summary(self, reasoning_block: Dict[str, Any]) -> Optional[str]:
        """Extract human-readable reasoning summary when available."""
        summary_items = reasoning_block.get("summary") or []
        texts: List[str] = []
        for item in summary_items:
            text = item.get("text") if isinstance(item, dict) else None
            if text:
                texts.append(text)

        if texts:
            return "\n".join(texts)

        encrypted = reasoning_block.get("encrypted_content")
        if encrypted:
            return "[encrypted reasoning content omitted]"

        return None
