#!/usr/bin/env python3
"""
Codex Plus Proxy using curl_cffi synchronous client for better SSE handling
Now with integrated slash command middleware for .claude/ infrastructure

🚨 CRITICAL: This proxy REQUIRES curl_cffi to bypass Cloudflare 🚨
DO NOT replace with httpx, requests, or any other HTTP client
Codex uses ChatGPT backend with session auth, NOT OpenAI API keys
"""
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from fastapi.responses import StreamingResponse, JSONResponse
from curl_cffi import requests
import logging
import json as _json
import json
import sys
import os
import time

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Session start hooks
        try:
            from .hooks import settings_session_start
            await settings_session_start(None, source="startup")
        except Exception as e:
            logger.error(f"Failed to execute session start hooks: {e}")
        yield
    finally:
        # Session end hooks
        try:
            from .hooks import settings_session_end
            await settings_session_end(None, reason="exit")
        except Exception as e:
            logger.error(f"Failed to execute session end hooks: {e}")


app = FastAPI(lifespan=lifespan)

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
from .hooks import (
    process_pre_input_hooks,
    process_post_output_hooks,
    settings_stop,
)


class HookMiddleware:
    """Lightweight middleware to run hook-like side effects around responses.

    This avoids invoking external scripts directly and computes any needed
    status lines using Python and standard git commands.
    """

    def __init__(self, enable_git_status: bool = True):
        self.enable_git_status = enable_git_status

    async def emit_status_line(self) -> None:
        if not self.enable_git_status:
            return
        import asyncio
        import subprocess
        import sys as _sys
        try:
            # Detect git root and branch
            git_root = subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            local_branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            # Upstream and ahead/behind
            try:
                upstream = subprocess.check_output(
                    ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                ).strip()
            except subprocess.CalledProcessError:
                upstream = "no upstream"

            local_status = ""
            if upstream != "no upstream":
                try:
                    ahead = int(
                        subprocess.check_output(
                            ["git", "rev-list", "--count", f"{upstream}..HEAD"],
                            text=True,
                            stderr=subprocess.DEVNULL,
                        ).strip()
                    )
                except Exception:
                    ahead = 0
                try:
                    behind = int(
                        subprocess.check_output(
                            ["git", "rev-list", "--count", f"HEAD..{upstream}"],
                            text=True,
                            stderr=subprocess.DEVNULL,
                        ).strip()
                    )
                except Exception:
                    behind = 0
                if ahead == 0 and behind == 0:
                    local_status = " (synced)"
                elif ahead > 0 and behind == 0:
                    local_status = f" (ahead {ahead})"
                elif ahead == 0 and behind > 0:
                    local_status = f" (behind {behind})"
                else:
                    local_status = f" (diverged +{ahead} -{behind})"
            else:
                local_status = " (no remote)"

            repo_name = git_root.rstrip("/\\").split("/")[-1]
            header = f"[Dir: {repo_name} | Local: {local_branch}{local_status} | Remote: {upstream} | PR: none]"
            logger.info("🎯 Git Status Line:")
            logger.info(f"   {header}")
            # Write transient status line to terminal
            print(f"\r{header}", file=_sys.stderr, flush=True)
        except Exception:
            # Best-effort only; never block or raise
            pass


hook_middleware = HookMiddleware()

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
            # If any settings hooks blocked the prompt, short-circuit
            if getattr(request.state, 'user_prompt_block', None):
                reason = request.state.user_prompt_block.get('reason', 'Blocked by hook')
                return JSONResponse({"error": reason}, status_code=400)
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
    
    # Run hook middleware side-effects (non-blocking)
    import asyncio
    asyncio.create_task(hook_middleware.emit_status_line())
    # Also trigger Stop settings hooks (best-effort)
    try:
        asyncio.create_task(settings_stop(request, {"transcript_path": ""}))
    except Exception:
        pass
    
    return response
