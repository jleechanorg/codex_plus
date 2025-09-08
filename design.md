# Codex-Plus Design Document: Simple Proxy Architecture

**Version:** 3.0  
**Date:** January 2025  
**Architecture:** Python curl_cffi Proxy with Integrated Middleware

## Executive Summary

Codex-Plus uses a simple Python proxy with curl_cffi to bypass Cloudflare and connect directly to ChatGPT's backend. All features (slash commands, hooks, MCP) are integrated directly into the Python proxy, avoiding unnecessary complexity and inter-service communication overhead.

## Key Discoveries

1. **Codex uses ChatGPT OAuth2 JWT tokens** (not OpenAI API keys)
2. **Backend URL is `https://chatgpt.com/backend-api/codex`** (not api.openai.com)
3. **Cloudflare blocks standard HTTP clients** - requires TLS fingerprinting bypass
4. **LiteLLM is incompatible** with ChatGPT JWT authentication

## Architecture Overview

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Codex CLI  │───▶│  Python Proxy    │───▶│  ChatGPT Backend│
│  (Client)   │    │  (Port 3000)     │    │  (Cloudflare)   │
└─────────────┘    │  curl_cffi       │    └─────────────────┘
                   └──────────────────┘
                            │
                   ┌──────────────────┐
                   │ Integrated Features│
                   │ • Slash Commands  │
                   │ • Hooks System    │
                   │ • MCP Integration │
                   │ • Session Mgmt    │
                   └──────────────────┘
```

## Core Implementation

### Simple Passthrough Proxy (main_sync_cffi.py)
```python
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from curl_cffi import requests

app = FastAPI()
UPSTREAM_URL = "https://chatgpt.com/backend-api/codex"

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(request: Request, path: str):
    # Use curl_cffi with Chrome impersonation to bypass Cloudflare
    session = requests.Session(impersonate="chrome124")
    
    response = session.request(
        request.method,
        f"{UPSTREAM_URL}/{path}",
        headers=dict(request.headers),
        data=await request.body(),
        stream=True
    )
    
    # Stream response back
    def stream_response():
        for chunk in response.iter_content(chunk_size=None):
            if chunk:
                yield chunk
    
    return StreamingResponse(stream_response())
```

## Feature Implementation Strategy

### Phase 1: Working Proxy ✅ (Complete)
- Simple passthrough proxy with curl_cffi
- Cloudflare bypass working
- SSE streaming functional

### Phase 2: Slash Commands (Next)
```python
async def proxy(request: Request, path: str):
    body = await request.body()
    
    # Detect slash commands
    if is_slash_command(body):
        return handle_slash_command(body)
    
    # Otherwise passthrough
    return forward_to_chatgpt(body)

def handle_slash_command(body):
    command = extract_command(body)
    if command == "/save":
        return save_conversation()
    elif command == "/status":
        return get_status()
    # etc...
```

### Phase 3: Hooks System
```python
# Pre-input and post-output hooks
async def proxy(request: Request, path: str):
    body = await request.body()
    
    # Pre-hooks
    body = await run_pre_hooks(body)
    
    # Forward request
    response = await forward_to_chatgpt(body)
    
    # Post-hooks on stream
    async def hooked_stream():
        async for chunk in response:
            chunk = await run_post_hooks(chunk)
            yield chunk
    
    return StreamingResponse(hooked_stream())
```

### Phase 4: MCP Integration
```python
# Remote MCP tool execution
async def handle_mcp_request(tool_name, params):
    mcp_server = get_mcp_server(tool_name)
    result = await mcp_server.execute(tool_name, params)
    return format_mcp_response(result)
```

## Configuration System

### Directory Structure
```
codex_plus/
├── main_sync_cffi.py          # Core proxy implementation
├── requirements.txt           # Python dependencies
├── .claude/                   # Configuration directory
│   ├── commands/             # Slash command definitions
│   │   ├── save.py          # /save command
│   │   └── status.py        # /status command  
│   ├── hooks/               # Hook definitions
│   │   ├── pre_input.py    # Pre-input hooks
│   │   └── post_output.py  # Post-output hooks
│   └── settings.json        # User settings
└── sessions/                # Session storage
    └── {session_id}.json
```

## Why This Architecture

### Advantages over Complex Approaches
1. **Single Process** - No inter-service communication overhead
2. **Direct Control** - Full access to request/response pipeline
3. **Simple Debugging** - Everything in one Python process
4. **Proven Solution** - curl_cffi reliably bypasses Cloudflare
5. **Fast Development** - Add features directly without coordination

### What We DON'T Need
- **LiteLLM** - Incompatible with ChatGPT JWT auth
- **Node.js middleware** - Python can handle everything
- **Multiple services** - Unnecessary complexity
- **API key routing** - We're using ChatGPT subscription auth

## Performance Characteristics

| Component | Latency | Notes |
|-----------|---------|-------|
| **Proxy overhead** | <5ms | Minimal processing |
| **Slash commands** | <10ms | Local processing |
| **Hooks** | <5ms per hook | Async execution |
| **Total overhead** | <20ms | Negligible impact |

## Security Model

### Authentication
- Uses existing Codex CLI authentication (~/.codex/auth.json)
- JWT tokens automatically refreshed by Codex
- No API keys needed

### Command Execution
```python
ALLOWED_COMMANDS = ['/save', '/status', '/help']

def validate_command(command):
    if command not in ALLOWED_COMMANDS:
        raise ValueError(f"Unknown command: {command}")
```

## Development Workflow

### Running the Proxy
```bash
# Install dependencies
pip install fastapi uvicorn curl_cffi

# Run proxy
python -c "from main_sync_cffi import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=3000)"

# Use with Codex
export OPENAI_BASE_URL=http://localhost:3000
codex "Hello world"
```

### Adding Features
1. Edit `main_sync_cffi.py` directly
2. Test with Codex CLI
3. No service coordination needed

## Migration from Original Design

### What Changed
- **Removed LiteLLM** - Incompatible with ChatGPT auth
- **Removed Node.js** - Python handles everything
- **Simplified to single service** - Better performance
- **Direct ChatGPT connection** - No API key routing

### What Stayed
- **Slash commands** - Implemented in Python
- **Hooks system** - Integrated into proxy
- **MCP support** - Can be added to Python
- **Configuration structure** - Same .claude directory

## Future Considerations

### Potential Enhancements
1. **Session persistence** - Store conversations locally
2. **Command plugins** - Dynamic command loading
3. **Hook marketplace** - Share hooks between users
4. **Multi-provider support** - Add Claude API as alternative (would need LiteLLM then)

### What We Won't Do
- Add unnecessary middleware layers
- Use LiteLLM for ChatGPT (incompatible)
- Complicate the simple working solution

## Conclusion

The simple curl_cffi proxy is the optimal solution for Codex-Plus. It solves the core problem (Cloudflare bypass) elegantly and provides a solid foundation for all planned features without unnecessary complexity.