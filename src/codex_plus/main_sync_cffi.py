#!/usr/bin/env python3
"""
Codex Plus Proxy using curl_cffi synchronous client for better SSE handling
Now with integrated slash command middleware for .claude/ infrastructure

🚨 CRITICAL: This proxy REQUIRES curl_cffi to bypass Cloudflare 🚨
DO NOT replace with httpx, requests, or any other HTTP client
Codex uses ChatGPT backend with session auth, NOT OpenAI API keys
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from curl_cffi import requests
import logging
import re
from urllib.parse import urlparse

app = FastAPI()

# Logger setup (must be defined before first use)
logger = logging.getLogger("codex_plus_proxy")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# Configuration
UPSTREAM_URL = "https://chatgpt.com/backend-api/codex"  # ChatGPT backend for Codex

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

# Initialize slash command middleware
logger.info("Initializing LLM execution middleware (instruction mode)")
from .llm_execution_middleware import create_llm_execution_middleware
slash_middleware = create_llm_execution_middleware(upstream_url=UPSTREAM_URL)

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

    # Security validation
    headers = dict(request.headers)
    try:
        _validate_proxy_request(path, headers)
    except HTTPException as e:
        logger.error(f"Security validation failed for {request.method} /{path}: {e.detail}")
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    # Read body for debug logging (preserve original behavior)
    body = await request.body()
    logger.debug(f"Path: {path}, Body length: {len(body) if body else 0}")

    # Debug: Log request payload for debugging (async, non-blocking)
    from .request_logger import RequestLogger
    RequestLogger.log_request_payload(body, path)

    # Process request through slash command middleware
    # This will either handle slash commands or proxy normally
    return await slash_middleware.process_request(request, path)
