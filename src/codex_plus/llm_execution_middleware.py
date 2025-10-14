"""
LLM Execution Middleware - Instructs LLM to execute slash commands natively
Instead of expanding commands to their content, this tells the LLM to read and execute them

🚨🚨🚨 WARNING: CONTAINS CRITICAL PROXY FORWARDING LOGIC 🚨🚨🚨

⚠️  CORE PROXY FORWARDING - EXTREME CAUTION REQUIRED ⚠️

This middleware contains the critical curl_cffi proxy forwarding logic that
enables Codex to bypass Cloudflare and communicate with ChatGPT backend.

🔒 PROTECTED COMPONENTS (DO NOT TOUCH):
- curl_cffi session configuration
- Request forwarding to upstream_url
- Authentication header handling
- Streaming response logic
- Chrome impersonation settings

✅ SAFE TO MODIFY:
- Slash command detection and processing
- Command file reading logic
- LLM instruction injection
- Hook integration points

❌ FORBIDDEN MODIFICATIONS:
- Changing curl_cffi to any other HTTP client
- Modifying upstream URL handling
- Altering authentication forwarding
- Removing Chrome impersonation
- Breaking streaming response handling

Breaking these rules WILL break all Codex functionality.
"""
import json
import logging
import os
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re
from fastapi.responses import JSONResponse

from .chat_colorizer import apply_claude_colors

logger = logging.getLogger(__name__)

STATUS_LINE_INSTRUCTION_PREFIX = "Append this status line as the final line of your response:"


class LLMExecutionMiddleware:
    """Middleware that instructs LLM to execute slash commands like Claude Code CLI"""

    # Class-level lock to prevent race condition in session initialization
    _session_init_lock = __import__('threading').Lock()
    _RETRY_DELAYS: Tuple[float, ...] = (0.5,)  # seconds
    _MAX_STREAM_ERROR_MESSAGE = 240

    def __init__(self, upstream_url: str):
        self.upstream_url = upstream_url
        self.claude_dir = self._find_claude_dir()
        self.commands_dir = self.claude_dir / "commands" if self.claude_dir else None
        self.codexplus_dir = Path(".codexplus/commands")
        self.home_codexplus_dir = Path.home() / ".codexplus" / "commands"
        self._retry_schedule = self._RETRY_DELAYS

    @staticmethod
    def _append_status_line(content: str, status_line_instruction: Optional[str]) -> str:
        """Append the status line instruction to the provided content if present."""
        if not status_line_instruction:
            return content
        if content:
            return f"{content}\n\n{status_line_instruction}"
        return status_line_instruction
        
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

        # Find all /command positions
        command_positions = []
        for match in re.finditer(r'(?:^|\s)/([A-Za-z0-9_-]+)', text):
            command_positions.append((match.start(), match.end(), match.group(1)))

        i = 0
        while i < len(command_positions):
            start, end, command = command_positions[i]

            # Find where this command's arguments end
            if i + 1 < len(command_positions):
                next_start, _, _ = command_positions[i + 1]
                # Arguments are everything between this command and the next command
                args = text[end:next_start].strip()
            else:
                # Last command - arguments are everything remaining
                args = text[end:].strip()

            commands.append((command, args))
            i += 1

        return commands
    
    def find_command_file(self, command_name: str) -> Optional[Path]:
        """Locate command definition with local .codexplus, home ~/.codexplus, then .claude."""
        search_roots = [self.codexplus_dir, self.home_codexplus_dir]
        if self.commands_dir:
            search_roots.append(self.commands_dir)

        for root in search_roots:
            if not root or not root.exists():
                continue
            command_file = root / f"{command_name}.md"
            if command_file.exists():
                return command_file

        return None
    
    def create_execution_instruction(self, commands: List[Tuple[str, str]]) -> str:
        """Create system instruction for LLM to execute commands"""
        
        instruction = """You are a slash command interpreter executing a command definition file.

ROLE: You are executing a program, not reading documentation.

INPUT: The file contains an executable workflow that MUST be run step-by-step.

EXECUTION RULES:
1. Execute each instruction in the exact order presented
2. When you see bash code blocks: RUN them and show actual output
3. When you see "Use Edit/MultiEdit tools": USE those tools immediately
4. When you see phases: COMPLETE each phase fully before proceeding

OUTPUT FORMAT:
- Show only execution results and actual outputs
- Do NOT explain what you're doing
- Do NOT summarize the commands
- Do NOT describe what the file contains

VERIFICATION GATES:
- After code changes: Show git diff output or mark "NO_CHANGES"
- Before posting comments: Verify "IMPLEMENTATION_COMPLETE" 
- If implementation fails: Output "EXECUTION_HALTED" and stop

EXAMPLE:
Input: "Phase 1: Run tests"
Output: [Actual test execution output]
NOT: "This phase runs tests to verify the code"

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
                        preview_lines = []
                        for _ in range(5):
                            line = f.readline()
                            if not line:
                                break
                            preview_lines.append(line.rstrip())
                        if preview_lines:
                            preview = '\n'.join(preview_lines)
                            instruction += f"\n  - Preview: {preview[:100]}..."
                except:
                    pass
            else:
                # Generic instruction for unknown commands
                instruction += f"\n/{command_name}:"
                instruction += f"\n  - Interpret and execute this command with args: {args}"
                instruction += f"\n  - Provide appropriate output for the command type"
        
        instruction += """

CRITICAL - YOU ARE NOW EXECUTING:
- This is NOT a request to explain the commands
- This is NOT documentation to summarize  
- This IS a program to execute immediately
- Begin execution with the first instruction
- Show ONLY actual outputs from running commands
- If you cannot execute something, output "EXECUTION_FAILED: [reason]"

Remember: You are an interpreter running a script, not an assistant explaining it.
BEGIN EXECUTION NOW:
"""
        
        return instruction
    
    def inject_execution_behavior(self, request_body: Dict) -> Dict:
        """Modify request to inject execution behavior"""

        # Get status line from request state if available
        status_line = getattr(self.current_request.state, 'status_line', None) if hasattr(self, 'current_request') and hasattr(self.current_request, 'state') else None

        # Detect slash commands in the user's message
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
        
        # Handle standard format with messages field
        elif "messages" in request_body:
            for message in request_body["messages"]:
                if message.get("role") == "user" and "content" in message:
                    text = message["content"]
                    detected = self.detect_slash_commands(text)
                    if detected:
                        commands.extend(detected)
        
        # Build injection content
        injection_parts = []

        # Add status line if available
        if status_line:
            # Guide Claude to render the status line at the end of its reply
            injection_parts.append(
                f"{STATUS_LINE_INSTRUCTION_PREFIX} {status_line}"
            )
            logger.info(f"📌 Will inject status line: {status_line}")

        # Add execution instructions if needed
        if commands:
            logger.info(f"🎯 Detected slash commands: {commands}")
            execution_instruction = self.create_execution_instruction(commands)
            injection_parts.append(execution_instruction)

        # If we have content to inject
        if injection_parts:
            # Split status line and execution instructions for different handling
            status_line_instruction = None
            execution_instructions = []

            for part in injection_parts:
                if part.startswith(STATUS_LINE_INSTRUCTION_PREFIX):
                    status_line_instruction = part
                else:
                    execution_instructions.append(part)

            # Inject as system message at the beginning
            if "messages" in request_body:
                # Standard format - insert system message for execution instructions only
                if execution_instructions:
                    combined_execution = "\n\n".join(execution_instructions)
                    request_body["messages"].insert(0, {
                        "role": "system",
                        "content": combined_execution
                    })

                # Add status line instruction directly to user message
                if status_line_instruction:
                    for message in request_body["messages"]:
                        if message.get("role") == "user":
                            current_content = message.get("content", "")
                            message["content"] = self._append_status_line(
                                current_content,
                                status_line_instruction,
                            )
                            break

                logger.info("💉 Injected status line and/or execution instruction as system message")

            elif "input" in request_body:
                # Codex format - handle status line and execution instructions separately
                for item in request_body["input"]:
                    if isinstance(item, dict) and item.get("type") == "message":
                        content_list = item.get("content", [])
                        for content_item in content_list:
                            if isinstance(content_item, dict) and content_item.get("type") == "input_text":
                                current_text = content_item.get("text", "")

                                # Add status line instruction directly as visible text
                                if status_line_instruction:
                                    current_text = self._append_status_line(
                                        current_text,
                                        status_line_instruction,
                                    )

                                # Add execution instructions as system instruction
                                if execution_instructions:
                                    combined_execution = "\n\n".join(execution_instructions)
                                    current_text = f"[SYSTEM: {combined_execution}]\n\n{current_text}"

                                content_item["text"] = current_text
                                logger.info("💉 Injected status line and/or execution instruction into input text")
                                break
                        break
        
        return request_body
    
    async def process_request(self, request, path: str):
        """Process request with execution behavior injection"""
        from fastapi.responses import StreamingResponse
        from curl_cffi import requests

        # Store request for status line access
        self.current_request = request

        # Check if logging-only mode is enabled (passthrough without modification)
        logging_mode = os.getenv("CODEX_PLUS_LOGGING_MODE", "false") == "true"
        if logging_mode:
            logger.info("📝 Logging mode enabled - forwarding request without modification")

        # In logging mode, always use original body; otherwise check for hook modifications
        if logging_mode:
            body = await request.body()
        elif hasattr(request.state, 'modified_body'):
            body = request.state.modified_body
            logger.info("Using modified body from pre-input hooks")
        else:
            body = await request.body()
        headers = dict(request.headers)

        # Only process if we have a JSON body and logging mode is NOT enabled
        if body and not logging_mode:
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

        # Validate upstream URL using security function
        from .main_sync_cffi import _validate_upstream_url, _sanitize_headers
        if not _validate_upstream_url(target_url):
            logger.error(f"Blocked request to invalid upstream URL: {target_url}")
            return JSONResponse({"error": "Invalid upstream URL"}, status_code=400)

        # Remove hop-by-hop headers that shouldn't be forwarded
        hop_by_hop = {
            'connection', 'keep-alive', 'proxy-authenticate',
            'proxy-authorization', 'te', 'trailers',
            'transfer-encoding', 'upgrade', 'host'
        }

        # Clean headers for forwarding
        clean_headers = {}
        for k, v in headers.items():
            if k.lower() not in hop_by_hop:
                clean_headers[k] = v

        # Apply security header sanitization
        clean_headers = _sanitize_headers(clean_headers)

        # 🚨🚨🚨 CRITICAL PROXY FORWARDING SECTION - DO NOT MODIFY 🚨🚨🚨
        # ⚠️ This is the HEART of Codex proxy functionality ⚠️
        # ❌ FORBIDDEN: Any changes to curl_cffi, session, or request handling
        try:
            # 🔒 PROTECTED: curl_cffi Chrome impersonation - REQUIRED for Cloudflare bypass
            # Thread-safe session creation with double-checked locking pattern
            if not hasattr(self, '_session'):
                with self._session_init_lock:
                    # Double-check pattern: verify session still doesn't exist after acquiring lock
                    if not hasattr(self, '_session'):
                        self._session = requests.Session(impersonate="chrome124")
            session = self._session

            # 🔒 PROTECTED: Core request forwarding - DO NOT CHANGE
            response = None
            attempt = 0
            retry_schedule = self._retry_schedule
            last_exception: Optional[Exception] = None
            while True:
                try:
                    response = session.request(
                        request.method,
                        target_url,
                        headers=clean_headers,
                        data=body if body else None,
                        stream=True,
                        timeout=30
                    )
                    break
                except requests.exceptions.RequestException as exc:
                    last_exception = exc
                    if attempt >= len(retry_schedule):
                        raise
                    delay = retry_schedule[attempt]
                    attempt += 1
                    logger.warning(
                        "Upstream request failed (%s). Retrying in %.1fs (attempt %d/%d)",
                        exc,
                        delay,
                        attempt,
                        len(retry_schedule) + 1,
                    )
                    await asyncio.sleep(delay)
            content_type = response.headers.get("content-type", "") or ""
            is_event_stream = "text/event-stream" in content_type.lower()
            
            # 🔒 PROTECTED: Streaming response generator - CRITICAL for real-time responses
            # Enhanced with proper resource cleanup to prevent connection leaks
            def stream_response():
                response_closed = False

                def close_response():
                    nonlocal response_closed
                    if not response_closed:
                        try:
                            response.close()
                        except Exception:
                            pass
                        else:
                            response_closed = True

                try:
                    # 🔒 PROTECTED: Core streaming iteration - DO NOT MODIFY
                    for chunk in response.iter_content(chunk_size=None):
                        if chunk:
                            # 🔒 PROTECTED: Chunk yielding - DO NOT REMOVE
                            yield chunk
                except Exception as exc:
                    logger.error(f"Error during streaming: {exc}")
                    if isinstance(exc, requests.exceptions.RequestException):
                        if is_event_stream:
                            error_code, safe_message = self._classify_stream_error(exc)
                            error_chunk = self._format_stream_error_event(error_code, safe_message)
                            close_response()
                            yield error_chunk
                            return
                    close_response()
                    raise
                finally:
                    close_response()
            
            # Get response headers
            resp_headers = dict(response.headers)
            resp_headers.pop("content-length", None)
            resp_headers.pop("content-encoding", None)
            
            # Store response reference for cleanup on middleware destruction
            if not hasattr(self, '_active_responses'):
                self._active_responses = []
            self._active_responses.append(response)

            # Create streaming response with automatic cleanup tracking
            body_stream = stream_response()
            content_type = resp_headers.get("content-type", "")
            if "text/event-stream" in content_type:
                body_stream = apply_claude_colors(body_stream)

            streaming_response = StreamingResponse(
                body_stream,
                status_code=response.status_code,
                headers=resp_headers,
                media_type=resp_headers.get("content-type", "text/event-stream")
            )

            # Schedule cleanup of response reference when streaming completes
            async def cleanup_response():
                try:
                    if hasattr(self, '_active_responses') and response in self._active_responses:
                        self._active_responses.remove(response)
                except:
                    pass

            # Add cleanup callback (if supported by FastAPI StreamingResponse)
            if hasattr(streaming_response, 'background'):
                from starlette.background import BackgroundTask
                streaming_response.background = BackgroundTask(cleanup_response)

            return streaming_response
            
        except Exception as e:
            logger.error(f"Proxy request failed: {e}")
            return JSONResponse(
                content={"error": f"Proxy failed: {str(e)}"},
                status_code=500
            )

    @classmethod
    def _classify_stream_error(cls, exc: Exception) -> Tuple[str, str]:
        """Classify upstream streaming errors for structured reporting."""
        message = str(exc).strip() or exc.__class__.__name__
        if len(message) > cls._MAX_STREAM_ERROR_MESSAGE:
            message = message[: cls._MAX_STREAM_ERROR_MESSAGE - 3] + "..."
        lower_msg = message.lower()
        if "timeout" in lower_msg or "too slow" in lower_msg:
            code = "UPSTREAM_TIMEOUT"
        else:
            code = "UPSTREAM_ERROR"
        return code, message

    @staticmethod
    def _format_stream_error_event(code: str, message: str) -> bytes:
        """Create an SSE payload describing a streaming error."""
        payload = {"type": "error", "code": code, "message": message}
        return f"data: {json.dumps(payload)}\n\n".encode("utf-8")


def create_llm_execution_middleware(upstream_url: str):
    """Factory function to create middleware instance"""
    return LLMExecutionMiddleware(upstream_url)
