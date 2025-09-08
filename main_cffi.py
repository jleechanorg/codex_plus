#!/usr/bin/env python3
"""
Codex Plus Proxy using curl_cffi for TLS fingerprint bypass
"""
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from curl_cffi.requests import AsyncSession
import logging
import asyncio

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
    """Proxy using curl_cffi to bypass Cloudflare TLS fingerprinting"""
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
    
    # Create session with Chrome impersonation to bypass Cloudflare
    async with AsyncSession(impersonate="chrome124") as session:
        try:
            # Make the request
            if request.method == "POST":
                response = await session.post(
                    target_url,
                    headers=headers,
                    data=body,
                    stream=True,
                    timeout=30
                )
            elif request.method == "GET":
                response = await session.get(
                    target_url,
                    headers=headers,
                    stream=True,
                    timeout=30
                )
            else:
                response = await session.request(
                    request.method,
                    target_url,
                    headers=headers,
                    data=body if body else None,
                    stream=True,
                    timeout=30
                )
            
            logger.info(f"{request.method} /{path} -> {response.status_code}")
            
            # Stream the response back
            async def stream_response():
                async for chunk in response.aiter_content(chunk_size=None):
                    if chunk:
                        yield chunk
            
            # Get response headers
            resp_headers = dict(response.headers)
            resp_headers.pop("content-length", None)  # Remove as we're streaming
            resp_headers.pop("content-encoding", None)  # Remove encoding headers
            
            return StreamingResponse(
                stream_response(),
                status_code=response.status_code,
                headers=resp_headers
            )
            
        except Exception as e:
            logger.exception(f"Error proxying request: {e}")
            return JSONResponse(
                {"error": str(e)},
                status_code=500
            )