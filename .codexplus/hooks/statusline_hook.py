---
name: "Statusline Hook"
type: "pre-input"
priority: 10
enabled: true
description: "Adds git status and project context to prompts"
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
    """Statusline hook that adds git status and project context to prompts"""
    
    async def pre_input(self, request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        """Add statusline information to the prompt"""
        try:
            # Get git status
            git_status = subprocess.run(['git', 'status', '--porcelain'], 
                                      capture_output=True, text=True, cwd='.')
            
            # Get current branch
            git_branch = subprocess.run(['git', 'branch', '--show-current'], 
                                      capture_output=True, text=True, cwd='.')
            
            # Get project info
            project_name = Path('.').resolve().name
            
            # Build statusline
            statusline = f"""
# Project Status
- **Project**: {project_name}
- **Branch**: {git_branch.stdout.strip() if git_branch.returncode == 0 else 'unknown'}
- **Status**: {'clean' if not git_status.stdout.strip() else f'{len(git_status.stdout.strip().splitlines())} changes'}

---

"""
            
            # Add statusline to first message if messages exist
            if 'messages' in body and body['messages']:
                first_message = body['messages'][0]
                if 'content' in first_message:
                    first_message['content'] = statusline + first_message['content']
            
            return body
            
        except Exception as e:
            # If statusline fails, return original body
            return body