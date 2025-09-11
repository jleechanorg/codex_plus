"""
LLM Execution Middleware - Instructs LLM to execute slash commands natively
Instead of expanding commands to their content, this tells the LLM to read and execute them
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re

logger = logging.getLogger(__name__)

class LLMExecutionMiddleware:
    """Middleware that instructs LLM to execute slash commands like Claude Code CLI"""
    
    def __init__(self, upstream_url: str):
        self.upstream_url = upstream_url
        self.claude_dir = self._find_claude_dir()
        self.commands_dir = self.claude_dir / "commands" if self.claude_dir else None
        self.codexplus_dir = Path(".codexplus/commands")
        
    def _find_claude_dir(self) -> Optional[Path]:
        """Find .claude directory in project hierarchy"""
        current = Path.cwd()
        while current != current.parent:
            claude_dir = current / ".claude"
            if claude_dir.exists():
                return claude_dir
            current = current.parent
        
        # Check in home directory as fallback
        home_claude = Path.home() / ".claude"
        if home_claude.exists():
            return home_claude
        
        return None
    
    def detect_slash_commands(self, text: str) -> List[Tuple[str, str]]:
        """Detect slash commands in text and return (command, args) tuples"""
        commands = []
        # Match commands at start of line or after whitespace
        pattern = r'(?:^|\s)/([A-Za-z0-9_-]+)(?:\s+([^\n/]*))?'
        
        for match in re.finditer(pattern, text):
            command = match.group(1)
            args = match.group(2) or ""
            commands.append((command, args.strip()))
            
        return commands
    
    def find_command_file(self, command_name: str) -> Optional[Path]:
        """Find command file in .codexplus/commands or .claude/commands"""
        # Check .codexplus/commands first (higher priority)
        if self.codexplus_dir.exists():
            command_file = self.codexplus_dir / f"{command_name}.md"
            if command_file.exists():
                return command_file
        
        # Then check .claude/commands
        if self.commands_dir and self.commands_dir.exists():
            command_file = self.commands_dir / f"{command_name}.md"
            if command_file.exists():
                return command_file
        
        return None
    
    def create_execution_instruction(self, commands: List[Tuple[str, str]]) -> str:
        """Create system instruction for LLM to execute commands"""
        
        instruction = """You are an AI assistant with slash command execution capabilities.

When you see slash commands (starting with /), you must:
1. Recognize them as executable commands, not conversation
2. Execute them directly and show actual results
3. Format output appropriately (code blocks, terminal output, etc.)
4. Do not explain what you're doing unless asked - just execute

Available slash commands and their behaviors:
"""
        
        # Add specific instructions for each detected command
        for command_name, args in commands:
            command_file = self.find_command_file(command_name)
            if command_file:
                instruction += f"\n/{command_name}:"
                instruction += f"\n  - Location: {command_file}"
                instruction += f"\n  - Execute the instructions in this command file"
                instruction += f"\n  - Apply arguments: {args}" if args else "\n  - No arguments provided"
                
                # Read first few lines of command file for context
                try:
                    with open(command_file, 'r') as f:
                        lines = f.readlines()[:5]
                        preview = ''.join(lines).strip()
                        if preview:
                            instruction += f"\n  - Preview: {preview[:100]}..."
                except:
                    pass
            else:
                # Generic instruction for unknown commands
                instruction += f"\n/{command_name}:"
                instruction += f"\n  - Interpret and execute this command with args: {args}"
                instruction += f"\n  - Provide appropriate output for the command type"
        
        instruction += """

IMPORTANT: 
- Execute these commands NOW in your response
- Show actual output, not descriptions
- Format as the command would naturally output
- For code/tests, use appropriate code blocks
- For searches, show file:line format
- For git commands, show git-style output
"""
        
        return instruction
    
    def inject_execution_behavior(self, request_body: Dict) -> Dict:
        """Modify request to inject execution behavior"""
        
        # Detect slash commands in the user's message
        user_message = ""
        commands = []
        
        # Handle Codex CLI format with input field
        if "input" in request_body:
            for item in request_body["input"]:
                if isinstance(item, dict) and item.get("type") == "message":
                    content_list = item.get("content", [])
                    for content_item in content_list:
                        if isinstance(content_item, dict) and content_item.get("type") == "input_text":
                            text = content_item.get("text", "")
                            detected = self.detect_slash_commands(text)
                            if detected:
                                commands.extend(detected)
                                user_message = text
        
        # Handle standard format with messages field
        elif "messages" in request_body:
            for message in request_body["messages"]:
                if message.get("role") == "user" and "content" in message:
                    text = message["content"]
                    detected = self.detect_slash_commands(text)
                    if detected:
                        commands.extend(detected)
                        user_message = text
        
        # If we found slash commands, inject execution instructions
        if commands:
            logger.info(f"🎯 Detected slash commands: {commands}")
            
            execution_instruction = self.create_execution_instruction(commands)
            
            # Inject as system message at the beginning
            if "messages" in request_body:
                # Standard format - insert system message
                request_body["messages"].insert(0, {
                    "role": "system",
                    "content": execution_instruction
                })
                logger.info("💉 Injected execution instruction as system message")
                
            elif "input" in request_body:
                # Codex format - modify the first message or add instruction
                # We'll prepend the instruction to the user's message
                for item in request_body["input"]:
                    if isinstance(item, dict) and item.get("type") == "message":
                        content_list = item.get("content", [])
                        for content_item in content_list:
                            if isinstance(content_item, dict) and content_item.get("type") == "input_text":
                                original = content_item.get("text", "")
                                # Prepend instruction as a hidden context
                                content_item["text"] = f"[SYSTEM: {execution_instruction}]\n\n{original}"
                                logger.info("💉 Injected execution instruction into input text")
                                break
                        break
        
        return request_body
    
    async def process_request(self, request, path: str):
        """Process request with execution behavior injection"""
        from fastapi.responses import StreamingResponse, JSONResponse
        from curl_cffi import requests
        
        body = await request.body()
        headers = dict(request.headers)
        
        # Only process if we have a JSON body
        if body:
            try:
                # Parse and potentially modify the request
                data = json.loads(body)
                modified_data = self.inject_execution_behavior(data)
                
                # Convert back to JSON
                modified_body = json.dumps(modified_data).encode('utf-8')
                
                # Update content length if changed
                if len(modified_body) != len(body):
                    headers['content-length'] = str(len(modified_body))
                    logger.info(f"📏 Updated content-length: {len(body)} -> {len(modified_body)}")
                
                body = modified_body
                
            except json.JSONDecodeError:
                logger.warning("Could not parse body as JSON, forwarding as-is")
            except Exception as e:
                logger.error(f"Error processing request: {e}")
        
        # Forward to upstream
        target_url = f"{self.upstream_url}/{path.lstrip('/')}"
        
        try:
            # Use synchronous curl_cffi with Chrome impersonation
            if not hasattr(self, '_session'):
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
            
            # Stream the response back
            def stream_response():
                try:
                    for chunk in response.iter_content(chunk_size=None):
                        if chunk:
                            yield chunk
                except Exception as e:
                    logger.error(f"Error during streaming: {e}")
                    raise
                finally:
                    try:
                        response.close()
                    except:
                        pass
            
            # Get response headers
            resp_headers = dict(response.headers)
            resp_headers.pop("content-length", None)
            resp_headers.pop("content-encoding", None)
            
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


def create_llm_execution_middleware(upstream_url: str):
    """Factory function to create middleware instance"""
    return LLMExecutionMiddleware(upstream_url)