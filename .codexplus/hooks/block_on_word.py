#!/usr/bin/env python3
import sys, json
d=json.load(sys.stdin)
prompt=str(d.get('prompt',''))
if 'FOOBAR' in prompt:
    print('Policy: FOOBAR not allowed', file=sys.stderr)
    sys.exit(2)
sys.exit(0)
