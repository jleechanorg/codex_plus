#!/usr/bin/env python3
"""
Compare outputs from passthrough and Cerebras proxies

Usage:
    python testing_integration/compare_proxies.py

Compares SSE event streams from:
- /tmp/codex_plus/chatgpt_responses/latest_response.txt (passthrough)
- /tmp/codex_plus/cerebras_responses/latest_response.txt (Cerebras)
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any


def parse_sse_events(log_file: Path) -> List[Dict[str, Any]]:
    """Parse SSE log into structured events"""
    events = []

    if not log_file.exists():
        print(f"❌ Log file not found: {log_file}")
        return events

    with open(log_file, 'rb') as f:
        content = f.read().decode('utf-8', errors='ignore')

    for line in content.split('\n'):
        if line.startswith('data: '):
            data_str = line[6:]  # Remove 'data: ' prefix

            if data_str == '[DONE]':
                events.append({"type": "stream_done", "data": "[DONE]"})
                continue

            try:
                event_data = json.loads(data_str)
                events.append(event_data)
            except json.JSONDecodeError:
                # Skip invalid JSON
                pass

    return events


def compare_event_types(chatgpt_events: List[Dict], cerebras_events: List[Dict]) -> bool:
    """Compare event types between two streams"""

    print(f"\n📊 Event Count Comparison:")
    print(f"  ChatGPT: {len(chatgpt_events)} events")
    print(f"  Cerebras: {len(cerebras_events)} events")

    if len(chatgpt_events) != len(cerebras_events):
        print(f"❌ Event count mismatch")
        return False

    print(f"✅ Event counts match\n")

    # Check event types match
    mismatches = []
    for i, (cg, cb) in enumerate(zip(chatgpt_events, cerebras_events)):
        cg_type = cg.get('type', 'unknown')
        cb_type = cb.get('type', 'unknown')

        if cg_type != cb_type:
            mismatches.append({
                'index': i,
                'chatgpt_type': cg_type,
                'cerebras_type': cb_type
            })

    if mismatches:
        print(f"❌ Event type mismatches found: {len(mismatches)}")
        for mismatch in mismatches[:5]:  # Show first 5
            print(f"  Event {mismatch['index']}: {mismatch['chatgpt_type']} vs {mismatch['cerebras_type']}")
        return False

    print("✅ All event types match")
    return True


def extract_content(events: List[Dict]) -> str:
    """Extract final text content from event stream"""
    content_parts = []

    for event in events:
        event_type = event.get('type', '')

        # Handle text deltas
        if event_type == 'response.output_text.delta':
            delta = event.get('delta', '')
            if delta:
                content_parts.append(delta)

        # Handle function call arguments
        elif event_type == 'response.function_call.arguments.delta':
            delta = event.get('delta', '')
            if delta:
                content_parts.append(delta)

    return ''.join(content_parts)


def compare_content(chatgpt_events: List[Dict], cerebras_events: List[Dict]) -> bool:
    """Compare final content from both streams"""

    chatgpt_content = extract_content(chatgpt_events)
    cerebras_content = extract_content(cerebras_events)

    print(f"\n📝 Content Comparison:")
    print(f"  ChatGPT length: {len(chatgpt_content)} chars")
    print(f"  Cerebras length: {len(cerebras_content)} chars")

    if chatgpt_content == cerebras_content:
        print(f"✅ Content matches exactly")
        return True
    else:
        print(f"❌ Content differs")

        # Show first difference
        for i, (c1, c2) in enumerate(zip(chatgpt_content, cerebras_content)):
            if c1 != c2:
                print(f"\n  First difference at position {i}:")
                print(f"    ChatGPT: '{chatgpt_content[max(0,i-20):i+20]}'")
                print(f"    Cerebras: '{cerebras_content[max(0,i-20):i+20]}'")
                break

        return False


def analyze_event_sequence(events: List[Dict], name: str):
    """Analyze and display event sequence"""
    print(f"\n🔍 {name} Event Sequence:")

    event_types = {}
    for event in events:
        event_type = event.get('type', 'unknown')
        event_types[event_type] = event_types.get(event_type, 0) + 1

    for event_type, count in sorted(event_types.items()):
        print(f"  {event_type}: {count}")


def main():
    """Main comparison function"""
    print("🔬 Dual-Proxy Response Comparison\n")
    print("=" * 60)

    chatgpt_log = Path("/tmp/codex_plus/chatgpt_responses/latest_response.txt")
    cerebras_log = Path("/tmp/codex_plus/cerebras_responses/latest_response.txt")

    print(f"\n📂 Log Files:")
    print(f"  ChatGPT:  {chatgpt_log}")
    print(f"  Cerebras: {cerebras_log}")

    # Parse events
    chatgpt_events = parse_sse_events(chatgpt_log)
    cerebras_events = parse_sse_events(cerebras_log)

    if not chatgpt_events and not cerebras_events:
        print("\n❌ No events found in either log file")
        print("   Make sure to run requests through both proxies first")
        sys.exit(1)

    # Analyze event sequences
    if chatgpt_events:
        analyze_event_sequence(chatgpt_events, "ChatGPT")
    if cerebras_events:
        analyze_event_sequence(cerebras_events, "Cerebras")

    # Compare events
    types_match = compare_event_types(chatgpt_events, cerebras_events)
    content_match = compare_content(chatgpt_events, cerebras_events)

    # Final verdict
    print("\n" + "=" * 60)
    if types_match and content_match:
        print("✅ VALIDATION PASSED: Responses are equivalent")
        sys.exit(0)
    else:
        print("❌ VALIDATION FAILED: Responses differ")
        if not types_match:
            print("   - Event type mismatch")
        if not content_match:
            print("   - Content mismatch")
        sys.exit(1)


if __name__ == "__main__":
    main()
