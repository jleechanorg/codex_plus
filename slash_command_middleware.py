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
    
    # Security: Maximum request body size to prevent ReDoS (10MB)
    MAX_BODY_SIZE = 10 * 1024 * 1024
    
    def __init__(self, upstream_url: str = "https://api.openai.com"):
        self.upstream_url = upstream_url
        self.claude_dir = self._find_claude_dir()
        self.commands_dir = self.claude_dir / "commands" if self.claude_dir else None
        self.hooks_config = self._load_hooks_config()
        # Performance: Reuse session for connection pooling
        self._session = None
    
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
        
        # Security: Check body size before processing
        if len(body) > self.MAX_BODY_SIZE:
            logger.warning(f"Request body too large: {len(body)} bytes")
            return False
        
        try:
            data = json.loads(body)
            
            # Check messages for slash commands (standard format)
            if "messages" in data:
                for message in data["messages"]:
                    if isinstance(message, dict) and "content" in message:
                        content = message["content"]
                        if isinstance(content, str) and re.search(r'/\w+', content):
                            return True
            
            # Check input field for slash commands (Codex CLI format)
            if "input" in data:
                for item in data["input"]:
                    if isinstance(item, dict) and item.get("type") == "message":
                        content_list = item.get("content", [])
                        for content_item in content_list:
                            if isinstance(content_item, dict) and content_item.get("type") == "input_text":
                                text = content_item.get("text", "")
                                # Only match slash commands at start of line or after whitespace
                                if re.search(r'(?:^|\s)/\w+', text):
                                    logger.info(f"Detected slash command in input field: {text[:50]}...")
                                    return True
            
            return False
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Error detecting slash command: {e}")
            return False
    
    def extract_slash_commands(self, body: str) -> List[SlashCommand]:
        """Extract all slash commands from request body"""
        commands = []
        
        def extract_from_text(text: str):
            """Helper to extract commands from text"""
            # Only match slash commands at start of line or after whitespace
            matches = re.finditer(r'(?:^|\s)(/(\w+)([^\n]*))', text)
            for match in matches:
                cmd_name = match.group(2)
                raw_args = match.group(3).strip()
                
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
                    original_text=match.group(1)  # The full slash command part
                ))
        
        try:
            data = json.loads(body)
            
            # Check messages field (standard format)
            if "messages" in data:
                for message in data["messages"]:
                    if isinstance(message, dict) and "content" in message:
                        content = message["content"]
                        if isinstance(content, str):
                            extract_from_text(content)
            
            # Check input field (Codex CLI format)
            if "input" in data:
                for item in data["input"]:
                    if isinstance(item, dict) and item.get("type") == "message":
                        content_list = item.get("content", [])
                        for content_item in content_list:
                            if isinstance(content_item, dict) and content_item.get("type") == "input_text":
                                text = content_item.get("text", "")
                                if text:
                                    logger.info(f"Extracting commands from input text: {text[:50]}...")
                                    extract_from_text(text)
                                    
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to extract slash commands: {e}")
        
        return commands
    
    def find_command_file(self, command_name: str) -> Optional[Path]:
        """Find .claude/commands/*.md file for command"""
        if not self.commands_dir or not self.commands_dir.exists():
            return None
        
        # Security: Validate command name to prevent path traversal
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', command_name):
            logger.warning(f"Invalid command name format: {command_name}")
            return None
        
        # Additional safety: Resolve paths and verify containment
        base_path = self.commands_dir.resolve()
        
        # Try exact match first with path validation
        command_file = (base_path / f"{command_name}.md").resolve()
        if str(command_file).startswith(str(base_path)) and command_file.exists():
            return command_file
        
        # Try case-insensitive search with validation
        for file_path in self.commands_dir.glob("*.md"):
            resolved_path = file_path.resolve()
            if str(resolved_path).startswith(str(base_path)) and file_path.stem.lower() == command_name.lower():
                return resolved_path
        
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
            # Performance: Reuse session for connection pooling
            if not self._session:
                self._session = requests.Session(impersonate="chrome124")
            session = self._session
            
            # Make the request with streaming
            response = session.request(
                request.method,
                target_url,
                headers=headers,
                data=body if body else None,
                stream=True,
                timeout=30
            )
            
            # Stream the response back with proper cleanup
            def stream_response():
                try:
                    # Stream raw content without buffering
                    for chunk in response.iter_content(chunk_size=None):
                        if chunk:
                            yield chunk
                except Exception as e:
                    logger.error(f"Error during streaming: {e}")
                    raise
                finally:
                    # Cleanup happens after streaming completes or on error
                    try:
                        response.close()
                    except:
                        pass
                    # Don't close the reused session
            
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
            logger.error(f"Proxy request failed: {e}")
            return JSONResponse(
                content={"error": f"Proxy failed: {str(e)}"},
                status_code=500
            )
    
    async def proxy_request_with_body(self, method: str, target_url: str, body: bytes, headers: dict) -> Response:
        """Proxy request with modified body and headers"""
        try:
            # Performance: Reuse session for connection pooling
            if not self._session:
                self._session = requests.Session(impersonate="chrome124")
            session = self._session
            
            # Make the request with streaming
            response = session.request(
                method,
                target_url,
                headers=headers,
                data=body,
                stream=True,
                timeout=30
            )
            
            # Stream the response back
            def stream_response():
                try:
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
            logger.error(f"Proxy request failed: {e}")
            return JSONResponse(
                content={"error": f"Proxy failed: {str(e)}"},
                status_code=500
            )
    
    async def expand_commands_in_body(self, body_str: str, commands: List[SlashCommand]) -> str:
        """Expand slash commands in request body by properly modifying JSON structure"""
        try:
            # Parse JSON body
            data = json.loads(body_str)
            
            # Handle Codex CLI format with input field
            if "input" in data:
                for item in data["input"]:
                    if isinstance(item, dict) and item.get("type") == "message":
                        content_list = item.get("content", [])
                        for content_item in content_list:
                            if isinstance(content_item, dict) and content_item.get("type") == "input_text":
                                text = content_item.get("text", "")
                                # Replace commands in this text
                                modified_text = await self.replace_commands_in_text(text, commands)
                                if modified_text != text:
                                    # Frame expanded commands as executable instructions
                                    instruction_framed = self.frame_as_executable_instruction(text, modified_text, commands)
                                    logger.info(f"📝 JSON UPDATE: Changing content_item text from '{text}' to '{instruction_framed[:100]}...'")
                                    content_item["text"] = instruction_framed
                                    logger.info(f"✅ Modified input text: {len(text)} -> {len(instruction_framed)} chars")
                                else:
                                    logger.warning(f"⚠️ No text modification occurred: '{text}' remained unchanged")
            
            # Handle standard format with messages field
            elif "messages" in data:
                for message in data["messages"]:
                    if isinstance(message, dict) and "content" in message:
                        content = message["content"]
                        if isinstance(content, str):
                            modified_content = await self.replace_commands_in_text(content, commands)
                            if modified_content != content:
                                message["content"] = modified_content
                                logger.info(f"Modified message content: {len(content)} -> {len(modified_content)} chars")
            
            # Return modified JSON
            modified_json = json.dumps(data, separators=(',', ':'))
            logger.info(f"🔍 FINAL JSON CHECK: Modified JSON length = {len(modified_json)} chars")
            
            # Verify the modification actually worked
            final_data = json.loads(modified_json)
            if "input" in final_data:
                for item in final_data["input"]:
                    if isinstance(item, dict) and item.get("type") == "message":
                        content_list = item.get("content", [])
                        for content_item in content_list:
                            if isinstance(content_item, dict) and content_item.get("type") == "input_text":
                                final_text = content_item.get("text", "")
                                logger.info(f"✅ VERIFICATION: Final text in JSON: '{final_text[:100]}...'")
            
            return modified_json
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON body: {e}")
            return body_str
        except Exception as e:
            logger.error(f"Error expanding commands in JSON: {e}")
            return body_str
    
    async def replace_commands_in_text(self, text: str, commands: List[SlashCommand]) -> str:
        """Replace slash commands in text with their expanded content"""
        modified_text = text
        
        for command in commands:
            logger.info(f"Attempting to replace '{command.original_text}' in text of length {len(text)}")
            if command.original_text in text:
                try:
                    # Execute command to get its content
                    result = await self.execute_command(command)
                    if "content" in result:
                        command_content = result["content"]
                        # Replace the original slash command with expanded content
                        modified_text = modified_text.replace(command.original_text, command_content)
                        logger.info(f"✅ Replaced /{command.name}: '{command.original_text}' -> {len(command_content)} chars")
                    else:
                        logger.warning(f"Command /{command.name} returned no content")
                        
                except Exception as e:
                    logger.error(f"Failed to expand command /{command.name}: {e}")
                    # Leave original command text if expansion fails
            else:
                logger.warning(f"❌ Command text '{command.original_text}' NOT FOUND in text: '{text[:100]}...'")
                    
        return modified_text
    
    def frame_as_executable_instruction(self, original_text: str, expanded_text: str, commands: List[SlashCommand]) -> str:
        """Frame expanded command content as executable instructions following Claude Code CLI pattern"""
        
        # Extract command names for the instruction
        command_names = [cmd.name for cmd in commands]
        
        # Create execution instruction following Claude Code CLI pattern
        if len(commands) == 1:
            instruction = f"""SLASH COMMAND EXECUTION: You have received an expanded command from the Codex Plus proxy.

Original command: {original_text.strip()}
Command: /{commands[0].name}

INSTRUCTIONS: The following content is the expanded definition of the /{commands[0].name} command. Execute the instructions contained within this command definition. Follow all steps, workflows, and procedures described in the command content.

COMMAND CONTENT TO EXECUTE:
{expanded_text}

Execute this command now by following all instructions, workflows, and procedures described above."""
        else:
            cmd_list = ", ".join([f"/{name}" for name in command_names])
            instruction = f"""SLASH COMMAND EXECUTION: You have received expanded commands from the Codex Plus proxy.

Original: {original_text.strip()}
Commands: {cmd_list}

INSTRUCTIONS: The following content contains expanded definitions of multiple commands. Execute all instructions contained within these command definitions. Follow all steps, workflows, and procedures described.

COMMAND CONTENT TO EXECUTE:
{expanded_text}

Execute these commands now by following all instructions, workflows, and procedures described above."""
        
        return instruction
    
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
            
            # Extract commands
            commands = self.extract_slash_commands(body_str)
            if commands:
                try:
                    # Expand commands in the request body
                    modified_body_str = await self.expand_commands_in_body(body_str, commands)
                    
                    if modified_body_str != body_str:
                        # Update request body and Content-Length
                        modified_body = modified_body_str.encode('utf-8')
                        
                        # Get headers and update Content-Length
                        headers = {}
                        for key, value in request.headers.items():
                            if key.lower() != "host":
                                headers[key] = value
                        headers["content-length"] = str(len(modified_body))
                        
                        logger.info(f"Modified request body: {len(body)} -> {len(modified_body)} bytes")
                        
                        # Proxy the modified request
                        return await self.proxy_request_with_body(request.method, target_url, modified_body, headers)
                    
                except Exception as e:
                    logger.error(f"Error expanding slash commands: {e}")
                    # Fall back to proxying original request
        
        # No slash commands or expansion failed - proxy original request
        return await self.proxy_request(request, target_url, body)


# Factory function for easy integration
def create_slash_command_middleware(upstream_url: str = "https://api.openai.com") -> SlashCommandMiddleware:
    """Create and configure slash command middleware"""
    return SlashCommandMiddleware(upstream_url=upstream_url)