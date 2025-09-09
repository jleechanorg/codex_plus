#!/usr/bin/env python3
"""
Enhanced Slash Command Middleware
Hybrid system using TypeScript CommandRegistry patterns with markdown command support

🚨 CRITICAL PROXY REQUIREMENTS - DO NOT CHANGE 🚨
1. MUST use curl_cffi with Chrome impersonation (line 335)
2. MUST forward to https://chatgpt.com/backend-api/codex
3. NO API KEYS - Codex uses session auth
4. NEVER replace the proxy forwarding logic in process_request()
"""
import json
import re
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Union
from abc import ABC, abstractmethod
from enum import Enum
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("enhanced_slash_middleware")

class ArgType(Enum):
    """Command argument types - matches TypeScript ArgType enum"""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"

class CommandArgDef:
    """Command argument definition - matches TypeScript CommandArgDef"""
    def __init__(self, name: str, arg_type: ArgType, description: str = "", 
                 required: bool = False, position: Optional[int] = None, 
                 choices: Optional[List[str]] = None, default: Any = None):
        self.name = name
        self.type = arg_type
        self.description = description
        self.required = required
        self.position = position
        self.choices = choices
        self.default = default

class HybridCommandDef:
    """Enhanced CommandDef supporting both TypeScript handlers and markdown templates"""
    def __init__(self, name: str, description: str, source: str = "markdown",
                 handler: Optional[callable] = None, args: Optional[List[CommandArgDef]] = None,
                 aliases: Optional[List[str]] = None, category: str = "User",
                 require_auth: bool = False, markdown_path: Optional[str] = None,
                 frontmatter: Optional[Dict[str, Any]] = None, prompt_template: Optional[str] = None):
        self.name = name
        self.description = description
        self.source = source  # 'builtin' or 'markdown'
        self.handler = handler
        self.args = args or []
        self.aliases = aliases or []
        self.category = category
        self.require_auth = require_auth
        self.markdown_path = markdown_path
        self.frontmatter = frontmatter or {}
        self.prompt_template = prompt_template

class CommandRegistry:
    """Central command registry - matches TypeScript CommandRegistry pattern"""
    def __init__(self):
        self.commands: Dict[str, HybridCommandDef] = {}
        self.aliases: Dict[str, str] = {}
        
    def register(self, command_def: HybridCommandDef):
        """Register a command with validation"""
        if not command_def.name:
            raise ValueError("Command name is required")
        
        if command_def.name in self.commands or command_def.name in self.aliases:
            logger.warning(f"Command '{command_def.name}' already registered, overriding")
        
        # Register command
        self.commands[command_def.name] = command_def
        logger.debug(f"Registered command: {command_def.name}")
        
        # Register aliases
        for alias in command_def.aliases:
            if alias in self.commands or alias in self.aliases:
                logger.warning(f"Alias '{alias}' conflicts, skipping")
                continue
            self.aliases[alias] = command_def.name
            logger.debug(f"Registered alias '{alias}' for command '{command_def.name}'")
    
    def get(self, name_or_alias: str) -> Optional[HybridCommandDef]:
        """Get command by name or alias"""
        if name_or_alias in self.commands:
            return self.commands[name_or_alias]
        
        command_name = self.aliases.get(name_or_alias)
        if command_name:
            return self.commands[command_name]
        
        return None
    
    def list_commands(self, include_hidden: bool = False) -> List[HybridCommandDef]:
        """List all commands"""
        return list(self.commands.values())

class MarkdownCommandLoader:
    """Loads and parses markdown command files"""
    
    def scan_directory(self, directory_path: str) -> List[HybridCommandDef]:
        """Scan directory for markdown command files"""
        commands = []
        dir_path = Path(directory_path)
        
        if not dir_path.exists():
            logger.info(f"Commands directory not found: {directory_path}")
            return commands
        
        for md_file in dir_path.rglob("*.md"):
            try:
                command_def = self.parse_markdown_file(str(md_file))
                if command_def:
                    commands.append(command_def)
            except Exception as e:
                logger.error(f"Error parsing {md_file}: {e}")
        
        logger.info(f"Loaded {len(commands)} markdown commands from {directory_path}")
        return commands
    
    def parse_markdown_file(self, file_path: str) -> Optional[HybridCommandDef]:
        """Parse markdown file with YAML frontmatter"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract command name from filename
            file_name = Path(file_path).stem
            
            # Parse YAML frontmatter and content
            frontmatter, markdown_content = self._parse_frontmatter(content)
            
            # Create command definition
            command_def = HybridCommandDef(
                name=file_name,
                description=frontmatter.get('description', f'Markdown command: {file_name}'),
                source='markdown',
                markdown_path=file_path,
                frontmatter=frontmatter,
                prompt_template=markdown_content,
                category=frontmatter.get('category', 'User'),
                aliases=frontmatter.get('aliases', [])
            )
            
            return command_def
            
        except Exception as e:
            logger.error(f"Failed to parse markdown file {file_path}: {e}")
            return None
    
    def _parse_frontmatter(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Parse YAML frontmatter from markdown content"""
        frontmatter = {}
        markdown_content = content
        
        if content.startswith('---\n'):
            parts = content.split('---\n', 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    markdown_content = parts[2]
                except yaml.YAMLError as e:
                    logger.warning(f"Invalid YAML frontmatter: {e}")
        
        return frontmatter, markdown_content

class ArgumentSubstitutor:
    """Handles argument substitution in markdown templates"""
    
    def substitute(self, template: str, args: Dict[str, Any]) -> str:
        """Substitute arguments in template - supports $ARGUMENTS, $1, $2, ${name:default}"""
        result = template
        
        # Handle $ARGUMENTS (full arguments string)
        arguments_str = ' '.join(str(v) for v in args.get('_raw_args', []))
        result = result.replace('$ARGUMENTS', arguments_str)
        
        # Handle positional arguments $1, $2, etc.
        raw_args = args.get('_raw_args', [])
        for i, arg in enumerate(raw_args, 1):
            result = result.replace(f'${i}', str(arg))
        
        # Handle named arguments ${name} and ${name:default}
        result = re.sub(
            r'\$\{(\w+)(?::([^}]*))?\}',
            lambda m: str(args.get(m.group(1), m.group(2) or '')),
            result
        )
        
        return result

class EnhancedSlashCommandMiddleware:
    """Enhanced middleware using TypeScript patterns with markdown support"""
    
    def __init__(self, upstream_url: str):
        self.upstream_url = upstream_url
        self.registry = CommandRegistry()
        self.loader = MarkdownCommandLoader()
        self.substitutor = ArgumentSubstitutor()
        
        # Initialize built-in commands
        self._register_builtin_commands()
        
        # Load markdown commands
        self._load_markdown_commands()
    
    def _register_builtin_commands(self):
        """Register built-in TypeScript-style commands"""
        # Help command
        help_cmd = HybridCommandDef(
            name="help",
            description="Show available slash commands",
            source="builtin", 
            handler=self._handle_help_command,
            aliases=["h"],
            category="System"
        )
        self.registry.register(help_cmd)
        
        # Clear command  
        clear_cmd = HybridCommandDef(
            name="clear",
            description="Clear conversation history",
            source="builtin",
            handler=self._handle_clear_command,
            category="System"
        )
        self.registry.register(clear_cmd)
        
    def _load_markdown_commands(self):
        """Load markdown commands from directories"""
        # Load from .codexplus/commands/ (project-level)
        project_commands = self.loader.scan_directory('.codexplus/commands')
        for cmd in project_commands:
            self.registry.register(cmd)

        # Also load from .claude/commands/ for backward compatibility
        claude_commands = self.loader.scan_directory('.claude/commands')
        for cmd in claude_commands:
            self.registry.register(cmd)

        # Load from user-level directories (future enhancement)
        # user_codexplus = self.loader.scan_directory(str(Path.home() / '.codexplus' / 'commands'))
        # for cmd in user_codexplus:
        #     self.registry.register(cmd)
        # user_claude = self.loader.scan_directory(str(Path.home() / '.claude' / 'commands'))
        # for cmd in user_claude:
        #     self.registry.register(cmd)
    
    def _handle_help_command(self, args: Dict[str, Any]) -> str:
        """Built-in help command handler"""
        commands = self.registry.list_commands()
        builtin_cmds = [cmd for cmd in commands if cmd.source == 'builtin']
        markdown_cmds = [cmd for cmd in commands if cmd.source == 'markdown']
        
        help_text = "Available slash commands:\n\n"
        
        if builtin_cmds:
            help_text += "Built-in commands:\n"
            for cmd in builtin_cmds:
                help_text += f"  /{cmd.name} - {cmd.description}\n"
            help_text += "\n"
        
        if markdown_cmds:
            help_text += "User commands:\n"
            for cmd in markdown_cmds:
                help_text += f"  /{cmd.name} - {cmd.description}\n"
        
        return help_text
    
    def _handle_clear_command(self, args: Dict[str, Any]) -> str:
        """Built-in clear command handler"""
        return "CLEAR_CONVERSATION_REQUESTED"
    
    async def process_request(self, request, path: str):
        """Process FastAPI request - main entry point"""
        from fastapi.responses import StreamingResponse, JSONResponse
        from curl_cffi import requests
        import os
        
        body = await request.body()
        headers = dict(request.headers)
        
        # Process slash commands first
        processed_body, processed_headers = self.process_request_body(body, headers)
        
        # No local test mode; always forward requests upstream
        
        # Normal proxy mode - forward to upstream WITH CHROME IMPERSONATION
        norm_path = path.lstrip("/")
        url = f"{self.upstream_url}/{norm_path}"
        
        # Add query parameters if present
        query_params = str(request.url.query)
        if query_params:
            url += f"?{query_params}"
        
        # Filter headers - skip host header as curl_cffi will set it
        filtered_headers = {k: v for k, v in processed_headers.items() 
                          if k.lower() != 'host'}
        
        logger.info(f"Proxying {request.method} /{path} -> {url}")
        
        try:
            # 🚨 CRITICAL: NEVER CHANGE THIS - PROXY WILL BREAK 🚨
            # MUST use curl_cffi with Chrome impersonation to bypass Cloudflare
            # Regular requests or httpx WILL BE BLOCKED BY CLOUDFLARE
            # This is NOT optional - it's the ONLY way to reach ChatGPT backend
            session = requests.Session(impersonate="chrome124")  # DO NOT CHANGE THIS LINE
            
            response = session.request(
                request.method,
                url,
                headers=filtered_headers,
                data=processed_body,
                stream=True
            )
            
            def generate():
                for chunk in response.iter_content(chunk_size=None):
                    if chunk:
                        yield chunk
            
            return StreamingResponse(
                generate(),
                status_code=response.status_code,
                headers=dict(response.headers)
            )
        except Exception as e:
            logger.error(f"Proxy error: {e}")
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=str(e))

    def process_request_body(self, body: bytes, headers: dict) -> Tuple[bytes, dict]:
        """Process request body for slash commands"""
        try:
            data = json.loads(body)
            modified = False
            
            # Process input messages for slash commands
            if 'input' in data and isinstance(data['input'], list):
                for item in data['input']:
                    if item.get('type') == 'message' and item.get('role') == 'user':
                        for content_item in item.get('content', []):
                            if content_item.get('type') == 'input_text':
                                text = content_item.get('text', '').strip()
                                if text.startswith('/'):
                                    logger.info(f"Processing slash command: {text}")
                                    processed_content = self._execute_command(text)
                                    if processed_content:
                                        content_item['text'] = processed_content
                                        modified = True
            
            if modified:
                new_body = json.dumps(data, ensure_ascii=False).encode('utf-8')
                new_headers = headers.copy()
                new_headers["content-length"] = str(len(new_body))
                logger.info(f"Modified request body: {len(body)} -> {len(new_body)} bytes")
                return new_body, new_headers
        
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error processing request body: {e}")
        
        return body, headers
    
    def _execute_command(self, input_text: str) -> Optional[str]:
        """Execute slash command - unified execution flow"""
        # Parse command and arguments
        command_match = re.match(r'^/([a-zA-Z0-9_-]+)(?:\s+(.*))?', input_text.strip())
        if not command_match:
            return None
        
        command_name = command_match.group(1)
        args_str = command_match.group(2) or ""
        
        # Get command definition
        command_def = self.registry.get(command_name)
        if not command_def:
            logger.warning(f"Unknown command: {command_name}")
            return f"Unknown command: /{command_name}. Type /help for available commands."
        
        # Parse arguments
        parsed_args = self._parse_args(args_str)
        
        try:
            if command_def.source == 'builtin':
                # Execute TypeScript-style handler
                result = command_def.handler(parsed_args)
                return f"SLASH COMMAND RESULT: {result}"
            
            elif command_def.source == 'markdown':
                # Process markdown template
                processed_prompt = self.substitutor.substitute(
                    command_def.prompt_template, parsed_args
                )
                
                # Frame as executable instruction for consistency with classic middleware
                framed = (
                    "SLASH COMMAND EXECUTION: You have received an expanded command from the Codex Plus proxy.\n\n"
                    f"Original command: {input_text.strip()}\n\n"
                    "INSTRUCTIONS: The following content is the expanded definition of the command. "
                    "Execute the instructions contained within this command definition. Follow all steps, "
                    "workflows, and procedures described in the command content.\n\n"
                    "COMMAND CONTENT TO EXECUTE:\n"
                    f"{processed_prompt}\n\n"
                    "Execute this command now by following all instructions, workflows, and procedures described above."
                )
                return framed
        
        except Exception as e:
            logger.error(f"Error executing command {command_name}: {e}")
            return f"Error executing command /{command_name}: {str(e)}"
        
        return None
    
    def _parse_args(self, args_str: str) -> Dict[str, Any]:
        """Parse command arguments - simplified version of TypeScript parseArgs"""
        # For MVP, simple space-splitting with raw args preservation
        raw_args = args_str.split() if args_str.strip() else []
        
        return {
            '_raw_args': raw_args,
            '_args_string': args_str
        }

def create_enhanced_slash_command_middleware(upstream_url: str = "https://chatgpt.com/backend-api/codex") -> EnhancedSlashCommandMiddleware:
    """Factory function to create enhanced middleware"""
    return EnhancedSlashCommandMiddleware(upstream_url)

# Test the system
if __name__ == "__main__":
    middleware = create_enhanced_slash_command_middleware()
    
    # Test help command
    help_result = middleware._execute_command("/help")
    print("Help command result:")
    print(help_result)
    
    # Test copilot-codex command if it exists
    copilot_result = middleware._execute_command("/copilot-codex analyze PR comments")
    print("\nCopilot-codex command result:")
    print(copilot_result)
