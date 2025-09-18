#!/usr/bin/env python3
"""
Codex Plus Proxy using curl_cffi synchronous client for better SSE handling
Now with integrated slash command middleware for .claude/ infrastructure

🚨 CRITICAL: This proxy REQUIRES curl_cffi to bypass Cloudflare 🚨
DO NOT replace with httpx, requests, or any other HTTP client
Codex uses ChatGPT backend with session auth, NOT OpenAI API keys
"""
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from fastapi.responses import StreamingResponse, JSONResponse
from curl_cffi import requests
import logging
import json as _json
import json
import sys
import os
import time
from .status_line_middleware import HookMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Session start hooks
        try:
            from .hooks import settings_session_start
            await settings_session_start(None, source="startup")
        except Exception as e:
            logger.error(f"Failed to execute session start hooks: {e}")
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

# Configuration
UPSTREAM_URL = "https://chatgpt.com/backend-api/codex"  # ChatGPT backend for Codex

# Initialize slash command middleware
logger.info("Initializing LLM execution middleware (instruction mode)")
from .llm_execution_middleware import create_llm_execution_middleware
slash_middleware = create_llm_execution_middleware(upstream_url=UPSTREAM_URL)
from .hooks import (
    process_pre_input_hooks,
    process_post_output_hooks,
    settings_stop,
    hook_system,
)


hook_middleware = HookMiddleware(hook_manager=hook_system)

@app.get("/health")
async def health():
    """Simple health check - not forwarded"""
    logger.info("HEALTH OK")
    return JSONResponse({"status": "healthy"})

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, path: str):
    """Proxy with integrated slash command middleware support"""
    # Log incoming request
    logger.info(f"Processing {request.method} /{path}")
    
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
    
    # Debug: Log request payload for debugging
    from .request_logger import RequestLogger
    RequestLogger.log_request_payload(body, path)

    # Get status line and store it in request context for middleware to use
    try:
        status_line = await hook_middleware.get_status_line()
        if status_line:
            logger.info(f"📍 Storing status line for injection: {status_line}")
            # Store status line in request state for middleware to access
            if hasattr(request, 'state'):
                request.state.status_line = status_line
            logger.info("✅ Status line stored for middleware injection")
    except Exception as e:
        logger.error(f"Status line storage failed: {e}")

    # Process request through slash command middleware
    # This will either handle slash commands or proxy normally
    try:
        logger.info(f"🎯 Calling middleware for {path}")
        response = await slash_middleware.process_request(request, path)
        logger.info(f"✅ Middleware completed for {path}")
    except Exception as e:
        logger.error(f"❌ Middleware failed for {path}: {e}")
        # Fallback to basic proxy behavior
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": f"Middleware error: {str(e)}"}, status_code=500)

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
