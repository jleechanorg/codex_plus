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
import re
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from fastapi.responses import JSONResponse
from curl_cffi import requests

from .cerebras_middleware import CerebrasMiddleware

logger = logging.getLogger(__name__)

class LLMExecutionMiddleware:
    """Middleware that instructs LLM to execute slash commands like Claude Code CLI"""

    # Class-level locks to prevent race conditions in session initialization
    _session_init_lock = __import__('threading').Lock()

    def __init__(self, upstream_url: Optional[str] = None, url_getter: Optional[callable] = None):
        """Initialize middleware with either static URL or dynamic URL getter

        Args:
            upstream_url: Static upstream URL (legacy support)
            url_getter: Callable that returns upstream URL (allows dynamic config)
        """
        if url_getter:
            self.url_getter = url_getter
        elif upstream_url:
            self.url_getter = lambda: upstream_url
        else:
            raise ValueError("Must provide either upstream_url or url_getter")

        self.cerebras_middleware = CerebrasMiddleware()
        self.claude_dir = self._find_claude_dir()
        self.commands_dir = self.claude_dir / "commands" if self.claude_dir else None
        self.codexplus_dir = Path(".codexplus/commands")
        self.home_codexplus_dir = Path.home() / ".codexplus" / "commands"

    def _is_cerebras_upstream(self, url: str) -> bool:
        """Check if URL is Cerebras API endpoint"""
        try:
            parsed = urlparse(url)
        except Exception:
            return False

        return parsed.hostname == "api.cerebras.ai"
        
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

        # Store request for status line access
        self.current_request = request

        cleanup_stack: Optional[AsyncExitStack] = None

        # Log request headers for debugging with sensitive values redacted
        raw_headers = dict(request.headers)
        redacted_headers = {}
        for key, value in raw_headers.items():
            key_lower = key.lower()
            if key_lower in {"authorization", "cookie", "set-cookie"} or "token" in key_lower:
                redacted_headers[key] = "<REDACTED>"
            else:
                redacted_headers[key] = value
        logger.debug("📨 Request headers received", extra={"headers": redacted_headers})

        # Check if logging-only mode is enabled (passthrough without modification)
        logging_mode = os.getenv("CODEX_PLUS_LOGGING_MODE", "false") == "true"
        if logging_mode:
            logger.info("📝 Logging mode enabled - forwarding request without modification")

        # In logging mode, always use original body; otherwise check for hook modifications
        # Starlette's request.state stores explicit attributes in __dict__, so guard against
        # Mock objects that auto-create attributes during tests.
        state_dict = getattr(request.state, "__dict__", {})
        if logging_mode:
            body = await request.body()
        elif "modified_body" in state_dict:
            body = state_dict["modified_body"]
            if isinstance(body, str):
                body = body.encode("utf-8")
            logger.info("Using modified body from pre-input hooks")
        else:
            body = await request.body()
        headers = raw_headers

        # Only process if we have a JSON body and logging mode is NOT enabled
        if body and not logging_mode:
            try:
                # Parse and potentially modify the request
                data = json.loads(body)
                modified_data = self.inject_execution_behavior(data)

                # Get upstream URL dynamically
                upstream_url = self.url_getter()
                logger.info(f"📡 Using upstream URL: {upstream_url}")

                # Apply Cerebras transformation if needed
                modified_data, transformed_path = self.cerebras_middleware.process_request(
                    modified_data,
                    upstream_url,
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

        # Forward to upstream - get URL dynamically
        upstream_url = self.url_getter()
        target_url = f"{upstream_url}/{path.lstrip('/')}"

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

        is_cerebras = self._is_cerebras_upstream(upstream_url)

        # Add Cerebras authentication if using Cerebras upstream
        if is_cerebras:
            # Try CEREBRAS_API_KEY first, fallback to OPENAI_API_KEY
            cerebras_api_key = os.getenv("CEREBRAS_API_KEY") or os.getenv("OPENAI_API_KEY")
            if cerebras_api_key:
                clean_headers["Authorization"] = f"Bearer {cerebras_api_key}"
                logger.debug("🔑 Added Cerebras API key to request headers (value redacted)")
            else:
                logger.warning(
                    "⚠️  No Cerebras API key found in CEREBRAS_API_KEY or OPENAI_API_KEY environment variable"
                )
            # Ensure Content-Type is set for JSON requests (required for httpx.stream)
            if "Content-Type" not in clean_headers and "content-type" not in [k.lower() for k in clean_headers.keys()]:
                clean_headers["Content-Type"] = "application/json"

        # 🚨🚨🚨 CRITICAL PROXY FORWARDING SECTION - DUAL HTTP CLIENT 🚨🚨🚨
        # ⚠️ This is the HEART of Codex proxy functionality ⚠️
        # ✅ EXCEPTION: Dual HTTP client to support both ChatGPT and Cerebras
        try:
            # DUAL HTTP CLIENT LOGIC:
            # - Use curl_cffi for ChatGPT (Cloudflare bypass with Chrome impersonation)
            # - Use httpx for Cerebras (avoid Cloudflare blocking curl_cffi)

            if is_cerebras:
                logger.info("🌐 Using httpx.AsyncClient for Cerebras upstream")
                try:
                    debug_body = json.loads(body) if body else {}
                    logger.info(
                        "📤 Sending to Cerebras",
                        extra={
                            "model": debug_body.get("model"),
                            "messages_count": len(debug_body.get("messages", [])),
                            "tools_count": len(debug_body.get("tools", [])),
                        },
                    )
                except Exception as e:
                    logger.warning(f"Failed to log debug info: {e}")

                minimal_headers = {
                    "Content-Type": clean_headers.get("Content-Type")
                    or clean_headers.get("content-type")
                    or "application/json"
                }
                if "Authorization" in clean_headers:
                    minimal_headers["Authorization"] = clean_headers["Authorization"]

                cleanup_stack = AsyncExitStack()
                try:
                    if not hasattr(self, "_async_httpx_client"):
                        self._async_httpx_client = httpx.AsyncClient(timeout=30.0)

                    async_client: httpx.AsyncClient = self._async_httpx_client
                    response = await cleanup_stack.enter_async_context(
                        async_client.stream(
                            request.method,
                            target_url,
                            headers=minimal_headers,
                            content=body if body else None,
                        )
                    )
                except Exception as e:
                    await cleanup_stack.aclose()
                    logger.error(f"Failed to initiate Cerebras request: {e}")
                    return JSONResponse({"error": str(e)}, status_code=500)

                if response.status_code >= 400:
                    try:
                        error_bytes = await response.aread()
                    except Exception as read_error:
                        logger.error(f"❌ Cerebras error ({response.status_code}) - failed to read body: {read_error}")
                        await cleanup_stack.aclose()
                        return JSONResponse({"error": "Cerebras upstream error"}, status_code=response.status_code)

                    error_text = error_bytes.decode("utf-8", errors="replace")
                    logger.error(
                        "❌ Cerebras error response",
                        extra={"status": response.status_code, "body": error_text[:500]},
                    )
                    await cleanup_stack.aclose()
                    return JSONResponse(
                        content={"error": error_text},
                        status_code=response.status_code,
                    )
            else:
                # 🔒 CHATGPT PATH: Use curl_cffi with Chrome impersonation (REQUIRED for Cloudflare bypass)
                logger.info("🔒 Using curl_cffi for ChatGPT upstream")
                # Thread-safe session creation with double-checked locking pattern
                if not hasattr(self, '_session'):
                    with self._session_init_lock:
                        # Double-check pattern: verify session still doesn't exist after acquiring lock
                        if not hasattr(self, '_session'):
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
            # Enhanced with proper resource cleanup and Cerebras SSE transformation
            if is_cerebras:
                async def stream_response_async():
                    chunk_buffer = b""
                    sent_initial_events = False
                    response_id = None
                    logger.info(
                        "🔄 Async stream response generator started",
                        extra={"upstream": upstream_url},
                    )
                    logger.info(
                        "🔍 Cerebras response status",
                        extra={"status": response.status_code, "headers": dict(response.headers)},
                    )

                    # Initialize Cerebras response log file
                    try:
                        log_dir = Path("/tmp/codex_plus/cerebras_responses")
                        log_dir.mkdir(parents=True, exist_ok=True)
                        # Clear previous response
                        (log_dir / "latest_response.txt").write_bytes(b"")
                        logger.info("📝 Initialized Cerebras response log at /tmp/codex_plus/cerebras_responses/latest_response.txt")
                    except Exception as e:
                        logger.warning(f"Failed to initialize Cerebras response log: {e}")

                    chunk_count = 0
                    try:
                        async for chunk in response.aiter_bytes():
                            chunk_count += 1
                            logger.info(
                                "📦 Received Cerebras chunk",
                                extra={"chunk_index": chunk_count, "size": len(chunk) if chunk else 0},
                            )
                            if not chunk:
                                continue

                            # Log raw Cerebras SSE chunk
                            try:
                                log_dir = Path("/tmp/codex_plus/cerebras_responses")
                                with open(log_dir / "latest_response.txt", "ab") as f:
                                    f.write(chunk)
                                logger.info("📝 Logged Cerebras chunk", extra={"bytes": len(chunk)})
                            except Exception as e:
                                logger.warning(f"Failed to log Cerebras response chunk: {e}")

                            chunk_buffer += chunk
                            events = chunk_buffer.split(b"\n\n")
                            chunk_buffer = events[-1]

                            for event in events[:-1]:
                                if not event.strip():
                                    continue

                                logger.info("🔍 Raw Cerebras event", extra={"preview": event[:300]})
                                lines = event.decode("utf-8", errors="ignore").strip().split("\n")
                                for line in lines:
                                    if not line.startswith("data: "):
                                        continue

                                    data_str = line[6:]
                                    if data_str == "[DONE]":
                                        completion = {
                                            "type": "response.completed",
                                            "response": {"status": "completed"},
                                        }
                                        yield f"data: {json.dumps(completion)}\n\n".encode("utf-8")
                                        continue

                                    try:
                                        chunk_data = json.loads(data_str)
                                    except json.JSONDecodeError:
                                        logger.warning(
                                            "Failed to parse SSE chunk", extra={"preview": data_str[:100]}
                                        )
                                        continue

                                    choices = chunk_data.get("choices", [])
                                    if not choices:
                                        continue

                                    delta = choices[0].get("delta", {})

                                    if not sent_initial_events and (
                                        delta.get("content") or delta.get("tool_calls")
                                    ):
                                        response_id = chunk_data.get("id", "")
                                        created = {
                                            "type": "response.created",
                                            "response": {
                                                "id": response_id,
                                                "status": "in_progress",
                                            },
                                        }
                                        yield f"data: {json.dumps(created)}\n\n".encode("utf-8")

                                        if delta.get("tool_calls"):
                                            tool_call = delta["tool_calls"][0]
                                            function_name = (
                                                tool_call.get("function", {}).get("name", "unknown")
                                            )
                                            call_id = tool_call.get("id", "call_0")
                                            added = {
                                                "type": "response.output_item.added",
                                                "item": {
                                                    "id": call_id,
                                                    "type": "function_call",
                                                    "name": function_name,
                                                    "call_id": call_id,
                                                    "arguments": "",
                                                },
                                            }
                                        else:
                                            added = {
                                                "type": "response.output_item.added",
                                                "item": {
                                                    "id": "item_0",
                                                    "type": "message",
                                                    "role": "assistant",
                                                    "content": [],
                                                },
                                            }

                                        yield f"data: {json.dumps(added)}\n\n".encode("utf-8")
                                        sent_initial_events = True

                                    if delta.get("content"):
                                        transformed = {
                                            "type": "response.output_text.delta",
                                            "delta": delta["content"],
                                        }
                                        yield f"data: {json.dumps(transformed)}\n\n".encode("utf-8")
                                    elif delta.get("tool_calls"):
                                        for tool_call in delta["tool_calls"]:
                                            function_data = tool_call.get("function", {})
                                            arguments = function_data.get("arguments")
                                            if arguments:
                                                tool_delta = {
                                                    "type": "response.function_call.arguments.delta",
                                                    "delta": arguments,
                                                }
                                                yield f"data: {json.dumps(tool_delta)}\n\n".encode("utf-8")
                                    elif choices[0].get("finish_reason"):
                                        completion = {
                                            "type": "response.completed",
                                            "response": {
                                                "id": response_id or chunk_data.get("id", ""),
                                                "status": "completed",
                                            },
                                        }
                                        yield f"data: {json.dumps(completion)}\n\n".encode("utf-8")
                                        yield b"\n"
                    finally:
                        if cleanup_stack is not None:
                            await cleanup_stack.aclose()

                stream_source = stream_response_async()
            else:
                def stream_response():
                    response_closed = False
                    logger.info(
                        "🔄 Stream response generator started",
                        extra={"upstream": upstream_url},
                    )
                    logger.info(
                        "🔍 Response status",
                        extra={"status": response.status_code, "headers": dict(response.headers)},
                    )

                    chunk_count = 0
                    try:
                        try:
                            log_dir = Path("/tmp/codex_plus/chatgpt_responses")
                            log_dir.mkdir(parents=True, exist_ok=True)
                            (log_dir / "latest_response.txt").write_bytes(b"")
                            logger.info(
                                "📝 Initialized response log at /tmp/codex_plus/chatgpt_responses/latest_response.txt"
                            )
                        except Exception as e:
                            logger.warning(f"Failed to initialize response log: {e}")

                        for chunk in response.iter_content(chunk_size=None):
                            chunk_count += 1
                            logger.info(
                                "📦 Received chunk",
                                extra={"chunk_index": chunk_count, "size": len(chunk) if chunk else 0},
                            )
                            if not chunk:
                                continue

                            try:
                                log_dir = Path("/tmp/codex_plus/chatgpt_responses")
                                log_dir.mkdir(parents=True, exist_ok=True)
                                with open(log_dir / "latest_response.txt", "ab") as f:
                                    f.write(chunk)
                                logger.info("📝 Logged ChatGPT chunk", extra={"bytes": len(chunk)})
                            except Exception as e:
                                logger.warning(f"Failed to log response chunk: {e}")

                            yield chunk
                    except Exception as e:
                        logger.error(f"Error during streaming: {e}")
                        if not response_closed:
                            try:
                                response.close()
                                response_closed = True
                            except Exception:
                                pass
                        raise
                    finally:
                        if not response_closed:
                            try:
                                response.close()
                            except Exception:
                                pass
                        if hasattr(response, "_close_cm"):
                            try:
                                response._close_cm(None, None, None)
                            except Exception:
                                pass

                stream_source = stream_response()
            # Get response headers - ONLY forward essential SSE headers
            # Strip all upstream-specific headers (Cloudflare, Cerebras, etc.)
            upstream_headers = dict(response.headers)

            # Whitelist of headers to forward (ChatGPT-compatible)
            resp_headers = {}
            safe_headers = {
                "content-type",  # Required for SSE
                "cache-control", # Caching behavior
                "connection",    # Keep-alive
            }

            # Only forward whitelisted headers
            for header in safe_headers:
                if header in upstream_headers:
                    resp_headers[header] = upstream_headers[header]

            # Ensure SSE content-type is set
            if "content-type" not in resp_headers:
                resp_headers["content-type"] = "text/event-stream; charset=utf-8"

            logger.info(f"📤 Forwarding headers: {list(resp_headers.keys())}")
            
            # Store response reference for cleanup on middleware destruction
            if not hasattr(self, '_active_responses'):
                self._active_responses = []
            self._active_responses.append(response)

            # Create streaming response with automatic cleanup tracking
            streaming_response = StreamingResponse(
                stream_source,
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


def create_llm_execution_middleware(upstream_url: Optional[str] = None, url_getter: Optional[callable] = None):
    """Factory function to create middleware instance

    Args:
        upstream_url: Static upstream URL (legacy support)
        url_getter: Callable that returns upstream URL (allows dynamic config)
    """
    return LLMExecutionMiddleware(upstream_url=upstream_url, url_getter=url_getter)
