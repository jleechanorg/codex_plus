"""
Codex to Cerebras Request Format Transformer

Transforms Codex CLI requests to Cerebras/OpenAI-compatible format.
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

    # Model name mapping
    MODEL_MAP = {
        "gpt-5-codex": "llama-3.3-70b",
        "gpt-4": "llama-3.3-70b",
        "gpt-3.5-turbo": "llama-3.1-8b",
    }

    def __init__(self, default_model: str = "llama-3.3-70b"):
        """
        Initialize transformer.

        Args:
            default_model: Default Cerebras model to use if mapping not found
        """
        self.default_model = default_model

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
            cerebras_request["model"] = self._map_model(codex_request.get("model", "gpt-5-codex"))

            # 2. Transform messages (instructions + input → messages)
            cerebras_request["messages"] = self._transform_messages(
                codex_request.get("instructions", ""),
                codex_request.get("input", [])
            )

            # 3. Transform tools if present
            if "tools" in codex_request and codex_request["tools"]:
                cerebras_request["tools"] = self._transform_tools(codex_request["tools"])

            # 4. Copy compatible fields
            compatible_fields = ["stream", "tool_choice", "parallel_tool_calls", "temperature", "max_tokens"]
            for field in compatible_fields:
                if field in codex_request:
                    cerebras_request[field] = codex_request[field]

            # 5. Add defaults for optional fields
            if "temperature" not in cerebras_request:
                cerebras_request["temperature"] = 0.7
            if "max_tokens" not in cerebras_request:
                cerebras_request["max_tokens"] = 4096

            # Note: reasoning, store, include, prompt_cache_key, strict are intentionally dropped

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
            Cerebras model name (e.g., "llama-3.3-70b")
        """
        return self.MODEL_MAP.get(codex_model, self.default_model)

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
