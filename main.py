from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from starlette.background import BackgroundTask
import httpx
import logging

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

        return StreamingResponse(
            aiter(),
            status_code=upstream.status_code,
            headers=dict(upstream.headers),
            background=BackgroundTask(upstream.aclose),
        )
