import os
import re
import subprocess
import yaml
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any, Union
from fastapi import FastAPI, Request, HTTPException
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SlashCommandModule(ABC):
    """Abstract base class for slash command modules"""
    
    @abstractmethod
    def handle_command(self, command_name: str, arguments: str, request: Request) -> str:
        """Handle a slash command and return the result"""
        pass

    @abstractmethod
    def get_command_names(self) -> List[str]:
        """Return list of command names this module handles"""
        pass

    @abstractmethod
    def get_command_metadata(self, command_name: str) -> Dict[str, Any]:
        """Return metadata for a specific command"""
        pass


class ClaudeCommandModule(SlashCommandModule):
    """Implementation of slash command module for Claude commands"""
    
    def __init__(self, commands_dirs: List[str] = None):
        if commands_dirs is None:
            # Default: search .codexplus/commands/ first, then .claude/commands/
            commands_dirs = [".codexplus/commands", ".claude/commands"]
        self.commands_dirs = commands_dirs
        self.commands = self._discover_commands()
    
    def _discover_commands(self) -> Dict[str, str]:
        """Discover all available commands in the commands directories"""
        commands = {}
        loaded_names = set()  # Track loaded command names for precedence
        
        for commands_dir in self.commands_dirs:
            if not os.path.exists(commands_dir):
                continue
                
            for filename in os.listdir(commands_dir):
                if filename.endswith(".md"):
                    command_name = filename[:-3]  # Remove .md extension
                    
                    # Skip if command already loaded from higher precedence directory
                    if command_name in loaded_names:
                        continue
                        
                    commands[command_name] = os.path.join(commands_dir, filename)
                    loaded_names.add(command_name)
        
        return commands
    
    def get_command_names(self) -> List[str]:
        """Return list of available command names"""
        return list(self.commands.keys())
    
    def get_command_metadata(self, command_name: str) -> Dict[str, Any]:
        """Extract metadata from command file's YAML frontmatter"""
        if command_name not in self.commands:
            return {}
        
        file_path = self.commands[command_name]
        return parse_command_file(file_path, "")[0]  # Return just the metadata
    
    def handle_command(self, command_name: str, arguments: str, request: Request) -> str:
        """Handle execution of a Claude command"""
        if command_name not in self.commands:
            raise HTTPException(status_code=404, detail=f"Command '{command_name}' not found")
        
        file_path = self.commands[command_name]
        metadata, content = parse_command_file(file_path, arguments)
        
        # Substitute arguments in the content
        processed_content = substitute_arguments(content, arguments)
        
        # Resolve file references
        processed_content = resolve_file_references(processed_content)
        
        # Execute bash command if it starts with !
        if processed_content.strip().startswith("!"):
            bash_command = processed_content.strip()[1:].strip()  # Remove the ! and any leading/trailing whitespace
            # Note: This would need to be made async in a real implementation
            # For now, return the bash command for synchronous processing
            return f"BASH_COMMAND: {bash_command}"
        
        return processed_content


def discover_claude_commands() -> Dict[str, str]:
    """
    Discover Claude commands from both .claude/commands/ and .codexplus/commands/
    directories, with .codexplus/ taking precedence.
    
    Returns:
        Dict mapping command names to file paths
    """
    # Discover from current working directory and home directory
    import os
    from pathlib import Path
    
    commands = {}
    loaded_names = set()
    
    # Search order: project .codexplus first, then project .claude, then personal ~/.claude
    search_paths = []
    
    # Project directories (current working directory)
    cwd = Path(os.getcwd())
    search_paths.append(cwd / ".codexplus" / "commands")
    search_paths.append(cwd / ".claude" / "commands")
    
    # Personal directory (home directory)
    home = Path(os.environ.get("HOME", "~")).expanduser()
    search_paths.append(home / ".claude" / "commands")
    
    for commands_dir in search_paths:
        if not commands_dir.exists():
            continue
            
        for filename in commands_dir.iterdir():
            if filename.suffix == ".md":
                command_name = filename.stem
                
                # Skip if command already loaded from higher precedence directory
                if command_name in loaded_names:
                    continue
                    
                commands[command_name] = str(filename)
                loaded_names.add(command_name)
    
    return commands


def parse_command_file(file_path: str, args: str = "") -> Tuple[Dict[str, Any], str]:
    """
    Parse a command file, extracting YAML frontmatter and processing content.
    
    Args:
        file_path: Path to the command file
        args: Arguments to substitute in the content
        
    Returns:
        Tuple of (frontmatter_dict, processed_content)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return {}, ""
    
    # Check if file has YAML frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                metadata = yaml.safe_load(parts[1])
                if metadata is None:
                    metadata = {}
            except yaml.YAMLError:
                metadata = {}
            body = parts[2].strip()
        else:
            metadata = {}
            body = content.strip()
    else:
        metadata = {}
        body = content.strip()
    
    return metadata, body


def substitute_arguments(content: str, args: str) -> str:
    """
    Substitute argument variables in command content.
    Supports: $ARGUMENTS, $1, $2, $3, etc.
    
    Args:
        content: Command content with variables
        args: Space-separated arguments
        
    Returns:
        Content with variables substituted
    """
    # Split arguments into a list
    args_list = args.strip().split()
    
    # Replace $ARGUMENTS with all arguments joined by spaces
    result = content.replace("$ARGUMENTS", args.strip())
    
    # Replace $1, $2, etc. with corresponding arguments
    for i, arg in enumerate(args_list, 1):
        result = result.replace(f"${i}", arg)
    
    return result


def resolve_file_references(content: str) -> str:
    """
    Resolve @filename references in command content.
    
    Args:
        content: Command content potentially containing @filename references
        
    Returns:
        Content with file references resolved
    """
    def replace_file_reference(match):
        filename = match.group(1)
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return f"[File '{filename}' not found]"
    
    # Pattern to match @filename references
    pattern = r"@([^\s]+)"
    return re.sub(pattern, replace_file_reference, content)


async def execute_bash_command(command: str, frontmatter: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute bash command with security constraints and timeout.
    
    Args:
        command: Bash command to execute (may include ! prefix)
        frontmatter: Command metadata including timeout settings
        
    Returns:
        Dict with execution results
    """
    # Strip ! prefix if present
    if command.startswith("!"):
        command = command[1:].strip()
    
    # Get timeout from frontmatter
    timeout = frontmatter.get("timeout", 30)
    
    # Basic security validation - prevent obvious injection attempts
    # Allow most common bash characters including quotes, pipes, etc.
    dangerous_patterns = [
        r'\$\(', r'`', r'\|\s*nc\b', r'\|\s*netcat\b', 
        r'\|\s*telnet\b', r'\|\s*ssh\b', r'rm\s+-rf\s+/', r'>\s*/dev/'
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, command):
            return {
                "type": "bash_execution",
                "success": False,
                "error": "Command contains potentially dangerous patterns",
                "output": ""
            }
    
    try:
        # Execute the command with timeout
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=timeout,
            cwd=os.getcwd()
        )
        
        return {
            "type": "bash_execution",
            "success": result.returncode == 0,
            "stdout": result.stdout or "",
            "stderr": result.stderr or "",
            "returncode": result.returncode
        }
        
    except subprocess.TimeoutExpired:
        return {
            "type": "bash_execution",
            "success": False,
            "error": "Command execution timed out",
            "output": ""
        }
    except Exception as e:
        return {
            "type": "bash_execution",
            "success": False,
            "error": f"Command execution failed: {str(e)}",
            "output": ""
        }


async def handle_slash_command(command: str, args: str, original_body: bytes) -> Union[bytes, None]:
    """
    Main slash command handler. Processes slash commands and returns modified body
    or None to forward to ChatGPT unchanged.
    
    Args:
        command: The slash command name (without /)
        args: Command arguments
        original_body: Original request body
        
    Returns:
        Modified request body or None to forward unchanged
    """
    try:
        command_module = ClaudeCommandModule()
        
        # Create a mock request for compatibility
        class MockRequest:
            def __init__(self):
                self.query_params = {}
        
        request = MockRequest()
        result = command_module.handle_command(command, args, request)
        
        # Return the result as bytes (simplified implementation)
        return result.encode('utf-8')
        
    except HTTPException:
        # Command not found or error - forward to ChatGPT
        return None
    except Exception as e:
        logger.error(f"Error handling slash command: {e}")
        return None


async def extract_user_message(body: bytes) -> Optional[str]:
    """
    Extract user message from request body.
    
    Args:
        body: Raw request body bytes
        
    Returns:
        Extracted user message or None
    """
    try:
        # Simple implementation - decode and extract from JSON-like structure
        content = body.decode('utf-8')
        # This is a simplified extraction - in real implementation would parse JSON
        return content
    except:
        return None


async def forward_to_chatgpt(body: bytes) -> Any:
    """
    Forward request to ChatGPT API unchanged.
    
    Args:
        body: Request body to forward
        
    Returns:
        ChatGPT API response
    """
    # In a real implementation, this would make an API call to ChatGPT
    # For now, we'll just return a placeholder response
    return f"Forwarded to ChatGPT: {body.decode('utf-8', errors='ignore')}"