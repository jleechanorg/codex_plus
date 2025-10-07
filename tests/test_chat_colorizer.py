"""Tests for Claude-inspired chat stream colourisation."""

import json

from src.codex_plus.chat_colorizer import apply_claude_colors
from src.codex_plus.claude_palette import CLAUDE_CHAT_PALETTE, RESET


def _collect_colored_chunks(raw: str) -> str:
    chunks = [raw.encode("utf-8")]
    colored_bytes = b"".join(apply_claude_colors(chunks))
    return colored_bytes.decode("utf-8")


def _extract_payload(colored_event: str) -> dict:
    lines = [line.strip() for line in colored_event.strip().splitlines() if line.startswith("data:")]
    assert lines, "Expected at least one data line"
    data_str = "\n".join(line[5:].lstrip() for line in lines)
    return json.loads(data_str)


def test_colorizes_simple_assistant_delta() -> None:
    raw_event = 'data: {"choices":[{"delta":{"role":"assistant","content":"Hello"}}]}' + "\n\n"
    colored = _collect_colored_chunks(raw_event)
    payload = _extract_payload(colored)
    content = payload["choices"][0]["delta"]["content"]
    assert content.startswith(CLAUDE_CHAT_PALETTE.role_colors["assistant"])
    assert content.endswith(RESET)


def test_colorizes_user_role_content_list() -> None:
    raw_event = (
        'data: {"choices":[{"delta":{"role":"user","content":[{"type":"text","text":"Question"}]}}]}'
        "\n\n"
    )
    colored = _collect_colored_chunks(raw_event)
    payload = _extract_payload(colored)
    content_item = payload["choices"][0]["delta"]["content"][0]["text"]
    assert content_item.startswith(CLAUDE_CHAT_PALETTE.role_colors["user"])
    assert content_item.endswith(RESET)


def test_passes_done_event_through() -> None:
    done_event = "data: [DONE]\n\n"
    result = b"".join(apply_claude_colors([done_event.encode("utf-8")]))
    assert result.decode("utf-8").strip() == "data: [DONE]"


def test_colors_tool_result_items() -> None:
    raw_event = (
        'data: {'
        '"choices":[{' \
        '"delta":{"role":"assistant","content":['
        '{"type":"tool_result","content":"ok"}'
        ']}'
        '}]}'
        "\n\n"
    )
    colored = _collect_colored_chunks(raw_event)
    payload = _extract_payload(colored)
    result_text = payload["choices"][0]["delta"]["content"][0]["content"]
    assert result_text.startswith(CLAUDE_CHAT_PALETTE.role_colors["tool_result"])
    assert result_text.endswith(RESET)


def test_preserves_existing_ansi_sequences() -> None:
    raw_event = (
        'data: {'
        '"choices":[{' \
        '"delta":{"role":"assistant","content":"\\u001b[38;2;1;1;1mHello"}'
        '}]}'
        "\n\n"
    )
    colored = _collect_colored_chunks(raw_event)
    payload = _extract_payload(colored)
    content = payload["choices"][0]["delta"]["content"]
    assert content == "\u001b[38;2;1;1;1mHello"
