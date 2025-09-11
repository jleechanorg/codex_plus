#!/usr/bin/env python3
"""
Codex Plus Proxy using curl_cffi synchronous client for better SSE handling
Now with integrated slash command middleware for .claude/ infrastructure

🚨 CRITICAL: This proxy REQUIRES curl_cffi to bypass Cloudflare 🚨
DO NOT replace with httpx, requests, or any other HTTP client
Codex uses ChatGPT backend with session auth, NOT OpenAI API keys
"""
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from curl_cffi import requests
import logging
import os
from enhanced_slash_middleware import create_enhanced_slash_command_middleware
from slash_command_middleware import create_slash_command_middleware

app = FastAPI()

# Logger setup (must be defined before first use)
logger = logging.getLogger("codex_plus_proxy")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# Configuration
UPSTREAM_URL = "https://chatgpt.com/backend-api/codex"  # ChatGPT backend for Codex

# Initialize slash command middleware
# Support selecting implementation via env var for testing different approaches
_mw_choice = os.getenv("CODEX_PLUS_MIDDLEWARE", "enhanced").lower()

if _mw_choice == "classic":
    logger.info("Initializing classic SlashCommandMiddleware (compat mode)")
    slash_middleware = create_slash_command_middleware(upstream_url=UPSTREAM_URL)
elif _mw_choice == "llm":
    logger.info("Initializing LLM execution middleware (instruction mode)")
    from llm_execution_middleware import create_llm_execution_middleware
    slash_middleware = create_llm_execution_middleware(upstream_url=UPSTREAM_URL)
else:
    logger.info("Initializing enhanced SlashCommandMiddleware")
    slash_middleware = create_enhanced_slash_command_middleware(upstream_url=UPSTREAM_URL)

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
    logger.debug(f"Path: {path}, Body length: {len(body) if body else 0}")
    
    # Debug: Log request body to see system prompts (preserve original behavior)
    if body and path == "responses":
        logger.info(f"Capturing request to /responses endpoint")
        try:
            import json
            from pathlib import Path
            import subprocess
            
            # Get current git branch name
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                text=True
            ).strip()
            
            payload = json.loads(body)
            logger.info(f"Parsed payload with keys: {list(payload.keys())}")
            
            # Create directory with branch name
            log_dir = Path(f"/tmp/codex_plus/{branch}")
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Write the full payload to see structure
            log_file = log_dir / "request_payload.json"
            log_file.write_text(json.dumps(payload, indent=2))
            
            logger.info(f"Logged full payload to {log_file}")
            
            # Also log just the instructions if available
            if "instructions" in payload:
                instructions_file = log_dir / "instructions.txt"
                instructions_file.write_text(payload["instructions"])
                logger.info(f"Logged instructions to {instructions_file}")
        except Exception as e:
            logger.error(f"Failed to log messages: {e}")
    
    # Process request through slash command middleware
    # This will either handle slash commands or proxy normally
    return await slash_middleware.process_request(request, path)
