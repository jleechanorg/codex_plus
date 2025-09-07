from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
import httpx

app = FastAPI()

# Configuration
UPSTREAM_URL = "https://api.openai.com"

@app.get("/health")
async def health():
    """Simple health check - not forwarded"""
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
        async with client.stream(
            request.method, 
            target_url,
            headers=headers,
            content=await request.body()
        ) as upstream:
            async def aiter():
                try:
                    async for chunk in upstream.aiter_raw():
                        yield chunk
                finally:
                    await upstream.aclose()
            
            return StreamingResponse(
                aiter(), 
                status_code=upstream.status_code, 
                headers=dict(upstream.headers)
            )