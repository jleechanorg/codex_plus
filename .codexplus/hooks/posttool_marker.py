---
name: posttool_marker
type: post-tool-use
priority: 100
enabled: true
description: Mark tool usage completion for monitoring and debugging
---

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

def handle_posttool_event(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle PostToolUse event by creating a marker file with tool usage information

    Args:
        event_data: Dictionary containing tool usage information

    Returns:
        Dictionary with execution result
    """
    try:
        # Extract tool information from event data
        tool_name = event_data.get('tool_name', 'unknown_tool')
        timestamp = event_data.get('timestamp', '')
        success = event_data.get('success', True)

        # Create marker data
        marker_data = {
            'tool_name': tool_name,
            'timestamp': timestamp,
            'success': success,
            'event_type': 'post_tool_use'
        }

        # Ensure marker directory exists
        marker_dir = Path('/tmp/codex_plus')
        marker_dir.mkdir(parents=True, exist_ok=True)

        # Write marker file with JSON data
        marker_file = marker_dir / 'posttool_marker.json'
        with open(marker_file, 'w') as f:
            json.dump(marker_data, f, indent=2)

        logger.info(f"Created PostToolUse marker for {tool_name}")

        return {
            'success': True,
            'marker_file': str(marker_file),
            'tool_name': tool_name
        }

    except Exception as e:
        logger.error(f"Failed to create PostToolUse marker: {e}")
        return {
            'success': False,
            'error': str(e)
        }

# Main execution when run as a script
if __name__ == '__main__':
    import sys

    # Read input data from stdin if available
    input_data = {}
    try:
        if not sys.stdin.isatty():
            input_text = sys.stdin.read().strip()
            if input_text:
                input_data = json.loads(input_text)
    except (json.JSONDecodeError, ValueError):
        pass

    # Execute the handler
    result = handle_posttool_event(input_data)

    # Output result as JSON
    print(json.dumps(result))
