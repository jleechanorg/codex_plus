#!/usr/bin/env python3
"""
Codex Plus Proxy using curl_cffi synchronous client for better SSE handling
"""
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from curl_cffi import requests
import logging

app = FastAPI()

# Configuration
UPSTREAM_URL = "https://chatgpt.com/backend-api/codex"  # ChatGPT backend for Codex

# Logger setup
logger = logging.getLogger("codex_plus_proxy")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

@app.get("/health")
async def health():
    """Simple health check - not forwarded"""
    logger.info("HEALTH OK")
    return JSONResponse({"status": "healthy"})

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, path: str):
    """Proxy using curl_cffi sync client for better SSE handling"""
    norm_path = path.lstrip("/")
    target_url = f"{UPSTREAM_URL}/{norm_path}"
    
    # Forward query parameters
    query_params = str(request.url.query)
    if query_params:
        target_url += f"?{query_params}"
    
    # Get headers from request
    headers = {}
    for key, value in request.headers.items():
        # Skip host header as curl_cffi will set it
        if key.lower() != "host":
            headers[key] = value
    
    # Log incoming request
    logger.info(f"Proxying {request.method} /{path} -> {target_url}")
    
    # Read body - TRUE PASSTHROUGH, NO MODIFICATIONS
    body = await request.body()
    
    # Debug: Log request body to see system prompts
    if body and path == "responses":
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
            if "messages" in payload:
                # Create directory with branch name
                log_dir = Path(f"/tmp/codex_plus/{branch}")
                log_dir.mkdir(parents=True, exist_ok=True)
                
                # Write to branch-specific file
                log_file = log_dir / "request_messages.json"
                log_file.write_text(json.dumps(payload["messages"], indent=2))
                
                logger.info(f"Logged {len(payload['messages'])} messages to {log_file}")
        except Exception as e:
            logger.error(f"Failed to log messages: {e}")
    
    try:
        # Use synchronous curl_cffi with Chrome impersonation
        session = requests.Session(impersonate="chrome124")
        
        # Make the request with streaming
        response = session.request(
            request.method,
            target_url,
            headers=headers,
            data=body if body else None,
            stream=True,
            timeout=30
        )
        
        logger.info(f"{request.method} /{path} -> {response.status_code}")
        
        # Stream the response back
        def stream_response():
            try:
                # Stream raw content without buffering
                for chunk in response.iter_content(chunk_size=None):
                    if chunk:
                        yield chunk
            finally:
                response.close()
                session.close()
        
        # Get response headers
        resp_headers = dict(response.headers)
        resp_headers.pop("content-length", None)  # Remove as we're streaming
        resp_headers.pop("content-encoding", None)  # Remove encoding headers
        
        return StreamingResponse(
            stream_response(),
            status_code=response.status_code,
            headers=resp_headers,
            media_type=resp_headers.get("content-type", "text/event-stream")
        )
        
    except Exception as e:
        logger.exception(f"Error proxying request: {e}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )