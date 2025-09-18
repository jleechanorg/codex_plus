#!/usr/bin/env python3
import sys
# create a marker so we know this ran
open('/tmp/codex_plus_pretool_blocked', 'w').write('blocked')
sys.stderr.write('blocked by pretool')
sys.exit(2)
