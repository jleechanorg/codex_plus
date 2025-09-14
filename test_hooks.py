import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock, patch

import pytest
import yaml
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

# Assuming the hook system implementation (to be tested)
class Hook:
    def __init__(self, name: str, priority: int, config: Dict[str, Any]):
        self.name = name
        self.priority = priority
        self.config = config
        self.enabled = config.get('enabled', True)
        
    async def pre_input(self, prompt: str, request: Request) -> str:
        """Modify user prompt before sending to API"""
        # Base implementation - subclasses should override
        return prompt
    
    async def post_output(self, response: Dict[str, Any], request: Request) -> Dict[str, Any]:
        """Process API response after receiving"""
        # Base implementation - subclasses should override
        return response

class HookSystem:
    def __init__(self, hooks_dir: str = ".claude/hooks/"):
        self.hooks_dir = hooks_dir
        self.pre_input_hooks: List[Hook] = []
        self.post_output_hooks: List[Hook] = []
        self.load_hooks()
    
    def load_hooks(self):
        """Load hooks from filesystem"""
        self.pre_input_hooks = []
        self.post_output_hooks = []
        
        if not os.path.exists(self.hooks_dir):
            return
            
        for file_path in Path(self.hooks_dir).glob("*.py"):
            try:
                # In a real implementation, we would dynamically load the module
                # For testing purposes, we'll mock this behavior
                hook_config = self._parse_hook_config(file_path)
                hook = Hook(
                    name=file_path.stem,
                    priority=hook_config.get('priority', 100),
                    config=hook_config
                )
                
                if hook_config.get('type') == 'pre-input':
                    self.pre_input_hooks.append(hook)
                elif hook_config.get('type') == 'post-output':
                    self.post_output_hooks.append(hook)
                    
            except Exception as e:
                # Log the error and continue with other hooks
                print(f"Failed to load hook {file_path}: {e}")
                continue
        
        # Sort by priority
        self.pre_input_hooks.sort(key=lambda h: h.priority)
        self.post_output_hooks.sort(key=lambda h: h.priority)
    
    def _parse_hook_config(self, file_path: Path) -> Dict[str, Any]:
        """Parse YAML frontmatter from hook file"""
        with open(file_path, 'r') as f:
            content = f.read()
            
        # Simple frontmatter parser for testing
        if content.startswith('---'):
            end_of_frontmatter = content.find('---', 3)
            if end_of_frontmatter != -1:
                frontmatter = content[3:end_of_frontmatter]
                return yaml.safe_load(frontmatter) or {}
        
        return {}
    
    async def execute_pre_input_hooks(self, prompt: str, request: Request) -> str:
        """Execute pre-input hooks in order"""
        modified_prompt = prompt
        for hook in self.pre_input_hooks:
            if hook.enabled:
                try:
                    modified_prompt = await hook.pre_input(modified_prompt, request)
                except Exception as e:
                    # Log hook execution error and continue
                    print(f"Pre-input hook {hook.name} failed: {e}")
                    continue
        return modified_prompt
    
    async def execute_post_output_hooks(self, response: Dict[str, Any], request: Request) -> Dict[str, Any]:
        """Execute post-output hooks in order"""
        modified_response = response
        for hook in self.post_output_hooks:
            if hook.enabled:
                try:
                    modified_response = await hook.post_output(modified_response, request)
                except Exception as e:
                    # Log hook execution error and continue
                    print(f"Post-output hook {hook.name} failed: {e}")
                    continue
        return modified_response

# Test implementation
class TestHookSystem:
    @pytest.fixture
    def temp_hooks_dir(self):
        """Create a temporary directory for hooks"""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks_dir = Path(tmpdir) / "hooks"
            hooks_dir.mkdir()
            yield str(hooks_dir)
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request"""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.hook_context = {}
        return request
    
    @pytest.fixture
    def sample_hooks(self, temp_hooks_dir):
        """Create sample hook files for testing"""
        hooks_dir = Path(temp_hooks_dir)
        
        # Pre-input hook with high priority
        pre_hook_1 = hooks_dir / "pre_hook_1.py"
        pre_hook_1.write_text("""---
name: "Pre Hook 1"
type: "pre-input"
priority: 10
enabled: true
---
async def pre_input(prompt, request):
    return prompt + " [modified by pre_hook_1]"
""")
        
        # Pre-input hook with low priority
        pre_hook_2 = hooks_dir / "pre_hook_2.py"
        pre_hook_2.write_text("""---
name: "Pre Hook 2"
type: "pre-input"
priority: 200
enabled: true
---
async def pre_input(prompt, request):
    return prompt.replace("test", "TEST")
""")
        
        return hooks_dir
    
    def test_hook_discovery_and_loading(self, sample_hooks):
        """Test that hooks are properly discovered and loaded from filesystem"""
        hook_system = HookSystem(hooks_dir=str(sample_hooks))
        hook_system.load_hooks()
        
        # Check that we have the right number of hooks
        assert len(hook_system.pre_input_hooks) == 2
        
        # Check that hooks are sorted by priority
        pre_priorities = [hook.priority for hook in hook_system.pre_input_hooks]
        assert pre_priorities == sorted(pre_priorities)
        
        # Check specific hook properties
        pre_hook_names = [hook.name for hook in hook_system.pre_input_hooks]
        assert 'pre_hook_1' in pre_hook_names
        assert 'pre_hook_2' in pre_hook_names