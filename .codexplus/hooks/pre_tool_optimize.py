---
name: "Pre Tool Optimization Hook"
type: "pre-tool-use"
priority: 20
enabled: true
description: "Optimizes tool usage before execution"
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
    """Pre-tool-use hook that optimizes tool execution"""
    
    async def pre_tool_use(self, request: Request, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize tool arguments before execution"""
        try:
            # Log tool usage for monitoring
            print(f"[PreToolUse] Executing tool: {tool_name} with args: {list(tool_args.keys())}")
            
            # Add optimization hints based on tool
            optimized_args = tool_args.copy()
            
            if tool_name in ['bash', 'shell']:
                # Add timeout for long-running commands
                if 'timeout' not in optimized_args:
                    optimized_args['timeout'] = 30
                    
            elif tool_name in ['read', 'read_file']:
                # Limit file size for large reads
                if 'limit' not in optimized_args:
                    optimized_args['limit'] = 1000
            
            return optimized_args
            
        except Exception as e:
            # If optimization fails, return original args
            return tool_args