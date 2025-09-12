import asyncio
import importlib.util
import logging
import os
import sys
import traceback
from typing import Any, Dict, List, Optional, Union, Tuple
from pathlib import Path

import yaml
from fastapi import Request, Response
from fastapi.responses import StreamingResponse

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class Hook:
    """Base hook class with multiple hook type methods"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.priority = config.get('priority', 100)
        self.enabled = config.get('enabled', True)
        self.hook_type = config.get('type', 'pre-input')  # Default type
    
    async def pre_input(self, request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the input before sending to the API (UserPromptSubmit).
        Should be overridden by subclasses.
        """
        return body
    
    async def post_output(self, response: Union[Response, StreamingResponse]) -> Union[Response, StreamingResponse]:
        """
        Process the output after receiving from the API (PostToolUse).
        Should be overridden by subclasses.
        """
        return response
    
    async def pre_tool_use(self, request: Request, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process before tool execution (PreToolUse).
        Should be overridden by subclasses.
        """
        return tool_args
    
    async def stop(self, request: Request, conversation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process when conversation ends (Stop).
        Should be overridden by subclasses.
        """
        return conversation_data

class HookSystem:
    """Hook system for managing and executing hooks"""
    
    def __init__(self, hooks_dirs: List[str] = None):
        if hooks_dirs is None:
            # Default: search .codexplus/hooks/ first (for new development), then .claude/hooks/
            hooks_dirs = [".codexplus/hooks/", ".claude/hooks/"]
        self.hooks_dirs = [Path(d) for d in hooks_dirs]
        self.hooks: List[Hook] = []
        # Settings-based hooks loaded from JSON settings files
        self.settings_hooks: Dict[str, List[Dict[str, Any]]] = {}
        self.session_id: str = os.environ.get("CODEX_PLUS_SESSION_ID", "local-session")
        self._load_hooks()
        self._load_settings_hooks()
    
    def _load_hooks(self) -> None:
        """Load all hooks from the hooks directories"""
        self.hooks = []
        loaded_names = set()  # Track loaded hook names to handle precedence
        
        for hooks_dir in self.hooks_dirs:
            if not hooks_dir.exists():
                logger.info(f"Hooks directory {hooks_dir} does not exist")
                continue
            
            # Avoid mutating sys.path; hook files can import codex_plus modules directly
            
            for hook_file in hooks_dir.glob("*.py"):
                # Skip if hook with same name already loaded (precedence)
                if hook_file.stem in loaded_names:
                    logger.info(f"Skipping {hook_file} - already loaded from higher precedence directory")
                    continue
                    
                try:
                    hook = self._load_hook_from_file(hook_file)
                    if hook:
                        self.hooks.append(hook)
                        loaded_names.add(hook_file.stem)
                        logger.info(f"Loaded hook: {hook.name} from {hooks_dir}")
                except Exception as e:
                    logger.error(f"Failed to load hook from {hook_file}: {e}")
                    logger.debug(traceback.format_exc())
        
        # Sort hooks by priority (lower number = higher priority)
        self.hooks.sort(key=lambda h: h.priority)
        logger.info(f"Loaded {len(self.hooks)} hooks")

    def _load_settings_hooks(self) -> None:
        """Load hooks from .codexplus/settings.json and .claude/settings.json.

        Merge arrays per event. .codexplus settings take precedence by ordering (first).
        """
        self.settings_hooks = {}

        def read_settings(p: Path) -> Dict[str, Any]:
            try:
                if p.exists():
                    import json
                    return json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error(f"Failed reading settings from {p}: {e}")
            return {}

        # Locate settings files
        codex_settings = Path(".codexplus/settings.json")
        claude_settings = Path(".claude/settings.json")
        cfgs = []
        for p in [codex_settings, claude_settings]:
            cfg = read_settings(p)
            if cfg:
                cfgs.append(cfg)

        # Merge hooks
        for cfg in cfgs:
            hooks_map = cfg.get("hooks", {}) or {}
            for event, entries in hooks_map.items():
                if not isinstance(entries, list):
                    continue
                self.settings_hooks.setdefault(event, [])
                # Normalize entries to dict with optional matcher and hooks list
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    hooks_arr = entry.get("hooks", []) or []
                    matcher = entry.get("matcher")  # may be None
                    for h in hooks_arr:
                        if not isinstance(h, dict):
                            continue
                        t = h.get("type")
                        if t != "command":
                            continue
                        cmd = h.get("command")
                        if not cmd:
                            continue
                        timeout = h.get("timeout", 5)
                        self.settings_hooks[event].append({
                            "matcher": matcher,
                            "type": "command",
                            "command": cmd,
                            "timeout": timeout,
                        })
        if self.settings_hooks:
            logger.info(f"Loaded settings hooks for events: {sorted(self.settings_hooks.keys())}")
    
    def _load_hook_from_file(self, file_path: Path) -> Optional[Hook]:
        """Load a single hook from a Python file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse YAML frontmatter
        config = self._parse_frontmatter(content)
        if not config:
            logger.warning(f"No valid frontmatter found in {file_path}")
            return None
        
        # Check if hook is enabled
        if not config.get('enabled', True):
            logger.info(f"Hook in {file_path} is disabled")
            return None
        
        # Extract Python code (after frontmatter)
        python_code = self._extract_python_code(content)
        if not python_code:
            logger.error(f"No Python code found in {file_path}")
            return None
        
        # Create a module using importlib without mutating sys.path
        try:
            module_name = f"codex_plus_hook_{file_path.stem}"
            # Create a bare module spec and set __file__ for better import semantics inside hook code
            spec = importlib.util.spec_from_loader(module_name, loader=None)
            module = importlib.util.module_from_spec(spec)
            module.__file__ = str(file_path)
            # Compile with the actual file path for accurate tracebacks
            code_obj = compile(python_code, str(file_path), 'exec')
            exec(code_obj, module.__dict__)
        except Exception as e:
            logger.error(f"Error loading hook module from {file_path}: {e}")
            logger.debug(traceback.format_exc())
            return None
        
        # Find a subclass of Hook defined in the module (excluding base Hook)
        hook_class = None
        for name, obj in module.__dict__.items():
            if name == 'Hook':
                continue
            if isinstance(obj, type) and issubclass(obj, Hook):
                hook_class = obj
                break
        if hook_class is None:
            logger.warning(f"No hook subclass found in {file_path}")
            return None
        # Create hook instance
        return hook_class(file_path.stem, config)
    
    def _parse_frontmatter(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse YAML frontmatter from file content"""
        lines = content.splitlines()
        
        if len(lines) < 3:
            return None
            
        # Check for frontmatter delimiter
        if lines[0].strip() != '---':
            return None
        
        # Find end of frontmatter
        end_index = -1
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == '---':
                end_index = i
                break
        
        if end_index == -1:
            return None
        
        # Extract and parse YAML
        yaml_content = '\n'.join(lines[1:end_index])
        try:
            return yaml.safe_load(yaml_content) or {}
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {e}")
            return None
    
    def _extract_python_code(self, content: str) -> Optional[str]:
        """Extract Python code from content after YAML frontmatter"""
        lines = content.splitlines()
        
        if len(lines) < 3:
            return content  # No frontmatter, return as-is
            
        # Check for frontmatter delimiter
        if lines[0].strip() != '---':
            return content  # No frontmatter, return as-is
        
        # Find end of frontmatter
        end_index = -1
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == '---':
                end_index = i
                break
        
        if end_index == -1:
            return content  # No valid frontmatter end, return as-is
        
        # Return everything after the frontmatter
        python_lines = lines[end_index + 1:]
        return '\n'.join(python_lines)
    
    async def execute_pre_input_hooks(self, request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all pre_input hooks in priority order"""
        modified_body = body.copy()
        
        for hook in self.hooks:
            if not hook.enabled or hook.hook_type != 'pre-input':
                continue
                
            try:
                modified_body = await hook.pre_input(request, modified_body)
            except Exception as e:
                logger.error(f"Error in pre_input hook '{hook.name}': {e}")
                logger.debug(traceback.format_exc())
                # Continue with the original body if hook fails
                continue
        
        return modified_body

    # =============== Settings-based hooks execution ===============
    def _match_tool(self, matcher: Optional[str], tool_name: str) -> bool:
        if not matcher or matcher == "*":
            return True
        try:
            import re
            return re.search(matcher, tool_name) is not None
        except Exception:
            return matcher == tool_name

    def _run_command_hook(self, cmd: str, payload: Dict[str, Any], timeout: Union[int, float]) -> Tuple[int, str, str, Optional[Dict[str, Any]]]:
        """Run a single command hook with JSON stdin. Return (exit_code, stdout, stderr, parsed_json)."""
        import subprocess, json, shlex, os as _os
        try:
            # Best-effort project dir discovery for CLAUDE_PROJECT_DIR
            project_dir = os.getcwd()
            try:
                git_root = subprocess.check_output(
                    ["git", "rev-parse", "--show-toplevel"], text=True, stderr=subprocess.DEVNULL
                ).strip()
                if git_root:
                    project_dir = git_root
            except Exception:
                pass
            env = os.environ.copy()
            env.setdefault("CLAUDE_PROJECT_DIR", project_dir)
            # Expand project variable and environment vars in command string
            cmd_str = str(cmd)
            cmd_str = cmd_str.replace("$CLAUDE_PROJECT_DIR", project_dir).replace("${CLAUDE_PROJECT_DIR}", project_dir)
            cmd_expanded = cmd if isinstance(cmd, list) else shlex.split(_os.path.expandvars(cmd_str))
            proc = subprocess.run(
                cmd_expanded,
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                timeout=timeout,
                cwd=os.getcwd(),
                env=env,
            )
            parsed = None
            if proc.stdout:
                try:
                    parsed = json.loads(proc.stdout)
                except Exception:
                    parsed = None
            return proc.returncode, proc.stdout or "", proc.stderr or "", parsed
        except subprocess.TimeoutExpired:
            return 124, "", "Hook timed out", None
        except Exception as e:
            return 1, "", f"Hook failed: {e}", None

    async def run_user_prompt_submit_hooks(self, request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        """Execute UserPromptSubmit hooks from settings: may block or add context; can also modify body."""
        event = "UserPromptSubmit"
        entries = self.settings_hooks.get(event, [])
        if not entries:
            return body

        # Build input payload per docs
        payload = {
            "session_id": self.session_id,
            "transcript_path": "",
            "cwd": os.getcwd(),
            "hook_event_name": event,
            "prompt": "",
        }
        try:
            # Extract raw prompt text heuristically from body
            if "messages" in body and body["messages"]:
                # use last user message
                for m in reversed(body["messages"]):
                    if m.get("role") == "user":
                        payload["prompt"] = m.get("content", "")
                        break
            elif "input" in body:
                # Codex format
                for item in body["input"]:
                    if isinstance(item, dict) and item.get("type") == "message":
                        for c in item.get("content", []):
                            if isinstance(c, dict) and c.get("type") == "input_text":
                                payload["prompt"] = c.get("text", "")
                                break
                        break
        except Exception:
            pass

        # Execute hooks in order; first block wins, collect additional context
        additional_contexts: List[str] = []
        for h in entries:
            code, out, err, parsed = self._run_command_hook(h["command"], payload, h["timeout"])
            if code == 2:
                # Block with reason in stderr
                request.state.user_prompt_block = {"reason": err.strip() or "Blocked by hook"}
                break
            if parsed and isinstance(parsed, dict):
                hs = parsed.get("hookSpecificOutput", {}) or {}
                if hs.get("hookEventName") == event and hs.get("additionalContext"):
                    additional_contexts.append(str(hs.get("additionalContext")))
                decision = parsed.get("decision")
                if decision == "block":
                    request.state.user_prompt_block = {"reason": parsed.get("reason", "Blocked by hook")}
                    break

        # Inject additional context if any
        if additional_contexts:
            context_text = "\n\n".join(additional_contexts)
            try:
                if "messages" in body:
                    body["messages"].insert(0, {"role": "system", "content": context_text})
                elif "input" in body:
                    # Prepend to first input_text
                    for item in body["input"]:
                        if isinstance(item, dict) and item.get("type") == "message":
                            for c in item.get("content", []):
                                if isinstance(c, dict) and c.get("type") == "input_text":
                                    c["text"] = f"[HOOK-CONTEXT]\n{context_text}\n\n" + c.get("text", "")
                                    raise StopIteration
            except StopIteration:
                pass
            except Exception:
                pass

        return body

    async def run_pre_tool_use_hooks(self, request: Request, tool_name: str, tool_args: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """Execute PreToolUse settings hooks. Returns (args, block_info|None)."""
        event = "PreToolUse"
        entries = self.settings_hooks.get(event, [])
        if not entries:
            return tool_args, None
        payload = {
            "session_id": self.session_id,
            "transcript_path": "",
            "cwd": os.getcwd(),
            "hook_event_name": event,
            "tool_name": tool_name,
            "tool_input": tool_args,
        }
        for h in entries:
            if h.get("matcher") and not self._match_tool(h["matcher"], tool_name):
                continue
            code, out, err, parsed = self._run_command_hook(h["command"], payload, h["timeout"])
            if code == 2:
                return tool_args, {"reason": err.strip() or "Blocked by hook"}
            if parsed and isinstance(parsed, dict):
                hs = parsed.get("hookSpecificOutput", {}) or {}
                decision = parsed.get("decision") or hs.get("permissionDecision")
                if decision in ("deny", "block"):
                    return tool_args, {"reason": parsed.get("reason") or hs.get("permissionDecisionReason", "Blocked by hook")}
                # Allow (or ask) — for now we just pass through args
        return tool_args, None

    async def run_post_tool_use_hooks(self, request: Request, tool_name: str, tool_args: Dict[str, Any], tool_response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute PostToolUse settings hooks. Returns optional feedback dict for Claude."""
        event = "PostToolUse"
        entries = self.settings_hooks.get(event, [])
        if not entries:
            return None
        payload = {
            "session_id": self.session_id,
            "transcript_path": "",
            "cwd": os.getcwd(),
            "hook_event_name": event,
            "tool_name": tool_name,
            "tool_input": tool_args,
            "tool_response": tool_response,
        }
        feedbacks = []
        for h in entries:
            if h.get("matcher") and not self._match_tool(h["matcher"], tool_name):
                continue
            _, out, err, parsed = self._run_command_hook(h["command"], payload, h["timeout"])
            if parsed and isinstance(parsed, dict):
                feedbacks.append(parsed)
        # For now return the first structured feedback
        return feedbacks[0] if feedbacks else None

    async def run_notification_hooks(self, request: Request, message: str) -> None:
        event = "Notification"
        entries = self.settings_hooks.get(event, [])
        if not entries:
            return
        payload = {
            "session_id": self.session_id,
            "transcript_path": "",
            "cwd": os.getcwd(),
            "hook_event_name": event,
            "message": message,
        }
        for h in entries:
            self._run_command_hook(h["command"], payload, h["timeout"])

    async def run_stop_hooks(self, request: Request, conversation_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        event = "Stop"
        entries = self.settings_hooks.get(event, [])
        if not entries:
            return None
        payload = {
            "session_id": self.session_id,
            "transcript_path": conversation_data.get("transcript_path", ""),
            "hook_event_name": event,
            "stop_hook_active": False,
        }
        for h in entries:
            _, out, err, parsed = self._run_command_hook(h["command"], payload, h["timeout"])
            if parsed:
                return parsed
        return None

    async def run_pre_compact_hooks(self, request: Request, trigger: str, custom_instructions: str = "") -> None:
        event = "PreCompact"
        entries = self.settings_hooks.get(event, [])
        if not entries:
            return
        payload = {
            "session_id": self.session_id,
            "transcript_path": "",
            "hook_event_name": event,
            "trigger": trigger,
            "custom_instructions": custom_instructions,
        }
        for h in entries:
            self._run_command_hook(h["command"], payload, h["timeout"])

    async def run_session_start_hooks(self, request: Optional[Request], source: str = "startup") -> None:
        event = "SessionStart"
        entries = self.settings_hooks.get(event, [])
        if not entries:
            return
        payload = {
            "session_id": self.session_id,
            "transcript_path": "",
            "hook_event_name": event,
            "source": source,
        }
        for h in entries:
            self._run_command_hook(h["command"], payload, h["timeout"])

    async def run_session_end_hooks(self, request: Optional[Request], reason: str = "exit") -> None:
        event = "SessionEnd"
        entries = self.settings_hooks.get(event, [])
        if not entries:
            return
        payload = {
            "session_id": self.session_id,
            "transcript_path": "",
            "cwd": os.getcwd(),
            "hook_event_name": event,
            "reason": reason,
        }
        for h in entries:
            self._run_command_hook(h["command"], payload, h["timeout"])
    
    async def execute_post_output_hooks(self, response: Union[Response, StreamingResponse]) -> Union[Response, StreamingResponse]:
        """Execute all post_output hooks in priority order"""
        modified_response = response
        
        for hook in self.hooks:
            if not hook.enabled or hook.hook_type != 'post-output':
                continue
                
            try:
                modified_response = await hook.post_output(modified_response)
            except Exception as e:
                logger.error(f"Error in post_output hook '{hook.name}': {e}")
                logger.debug(traceback.format_exc())
                # Continue with the original response if hook fails
                continue
        
        return modified_response
    
    async def execute_pre_tool_use_hooks(self, request: Request, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all pre_tool_use hooks in priority order"""
        modified_args = tool_args.copy()
        
        for hook in self.hooks:
            if not hook.enabled or hook.hook_type != 'pre-tool-use':
                continue
                
            try:
                modified_args = await hook.pre_tool_use(request, tool_name, modified_args)
            except Exception as e:
                logger.error(f"Error in pre_tool_use hook '{hook.name}': {e}")
                logger.debug(traceback.format_exc())
                # Continue with the original args if hook fails
                continue
        
        return modified_args
    
    async def execute_stop_hooks(self, request: Request, conversation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all stop hooks in priority order"""
        modified_data = conversation_data.copy()
        
        for hook in self.hooks:
            if not hook.enabled or hook.hook_type != 'stop':
                continue
                
            try:
                modified_data = await hook.stop(request, modified_data)
            except Exception as e:
                logger.error(f"Error in stop hook '{hook.name}': {e}")
                logger.debug(traceback.format_exc())
                # Continue with the original data if hook fails
                continue
        
        return modified_data

# Global hook system instance
hook_system = HookSystem()

# Integration points for FastAPI route handler
async def process_pre_input_hooks(request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
    """Process pre-input hooks before making API call"""
    body = await hook_system.execute_pre_input_hooks(request, body)
    # Run settings-based UserPromptSubmit hooks
    body = await hook_system.run_user_prompt_submit_hooks(request, body)
    return body

async def process_post_output_hooks(response: Union[Response, StreamingResponse]) -> Union[Response, StreamingResponse]:
    """Process post-output hooks after receiving API response"""
    return await hook_system.execute_post_output_hooks(response)

async def process_pre_tool_use_hooks(request: Request, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """Process pre-tool-use hooks before tool execution"""
    return await hook_system.execute_pre_tool_use_hooks(request, tool_name, tool_args)

async def process_stop_hooks(request: Request, conversation_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process stop hooks when conversation ends"""
    return await hook_system.execute_stop_hooks(request, conversation_data)

# Settings-based helpers (exported)
async def settings_pre_tool_use(request: Request, tool_name: str, tool_args: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    return await hook_system.run_pre_tool_use_hooks(request, tool_name, tool_args)

async def settings_post_tool_use(request: Request, tool_name: str, tool_args: Dict[str, Any], tool_response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return await hook_system.run_post_tool_use_hooks(request, tool_name, tool_args, tool_response)

async def settings_notification(request: Request, message: str) -> None:
    return await hook_system.run_notification_hooks(request, message)

async def settings_stop(request: Request, conversation_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return await hook_system.run_stop_hooks(request, conversation_data)

async def settings_pre_compact(request: Request, trigger: str, custom_instructions: str = "") -> None:
    return await hook_system.run_pre_compact_hooks(request, trigger, custom_instructions)

async def settings_session_start(request: Optional[Request], source: str = "startup") -> None:
    return await hook_system.run_session_start_hooks(request, source)

async def settings_session_end(request: Optional[Request], reason: str = "exit") -> None:
    return await hook_system.run_session_end_hooks(request, reason)

# Example hook implementation (for reference)
class ExampleHook(Hook):
    """Example hook implementation"""
    
    async def pre_input(self, request: Request, body: Dict[str, Any]) -> Dict[str, Any]:
        # Example: Add a custom header to the body
        if 'messages' in body:
            body['messages'][0]['content'] = f"[Processed by {self.name}] {body['messages'][0]['content']}"
        return body
    
    async def post_output(self, response: Union[Response, StreamingResponse]) -> Union[Response, StreamingResponse]:
        # Example: Add a custom header to the response
        if isinstance(response, Response):
            response.headers['X-Processed-By'] = self.name
        return response
