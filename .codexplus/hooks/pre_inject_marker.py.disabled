---
name: inject-marker
type: pre-input
priority: 10
enabled: true
---
from codex_plus.hooks import Hook

class InjectMarker(Hook):
    name = "inject-marker"
    async def pre_input(self, request, body):
        # add marker and a note
        body['hooked'] = True
        body['hook_note'] = 'pre-input-injected'
        return body
hook = InjectMarker('inject-marker', {'type':'pre-input','priority':10,'enabled':True})
