---
name: "Post Tool Monitoring Hook"
type: "post-output"
priority: 30
enabled: true
description: "Monitors and processes tool outputs"
---

import subprocess
import os
from pathlib import Path
from typing import Any, Dict, Union
from fastapi import Request, Response
from fastapi.responses import StreamingResponse

# Import base Hook class
import sys
sys.path.append('..')
from hooks import Hook as BaseHook

class Hook(BaseHook):
    """Post-output hook that monitors tool outputs"""
    
    async def post_output(self, response: Union[Response, StreamingResponse]) -> Union[Response, StreamingResponse]:
        """Monitor and process tool outputs"""
        try:
            # Add monitoring headers
            if isinstance(response, Response):
                response.headers['X-Monitored-By'] = 'PostToolMonitor'
                response.headers['X-Processing-Time'] = str(os.times().user)
            
            # Log response processing
            print(f"[PostToolUse] Processed response of type: {type(response).__name__}")
            
            return response
            
        except Exception as e:
            # If monitoring fails, return original response
            return response