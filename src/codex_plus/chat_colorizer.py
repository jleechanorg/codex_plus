"""Utilities for coloring streaming chat output like Claude Code CLI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Mapping, Optional, Sequence

from .claude_palette import RESET, ensure_role_colors


@dataclass
class ChoiceState:
    """Track palette state for each streamed choice."""

    role: str = "assistant"


class ClaudeSSEColorizer:
    """Inject Claude CLI ANSI colors into streamed SSE chat payloads."""

    def __init__(self, role_colors: Optional[Mapping[str, str]] = None) -> None:
        self._role_colors = ensure_role_colors(role_colors)
        self._choice_state: Dict[int, ChoiceState] = {}
        self._buffer = bytearray()

    def iter_colorized(self, chunks: Iterable[bytes]) -> Iterator[bytes]:
        """Yield colorized SSE chunks from an iterable of raw chunks."""

        delimiter = b"\n\n"
        alt_delimiter = b"\r\n\r\n"

        for chunk in chunks:
            if not chunk:
                continue
            self._buffer.extend(chunk)

            while True:
                index = self._buffer.find(delimiter)
                delim_len = len(delimiter)
                delim_bytes = delimiter
                if index == -1:
                    index = self._buffer.find(alt_delimiter)
                    if index == -1:
                        break
                    delim_len = len(alt_delimiter)
                    delim_bytes = alt_delimiter
                event_bytes = self._buffer[:index]
                # Remove the delimiter from the buffer
                self._buffer = self._buffer[index + delim_len :]
                yield self._process_event(event_bytes, delim_bytes)

        if self._buffer:
            remainder = bytes(self._buffer)
            self._buffer.clear()
            yield remainder

    def _process_event(self, event_bytes: bytes, delimiter: bytes = b"\n\n") -> bytes:
        try:
            event_text = event_bytes.decode("utf-8")
        except UnicodeDecodeError:
            # If decoding fails, pass the original bytes through untouched.
            return event_bytes + delimiter

        delimiter_text = delimiter.decode("utf-8", errors="ignore") or "\n\n"
        line_separator = "\r\n" if delimiter_text.endswith("\r\n\r\n") else "\n"

        stripped = event_text.strip()
        if not stripped:
            return (event_text + delimiter_text).encode("utf-8")

        lines = event_text.splitlines()
        other_lines: List[str] = []
        data_lines: List[str] = []

        for line in lines:
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
            else:
                other_lines.append(line)

        if not data_lines:
            return (event_text + delimiter_text).encode("utf-8")

        data_payload = "\n".join(data_lines)
        if data_payload.strip() == "[DONE]":
            return (event_text + delimiter_text).encode("utf-8")

        try:
            parsed = json.loads(data_payload)
        except json.JSONDecodeError:
            return (event_text + delimiter_text).encode("utf-8")

        modified = self._colorize_payload(parsed)
        if not modified:
            return (event_text + delimiter_text).encode("utf-8")

        new_payload = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
        serialized_lines = other_lines + [f"data: {line}" for line in new_payload.split("\n")]
        return (line_separator.join(serialized_lines) + delimiter_text).encode("utf-8")

    def _colorize_payload(self, payload: object) -> bool:
        if not isinstance(payload, dict):
            return False

        choices = payload.get("choices")
        if not isinstance(choices, list):
            return False

        modified = False
        for idx, choice in enumerate(choices):
            if not isinstance(choice, dict):
                continue
            if self._colorize_choice(idx, choice):
                modified = True

        return modified

    def _colorize_choice(self, idx: int, choice: Dict) -> bool:
        state = self._choice_state.setdefault(idx, ChoiceState())
        modified = False

        role = state.role
        for key in ("delta", "message"):
            section = choice.get(key)
            if isinstance(section, dict) and isinstance(section.get("role"), str):
                role = section["role"]
                state.role = role

        role_color = self._role_colors.get(role, self._role_colors.get("assistant"))
        if not role_color:
            return False

        if "delta" in choice and isinstance(choice["delta"], dict):
            if self._colorize_content(choice["delta"], role, role_color):
                modified = True
        if "message" in choice and isinstance(choice["message"], dict):
            if self._colorize_content(choice["message"], role, role_color):
                modified = True
        if isinstance(choice.get("text"), str):
            colored, changed = self._wrap_text(choice["text"], role)
            if changed:
                choice["text"] = colored
                modified = True

        return modified

    def _colorize_content(self, section: Dict, role: str, role_color: str) -> bool:
        modified = False
        content = section.get("content")
        if isinstance(content, str):
            colored, changed = self._wrap_text(content, role)
            if changed:
                section["content"] = colored
                modified = True
        elif isinstance(content, list):
            if self._colorize_content_list(content, role):
                modified = True

        if "tool_calls" in section:
            tool_calls = section.get("tool_calls")
            if isinstance(tool_calls, list):
                if self._colorize_tool_calls(tool_calls):
                    modified = True

        return modified

    def _colorize_content_list(self, items: Sequence[object], role: str) -> bool:
        modified = False
        for item in items:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "text" and isinstance(item.get("text"), str):
                colored, changed = self._wrap_text(item["text"], role)
                if changed:
                    item["text"] = colored
                    modified = True
            elif item_type == "tool_result":
                if self._apply_color_to_field(item, "content", "tool_result"):
                    modified = True
            elif item_type == "tool_use":
                if self._apply_color_to_field(item, "name", "tool"):
                    modified = True
        return modified

    def _colorize_tool_calls(self, tool_calls: Sequence[object]) -> bool:
        modified = False
        for call in tool_calls:
            if not isinstance(call, dict):
                continue
            if call.get("type") == "function":
                function = call.get("function")
                if isinstance(function, dict):
                    if self._apply_color_to_field(function, "name", "tool"):
                        modified = True
        return modified

    def _apply_color_to_field(self, container: Dict, key: str, role: str) -> bool:
        value = container.get(key)
        if isinstance(value, str):
            colored, changed = self._wrap_text(value, role)
            if changed:
                container[key] = colored
                return True
        return False

    def _wrap_text(self, text: str, role: str) -> (str, bool):
        if not text:
            return text, False
        if "\x1b[" in text:
            return text, False
        color = self._role_colors.get(role, self._role_colors.get("assistant"))
        if not color:
            return text, False
        return f"{color}{text}{RESET}", True


def apply_claude_colors(chunks: Iterable[bytes], role_colors: Optional[Mapping[str, str]] = None) -> Iterator[bytes]:
    """Apply Claude CLI color theming to an iterable of SSE chunks."""

    colorizer = ClaudeSSEColorizer(role_colors)
    return colorizer.iter_colorized(chunks)


__all__ = ["ClaudeSSEColorizer", "apply_claude_colors"]

