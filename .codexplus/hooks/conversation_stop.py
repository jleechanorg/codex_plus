---
name: "Conversation Stop Hook"
type: "stop"
priority: 40
enabled: true
description: "Handles conversation end cleanup and status"
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
    """Stop hook that handles conversation end"""
    
    async def stop(self, request: Request, conversation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle conversation end with status and cleanup"""
        try:
            # Get final git status
            git_status = subprocess.run(['git', 'status', '--porcelain'], 
                                      capture_output=True, text=True, cwd='.')
            
            # Get current branch
            git_branch = subprocess.run(['git', 'branch', '--show-current'], 
                                      capture_output=True, text=True, cwd='.')
            
            # Build final status
            final_status = f"""

# Conversation Complete
- **Branch**: {git_branch.stdout.strip() if git_branch.returncode == 0 else 'unknown'}
- **Final Status**: {'clean' if not git_status.stdout.strip() else f'{len(git_status.stdout.strip().splitlines())} changes'}

Remember to commit your changes if needed!
"""
            
            print(final_status)
            
            # Add status to conversation data
            enhanced_data = conversation_data.copy()
            enhanced_data['final_status'] = final_status
            
            return enhanced_data
            
        except Exception as e:
            # If status fails, return original data
            return conversation_data