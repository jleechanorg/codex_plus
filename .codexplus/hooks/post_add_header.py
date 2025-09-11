---
name: add-header
type: post-output
priority: 50
enabled: true
---
from codex_plus.hooks import Hook
from fastapi.responses import Response

class AddHeader(Hook):
    name = "add-header"
    async def post_output(self, response):
        # only add on non-streaming responses
        try:
            response.headers['X-Hooked'] = '1'
        except Exception:
            pass
        return response
hook = AddHeader('add-header', {'type':'post-output','priority':50,'enabled':True})
