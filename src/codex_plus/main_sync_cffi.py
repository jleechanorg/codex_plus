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
import json as _json
import json
import sys
import os
import time

app = FastAPI()

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
from .hooks import process_pre_input_hooks, process_post_output_hooks

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
        except _json.JSONDecodeError:
            logger.debug("Request body not JSON; skipping pre-input hooks")

    # Debug: Log request body to see system prompts
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
    response = await slash_middleware.process_request(request, path)

    # Apply post-output hooks only for non-streaming responses to avoid consuming streams
    try:
        if not isinstance(response, StreamingResponse):
            response = await process_post_output_hooks(response)
    except Exception as e:
        logger.debug(f"post-output hooks failed: {e}")
    
    # Execute git header hook and potentially modify response
    import asyncio
    
    # Option 1: Add git status to streaming response (requires response modification)
    # Option 2: Add git status as a separate message after main response
    # Option 3: Terminal status line simulation via ANSI escape codes
    
    async def run_git_header_async():
        start_time = time.time()
        try:
            import subprocess
            from pathlib import Path
            
            git_root = subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"], 
                text=True, 
                stderr=subprocess.DEVNULL
            ).strip()
            
            git_header_script = Path(git_root) / ".claude/hooks/git-header.sh"
            
            if git_header_script.exists() and git_header_script.is_file():
                logger.info("🔍 Executing git header script (async)...")
                result = subprocess.run(
                    [str(git_header_script), "--status-only"],  # Use minimal output
                    capture_output=True,
                    text=True,
                    timeout=5  # Reduced from 45 to 5 seconds
                )
                
                if result.stdout.strip():
                    # Extract just the colored status line (last line typically)
                    lines = result.stdout.strip().split('\n')
                    status_line = None
                    for line in reversed(lines):
                        if '[' in line and ']' in line:  # Find colored status line
                            status_line = line.strip()
                            break
                    
                    if status_line:
                        execution_time = time.time() - start_time
                        logger.info("🎯 Git Status Line:")
                        logger.info(f"   {status_line}")
                        logger.info(f"🕐 Git header took {execution_time:.2f}s")
                        
                        # Print to stderr so it appears in terminal
                        print(f"\r{status_line}", file=sys.stderr, flush=True)
                        
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            logger.info(f"⚠️ Git header timed out after {execution_time:.2f}s")
        except Exception as e:
            execution_time = time.time() - start_time
            logger.info(f"⚠️ Git header failed after {execution_time:.2f}s: {e}")
    
    # Start git header task asynchronously (fire and forget)
    asyncio.create_task(run_git_header_async())
    
    return response
