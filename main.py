from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from starlette.background import BackgroundTask
import httpx
import logging
import os

app = FastAPI()

# Configuration
UPSTREAM_URL = "https://api.openai.com"

# Logger setup (propagates to Uvicorn, which writes to /tmp logs via proxy.sh)
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
    """Simple passthrough proxy - intercepts Codex requests for hooks/slash commands/MCP"""
    target_url = f"{UPSTREAM_URL}/{path}"
    
    # Forward query parameters
    query_params = str(request.url.query)
    if query_params:
        target_url += f"?{query_params}"
    
    # Prepare headers (filter out hop-by-hop headers)
    headers = dict(request.headers)
    hop_by_hop_headers = ["host", "connection", "upgrade", "proxy-authorization", "proxy-authenticate"]
    for header in hop_by_hop_headers:
        headers.pop(header, None)
    # Ensure upstream sends identity encoding so we can safely prefix body
    headers["accept-encoding"] = "identity"
    # Inject Authorization from env if missing
    if not headers.get("authorization"):
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            headers["authorization"] = f"Bearer {api_key}"
            logger.info("AUTH_INJECTED via env OPENAI_API_KEY")
    
    async with httpx.AsyncClient() as client:
        # Build and send streaming request upstream
        req_out = client.build_request(
            request.method,
            target_url,
            headers=headers,
            content=await request.body(),
        )
        upstream = await client.send(req_out, stream=True)

        client_ip = request.client.host if request.client else "-"
        outcome = "OK" if 200 <= upstream.status_code < 400 else "FAIL"
        logger.info(f"{outcome} {request.method} /{path} -> {upstream.status_code} (ip={client_ip})")

        async def aiter():
            try:
                async for chunk in upstream.aiter_raw():
                    yield chunk
            except Exception as e:
                logger.exception(f"STREAM ERROR {request.method} /{path} -> {upstream.status_code}: {e}")
                raise

        # Prepend a title to all proxied output (temporary instrumentation)
        async def aiter_with_prefix():
            prefix = b"Genesis coder, "
            # Emit prefix first so clients see the banner immediately
            yield prefix
            async for chunk in upstream.aiter_raw():
                yield chunk

        # Copy upstream headers but remove Content-Length since body is modified
        resp_headers = dict(upstream.headers)
        resp_headers.pop("content-length", None)
        # Body modified; remove content-encoding if present
        resp_headers.pop("content-encoding", None)

        return StreamingResponse(
            aiter_with_prefix(),
            status_code=upstream.status_code,
            headers=resp_headers,
            background=BackgroundTask(upstream.aclose),
        )
