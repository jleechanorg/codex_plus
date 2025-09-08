"""
Slash Command Middleware for Codex Plus Proxy
Integrates with existing .claude/ infrastructure for hooks and commands
"""
import json
import re
import yaml
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, AsyncGenerator
from dataclasses import dataclass
from fastapi import Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
from curl_cffi import requests
import shlex

logger = logging.getLogger("slash_command_middleware")


@dataclass
class SlashCommand:
    """Represents a parsed slash command"""
    name: str
    args: List[str]
    raw_args: str
    original_text: str


@dataclass
class CommandMetadata:
    """Metadata from command file YAML frontmatter"""
    name: str
    description: str
    usage: str
    arguments: Optional[List[str]] = None


class SlashCommandMiddleware:
    """Middleware for processing slash commands and integrating with .claude/ infrastructure"""
    
    def __init__(self, upstream_url: str = "https://api.openai.com"):
        self.upstream_url = upstream_url
        self.claude_dir = self._find_claude_dir()
        self.commands_dir = self.claude_dir / "commands" if self.claude_dir else None
        self.hooks_config = self._load_hooks_config()
    
    def _find_claude_dir(self) -> Optional[Path]:
        """Find .claude directory in project hierarchy"""
        current = Path.cwd()
        while current != current.parent:
            claude_dir = current / ".claude"
            if claude_dir.exists():
                return claude_dir
            current = current.parent
        return None
    
    def _load_hooks_config(self) -> Dict[str, Any]:
        """Load hooks configuration from .claude/settings.json"""
        if not self.claude_dir:
            return {"hooks": {}}
        
        settings_file = self.claude_dir / "settings.json"
        if not settings_file.exists():
            return {"hooks": {}}
        
        try:
            with open(settings_file) as f:
                config = json.load(f)
                return config.get("hooks", {})
        except Exception as e:
            logger.error(f"Failed to load hooks config: {e}")
            return {"hooks": {}}
    
    def detect_slash_command(self, body: str) -> bool:
        """Detect if request body contains slash commands"""
        if not body:
            return False
        
        try:
            data = json.loads(body)
            # Check messages for slash commands
            if "messages" in data:
                for message in data["messages"]:
                    if isinstance(message, dict) and "content" in message:
                        content = message["content"]
                        if isinstance(content, str) and re.search(r'/\w+', content):
                            return True
            return False
        except (json.JSONDecodeError, TypeError):
            return False
    
    def extract_slash_commands(self, body: str) -> List[SlashCommand]:
        """Extract all slash commands from request body"""
        commands = []
        
        try:
            data = json.loads(body)
            if "messages" in data:
                for message in data["messages"]:
                    if isinstance(message, dict) and "content" in message:
                        content = message["content"]
                        if isinstance(content, str):
                            # Find all slash commands in the content
                            matches = re.finditer(r'/(\w+)([^\n]*)', content)
                            for match in matches:
                                cmd_name = match.group(1)
                                raw_args = match.group(2).strip()
                                
                                # Parse arguments
                                try:
                                    args = shlex.split(raw_args) if raw_args else []
                                except ValueError:
                                    # Fallback to simple split if shlex fails
                                    args = raw_args.split() if raw_args else []
                                
                                commands.append(SlashCommand(
                                    name=cmd_name,
                                    args=args,
                                    raw_args=raw_args,
                                    original_text=match.group(0)
                                ))
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to extract slash commands: {e}")
        
        return commands
    
    def find_command_file(self, command_name: str) -> Optional[Path]:
        """Find .claude/commands/*.md file for command"""
        if not self.commands_dir or not self.commands_dir.exists():
            return None
        
        # Try exact match first
        command_file = self.commands_dir / f"{command_name}.md"
        if command_file.exists():
            return command_file
        
        # Try case-insensitive search
        for file_path in self.commands_dir.glob("*.md"):
            if file_path.stem.lower() == command_name.lower():
                return file_path
        
        return None
    
    def parse_command_metadata(self, command_file: Path) -> CommandMetadata:
        """Parse YAML frontmatter from command file"""
        try:
            content = command_file.read_text()
            
            # Extract YAML frontmatter
            if content.startswith('---\n'):
                end_marker = content.find('\n---\n', 4)
                if end_marker != -1:
                    yaml_content = content[4:end_marker]
                    try:
                        metadata = yaml.safe_load(yaml_content)
                        return CommandMetadata(
                            name=metadata.get('name', command_file.stem),
                            description=metadata.get('description', ''),
                            usage=metadata.get('usage', f'/{command_file.stem}'),
                            arguments=metadata.get('arguments')
                        )
                    except yaml.YAMLError as e:
                        logger.error(f"YAML parse error in {command_file}: {e}")
            
            # Fallback metadata
            return CommandMetadata(
                name=command_file.stem,
                description=f"Command from {command_file.name}",
                usage=f"/{command_file.stem}"
            )
            
        except Exception as e:
            logger.error(f"Failed to parse command metadata from {command_file}: {e}")
            return CommandMetadata(
                name=command_file.stem,
                description="Unknown command",
                usage=f"/{command_file.stem}"
            )
    
    def substitute_arguments(self, content: str, args: List[str], raw_args: str) -> str:
        """Substitute $ARGUMENTS and positional arguments in command content"""
        # Substitute $ARGUMENTS with raw arguments
        content = content.replace('$ARGUMENTS', raw_args)
        
        # Substitute positional arguments $1, $2, etc.
        for i, arg in enumerate(args, 1):
            content = content.replace(f'${i}', arg)
        
        return content
    
    def execute_hooks(self, hook_type: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute hooks of specified type"""
        if hook_type not in self.hooks_config:
            return {}
        
        results = {}
        hooks = self.hooks_config[hook_type]
        
        for hook_group in hooks:
            matcher = hook_group.get("matcher", "*")
            # For now, execute all hooks (matcher logic can be enhanced later)
            
            for hook in hook_group.get("hooks", []):
                hook_command = hook.get("command")
                hook_desc = hook.get("description", "Unknown hook")
                
                if hook_command:
                    try:
                        # Execute hook command
                        result = subprocess.run(
                            hook_command,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=30,
                            cwd=self.claude_dir.parent if self.claude_dir else None
                        )
                        
                        results[hook_desc] = {
                            "stdout": result.stdout,
                            "stderr": result.stderr,
                            "returncode": result.returncode
                        }
                        
                        if result.returncode != 0:
                            logger.warning(f"Hook '{hook_desc}' failed with code {result.returncode}")
                        
                    except subprocess.TimeoutExpired:
                        logger.error(f"Hook '{hook_desc}' timed out")
                        results[hook_desc] = {"error": "timeout"}
                    except Exception as e:
                        logger.error(f"Hook '{hook_desc}' execution failed: {e}")
                        results[hook_desc] = {"error": str(e)}
        
        return results
    
    async def execute_command(self, command: SlashCommand) -> Dict[str, Any]:
        """Execute a slash command using .claude/commands/*.md file"""
        command_file = self.find_command_file(command.name)
        
        if not command_file:
            return {
                "error": f"Command '/{command.name}' not found",
                "available_commands": [f.stem for f in (self.commands_dir.glob("*.md") if self.commands_dir else [])]
            }
        
        try:
            # Parse command metadata
            metadata = self.parse_command_metadata(command_file)
            
            # Read command content
            content = command_file.read_text()
            
            # Remove YAML frontmatter
            if content.startswith('---\n'):
                end_marker = content.find('\n---\n', 4)
                if end_marker != -1:
                    content = content[end_marker + 5:]  # Skip the closing ---\n
            
            # Substitute arguments
            processed_content = self.substitute_arguments(content, command.args, command.raw_args)
            
            return {
                "command": command.name,
                "metadata": {
                    "name": metadata.name,
                    "description": metadata.description,
                    "usage": metadata.usage
                },
                "content": processed_content,
                "arguments": command.args,
                "raw_arguments": command.raw_args
            }
            
        except Exception as e:
            logger.error(f"Failed to execute command '{command.name}': {e}")
            return {
                "error": f"Failed to execute command '/{command.name}': {str(e)}"
            }
    
    async def process_slash_commands(self, commands: List[SlashCommand]) -> Dict[str, Any]:
        """Process multiple slash commands and return results"""
        results = []
        
        # Execute pre-hooks
        pre_hook_results = self.execute_hooks("PreToolUse")
        
        # Process each command
        for command in commands:
            result = await self.execute_command(command)
            results.append(result)
        
        # Execute post-hooks
        post_hook_results = self.execute_hooks("PostToolUse")
        
        return {
            "slash_commands": results,
            "pre_hooks": pre_hook_results,
            "post_hooks": post_hook_results,
            "processed_at": "middleware"
        }
    
    async def create_command_response(self, command_results: Dict[str, Any]) -> Response:
        """Create response from command execution results"""
        # Format results as JSON response
        response_data = {
            "type": "slash_command_response",
            "results": command_results,
            "message": "Slash commands processed by Codex Plus middleware"
        }
        
        return JSONResponse(content=response_data, status_code=200)
    
    async def proxy_request(self, request: Request, target_url: str, body: bytes) -> Response:
        """Proxy request to upstream server with streaming support"""
        # Get headers from request
        headers = {}
        for key, value in request.headers.items():
            # Skip host header as curl_cffi will set it
            if key.lower() != "host":
                headers[key] = value
        
        try:
            # Use synchronous curl_cffi with Chrome impersonation
            session = requests.Session(impersonate="chrome124")
            
            # Make the request with streaming
            response = session.request(
                request.method,
                target_url,
                headers=headers,
                data=body if body else None,
                stream=True,
                timeout=30
            )
            
            # Stream the response back
            def stream_response():
                try:
                    # Stream raw content without buffering
                    for chunk in response.iter_content(chunk_size=None):
                        if chunk:
                            yield chunk
                finally:
                    response.close()
                    session.close()
            
            # Get response headers
            resp_headers = dict(response.headers)
            resp_headers.pop("content-length", None)  # Remove as we're streaming
            resp_headers.pop("content-encoding", None)  # Remove encoding headers
            
            return StreamingResponse(
                stream_response(),
                status_code=response.status_code,
                headers=resp_headers,
                media_type=resp_headers.get("content-type", "text/event-stream")
            )
            
        except Exception as e:
            logger.exception(f"Error proxying request: {e}")
            return JSONResponse(
                {"error": str(e)},
                status_code=500
            )
    
    async def process_request(self, request: Request, path: str) -> Response:
        """Main middleware entry point - process request and return response"""
        # Build target URL
        norm_path = path.lstrip("/")
        target_url = f"{self.upstream_url}/{norm_path}"
        
        # Forward query parameters
        query_params = str(request.url.query)
        if query_params:
            target_url += f"?{query_params}"
        
        # Read request body
        body = await request.body()
        body_str = body.decode('utf-8') if body else ""
        
        # Check for slash commands
        if self.detect_slash_command(body_str):
            logger.info(f"Detected slash commands in {request.method} /{path}")
            
            # Extract and process commands
            commands = self.extract_slash_commands(body_str)
            if commands:
                try:
                    # Process slash commands
                    command_results = await self.process_slash_commands(commands)
                    
                    # Return command response instead of proxying
                    return await self.create_command_response(command_results)
                    
                except Exception as e:
                    logger.error(f"Error processing slash commands: {e}")
                    # Fall back to proxying on error
                    return await self.proxy_request(request, target_url, body)
        
        # No slash commands detected - proxy normally
        return await self.proxy_request(request, target_url, body)


# Factory function for easy integration
def create_slash_command_middleware(upstream_url: str = "https://api.openai.com") -> SlashCommandMiddleware:
    """Create and configure slash command middleware"""
    return SlashCommandMiddleware(upstream_url=upstream_url)