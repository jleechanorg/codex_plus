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

### Phase 2: Slash Commands - Module Architecture
```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class SlashCommandModule(ABC):
    """Base class for all slash command modules with prompt mutation capability"""
    
    def __init__(self, command_name: str):
        self.command_name = command_name
        self.description = ""
        self.usage = ""
    
    @abstractmethod
    def can_handle(self, command: str, args: str) -> bool:
        """Check if this module can handle the given command"""
        return command == self.command_name
    
    @abstractmethod 
    def mutate_prompt(self, original_prompt: str, args: str) -> Optional[str]:
        """Mutate the prompt before sending to ChatGPT. Return None for local execution."""
        pass
        
    @abstractmethod
    def execute_locally(self, args: str) -> Optional[Dict[str, Any]]:
        """Execute command locally if mutate_prompt returns None"""
        pass

# Example implementations
class SaveModule(SlashCommandModule):
    def __init__(self):
        super().__init__("/save")
        self.description = "Save conversation to file"
    
    def can_handle(self, command: str, args: str) -> bool:
        return command == "/save"
    
    def mutate_prompt(self, original_prompt: str, args: str) -> Optional[str]:
        return None  # Execute locally, don't send to ChatGPT
    
    def execute_locally(self, args: str) -> Dict[str, Any]:
        # Save conversation logic
        return {"success": True, "message": "Conversation saved"}

class HelpModule(SlashCommandModule):
    def __init__(self):
        super().__init__("/help")
        self.description = "Get help with commands"
    
    def can_handle(self, command: str, args: str) -> bool:
        return command in ["/help", "/?"]
    
    def mutate_prompt(self, original_prompt: str, args: str) -> Optional[str]:
        # Transform slash command into enhanced prompt for ChatGPT
        if args.strip():
            return f"Provide detailed help about: {args}. Include usage examples and best practices."
        return "List all available slash commands with descriptions and usage examples."
    
    def execute_locally(self, args: str) -> Optional[Dict[str, Any]]:
        return None  # Send to ChatGPT instead

class AnalyzeModule(SlashCommandModule):
    def __init__(self):
        super().__init__("/analyze")
        self.description = "Analyze code or system"
    
    def can_handle(self, command: str, args: str) -> bool:
        return command in ["/analyze", "/arch", "/review"]
    
    def mutate_prompt(self, original_prompt: str, args: str) -> Optional[str]:
        # Enhance prompt with analysis context
        return f"""Perform comprehensive analysis: {args}
        
Please provide:
1. Architecture overview
2. Code quality assessment  
3. Performance considerations
4. Security review
5. Recommendations for improvement

Focus on actionable insights and specific examples."""
    
    def execute_locally(self, args: str) -> Optional[Dict[str, Any]]:
        return None  # Send enhanced prompt to ChatGPT

# Command processor in main proxy
async def proxy(request: Request, path: str):
    body = await request.body()
    
    # Parse request to extract user message
    user_message = extract_user_message(body)
    
    # Check for slash commands
    if user_message.startswith('/'):
        command, args = parse_slash_command(user_message)
        
        # Find appropriate module
        for module in command_modules:
            if module.can_handle(command, args):
                # Try prompt mutation first
                mutated_prompt = module.mutate_prompt(user_message, args)
                
                if mutated_prompt:
                    # Send mutated prompt to ChatGPT
                    modified_body = replace_user_message(body, mutated_prompt)
                    return forward_to_chatgpt(modified_body)
                else:
                    # Execute locally and return result
                    result = module.execute_locally(args)
                    return create_local_response(result)
        
        # Unknown command - let ChatGPT handle it
        return forward_to_chatgpt(body)
    
    # Regular message - passthrough
    return forward_to_chatgpt(body)

# Module registration
command_modules = [
    SaveModule(),
    HelpModule(), 
    AnalyzeModule(),
    # Add more modules here...
]
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

### Directory Structure with Module System
```
codex_plus/
├── main_sync_cffi.py          # Core proxy implementation
├── slash_modules/             # Slash command module system
│   ├── __init__.py           # Module registry and base classes
│   ├── base.py              # SlashCommandModule abstract base
│   ├── save_module.py       # /save command implementation
│   ├── help_module.py       # /help command implementation  
│   ├── analyze_module.py    # /analyze, /arch, /review commands
│   ├── status_module.py     # /status command implementation
│   └── custom/              # User-defined custom modules
│       └── my_module.py     # Example custom module
├── requirements.txt           # Python dependencies
├── .claude/                   # Configuration directory (Claude Code CLI compatibility)
│   ├── commands/             # Claude Code CLI command definitions (*.md files)
│   │   ├── save.md          # /save command for native Claude Code CLI
│   │   └── status.md        # /status command for native Claude Code CLI
│   ├── hooks/               # Hook definitions
│   │   ├── pre_input.py    # Pre-input hooks
│   │   └── post_output.py  # Post-output hooks
│   └── settings.json        # User settings
└── sessions/                # Session storage
    └── {session_id}.json
```

## Module System Integration Strategy

### Dual Compatibility Approach
The system supports both:
1. **Native Module System**: Python classes with prompt mutation capability
2. **Claude Code CLI Compatibility**: Standard `.claude/commands/*.md` files

### Module Discovery and Loading
```python
# In slash_modules/__init__.py
import importlib
import os
from typing import List
from .base import SlashCommandModule

def discover_modules() -> List[SlashCommandModule]:
    """Auto-discover and load all slash command modules"""
    modules = []
    
    # Load built-in modules
    builtin_modules = [
        'save_module', 'help_module', 'analyze_module', 'status_module'
    ]
    
    for module_name in builtin_modules:
        try:
            mod = importlib.import_module(f'.{module_name}', __package__)
            if hasattr(mod, 'create_module'):
                modules.append(mod.create_module())
        except ImportError:
            continue
    
    # Load custom modules from custom/ directory  
    custom_dir = os.path.join(os.path.dirname(__file__), 'custom')
    if os.path.exists(custom_dir):
        for filename in os.listdir(custom_dir):
            if filename.endswith('_module.py'):
                module_name = filename[:-3]  # Remove .py
                try:
                    mod = importlib.import_module(f'.custom.{module_name}', __package__)
                    if hasattr(mod, 'create_module'):
                        modules.append(mod.create_module())
                except ImportError:
                    continue
    
    return modules

# Global module registry
_command_modules = None

def get_command_modules() -> List[SlashCommandModule]:
    """Get singleton list of command modules"""
    global _command_modules
    if _command_modules is None:
        _command_modules = discover_modules()
    return _command_modules
```

### Claude Code CLI Fallback Strategy
```python
async def handle_slash_command(command: str, args: str, original_body: bytes):
    """Handle slash command with module system + Claude Code CLI fallback"""
    
    # Try module system first
    for module in get_command_modules():
        if module.can_handle(command, args):
            mutated_prompt = module.mutate_prompt(f"{command} {args}", args)
            
            if mutated_prompt:
                # Send mutated prompt to ChatGPT
                modified_body = replace_user_message(original_body, mutated_prompt)
                return await forward_to_chatgpt(modified_body)
            else:
                # Execute locally
                result = module.execute_locally(args)
                return create_local_response(result)
    
    # Fallback: Check for Claude Code CLI .md commands
    md_command_path = f".claude/commands/{command[1:]}.md"  # Remove leading /
    if os.path.exists(md_command_path):
        # Read markdown command and execute as enhanced prompt
        with open(md_command_path, 'r') as f:
            content = f.read()
        
        # Parse frontmatter and content
        enhanced_prompt = parse_claude_code_command(content, args)
        modified_body = replace_user_message(original_body, enhanced_prompt)
        return await forward_to_chatgpt(modified_body)
    
    # Unknown command - pass through to ChatGPT for natural handling
    return await forward_to_chatgpt(original_body)
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
- Break compatibility with existing Claude Code CLI commands

## Slash Command Module System Benefits

### Key Advantages
1. **Prompt Mutation**: Transform slash commands into enhanced prompts for better AI responses
2. **Flexible Execution**: Choose between local execution or AI-powered responses per command
3. **Inheritance-Based**: Clean OOP design with shared functionality in base class
4. **Auto-Discovery**: Modules are automatically loaded and registered
5. **Claude Code CLI Compatible**: Fallback to existing .md command files seamlessly  
6. **Extensible**: Easy to add new commands without modifying core proxy code

### Example Module Implementation
```python
# slash_modules/research_module.py
from .base import SlashCommandModule
from typing import Optional, Dict, Any

class ResearchModule(SlashCommandModule):
    def __init__(self):
        super().__init__("/research")
        self.description = "Enhanced research with multi-source analysis"
    
    def can_handle(self, command: str, args: str) -> bool:
        return command in ["/research", "/investigate", "/analyze"]
    
    def mutate_prompt(self, original_prompt: str, args: str) -> Optional[str]:
        return f"""Conduct comprehensive research on: {args}

Please provide:
1. **Overview**: High-level summary and context
2. **Key Findings**: Most important discoveries and insights  
3. **Technical Details**: Implementation specifics and examples
4. **Alternatives**: Different approaches and trade-offs
5. **Recommendations**: Actionable next steps

Use multiple perspectives and cite specific examples where possible."""
    
    def execute_locally(self, args: str) -> Optional[Dict[str, Any]]:
        return None  # Always send enhanced prompt to AI

def create_module() -> ResearchModule:
    return ResearchModule()
```

### Integration Benefits
- **Seamless Migration**: Existing users keep their .claude/commands/*.md files working
- **Power User Features**: Module system provides advanced prompt engineering capabilities
- **Performance**: No overhead for non-slash-command requests
- **Maintainability**: Clear separation between command logic and proxy infrastructure

## Conclusion

The simple curl_cffi proxy is the optimal solution for Codex-Plus. It solves the core problem (Cloudflare bypass) elegantly and provides a solid foundation for all planned features without unnecessary complexity.