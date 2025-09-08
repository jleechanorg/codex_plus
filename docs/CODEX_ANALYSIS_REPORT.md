# Codex CLI Analysis Report

**Date:** January 8, 2025  
**Analysis Type:** System Prompt and API Structure Investigation

## Executive Summary

Successfully reverse-engineered Codex CLI's communication protocol with ChatGPT backend through proxy interception. Discovered that Codex uses a proprietary instruction format (not standard OpenAI Chat Completions) with ~377 lines of system instructions defining it as a specialized coding agent.

## Key Discoveries

### 1. Authentication & Endpoint
- **Authentication:** ChatGPT OAuth2 JWT tokens (NOT OpenAI API keys)
- **Backend URL:** `https://chatgpt.com/backend-api/codex` (NOT api.openai.com)
- **Protection:** Cloudflare TLS fingerprinting blocks standard HTTP clients
- **Solution:** curl_cffi with Chrome impersonation successfully bypasses protection

### 2. API Structure

#### Request Format
```json
{
  "model": "gpt-5",
  "instructions": "[system instructions here]",
  "input": [
    {
      "type": "message",
      "role": "user",
      "content": [...]
    }
  ],
  "tools": [...],
  "reasoning": {
    "effort": "medium",
    "summary": "auto"
  },
  "stream": true,
  "prompt_cache_key": "[unique-key]"
}
```

**Key Differences from OpenAI API:**
- Uses `instructions` field instead of system message in `messages` array
- Has `input` array for conversation history (not `messages`)
- Includes `reasoning` configuration with effort levels
- Tools defined in request (shell, view_image, update_plan, apply_patch)
- Uses prompt caching with unique keys

### 3. System Instructions Analysis

#### Core Identity
- Positioned as "coding agent running in the Codex CLI"
- Emphasizes being "precise, safe, and helpful"
- Open source project led by OpenAI

#### Major Components
1. **Personality & Tone**
   - Concise, direct, friendly
   - Efficient communication
   - Actionable guidance focus

2. **Planning System**
   - `update_plan` tool for task tracking
   - Step-by-step execution with status tracking
   - Progress updates for longer tasks

3. **File Editing**
   - Custom `apply_patch` format (not standard diff)
   - Structured patch language with Begin/End envelope
   - Add/Delete/Update file operations

4. **Sandbox Modes**
   - **Filesystem:** read-only, workspace-write, danger-full-access
   - **Network:** restricted, enabled
   - **Approvals:** untrusted, on-failure, on-request, never

5. **Special Features**
   - AGENTS.md file support for per-directory instructions
   - Reasoning with configurable effort levels
   - Streaming responses with thinking content

## Technical Implementation

### Working Solution: curl_cffi Proxy
```python
# main_sync_cffi.py - Simple passthrough proxy
from fastapi import FastAPI, Request
from curl_cffi import requests

app = FastAPI()
UPSTREAM_URL = "https://chatgpt.com/backend-api/codex"

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(request: Request, path: str):
    session = requests.Session(impersonate="chrome124")
    response = session.request(
        request.method,
        f"{UPSTREAM_URL}/{path}",
        headers=dict(request.headers),
        data=await request.body(),
        stream=True
    )
    # Stream response back...
```

### Why LiteLLM Failed
- LiteLLM expects API keys, not JWT tokens
- Designed for standard OpenAI/Anthropic APIs
- Cannot handle ChatGPT's OAuth2 authentication
- Incompatible with Codex's custom instruction format

## Implications for Codex-Plus

### Opportunities
1. **Slash Commands** - Can intercept and modify `input` field
2. **Instruction Enhancement** - Can append to system instructions
3. **Tool Injection** - Can add custom tools to requests
4. **Response Processing** - Can modify streaming responses
5. **Session Management** - Can cache and replay conversations

### Architecture Decision
- **Keep:** Simple Python proxy with curl_cffi
- **Remove:** LiteLLM, Node.js middleware
- **Reason:** Direct control over request/response pipeline

## Testing Results

| Test Type | Result | Notes |
|-----------|--------|-------|
| Simple Math | ✅ Pass | "What is 15 + 27?" → 42 |
| Code Generation | ✅ Pass | Prime number function |
| Concept Explanation | ✅ Pass | REST API explanation |
| Streaming | ✅ Pass | Real-time response streaming |
| Request Logging | ✅ Pass | Full payload capture |

## File Artifacts

- `docs/codex_system_instructions.md` - Full 377-line system prompt
- `docs/codex_request_structure.json` - Complete request payload example
- `main_sync_cffi.py` - Working proxy implementation
- `design.md` - Updated architecture documentation

## Recommendations

1. **Immediate:** Use simple proxy for slash command implementation
2. **Short-term:** Build instruction modification layer
3. **Long-term:** Consider MCP tool integration
4. **Avoid:** Complex multi-service architectures

## Conclusion

The investigation successfully revealed Codex's internal architecture. The simple curl_cffi proxy provides full control over the request/response pipeline, enabling all planned Codex-Plus features without the complexity of LiteLLM or multi-service coordination.