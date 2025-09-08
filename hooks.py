import asyncio
import importlib.util
import logging
import os
import sys
import traceback
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

import yaml
from fastapi import Request, Response
from fastapi.responses import StreamingResponse

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class Hook:
    """Base hook class with multiple hook type methods"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.priority = config.get('priority', 100)
        self.enabled = config.get('enabled', True)
        self.hook_type = config.get('type', 'pre-input')  # Default type
    
    async def pre_input(self, request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the input before sending to the API (UserPromptSubmit).
        Should be overridden by subclasses.
        """
        return body
    
    async def post_output(self, response: Union[Response, StreamingResponse]) -> Union[Response, StreamingResponse]:
        """
        Process the output after receiving from the API (PostToolUse).
        Should be overridden by subclasses.
        """
        return response
    
    async def pre_tool_use(self, request: Request, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process before tool execution (PreToolUse).
        Should be overridden by subclasses.
        """
        return tool_args
    
    async def stop(self, request: Request, conversation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process when conversation ends (Stop).
        Should be overridden by subclasses.
        """
        return conversation_data

class HookSystem:
    """Hook system for managing and executing hooks"""
    
    def __init__(self, hooks_dirs: List[str] = None):
        if hooks_dirs is None:
            # Default: search .codexplus/hooks/ first (for new development), then .claude/hooks/
            hooks_dirs = [".codexplus/hooks/", ".claude/hooks/"]
        self.hooks_dirs = [Path(d) for d in hooks_dirs]
        self.hooks: List[Hook] = []
        self._load_hooks()
    
    def _load_hooks(self) -> None:
        """Load all hooks from the hooks directories"""
        self.hooks = []
        loaded_names = set()  # Track loaded hook names to handle precedence
        
        for hooks_dir in self.hooks_dirs:
            if not hooks_dir.exists():
                logger.info(f"Hooks directory {hooks_dir} does not exist")
                continue
            
            # Add hooks directory to Python path
            hooks_path = str(hooks_dir.absolute())
            if hooks_path not in sys.path:
                sys.path.insert(0, hooks_path)
            
            for hook_file in hooks_dir.glob("*.py"):
                # Skip if hook with same name already loaded (precedence)
                if hook_file.stem in loaded_names:
                    logger.info(f"Skipping {hook_file} - already loaded from higher precedence directory")
                    continue
                    
                try:
                    hook = self._load_hook_from_file(hook_file)
                    if hook:
                        self.hooks.append(hook)
                        loaded_names.add(hook_file.stem)
                        logger.info(f"Loaded hook: {hook.name} from {hooks_dir}")
                except Exception as e:
                    logger.error(f"Failed to load hook from {hook_file}: {e}")
                    logger.debug(traceback.format_exc())
        
        # Sort hooks by priority (lower number = higher priority)
        self.hooks.sort(key=lambda h: h.priority)
        logger.info(f"Loaded {len(self.hooks)} hooks")
    
    def _load_hook_from_file(self, file_path: Path) -> Optional[Hook]:
        """Load a single hook from a Python file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse YAML frontmatter
        config = self._parse_frontmatter(content)
        if not config:
            logger.warning(f"No valid frontmatter found in {file_path}")
            return None
        
        # Check if hook is enabled
        if not config.get('enabled', True):
            logger.info(f"Hook in {file_path} is disabled")
            return None
        
        # Extract Python code (after frontmatter)
        python_code = self._extract_python_code(content)
        if not python_code:
            logger.error(f"No Python code found in {file_path}")
            return None
        
        # Create a temporary module and execute the Python code
        spec = importlib.util.spec_from_loader(file_path.stem, loader=None)
        if not spec:
            logger.error(f"Could not create module spec for {file_path}")
            return None
            
        module = importlib.util.module_from_spec(spec)
        try:
            exec(python_code, module.__dict__)
        except Exception as e:
            logger.error(f"Error executing Python code in {file_path}: {e}")
            return None
        
        # Find the hook class
        hook_class = getattr(module, 'Hook', None)
        if not hook_class or not issubclass(hook_class, Hook):
            logger.warning(f"No valid Hook class found in {file_path}")
            return None
        
        # Create hook instance
        return hook_class(file_path.stem, config)
    
    def _parse_frontmatter(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse YAML frontmatter from file content"""
        lines = content.splitlines()
        
        if len(lines) < 3:
            return None
            
        # Check for frontmatter delimiter
        if lines[0].strip() != '---':
            return None
        
        # Find end of frontmatter
        end_index = -1
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == '---':
                end_index = i
                break
        
        if end_index == -1:
            return None
        
        # Extract and parse YAML
        yaml_content = '\n'.join(lines[1:end_index])
        try:
            return yaml.safe_load(yaml_content) or {}
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {e}")
            return None
    
    def _extract_python_code(self, content: str) -> Optional[str]:
        """Extract Python code from content after YAML frontmatter"""
        lines = content.splitlines()
        
        if len(lines) < 3:
            return content  # No frontmatter, return as-is
            
        # Check for frontmatter delimiter
        if lines[0].strip() != '---':
            return content  # No frontmatter, return as-is
        
        # Find end of frontmatter
        end_index = -1
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == '---':
                end_index = i
                break
        
        if end_index == -1:
            return content  # No valid frontmatter end, return as-is
        
        # Return everything after the frontmatter
        python_lines = lines[end_index + 1:]
        return '\n'.join(python_lines)
    
    async def execute_pre_input_hooks(self, request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all pre_input hooks in priority order"""
        modified_body = body.copy()
        
        for hook in self.hooks:
            if not hook.enabled or hook.hook_type != 'pre-input':
                continue
                
            try:
                modified_body = await hook.pre_input(request, modified_body)
            except Exception as e:
                logger.error(f"Error in pre_input hook '{hook.name}': {e}")
                logger.debug(traceback.format_exc())
                # Continue with the original body if hook fails
                continue
        
        return modified_body
    
    async def execute_post_output_hooks(self, response: Union[Response, StreamingResponse]) -> Union[Response, StreamingResponse]:
        """Execute all post_output hooks in priority order"""
        modified_response = response
        
        for hook in self.hooks:
            if not hook.enabled or hook.hook_type != 'post-output':
                continue
                
            try:
                modified_response = await hook.post_output(modified_response)
            except Exception as e:
                logger.error(f"Error in post_output hook '{hook.name}': {e}")
                logger.debug(traceback.format_exc())
                # Continue with the original response if hook fails
                continue
        
        return modified_response
    
    async def execute_pre_tool_use_hooks(self, request: Request, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all pre_tool_use hooks in priority order"""
        modified_args = tool_args.copy()
        
        for hook in self.hooks:
            if not hook.enabled or hook.hook_type != 'pre-tool-use':
                continue
                
            try:
                modified_args = await hook.pre_tool_use(request, tool_name, modified_args)
            except Exception as e:
                logger.error(f"Error in pre_tool_use hook '{hook.name}': {e}")
                logger.debug(traceback.format_exc())
                # Continue with the original args if hook fails
                continue
        
        return modified_args
    
    async def execute_stop_hooks(self, request: Request, conversation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all stop hooks in priority order"""
        modified_data = conversation_data.copy()
        
        for hook in self.hooks:
            if not hook.enabled or hook.hook_type != 'stop':
                continue
                
            try:
                modified_data = await hook.stop(request, modified_data)
            except Exception as e:
                logger.error(f"Error in stop hook '{hook.name}': {e}")
                logger.debug(traceback.format_exc())
                # Continue with the original data if hook fails
                continue
        
        return modified_data

# Global hook system instance
hook_system = HookSystem()

# Integration points for FastAPI route handler
async def process_pre_input_hooks(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    """Process pre-input hooks before making API call"""
    return await hook_system.execute_pre_input_hooks(request, body)

async def process_post_output_hooks(response: Union[Response, StreamingResponse]) -> Union[Response, StreamingResponse]:
    """Process post-output hooks after receiving API response"""
    return await hook_system.execute_post_output_hooks(response)

async def process_pre_tool_use_hooks(request: Request, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """Process pre-tool-use hooks before tool execution"""
    return await hook_system.execute_pre_tool_use_hooks(request, tool_name, tool_args)

async def process_stop_hooks(request: Request, conversation_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process stop hooks when conversation ends"""
    return await hook_system.execute_stop_hooks(request, conversation_data)

# Example hook implementation (for reference)
class ExampleHook(Hook):
    """Example hook implementation"""
    
    async def pre_input(self, request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        # Example: Add a custom header to the body
        if 'messages' in body:
            body['messages'][0]['content'] = f"[Processed by {self.name}] {body['messages'][0]['content']}"
        return body
    
    async def post_output(self, response: Union[Response, StreamingResponse]) -> Union[Response, StreamingResponse]:
        # Example: Add a custom header to the response
        if isinstance(response, Response):
            response.headers['X-Processed-By'] = self.name
        return response