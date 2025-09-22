#!/usr/bin/env python3
"""
Codex Plus Proxy using curl_cffi synchronous client for better SSE handling
Now with integrated slash command middleware for .claude/ infrastructure

🚨🚨🚨 CRITICAL WARNING - DO NOT MODIFY PROXY FORWARDING LOGIC 🚨🚨🚨

⚠️  PROXY FORWARDING CORE IS OFF-LIMITS - MODIFICATIONS FORBIDDEN ⚠️
- This proxy REQUIRES curl_cffi to bypass Cloudflare - DO NOT CHANGE
- DO NOT replace with httpx, requests, or any other HTTP client
- DO NOT modify upstream URL forwarding to ChatGPT backend
- DO NOT change authentication header handling
- DO NOT alter streaming response logic
- Codex uses ChatGPT backend with session auth, NOT OpenAI API keys

✅ SAFE TO MODIFY: Only the hooks module and hook-related functionality
- Modify files in .codexplus/hooks/ and .claude/hooks/
- Edit hook processing logic in hooks.py module
- Add new hook types or middleware integrations
- Extend status line middleware functionality

🔒 PROTECTED COMPONENTS (DO NOT TOUCH):
- curl_cffi session configuration and requests
- Upstream URL and forwarding logic
- Authentication header preservation
- Streaming response handling
- Security validation functions
- Core proxy request/response cycle

Breaking these rules WILL break the proxy and block all Codex requests.
"""
from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from curl_cffi import requests
import logging
import json as _json
import json
import sys
import os
import time
import re
from urllib.parse import urlparse
from .status_line_middleware import HookMiddleware

# Pydantic models for API request/response validation
class AgentConfigCreate(BaseModel):
    """Model for creating new agent configurations."""
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    tools: List[str] = Field(default_factory=list, description="List of available tools")
    model: str = Field(default="claude-3-5-sonnet-20241022", description="LLM model to use")
    temperature: float = Field(default=0.7, ge=0, le=2, description="Model temperature")
    max_tokens: int = Field(default=4096, gt=0, description="Maximum tokens")
    system_prompt: Optional[str] = Field(None, description="Custom system prompt")
    instructions: Optional[str] = Field(None, description="Agent instructions")
    allowed_paths: List[str] = Field(default_factory=list, description="Allowed file paths")
    forbidden_paths: List[str] = Field(default_factory=list, description="Forbidden file paths")
    capabilities: List[str] = Field(default_factory=list, description="Agent capabilities")
    version: str = Field(default="1.0.0", description="Configuration version")
    author: Optional[str] = Field(None, description="Agent author")
    tags: List[str] = Field(default_factory=list, description="Agent tags")

class AgentConfigUpdate(BaseModel):
    """Model for updating existing agent configurations."""
    name: Optional[str] = Field(None, description="Agent name")
    description: Optional[str] = Field(None, description="Agent description")
    tools: Optional[List[str]] = Field(None, description="List of available tools")
    model: Optional[str] = Field(None, description="LLM model to use")
    temperature: Optional[float] = Field(None, ge=0, le=2, description="Model temperature")
    max_tokens: Optional[int] = Field(None, gt=0, description="Maximum tokens")
    system_prompt: Optional[str] = Field(None, description="Custom system prompt")
    instructions: Optional[str] = Field(None, description="Agent instructions")
    allowed_paths: Optional[List[str]] = Field(None, description="Allowed file paths")
    forbidden_paths: Optional[List[str]] = Field(None, description="Forbidden file paths")
    capabilities: Optional[List[str]] = Field(None, description="Agent capabilities")
    version: Optional[str] = Field(None, description="Configuration version")
    author: Optional[str] = Field(None, description="Agent author")
    tags: Optional[List[str]] = Field(None, description="Agent tags")

class AgentConfigResponse(BaseModel):
    """Model for agent configuration responses."""
    id: str = Field(..., description="Agent ID")
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    tools: List[str] = Field(..., description="List of available tools")
    model: str = Field(..., description="LLM model to use")
    temperature: float = Field(..., description="Model temperature")
    max_tokens: int = Field(..., description="Maximum tokens")
    system_prompt: Optional[str] = Field(None, description="Custom system prompt")
    instructions: Optional[str] = Field(None, description="Agent instructions")
    allowed_paths: List[str] = Field(..., description="Allowed file paths")
    forbidden_paths: List[str] = Field(..., description="Forbidden file paths")
    capabilities: List[str] = Field(..., description="Agent capabilities")
    version: str = Field(..., description="Configuration version")
    author: Optional[str] = Field(None, description="Agent author")
    tags: List[str] = Field(..., description="Agent tags")

class AgentInvokeRequest(BaseModel):
    """Model for agent invocation requests."""
    task: str = Field(..., description="Task description for the agent")
    working_directory: Optional[str] = Field(None, description="Working directory for execution")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context data")

class AgentInvokeResponse(BaseModel):
    """Model for agent invocation responses."""
    agent_id: str = Field(..., description="Agent ID")
    task: str = Field(..., description="Task description")
    success: bool = Field(..., description="Execution success status")
    output: str = Field(..., description="Agent output")
    error: Optional[str] = Field(None, description="Error message if failed")
    duration: float = Field(..., description="Execution duration in seconds")
    timestamp: float = Field(..., description="Execution timestamp")

class MultiAgentInvokeRequest(BaseModel):
    """Model for multiple agent invocation requests."""
    agents: List[str] = Field(..., description="List of agent IDs to invoke")
    task: str = Field(..., description="Task description for all agents")
    working_directory: Optional[str] = Field(None, description="Working directory for execution")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context data")

class MultiAgentInvokeResponse(BaseModel):
    """Model for multiple agent invocation responses."""
    results: List[AgentInvokeResponse] = Field(..., description="Individual agent results")
    summary: str = Field(..., description="Summary of all agent executions")
    total_duration: float = Field(..., description="Total execution duration")
    successful_agents: int = Field(..., description="Number of successful agents")
    total_agents: int = Field(..., description="Total number of agents")

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Session start hooks
        try:
            from .hooks import settings_session_start
            await settings_session_start(None, source="startup")
        except Exception as e:
            logger.error(f"Failed to execute session start hooks: {e}")

        # Start background status line updates
        try:
            await hook_middleware.start_background_status_update()
            logger.info("🚀 Started background status line updates")
        except Exception as e:
            logger.error(f"Failed to start background status updates: {e}")

        yield
    finally:
        # Session end hooks
        try:
            from .hooks import settings_session_end
            await settings_session_end(None, reason="exit")
        except Exception as e:
            logger.error(f"Failed to execute session end hooks: {e}")


app = FastAPI(lifespan=lifespan)

# Logger setup (must be defined before first use)
logger = logging.getLogger("codex_plus_proxy")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# 🔒 PROTECTED CONFIGURATION - DO NOT MODIFY 🔒
# CRITICAL: This URL MUST remain exactly as specified for Codex to work
UPSTREAM_URL = "https://chatgpt.com/backend-api/codex"  # ChatGPT backend for Codex
# ⚠️ Changing this URL will break all Codex functionality ⚠️

# Security validation
def _validate_proxy_request(path: str, headers: dict) -> None:
    """Validate proxy request to prevent SSRF and other attacks"""
    # Prevent path traversal attempts
    if any(pattern in path.lower() for pattern in ['../', '.\\', 'file://', 'ftp://']):
        logger.warning(f"Blocked path traversal attempt: {path}")
        raise HTTPException(status_code=400, detail="Invalid request path")

    # Prevent localhost/internal network access attempts
    if any(pattern in path.lower() for pattern in ['localhost', '127.0.0.1', '::1', '0.0.0.0']):
        logger.warning(f"Blocked internal network access attempt: {path}")
        raise HTTPException(status_code=400, detail="Access to internal resources denied")

    # Validate content-length to prevent oversized requests
    content_length = headers.get('content-length', '0')
    try:
        if int(content_length) > 10 * 1024 * 1024:  # 10MB limit
            logger.warning(f"Blocked oversized request: {content_length} bytes")
            raise HTTPException(status_code=413, detail="Request entity too large")
    except ValueError:
        logger.warning(f"Invalid content-length header: {content_length}")
        raise HTTPException(status_code=400, detail="Invalid content-length header")

def _sanitize_headers(headers: dict) -> dict:
    """Remove potentially dangerous headers before forwarding"""
    # Headers that should not be forwarded to upstream
    dangerous_headers = {
        'host', 'x-forwarded-for', 'x-forwarded-proto', 'x-forwarded-host',
        'connection', 'upgrade', 'proxy-connection', 'proxy-authorization'
    }

    return {k: v for k, v in headers.items()
            if k.lower() not in dangerous_headers and not k.lower().startswith('x-forwarded-')}

def _validate_upstream_url(url: str) -> bool:
    """Validate that upstream URL is allowed"""
    try:
        parsed = urlparse(url)
        # Only allow HTTPS to ChatGPT backend
        return (parsed.scheme == 'https' and
                parsed.hostname == 'chatgpt.com' and
                parsed.path.startswith('/backend-api/'))
    except Exception:
        return False

# 🔒 PROTECTED MIDDLEWARE INITIALIZATION - MODIFY ONLY HOOK COMPONENTS 🔒
# ✅ SAFE: Hook-related imports and hook_middleware modifications
# ❌ FORBIDDEN: slash_middleware initialization or create_llm_execution_middleware calls

# Initialize slash command middleware
logger.info("Initializing LLM execution middleware (instruction mode)")
from .llm_execution_middleware import create_llm_execution_middleware
# ⚠️ DO NOT MODIFY: This creates the core proxy forwarding with curl_cffi
slash_middleware = create_llm_execution_middleware(upstream_url=UPSTREAM_URL)

# Initialize agent orchestrator middleware
logger.info("Initializing agent orchestrator middleware")
from .agent_orchestrator_middleware import create_agent_orchestrator_middleware
agent_middleware = create_agent_orchestrator_middleware(max_concurrent_agents=3, agent_timeout=30)
logger.info(f"🤖 Agent orchestrator loaded: {len(agent_middleware.agents)} agents available")

# ✅ SAFE TO MODIFY: Hook system imports and processing
from .hooks import (
    process_pre_input_hooks,
    process_post_output_hooks,
    settings_stop,
    hook_system,
)

# ✅ SAFE TO MODIFY: Hook middleware configuration and extensions
hook_middleware = HookMiddleware(hook_manager=hook_system)

@app.get("/health")
async def health():
    """Simple health check - not forwarded"""
    logger.info("HEALTH OK")
    return JSONResponse({"status": "healthy"})

@app.get("/agents/status")
async def agents_status():
    """Agent orchestrator status - not forwarded"""
    logger.info("AGENT STATUS REQUEST")
    return JSONResponse(agent_middleware.get_agent_status())

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, path: str):
    """
    🚨🚨🚨 CRITICAL PROXY FUNCTION - EXTREMELY DANGEROUS TO MODIFY 🚨🚨🚨

    ⚠️  CORE PROXY FORWARDING LOGIC - DO NOT TOUCH UNLESS ABSOLUTELY NECESSARY ⚠️

    This function handles the core Codex proxy forwarding to ChatGPT backend.
    Modifications to this function can break ALL Codex functionality.

    ✅ SAFE TO MODIFY: Hook processing sections (clearly marked)
    ❌ FORBIDDEN: Request forwarding, middleware calls, response handling

    Proxy with integrated slash command middleware support
    """
    # Skip forwarding for local endpoints
    if path in ["health", "agents/status"]:
        logger.warning(f"Path {path} should be handled by dedicated endpoint, not proxy")
        return JSONResponse({"error": "Endpoint not found"}, status_code=404)

    # Log incoming request
    logger.info(f"Processing {request.method} /{path}")

    # Security validation
    headers = dict(request.headers)
    try:
        _validate_proxy_request(path, headers)
    except HTTPException as e:
        logger.error(f"Security validation failed for {request.method} /{path}: {e.detail}")
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    # Read body for debug logging (preserve original behavior)
    body = await request.body()
    # Apply pre-input hooks for JSON bodies on /responses
    if body and path == "responses":
        try:
            body_dict = _json.loads(body)
            modified = await process_pre_input_hooks(request, body_dict)
            if modified != body_dict:
                # stash modified body for downstream middleware
                try:
                    request.state.modified_body = _json.dumps(modified).encode('utf-8')
                    logger.info("Pre-input hooks applied: request body modified")
                except Exception as e:
                    logger.debug(f"Unable to set modified_body on request.state: {e}")
            # If any settings hooks blocked the prompt, short-circuit
            if getattr(request.state, 'user_prompt_block', None):
                reason = request.state.user_prompt_block.get('reason', 'Blocked by hook')
                return JSONResponse({"error": reason}, status_code=400)
        except _json.JSONDecodeError:
            logger.debug("Request body not JSON; skipping pre-input hooks")

    # Debug: Log request body to see system prompts
    logger.debug(f"Path: {path}, Body length: {len(body) if body else 0}")

    # Debug: Log request payload for debugging (async, non-blocking)
    from .request_logger import RequestLogger
    RequestLogger.log_request_payload(body, path)

    # ✅ SAFE TO MODIFY: Hook processing and status line handling
    # Extract working directory from headers or request body
    working_directory = headers.get('x-working-directory')

    # Also check for working directory in request body (Codex CLI format)
    if not working_directory and body:
        try:
            import re
            # Look for <cwd>/path/to/directory</cwd> in the request body
            cwd_match = re.search(r'<cwd>([^<]+)</cwd>', body.decode('utf-8', errors='ignore'))
            if cwd_match:
                working_directory = cwd_match.group(1)
                logger.info(f"📂 Found working directory in request body: {working_directory}")
        except Exception as e:
            logger.debug(f"Failed to extract working directory from body: {e}")

    # Get status line based on working directory (if provided) or cached status line
    try:
        if working_directory:
            logger.info(f"📂 Using working directory: {working_directory}")
            status_line = await hook_middleware.get_status_line(working_directory)
        else:
            status_line = hook_middleware.get_cached_status_line()

        if status_line:
            logger.info(f"📍 Storing status line for injection: {status_line}")
            # Store status line in request state for middleware to access
            if hasattr(request, 'state'):
                request.state.status_line = status_line
            logger.info("✅ Status line stored for middleware injection")
    except Exception as e:
        logger.error(f"Status line storage failed: {e}")

    # ✅ SAFE TO MODIFY: Agent orchestrator middleware processing
    # Process agent invocation patterns (/agent, /agents run, /delegate)
    try:
        logger.info(f"🤖 Processing agent commands for {path}")
        modified_request_data = await agent_middleware.process_request(request, path)
        if modified_request_data:
            # Agent commands were processed, update request body
            modified_body = json.dumps(modified_request_data).encode('utf-8')
            request.state.modified_body = modified_body
            logger.info("🤖 Agent commands processed, request body modified")
    except Exception as e:
        logger.error(f"❌ Agent middleware failed for {path}: {e}")
        # Continue processing - agent middleware failure shouldn't block the request

    # 🔒 PROTECTED: Core middleware call - DO NOT MODIFY 🔒
    # ❌ CRITICAL: This handles curl_cffi forwarding to ChatGPT backend
    # Process request through slash command middleware
    # This will either handle slash commands or proxy normally
    try:
        logger.info(f"🎯 Calling middleware for {path}")
        response = await slash_middleware.process_request(request, path)
        logger.info(f"✅ Middleware completed for {path}")
    except Exception as e:
        logger.error(f"❌ Middleware failed for {path}: {e}")
        # Fallback to basic proxy behavior
        return JSONResponse({"error": f"Middleware error: {str(e)}"}, status_code=500)

    # ✅ SAFE TO MODIFY: Post-output hook processing
    # Apply post-output hooks only for non-streaming responses to avoid consuming streams
    try:
        if not isinstance(response, StreamingResponse):
            response = await process_post_output_hooks(response)
    except Exception as e:
        logger.debug(f"post-output hooks failed: {e}")

    # Run hook middleware side-effects (non-blocking)
    import asyncio
    # Also trigger Stop settings hooks (best-effort)
    try:
        asyncio.create_task(settings_stop(request, {"transcript_path": ""}))
    except Exception:
        pass

    return response
