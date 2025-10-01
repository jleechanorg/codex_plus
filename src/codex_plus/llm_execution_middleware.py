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
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re
from fastapi.responses import JSONResponse
from .cerebras_middleware import CerebrasMiddleware
import httpx

logger = logging.getLogger(__name__)

class LLMExecutionMiddleware:
    """Middleware that instructs LLM to execute slash commands like Claude Code CLI"""

    # Class-level lock to prevent race condition in session initialization
    _session_init_lock = __import__('threading').Lock()

    def __init__(self, upstream_url: str):
        self.upstream_url = upstream_url
        self.cerebras_middleware = CerebrasMiddleware()
        self.claude_dir = self._find_claude_dir()
        self.commands_dir = self.claude_dir / "commands" if self.claude_dir else None
        self.codexplus_dir = Path(".codexplus/commands")
        self.home_codexplus_dir = Path.home() / ".codexplus" / "commands"

    def _is_cerebras_upstream(self, url: str) -> bool:
        """Check if URL is Cerebras API endpoint"""
        return "api.cerebras.ai" in url
        
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
            # Simple, direct instruction that Claude is more likely to follow
            injection_parts.append(f"Display this status line first: {status_line}")
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
                if part.startswith("Display this status line first:"):
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
                            message["content"] = f"{status_line_instruction}\n\n{current_content}"
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
                                    current_text = f"{status_line_instruction}\n\n{current_text}"

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

        # Check if pre-input hooks modified the body
        if hasattr(request.state, 'modified_body'):
            body = request.state.modified_body
            logger.info("Using modified body from pre-input hooks")
        else:
            body = await request.body()
        headers = dict(request.headers)

        # Only process if we have a JSON body
        if body:
            try:
                # Parse and potentially modify the request
                data = json.loads(body)
                modified_data = self.inject_execution_behavior(data)

                # Apply Cerebras transformation if needed
                modified_data, transformed_path = self.cerebras_middleware.process_request(
                    modified_data,
                    self.upstream_url,
                    path
                )

                # Use transformed path if provided
                if transformed_path != path:
                    logger.info(f"📍 Path transformed: {path} → {transformed_path}")
                    path = transformed_path

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

        # Add Cerebras authentication if using Cerebras upstream
        if "api.cerebras.ai" in self.upstream_url:
            import os
            # Try CEREBRAS_API_KEY first, fallback to OPENAI_API_KEY
            cerebras_api_key = os.getenv("CEREBRAS_API_KEY") or os.getenv("OPENAI_API_KEY")
            if cerebras_api_key:
                clean_headers["Authorization"] = f"Bearer {cerebras_api_key}"
                logger.info(f"🔑 Added Cerebras API key to request headers (ends with ...{cerebras_api_key[-10:]})")
            else:
                logger.warning("⚠️  No Cerebras API key found in CEREBRAS_API_KEY or OPENAI_API_KEY environment variable")
            # Ensure Content-Type is set for JSON requests (required for httpx.Request with content=)
            if "Content-Type" not in clean_headers and "content-type" not in [k.lower() for k in clean_headers.keys()]:
                clean_headers["Content-Type"] = "application/json"

        # 🚨🚨🚨 CRITICAL PROXY FORWARDING SECTION - DUAL HTTP CLIENT 🚨🚨🚨
        # ⚠️ This is the HEART of Codex proxy functionality ⚠️
        # ✅ EXCEPTION: Dual HTTP client to support both ChatGPT and Cerebras
        try:
            # DUAL HTTP CLIENT LOGIC:
            # - Use curl_cffi for ChatGPT (Cloudflare bypass with Chrome impersonation)
            # - Use httpx for Cerebras (avoid Cloudflare blocking curl_cffi)

            if self._is_cerebras_upstream(target_url):
                # 🔧 CEREBRAS PATH: Use httpx (Cloudflare blocks curl_cffi impersonation)
                logger.info("🌐 Using httpx for Cerebras upstream")
                # Debug: log what we're sending
                try:
                    debug_body = json.loads(body) if body else {}
                    logger.info(f"📤 Sending to Cerebras: model={debug_body.get('model')}, messages_count={len(debug_body.get('messages', []))}, tools_count={len(debug_body.get('tools', []))}")
                    # Save full request for debugging
                    import os
                    os.makedirs("/tmp/codex_plus/cerebras_debug", exist_ok=True)
                    with open("/tmp/codex_plus/cerebras_debug/last_request.json", "w") as f:
                        json.dump(debug_body, f, indent=2)
                    logger.info("📝 Saved full request to /tmp/codex_plus/cerebras_debug/last_request.json")
                except Exception as e:
                    logger.warning(f"Failed to log debug info: {e}")
                # Use httpx for Cerebras (no Chrome impersonation needed/wanted)
                httpx_client = httpx.Client(timeout=30.0)
                # Parse JSON body for proper httpx.post() usage
                try:
                    json_body = json.loads(body) if body else {}
                except Exception as e:
                    logger.error(f"Failed to parse body as JSON: {e}")
                    json_body = {}
                # Use ONLY minimal headers (Authorization + Content-Type)
                # This matches what works in direct API calls
                # Forwarding all headers from original request triggers Cloudflare WAF
                minimal_headers = {
                    "Authorization": clean_headers.get("Authorization", ""),
                    "Content-Type": "application/json"
                }
                # Make request using httpx with json= parameter (NOT content=)
                # This ensures proper Content-Type and encoding
                request_obj = httpx_client.build_request(
                    "POST",
                    target_url,
                    headers=minimal_headers,
                    json=json_body
                )
                response = httpx_client.send(request_obj, stream=True)
                # Log error responses for debugging
                if response.status_code >= 400:
                    try:
                        error_text = response.read().decode('utf-8')
                        logger.error(f"❌ Cerebras error ({response.status_code}): {error_text[:500]}")
                        # Save error for debugging
                        import os
                        with open("/tmp/codex_plus/cerebras_debug/last_error.txt", "w") as f:
                            f.write(f"Status: {response.status_code}\n\n{error_text}")
                        # Need to recreate response since we read the body
                        response = httpx_client.send(
                            httpx.Request(
                                request.method,
                                target_url,
                                headers=clean_headers,
                                content=body if body else None
                            ),
                            stream=True
                        )
                    except Exception as e:
                        logger.warning(f"Failed to log error: {e}")
                # Convert httpx response to compatible format
                response.iter_content = lambda chunk_size=None: response.iter_bytes()
                # Store client for cleanup
                response._httpx_client = httpx_client
            else:
                # 🔒 CHATGPT PATH: Use curl_cffi with Chrome impersonation (REQUIRED for Cloudflare bypass)
                logger.info("🔒 Using curl_cffi for ChatGPT upstream")
                # Thread-safe session creation with double-checked locking pattern
                if not hasattr(self, '_session'):
                    with self._session_init_lock:
                        # Double-check pattern: verify session still doesn't exist after acquiring lock
                        if not hasattr(self, '_session'):
                            from curl_cffi import requests
                            self._session = requests.Session(impersonate="chrome124")
                session = self._session

                # Core request forwarding
                response = session.request(
                    request.method,
                    target_url,
                    headers=clean_headers,
                    data=body if body else None,
                    stream=True,
                    timeout=30
                )
            
            # 🔒 PROTECTED: Streaming response generator - CRITICAL for real-time responses
            # Enhanced with proper resource cleanup to prevent connection leaks
            def stream_response():
                response_closed = False
                try:
                    # 🔒 PROTECTED: Core streaming iteration - DO NOT MODIFY
                    for chunk in response.iter_content(chunk_size=None):
                        if chunk:
                            # 🔒 PROTECTED: Chunk yielding - DO NOT REMOVE
                            yield chunk
                except Exception as e:
                    logger.error(f"Error during streaming: {e}")
                    # Ensure response is closed on error
                    if not response_closed:
                        try:
                            response.close()
                            # Cleanup httpx client if present
                            if hasattr(response, '_httpx_client'):
                                response._httpx_client.close()
                            response_closed = True
                        except:
                            pass
                    raise
                finally:
                    # Ensure response is always closed
                    if not response_closed:
                        try:
                            response.close()
                            # Cleanup httpx client if present
                            if hasattr(response, '_httpx_client'):
                                response._httpx_client.close()
                        except:
                            pass
            
            # Get response headers
            resp_headers = dict(response.headers)
            resp_headers.pop("content-length", None)
            resp_headers.pop("content-encoding", None)
            
            # Store response reference for cleanup on middleware destruction
            if not hasattr(self, '_active_responses'):
                self._active_responses = []
            self._active_responses.append(response)

            # Create streaming response with automatic cleanup tracking
            streaming_response = StreamingResponse(
                stream_response(),
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


def create_llm_execution_middleware(upstream_url: str):
    """Factory function to create middleware instance"""
    return LLMExecutionMiddleware(upstream_url)
