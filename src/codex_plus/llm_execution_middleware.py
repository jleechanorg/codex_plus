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
import asyncio
import json
import logging
import os
import re
import time
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4
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
        self.upstream_url: Optional[str]

        if url_getter:
            self.url_getter = url_getter
            try:
                # Best-effort capture of the current value for backward compatibility tests
                self.upstream_url = self.url_getter()
            except Exception:
                # Dynamic getters may rely on runtime state; defer resolution until later
                self.upstream_url = None
        elif upstream_url:
            self.upstream_url = upstream_url
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
        # Starlette's request.state stores attributes in _state dict
        state_dict = getattr(request.state, "_state", {}) if hasattr(request, 'state') else {}
        logger.debug(f"Middleware state: logging_mode={logging_mode}, has_modified_body={'modified_body' in state_dict}, state_dict_keys={list(state_dict.keys())}")
        if logging_mode:
            body = await request.body()
            logger.debug("Using original body (logging mode)")
        elif "modified_body" in state_dict:
            body = state_dict["modified_body"]
            if isinstance(body, str):
                body = body.encode("utf-8")
            logger.info("Using modified body from pre-input hooks")
        else:
            body = await request.body()
            logger.debug("Using original body (no modifications)")
        headers = raw_headers

        cached_upstream_url: Optional[str] = None
        request_metadata: Dict[str, Any] = {}

        # Only process if we have a JSON body and logging mode is NOT enabled
        if body and not logging_mode:
            try:
                # Parse and potentially modify the request
                data = json.loads(body)
                modified_data = self.inject_execution_behavior(data)
                request_metadata = {
                    "instructions": modified_data.get("instructions"),
                    "parallel_tool_calls": modified_data.get("parallel_tool_calls"),
                    "metadata": modified_data.get("metadata"),
                }

                # Get upstream URL dynamically
                upstream_url = self.url_getter()
                self.upstream_url = upstream_url
                cached_upstream_url = upstream_url
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
            except Exception:
                logger.exception("Error processing request")

        # Forward to upstream - get URL dynamically
        if cached_upstream_url is None:
            cached_upstream_url = self.url_getter()
            self.upstream_url = cached_upstream_url
        upstream_url = cached_upstream_url
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
                    logger.info(
                        "🔄 Cerebras transformer stream started",
                        extra={"upstream": upstream_url},
                    )
                    logger.info(
                        "🔍 Cerebras response status",
                        extra={"status": response.status_code, "headers": dict(response.headers)},
                    )

                    try:
                        log_dir = Path("/tmp/codex_plus/cerebras_responses")
                        log_dir.mkdir(parents=True, exist_ok=True)
                        (log_dir / "latest_response.txt").write_bytes(b"")
                        logger.info("📝 Initialized Cerebras response log at /tmp/codex_plus/cerebras_responses/latest_response.txt")
                        transformed_dir = Path("/tmp/codex_plus/cerebras_transformed")
                        transformed_dir.mkdir(parents=True, exist_ok=True)
                        (transformed_dir / "latest_response.txt").write_bytes(b"")
                    except Exception as e:
                        logger.warning(f"Failed to initialize Cerebras response log: {e}")

                    chunk_buffer = b""
                    sequence_number = 0
                    sent_created = False
                    sent_in_progress = False
                    reasoning_item_sent = False
                    reasoning_item_done = False
                    completion_sent = False
                    current_output_index = 0
                    response_id: Optional[str] = None
                    reasoning_item_id: Optional[str] = None
                    function_call_item_id: Optional[str] = None
                    function_call_name: Optional[str] = None
                    message_item_id: Optional[str] = None
                    active_item_type: Optional[str] = None
                    instructions_text = (
                        request_metadata.get("instructions")
                        if isinstance(request_metadata.get("instructions"), str)
                        else None
                    )
                    response_metadata_cache: Dict[str, Any] = {}
                    function_arguments_chunks: List[str] = []

                    def sse_event(event_type: str, payload: Dict[str, Any]) -> bytes:
                        payload = dict(payload)
                        payload.setdefault("type", event_type)
                        json_payload = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
                        logger.debug(
                            "📤 Emitting transformed event",
                            extra={
                                "event_type": event_type,
                                "sequence_number": payload.get("sequence_number"),
                            },
                        )
                        try:
                            transformed_dir = Path("/tmp/codex_plus/cerebras_transformed")
                            transformed_dir.mkdir(parents=True, exist_ok=True)
                            with open(transformed_dir / "latest_response.txt", "ab") as handle:
                                handle.write(f"event: {event_type}\n".encode("utf-8"))
                                handle.write(f"data: {json_payload}\n\n".encode("utf-8"))
                        except Exception as exc:
                            logger.debug(f"Failed to log transformed event: {exc}")
                        return (
                            f"event: {event_type}\n".encode("utf-8")
                            + f"data: {json_payload}\n\n".encode("utf-8")
                        )

                    def log_chunk(chunk_bytes: bytes) -> None:
                        try:
                            log_dir = Path("/tmp/codex_plus/cerebras_responses")
                            with open(log_dir / "latest_response.txt", "ab") as handle:
                                handle.write(chunk_bytes)
                        except Exception as exc:
                            logger.warning(f"Failed to log Cerebras response chunk: {exc}")

                    try:
                        async for chunk in response.aiter_bytes():
                            if not chunk:
                                continue

                            log_chunk(chunk)
                            chunk_buffer += chunk

                            while b"\n\n" in chunk_buffer:
                                raw_event, chunk_buffer = chunk_buffer.split(b"\n\n", 1)
                                if not raw_event.strip():
                                    continue

                                data_lines: List[bytes] = []
                                for line in raw_event.splitlines():
                                    if line.startswith(b"data: "):
                                        data_lines.append(line[6:])

                                if not data_lines:
                                    continue

                                data_str = b"\n".join(data_lines).decode("utf-8", errors="ignore").strip()
                                if not data_str:
                                    continue

                                if data_str == "[DONE]":
                                    if not completion_sent and response_id:
                                        completed_meta = dict(response_metadata_cache)
                                        if completed_meta:
                                            completed_meta["status"] = "completed"
                                        else:
                                            completed_meta = {
                                                "id": response_id,
                                                "object": "response",
                                                "created_at": int(time.time()),
                                                "status": "completed",
                                                "background": False,
                                                "error": None,
                                                "incomplete_details": None,
                                            }
                                            if instructions_text is not None:
                                                completed_meta["instructions"] = instructions_text
                                        completion_event = sse_event(
                                            "response.completed",
                                            {
                                                "sequence_number": sequence_number,
                                                "response": completed_meta,
                                            },
                                        )
                                        yield completion_event
                                        sequence_number += 1
                                        completion_sent = True
                                    try:
                                        transformed_dir = Path("/tmp/codex_plus/cerebras_transformed")
                                        transformed_dir.mkdir(parents=True, exist_ok=True)
                                        with open(transformed_dir / "latest_response.txt", "ab") as handle:
                                            handle.write(b"data: [DONE]\n\n")
                                    except Exception:
                                        logger.debug("Failed to log [DONE] sentinel")
                                    yield b"data: [DONE]\n\n"
                                    continue

                                try:
                                    chunk_data = json.loads(data_str)
                                except json.JSONDecodeError:
                                    logger.debug("Failed to parse Cerebras SSE chunk", extra={"preview": data_str[:100]})
                                    continue

                                choices = chunk_data.get("choices", [])
                                if not choices:
                                    continue

                                delta = choices[0].get("delta", {})
                                finish_reason = choices[0].get("finish_reason")

                                if not sent_created and (
                                    delta.get("role")
                                    or delta.get("reasoning")
                                    or delta.get("content")
                                    or delta.get("tool_calls")
                                ):
                                    raw_response_id = chunk_data.get("id", "")
                                    if raw_response_id:
                                        response_id = (
                                            raw_response_id
                                            if raw_response_id.startswith("resp_")
                                            else f"resp_{raw_response_id}"
                                        )
                                    else:
                                        response_id = f"resp_{uuid4().hex}"
                                    created_at = chunk_data.get("created") or int(time.time())
                                    base_response_info = {
                                        "id": response_id,
                                        "object": "response",
                                        "created_at": created_at,
                                        "status": "in_progress",
                                        "background": False,
                                        "error": None,
                                        "incomplete_details": None,
                                    }
                                    if instructions_text is not None:
                                        base_response_info["instructions"] = instructions_text
                                    created_event = sse_event(
                                        "response.created",
                                        {
                                            "sequence_number": sequence_number,
                                            "response": base_response_info,
                                        },
                                    )
                                    yield created_event
                                    sequence_number += 1
                                    sent_created = True
                                    response_metadata_cache = base_response_info

                                if sent_created and not sent_in_progress:
                                    response_meta = dict(response_metadata_cache)
                                    in_progress_event = sse_event(
                                        "response.in_progress",
                                        {
                                            "sequence_number": sequence_number,
                                            "response": response_meta,
                                        },
                                    )
                                    yield in_progress_event
                                    sequence_number += 1
                                    sent_in_progress = True

                                if delta.get("reasoning"):
                                    if not reasoning_item_sent:
                                        reasoning_item_id = f"rs_{response_id}" if response_id else "rs_0"
                                        reasoning_event = sse_event(
                                            "response.output_item.added",
                                            {
                                                "sequence_number": sequence_number,
                                                "output_index": 0,
                                                "item": {
                                                    "id": reasoning_item_id,
                                                    "type": "reasoning",
                                                    "encrypted_content": "",
                                                    "summary": [],
                                                },
                                            },
                                        )
                                        yield reasoning_event
                                        sequence_number += 1
                                        reasoning_item_sent = True
                                        current_output_index = 0

                                if delta.get("tool_calls"):
                                    if reasoning_item_sent and not reasoning_item_done and reasoning_item_id:
                                        reasoning_done_event = sse_event(
                                            "response.output_item.done",
                                            {
                                                "sequence_number": sequence_number,
                                                "output_index": 0,
                                                "item": {
                                                    "id": reasoning_item_id,
                                                    "type": "reasoning",
                                                    "encrypted_content": "",
                                                    "summary": [],
                                                },
                                            },
                                        )
                                        yield reasoning_done_event
                                        sequence_number += 1
                                        reasoning_item_done = True
                                        current_output_index = 1

                                    if active_item_type != "function_call":
                                        tool_call = delta["tool_calls"][0]
                                        call_id_raw = tool_call.get("id") or "0"
                                        function_call_item_id = call_id_raw if call_id_raw.startswith("call_") else f"call_{call_id_raw}"
                                        function_call_name = tool_call.get("function", {}).get("name", "unknown")
                                        function_event = sse_event(
                                            "response.output_item.added",
                                            {
                                                "sequence_number": sequence_number,
                                                "output_index": current_output_index,
                                                "item": {
                                                    "id": function_call_item_id,
                                                    "type": "function_call",
                                                    "name": function_call_name,
                                                    "call_id": function_call_item_id,
                                                    "arguments": "",
                                                    "status": "in_progress",
                                                },
                                            },
                                        )
                                        yield function_event
                                        sequence_number += 1
                                        active_item_type = "function_call"

                                if delta.get("content") and active_item_type is None and not reasoning_item_sent:
                                    message_item_id = f"msg_{response_id}" if response_id else "msg_0"
                                    message_added_event = sse_event(
                                        "response.output_item.added",
                                        {
                                            "sequence_number": sequence_number,
                                            "output_index": current_output_index,
                                            "item": {
                                                "id": message_item_id,
                                                "type": "message",
                                                "role": "assistant",
                                                "content": [],
                                            },
                                        },
                                    )
                                    yield message_added_event
                                    sequence_number += 1
                                    active_item_type = "message"

                                if delta.get("content") and sent_created:
                                    message_item_id = message_item_id or (f"msg_{response_id}" if response_id else "msg_0")
                                    text_event = sse_event(
                                        "response.output_text.delta",
                                        {
                                            "sequence_number": sequence_number,
                                            "item_id": message_item_id,
                                            "delta": delta["content"],
                                        },
                                    )
                                    yield text_event
                                    sequence_number += 1

                                if delta.get("tool_calls") and function_call_item_id:
                                    for tool_call in delta["tool_calls"]:
                                        function_data = tool_call.get("function", {})
                                        arguments = function_data.get("arguments")
                                        if arguments:
                                            args_event = sse_event(
                                                "response.function_call.arguments.delta",
                                                {
                                                    "sequence_number": sequence_number,
                                                    "output_index": current_output_index,
                                                    "tool_call_index": tool_call.get("index", 0),
                                                    "item_id": function_call_item_id,
                                                    "call_id": function_call_item_id,
                                                    "delta": arguments,
                                                },
                                            )
                                            yield args_event
                                            sequence_number += 1
                                            function_arguments_chunks.append(arguments)

                                if finish_reason:
                                    tool_call_result_text: Optional[str] = None
                                    if finish_reason == "tool_calls" and function_arguments_chunks:
                                        arguments_json = "".join(function_arguments_chunks)
                                        try:
                                            call_payload = json.loads(arguments_json)
                                        except json.JSONDecodeError as exc:
                                            logger.error(f"Failed to parse tool arguments: {exc}")
                                            call_payload = None

                                        if isinstance(call_payload, dict):
                                            command = call_payload.get("command") or []
                                            timeout_ms = call_payload.get("timeout_ms")
                                            cwd = call_payload.get("workdir") or call_payload.get("cwd")
                                            env = call_payload.get("env") or {}
                                            if isinstance(command, list) and command:
                                                try:
                                                    logger.info(
                                                        "⚙️ Executing tool call locally",
                                                        extra={
                                                            "command": command,
                                                            "cwd": cwd,
                                                            "timeout_ms": timeout_ms,
                                                        },
                                                    )
                                                    proc = await asyncio.create_subprocess_exec(
                                                        *command,
                                                        cwd=cwd,
                                                        env={**os.environ, **{str(k): str(v) for k, v in env.items()}},
                                                        stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.PIPE,
                                                    )
                                                    try:
                                                        stdout_bytes, stderr_bytes = await asyncio.wait_for(
                                                            proc.communicate(),
                                                            timeout=(timeout_ms / 1000) if timeout_ms else None,
                                                        )
                                                        timed_out = False
                                                    except asyncio.TimeoutError:
                                                        proc.kill()
                                                        stdout_bytes, stderr_bytes = await proc.communicate()
                                                        timed_out = True

                                                    stdout_text = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
                                                    stderr_text = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
                                                    exit_code = proc.returncode
                                                    parts = ["# Shell Output"]
                                                    parts.append(f"Command: {' '.join(command)}")
                                                    parts.append(f"Exit code: {exit_code}")
                                                    if timed_out:
                                                        parts.append("Result: ⏰ Timed out")
                                                    if stdout_text.strip():
                                                        parts.append("STDOUT:\n" + stdout_text.strip())
                                                    if stderr_text.strip():
                                                        parts.append("STDERR:\n" + stderr_text.strip())
                                                    tool_call_result_text = "\n\n".join(parts)
                                                except Exception as exec_exc:
                                                    logger.error(f"Failed to execute tool call: {exec_exc}")
                                                    tool_call_result_text = f"Shell command execution failed: {exec_exc}"
                                            else:
                                                tool_call_result_text = "Shell command execution skipped (no command provided)."
                                        else:
                                            tool_call_result_text = "Shell command execution skipped (invalid arguments)."
                                        function_arguments_chunks.clear()

                                    if active_item_type == "function_call":
                                        done_event = sse_event(
                                            "response.output_item.done",
                                            {
                                                "sequence_number": sequence_number,
                                                "output_index": current_output_index,
                                                "item": {
                                                    "id": function_call_item_id or "call_0",
                                                    "type": "function_call",
                                                    "name": function_call_name or "unknown",
                                                    "call_id": function_call_item_id or "call_0",
                                                    "status": "completed",
                                                },
                                            },
                                        )
                                        yield done_event
                                        sequence_number += 1

                                    if finish_reason == "tool_calls" and tool_call_result_text is not None:
                                        current_output_index = max(current_output_index + 1, 2)
                                        if not message_item_id:
                                            message_item_id = f"msg_{response_id}" if response_id else f"msg_{uuid4().hex}"
                                            message_added_event = sse_event(
                                                "response.output_item.added",
                                                {
                                                    "sequence_number": sequence_number,
                                                    "output_index": current_output_index,
                                                    "item": {
                                                        "id": message_item_id,
                                                        "type": "message",
                                                        "role": "assistant",
                                                        "status": "in_progress",
                                                        "content": [],
                                                    },
                                                },
                                            )
                                            yield message_added_event
                                            sequence_number += 1
                                        text_event = sse_event(
                                            "response.output_text.delta",
                                            {
                                                "sequence_number": sequence_number,
                                                "item_id": message_item_id,
                                                "output_index": current_output_index,
                                                "content_index": 0,
                                                "delta": tool_call_result_text,
                                            },
                                        )
                                        yield text_event
                                        sequence_number += 1
                                        message_done_event = sse_event(
                                            "response.output_item.done",
                                            {
                                                "sequence_number": sequence_number,
                                                "output_index": current_output_index,
                                                "item": {
                                                    "id": message_item_id,
                                                    "type": "message",
                                                    "status": "completed",
                                                },
                                            },
                                        )
                                        yield message_done_event
                                        sequence_number += 1
                                        active_item_type = None

                                    if active_item_type == "message":
                                        message_item_id = message_item_id or (f"msg_{response_id}" if response_id else "msg_0")
                                        message_done_event = sse_event(
                                            "response.output_item.done",
                                            {
                                                "sequence_number": sequence_number,
                                                "output_index": current_output_index,
                                                "item": {
                                                    "id": message_item_id,
                                                    "type": "message",
                                                    "status": "completed",
                                                },
                                            },
                                        )
                                        yield message_done_event
                                        sequence_number += 1

                                    if response_id and not completion_sent:
                                        completed_meta = dict(response_metadata_cache)
                                        completed_meta["status"] = "completed"
                                        completion_event = sse_event(
                                            "response.completed",
                                            {
                                                "sequence_number": sequence_number,
                                                "response": completed_meta,
                                            },
                                        )
                                        yield completion_event
                                        sequence_number += 1
                                        completion_sent = True
                                    active_item_type = None
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
