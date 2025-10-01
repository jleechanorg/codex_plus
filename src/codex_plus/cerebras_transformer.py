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

    # Model name mapping - will use env CEREBRAS_MODEL or llama-3.3-70b as default
    MODEL_MAP = {
        # Map all Codex models to the configured Cerebras model (via __init__)
        # The actual mapping happens in _map_model which uses self.default_model
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

            # 3. Transform tools if present AND model supports tools
            # Note: qwen models don't support function calling, only llama models do
            if "tools" in codex_request and codex_request["tools"]:
                if self._model_supports_tools(model):
                    cerebras_request["tools"] = self._transform_tools(codex_request["tools"])
                    # Only include tool_choice if tools are present
                    if "tool_choice" in codex_request:
                        cerebras_request["tool_choice"] = codex_request["tool_choice"]
                    logger.info(f"✅ Tools included - {model} supports function calling")
                else:
                    logger.warning(f"⚠️  Tools stripped - {model} does not support function calling")

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
            # - parallel_tool_calls (not supported by Cerebras)
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
        logger.debug(f"Mapping {codex_model} → {self.default_model}")
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
        # Models that don't support function calling:
        # - qwen models (qwen-3-coder-480b, etc.)
        return model.startswith("llama") or model.startswith("gpt-oss")

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
        for input_msg in input_array:
            # Remove "type": "message" wrapper
            if input_msg.get("type") == "message":
                transformed_msg = {
                    "role": input_msg["role"]
                }

                # Flatten content array to string
                content = self._extract_content(input_msg.get("content", []))
                if content:
                    transformed_msg["content"] = content

                # Handle tool call responses if present
                if "tool_call_id" in input_msg:
                    transformed_msg["tool_call_id"] = input_msg["tool_call_id"]

                messages.append(transformed_msg)

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
            if content_item.get("type") == "input_text":
                text = content_item.get("text", "")
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
