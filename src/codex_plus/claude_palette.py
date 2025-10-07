"""Shared Claude Code CLI palette helpers.

This module centralises the 24-bit ANSI escape sequences that emulate the
official Claude Code CLI brand colours.  It exposes convenience utilities for
converting hex triplets to escape sequences, stripping ANSI codes, and mapping
chat roles to their canonical colours so other modules (chat streaming,
status-line renderers, etc.) can stay consistent.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, Mapping, Optional

RESET = "\x1b[0m"

ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def _rgb_escape(r: int, g: int, b: int) -> str:
    """Return a 24-bit ANSI foreground colour escape sequence."""

    return f"\x1b[38;2;{r};{g};{b}m"


def hex_to_ansi(hex_color: str) -> str:
    """Convert a #RRGGBB style hex string into a 24-bit ANSI sequence."""

    hex_color = hex_color.strip().lstrip("#")
    if len(hex_color) != 6:
        raise ValueError(f"Invalid hex colour value: {hex_color!r}")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return _rgb_escape(r, g, b)


def strip_ansi(text: Optional[str]) -> Optional[str]:
    """Remove ANSI escape codes from *text* while keeping the raw content."""

    if text is None:
        return None
    return ANSI_PATTERN.sub("", text)


@dataclass(frozen=True)
class ChatPalette:
    """Represents the Claude CLI chat palette mapping roles to ANSI escapes."""

    role_colors: Mapping[str, str]

    def color_for(self, role: str, fallback_role: str = "assistant") -> str:
        mapping = self.role_colors
        if role in mapping:
            return mapping[role]
        return mapping.get(fallback_role, next(iter(mapping.values())))


# Claude Code CLI role colours derived from sampled CLI output frames.  The
# palette balances readability with the brand accents Anthropic ship in the
# official tool: lavender for Claude, cyan for the user, amber for tools, and a
# muted mint for observations.
_CHAT_ROLE_HEX: Dict[str, str] = {
    "assistant": "#BDA6FF",  # Lavender accent used for Claude responses
    "assistant_label": "#E4D9FF",  # Brighter lavender for assistant name tags
    "user": "#6CD9FF",  # Cyan used for prompts in the CLI transcript
    "user_label": "#B4F0FF",
    "system": "#93A1AD",  # Muted slate for scaffolding/system notices
    "developer": "#FF8BC0",  # Pink accent for developer directives
    "tool": "#F5B971",  # Amber for tool invocation metadata
    "function": "#F5B971",
    "tool_result": "#7FE3AE",  # Mint for tool result / observation blocks
    "observation": "#7FE3AE",
    "error": "#FF7A7A",  # Soft red for failures or exceptions
}

CLAUDE_CHAT_PALETTE = ChatPalette({role: hex_to_ansi(color) for role, color in _CHAT_ROLE_HEX.items()})


def ensure_role_colors(mapping: Optional[Mapping[str, str]] = None) -> Mapping[str, str]:
    """Return a role→ANSI mapping, defaulting to the shared CLAUDE palette."""

    return mapping if mapping is not None else CLAUDE_CHAT_PALETTE.role_colors


def apply_color(text: str, color: str) -> str:
    """Wrap *text* in the provided ANSI colour while guarding duplicates."""

    if not text or "\x1b[" in text:
        return text
    return f"{color}{text}{RESET}"


__all__ = [
    "ANSI_PATTERN",
    "ChatPalette",
    "CLAUDE_CHAT_PALETTE",
    "RESET",
    "apply_color",
    "ensure_role_colors",
    "hex_to_ansi",
    "strip_ansi",
]

