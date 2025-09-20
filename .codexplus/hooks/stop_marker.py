#!/usr/bin/env python3
"""
Hook Metadata:
name: stop-marker
type: Stop
priority: 50
enabled: true
"""
if __name__ == "__main__":
    open('/tmp/codex_plus_stop_marker','w').write('stop')
