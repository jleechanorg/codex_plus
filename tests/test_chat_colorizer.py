"""Tests for Claude-inspired chat stream colorization."""

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


def test_handles_multibyte_characters_split_across_chunks() -> None:
    payload = {
        "choices": [
            {
                "delta": {
                    "role": "assistant",
                    "content": "Hello 😀",
                }
            }
        ]
    }
    event_bytes = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
    emoji_bytes = "😀".encode("utf-8")
    start = event_bytes.find(emoji_bytes)
    assert start != -1, "Emoji bytes not found in payload"
    split_index = start + 2  # Split the multi-byte sequence across chunks
    chunks = [event_bytes[:split_index], event_bytes[split_index:]]

    colored_bytes = b"".join(apply_claude_colors(chunks))
    payload_out = _extract_payload(colored_bytes.decode("utf-8"))
    content = payload_out["choices"][0]["delta"]["content"]

    assert "😀" in content
    assert content.startswith(CLAUDE_CHAT_PALETTE.role_colors["assistant"])
    assert content.endswith(RESET)


def test_does_not_color_tool_call_arguments() -> None:
    payload = {
        "choices": [
            {
                "delta": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {
                                "name": "search",
                                "arguments": "{\"query\":\"hi\"}",
                            },
                        }
                    ],
                }
            }
        ]
    }
    raw_event = f"data: {json.dumps(payload)}\n\n"
    colored = _collect_colored_chunks(raw_event)
    payload_out = _extract_payload(colored)
    arguments = payload_out["choices"][0]["delta"]["tool_calls"][0]["function"]["arguments"]

    assert "\x1b[" not in arguments


def test_preserves_crlf_event_delimiters() -> None:
    payload = {
        "choices": [
            {
                "delta": {
                    "role": "assistant",
                    "content": "Hi",
                }
            }
        ]
    }
    raw_bytes = f"data: {json.dumps(payload)}\r\n\r\n".encode("utf-8")
    result = b"".join(apply_claude_colors([raw_bytes]))

    assert result.endswith(b"\r\n\r\n")
