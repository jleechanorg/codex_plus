#!/usr/bin/env python3
"""
Hook Metadata:
name: pretool-block
type: PreToolUse
priority: 50
enabled: true
"""
import sys
# create a marker so we know this ran
open('/tmp/codex_plus_pretool_blocked', 'w').write('blocked')
sys.stderr.write('blocked by pretool')
sys.exit(2)
