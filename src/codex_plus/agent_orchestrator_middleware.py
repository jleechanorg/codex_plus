"""
Agent Orchestrator Middleware - Routes tasks to specialized subagents

This middleware integrates with the existing FastAPI proxy architecture to:
1. Detect agent invocation patterns in requests
2. Load agent configurations from .claude/agents/
3. Route tasks to appropriate subagents based on capabilities
4. Execute agents in parallel when needed
5. Aggregate and format results for conversation injection

Follows Anthropic Claude Code CLI subagent patterns:
https://docs.claude.com/en/docs/claude-code/sub-agents

🚨 SECURITY NOTE 🚨
This middleware operates independently of the proxy forwarding logic.
It only processes agent commands and does not interfere with curl_cffi
or upstream URL forwarding to ChatGPT backend.
"""

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import Request

from .subagents import AgentCapability, AgentContext, AgentStatus, SubAgent
from .subagents.config_loader import AgentConfiguration, AgentConfigurationLoader

logger = logging.getLogger(__name__)


class AgentExecutionContext:
    """Context for agent execution with shared resources."""

    def __init__(self, request: Request, working_directory: Optional[str] = None):
        self.request = request
        self.working_directory = working_directory
        self.start_time = time.time()
        self.shared_state: Dict[str, Any] = {}
        self.execution_log: List[str] = []

    def log(self, message: str):
        """Add message to execution log."""
        timestamp = time.time() - self.start_time
        self.execution_log.append(f"[{timestamp:.2f}s] {message}")
        logger.info(f"Agent execution: {message}")


class AgentResult:
    """Result from agent execution."""

    def __init__(self, agent_id: str, task: str, success: bool,
                 output: str = "", error: str = "", duration: float = 0.0):
        self.agent_id = agent_id
        self.task = task
        self.success = success
        self.output = output
        self.error = error
        self.duration = duration
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            'agent_id': self.agent_id,
            'task': self.task,
            'success': self.success,
            'output': self.output,
            'error': self.error,
            'duration': self.duration,
            'timestamp': self.timestamp
        }


class AgentOrchestrationMiddleware:
    """Middleware for orchestrating subagent execution."""

    def __init__(self, max_concurrent_agents: int = 3, agent_timeout: int = 30):
        """Initialize agent orchestrator.

        Args:
            max_concurrent_agents: Maximum number of agents to run concurrently
            agent_timeout: Timeout for individual agent execution in seconds
        """
        self.config_loader = AgentConfigurationLoader()
        self.max_concurrent_agents = max_concurrent_agents
        self.agent_timeout = agent_timeout
        self.active_executions: Dict[str, asyncio.Task] = {}
        self._subagent_cache: Dict[str, Dict[str, Any]] = {}

        # Load agent configurations
        self._load_agents()

        # Agent invocation patterns
        self.agent_patterns = {
            'explicit': re.compile(r'/agent\s+([\w-]+)\s+(.*)', re.IGNORECASE),
            'multi_agent': re.compile(r'/agents\s+run\s+([\w,-]+)\s+(.*)', re.IGNORECASE),
            'auto_delegate': re.compile(r'/delegate\s+(.*)', re.IGNORECASE),
        }

        # Task pattern matching for auto-delegation
        self.task_patterns = {
            'code_review': re.compile(r'review|analyze|check|security|quality', re.IGNORECASE),
            'testing': re.compile(r'test|spec|coverage|validation', re.IGNORECASE),
            'documentation': re.compile(r'document|doc|readme|api|guide', re.IGNORECASE),
            'debugging': re.compile(r'debug|error|fix|issue|problem|trace', re.IGNORECASE),
            'refactoring': re.compile(r'refactor|clean|optimize|improve|restructure', re.IGNORECASE),
        }

    def _load_agents(self):
        """Load agent configurations from directories."""
        try:
            self.agents = self.config_loader.load_all()
            logger.info(f"Loaded {len(self.agents)} agent configurations")

            # Create default agents if none exist
            if not self.agents:
                logger.info("No agents found, creating default configurations")
                self.config_loader.create_default_agents()
                self.agents = self.config_loader.load_all()

            # Synchronize runtime subagent cache with latest configurations
            self._build_subagent_cache()

        except Exception as e:
            logger.error(f"Failed to load agent configurations: {e}")
            self.agents = {}
            self._subagent_cache = {}

    def _build_subagent_cache(self) -> None:
        """Create runtime subagent blueprints for loaded configurations."""
        cache: Dict[str, Dict[str, Any]] = {}

        for agent_id, config in self.agents.items():
            try:
                cache[agent_id] = self._create_subagent_blueprint(agent_id, config)
            except Exception as exc:
                logger.error(
                    "Failed to build subagent '%s': %s",
                    agent_id,
                    exc,
                )

        self._subagent_cache = cache

    def _create_subagent_blueprint(self, agent_id: str, config: AgentConfiguration) -> Dict[str, Any]:
        """Create a blueprint dict used to instantiate SubAgents on demand."""

        capability_set: Set[AgentCapability] = set()
        for raw_capability in config.capabilities:
            enum_key = raw_capability.replace("-", "_").upper()
            try:
                capability_set.add(AgentCapability[enum_key])
            except KeyError:
                logger.debug(
                    "Ignoring unknown agent capability '%s' for agent '%s'",
                    raw_capability,
                    agent_id,
                )

        return {
            "agent_id": agent_id,
            "name": config.name,
            "description": config.description,
            "capabilities": capability_set,
            "config": {
                "tools": config.tools,
                "model": config.model,
                "temperature": config.temperature,
                "max_tokens": config.max_tokens,
                "tags": config.tags,
            },
        }

    def detect_agent_invocation(self, request_body: Dict) -> Optional[Dict[str, Any]]:
        """Detect agent invocation patterns in request body.

        Returns:
            Dictionary with invocation details or None if no agent commands found
        """
        # Extract text from different request formats
        text_content = self._extract_text_content(request_body)
        if not text_content:
            return None

        # Check for explicit agent commands
        for pattern_name, pattern in self.agent_patterns.items():
            match = pattern.search(text_content)
            if match:
                if pattern_name == 'explicit':
                    agent_id = match.group(1)
                    task = match.group(2).strip()
                    return {
                        'type': 'explicit',
                        'agent_id': agent_id,
                        'task': task,
                        'original_text': text_content
                    }
                elif pattern_name == 'multi_agent':
                    agent_ids = [aid.strip() for aid in match.group(1).split(',')]
                    task = match.group(2).strip()
                    return {
                        'type': 'multi_agent',
                        'agent_ids': agent_ids,
                        'task': task,
                        'original_text': text_content
                    }
                elif pattern_name == 'auto_delegate':
                    task = match.group(1).strip()
                    return {
                        'type': 'auto_delegate',
                        'task': task,
                        'original_text': text_content
                    }

        return None

    def _extract_text_content(self, request_body: Dict) -> Optional[str]:
        """Extract text content from request body."""
        # Handle Codex CLI format with input field
        if "input" in request_body:
            for item in request_body["input"]:
                if isinstance(item, dict) and item.get("type") == "message":
                    content_list = item.get("content", [])
                    for content_item in content_list:
                        if isinstance(content_item, dict) and content_item.get("type") == "input_text":
                            return content_item.get("text", "")

        # Handle standard format with messages field
        elif "messages" in request_body:
            for message in request_body["messages"]:
                if message.get("role") == "user" and "content" in message:
                    return message["content"]

        return None

    def select_agents_for_task(self, task: str, available_agents: Optional[List[str]] = None) -> List[str]:
        """Select appropriate agents for a task based on capabilities.

        Args:
            task: Task description
            available_agents: Optional list to restrict agent selection

        Returns:
            List of agent IDs best suited for the task
        """
        if available_agents:
            # Use specified agents if provided
            return [aid for aid in available_agents if aid in self.agents]

        # Auto-select based on task patterns
        selected_agents = []

        for task_type, pattern in self.task_patterns.items():
            if pattern.search(task):
                # Find agents with matching capabilities
                for agent_id, config in self.agents.items():
                    capability_match = any(
                        task_type in str(cap).lower()
                        for cap in config.capabilities
                    )
                    tag_match = any(
                        task_type in tag.lower()
                        for tag in config.tags
                    )

                    if capability_match or tag_match:
                        selected_agents.append(agent_id)

        # Remove duplicates while preserving order
        return list(dict.fromkeys(selected_agents))

    def validate_agent_access(self, agent_id: str, context: AgentExecutionContext) -> List[str]:
        """Validate agent access permissions.

        Returns:
            List of validation issues, empty if all checks pass
        """
        issues = []

        if agent_id not in self.agents:
            issues.append(f"Agent '{agent_id}' not found")
            return issues

        config = self.agents[agent_id]

        # Check working directory access
        if context.working_directory:
            wd_path = Path(context.working_directory).resolve()

            # Check forbidden paths
            for forbidden in config.forbidden_paths:
                forbidden_path = Path(forbidden).resolve()
                try:
                    wd_path.relative_to(forbidden_path)
                    issues.append(f"Access denied to forbidden path: {context.working_directory}")
                    break
                except ValueError:
                    continue  # Not under forbidden path

            # Check allowed paths (if specified)
            if config.allowed_paths:
                allowed = False
                for allowed_path in config.allowed_paths:
                    allowed_path_resolved = Path(allowed_path).resolve()
                    try:
                        wd_path.relative_to(allowed_path_resolved)
                        allowed = True
                        break
                    except ValueError:
                        continue

                if not allowed:
                    issues.append("Access denied: working directory not in allowed paths")

        return issues

    async def execute_agent(self, agent_id: str, task: str, context: AgentExecutionContext) -> AgentResult:
        """Execute a single agent with the given task.

        Args:
            agent_id: ID of the agent to execute
            task: Task description for the agent
            context: Execution context with shared state

        Returns:
            AgentResult with execution outcome
        """
        start_time = time.time()
        context.log(f"Starting execution of agent '{agent_id}' with task: {task}")

        try:
            # Validate agent access
            access_issues = self.validate_agent_access(agent_id, context)
            if access_issues:
                error_msg = "; ".join(access_issues)
                context.log(f"Agent '{agent_id}' access denied: {error_msg}")
                return AgentResult(
                    agent_id=agent_id,
                    task=task,
                    success=False,
                    error=f"Access denied: {error_msg}",
                    duration=time.time() - start_time
                )

            # Get agent configuration
            config = self.agents[agent_id]

            # Create agent execution payload
            agent_payload = self._create_agent_payload(config, task, context)

            # Execute agent with timeout
            try:
                result = await asyncio.wait_for(
                    self._execute_agent_request(agent_id, agent_payload, config, context),
                    timeout=self.agent_timeout
                )

                duration = time.time() - start_time
                context.log(f"Agent '{agent_id}' completed successfully in {duration:.2f}s")

                return AgentResult(
                    agent_id=agent_id,
                    task=task,
                    success=True,
                    output=result,
                    duration=duration
                )

            except asyncio.TimeoutError:
                error_msg = f"Agent execution timed out after {self.agent_timeout}s"
                context.log(f"Agent '{agent_id}' timed out")
                return AgentResult(
                    agent_id=agent_id,
                    task=task,
                    success=False,
                    error=error_msg,
                    duration=time.time() - start_time
                )

        except Exception as e:
            error_msg = f"Agent execution failed: {str(e)}"
            context.log(f"Agent '{agent_id}' failed: {error_msg}")
            return AgentResult(
                agent_id=agent_id,
                task=task,
                success=False,
                error=error_msg,
                duration=time.time() - start_time
            )

    def _create_agent_payload(self, config: AgentConfiguration, task: str, context: AgentExecutionContext) -> Dict:
        """Create request payload for agent execution."""
        # Build system prompt
        system_prompt = config.system_prompt or f"You are {config.name}. {config.description}"

        if config.instructions:
            system_prompt += f"\n\nInstructions:\n{config.instructions}"

        # Add context information
        if context.working_directory:
            system_prompt += f"\n\nWorking directory: {context.working_directory}"

        if context.shared_state:
            system_prompt += f"\n\nShared context: {json.dumps(context.shared_state, indent=2)}"

        # Create request payload
        payload = {
            "model": config.model,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": task
                }
            ]
        }

        # Add tool configuration if specified
        if config.tools:
            payload["tools"] = [{"type": "function", "function": {"name": tool}} for tool in config.tools]

        return payload

    async def _execute_agent_request(
        self,
        agent_id: str,
        payload: Dict[str, Any],
        config: AgentConfiguration,
        context: AgentExecutionContext,
    ) -> str:
        """Execute the agent request and return response."""

        task_content = payload["messages"][-1]["content"]

        blueprint = self._subagent_cache.get(agent_id)
        if not blueprint:
            blueprint = self._create_subagent_blueprint(agent_id, config)
            self._subagent_cache[agent_id] = blueprint

        subagent = SubAgent(
            agent_id=blueprint["agent_id"],
            name=blueprint["name"],
            description=blueprint["description"],
            capabilities=set(blueprint["capabilities"]),
            config=blueprint["config"],
        )

        agent_context = AgentContext(
            parent_context=dict(context.shared_state),
            allowed_paths=config.allowed_paths or ([context.working_directory] if context.working_directory else []),
            forbidden_paths=config.forbidden_paths,
            timeout=self.agent_timeout,
        )

        try:
            agent_result = await subagent.execute(task_content, agent_context)

            status_label = {
                AgentStatus.COMPLETED: "✅ Success",
                AgentStatus.TIMEOUT: "⏱️ Timeout",
                AgentStatus.FAILED: "❌ Failed",
                AgentStatus.CANCELLED: "⚠️ Cancelled",
            }.get(agent_result.status, agent_result.status.value.upper())

            output_lines = [f"# Agent Execution: {config.name}", ""]
            output_lines.append(f"**Status**: {status_label}")
            output_lines.append(f"**Duration**: {agent_result.execution_time:.2f}s")
            output_lines.append(f"**Task**: {task_content}")

            if config.allowed_paths:
                output_lines.append(
                    f"**Allowed Paths**: {', '.join(config.allowed_paths)}"
                )

            if config.tools:
                output_lines.append(
                    f"**Tools**: {', '.join(config.tools)}"
                )

            if agent_result.output:
                output_lines.append("\n**Output:**\n")
                output_lines.append(agent_result.output.strip())

            if agent_result.error:
                output_lines.append("\n**Error:**\n")
                output_lines.append(agent_result.error.strip())

            if agent_result.metadata:
                output_lines.append("\n**Metadata:**\n")
                output_lines.append(json.dumps(agent_result.metadata, indent=2))

            return "\n".join(output_lines)

        except Exception as exc:
            logger.error("Agent execution failed for %s: %s", config.name, exc)
            return (
                f"# Agent Execution Failed: {config.name}\n\n"
                f"**Error**: {exc}\n"
                f"**Task**: {task_content}"
            )

    async def execute_agents_parallel(self, agent_tasks: List[Tuple[str, str]],
                                    context: AgentExecutionContext) -> List[AgentResult]:
        """Execute multiple agents in parallel.

        Args:
            agent_tasks: List of (agent_id, task) tuples
            context: Execution context

        Returns:
            List of AgentResult objects
        """
        # Limit concurrent executions
        if len(agent_tasks) > self.max_concurrent_agents:
            context.log(f"Limiting concurrent agents to {self.max_concurrent_agents}")
            agent_tasks = agent_tasks[:self.max_concurrent_agents]

        context.log(f"Executing {len(agent_tasks)} agents in parallel")

        # Create execution tasks
        execution_tasks = []
        for agent_id, task in agent_tasks:
            execution_task = asyncio.create_task(
                self.execute_agent(agent_id, task, context),
                name=f"agent_{agent_id}"
            )
            execution_tasks.append(execution_task)

        # Wait for all agents to complete
        try:
            results = await asyncio.gather(*execution_tasks, return_exceptions=True)

            # Process results and handle exceptions
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    agent_id, task = agent_tasks[i]
                    error_result = AgentResult(
                        agent_id=agent_id,
                        task=task,
                        success=False,
                        error=f"Execution exception: {str(result)}",
                        duration=0.0
                    )
                    processed_results.append(error_result)
                else:
                    processed_results.append(result)

            context.log(f"Parallel execution completed: {len(processed_results)} agents")
            return processed_results

        except Exception as e:
            context.log(f"Parallel execution failed: {str(e)}")
            # Return error results for all agents
            return [
                AgentResult(
                    agent_id=agent_id,
                    task=task,
                    success=False,
                    error=f"Parallel execution failed: {str(e)}",
                    duration=0.0
                )
                for agent_id, task in agent_tasks
            ]

    def format_agent_results(self, results: List[AgentResult],
                           context: AgentExecutionContext) -> str:
        """Format agent results for conversation injection.

        Args:
            results: List of agent execution results
            context: Execution context with logs

        Returns:
            Formatted string for injection into conversation
        """
        if not results:
            return ""

        # Build formatted output
        output_parts = ["# Agent Execution Results\n"]

        # Add execution summary
        total_agents = len(results)
        successful_agents = sum(1 for r in results if r.success)
        total_duration = sum(r.duration for r in results)

        output_parts.append(f"**Summary**: {successful_agents}/{total_agents} agents completed successfully")
        output_parts.append(f"**Total Duration**: {total_duration:.2f}s")
        output_parts.append(f"**Execution Log**: {len(context.execution_log)} events\n")

        # Add individual results
        for result in results:
            output_parts.append(f"## Agent: {result.agent_id}")
            output_parts.append(f"**Task**: {result.task}")
            output_parts.append(f"**Status**: {'✅ Success' if result.success else '❌ Failed'}")
            output_parts.append(f"**Duration**: {result.duration:.2f}s")

            if result.success and result.output:
                output_parts.append(f"**Output**:\n{result.output}")
            elif result.error:
                output_parts.append(f"**Error**: {result.error}")

            output_parts.append("")  # Add spacing

        # Add execution log if there are failures
        if any(not r.success for r in results):
            output_parts.append("## Execution Log")
            output_parts.extend(context.execution_log)

        return "\n".join(output_parts)

    async def process_request(self, request: Request, path: str) -> Optional[Dict]:
        """Main middleware entry point for request processing.

        Args:
            request: FastAPI request object
            path: Request path

        Returns:
            Modified request body if agent commands were processed, None otherwise
        """
        # Only process /responses path for now
        if path != "/responses":
            return None

        # Check if body was already modified by hooks
        if hasattr(request.state, 'modified_body'):
            body = request.state.modified_body
        else:
            body = await request.body()

        if not body:
            return None

        try:
            # Parse request body
            request_data = json.loads(body)

            # Detect agent invocation
            invocation = self.detect_agent_invocation(request_data)
            if not invocation:
                return None

            logger.info(f"Detected agent invocation: {invocation['type']}")

            # Extract working directory from request headers or body
            working_directory = request.headers.get('x-working-directory')
            if not working_directory and body:
                # Look for <cwd> tags in request body
                cwd_match = re.search(r'<cwd>([^<]+)</cwd>', body.decode('utf-8', errors='ignore'))
                if cwd_match:
                    working_directory = cwd_match.group(1)

            # Create execution context
            context = AgentExecutionContext(request, working_directory)

            # Process based on invocation type
            if invocation['type'] == 'explicit':
                # Single agent execution
                agent_id = invocation['agent_id']
                task = invocation['task']

                result = await self.execute_agent(agent_id, task, context)
                results = [result]

            elif invocation['type'] == 'multi_agent':
                # Multiple agent execution
                agent_ids = invocation['agent_ids']
                task = invocation['task']

                agent_tasks = [(agent_id, task) for agent_id in agent_ids]
                results = await self.execute_agents_parallel(agent_tasks, context)

            elif invocation['type'] == 'auto_delegate':
                # Auto-delegation based on task analysis
                task = invocation['task']
                selected_agents = self.select_agents_for_task(task)

                if not selected_agents:
                    context.log("No suitable agents found for auto-delegation")
                    return None

                agent_tasks = [(agent_id, task) for agent_id in selected_agents]
                results = await self.execute_agents_parallel(agent_tasks, context)

            else:
                logger.warning(f"Unknown invocation type: {invocation['type']}")
                return None

            # Format results for injection
            formatted_results = self.format_agent_results(results, context)

            # Inject results into request
            return self._inject_agent_results(request_data, formatted_results, invocation)

        except json.JSONDecodeError:
            logger.debug("Request body not JSON, skipping agent processing")
            return None
        except Exception as e:
            logger.error(f"Agent orchestration failed: {e}")
            return None

    def _inject_agent_results(self, request_data: Dict, results: str,
                            invocation: Dict) -> Dict:
        """Inject agent results into request data.

        Args:
            request_data: Original request data
            results: Formatted agent results
            invocation: Original invocation details

        Returns:
            Modified request data with agent results injected
        """
        # Create injection message
        injection_content = f"""Agent execution completed. Here are the results:

{results}

Original request: {invocation['original_text']}

Please review the agent outputs and provide a summary or take further action as needed."""

        # Inject into appropriate request format
        if "messages" in request_data:
            # Standard format - add as system message
            request_data["messages"].insert(0, {
                "role": "system",
                "content": injection_content
            })
        elif "input" in request_data:
            # Codex format - modify input text
            for item in request_data["input"]:
                if isinstance(item, dict) and item.get("type") == "message":
                    content_list = item.get("content", [])
                    for content_item in content_list:
                        if isinstance(content_item, dict) and content_item.get("type") == "input_text":
                            original_text = content_item.get("text", "")
                            content_item["text"] = f"{injection_content}\n\n{original_text}"
                            break
                    break

        logger.info("Agent results injected into request")
        return request_data

    def get_agent_status(self) -> Dict[str, Any]:
        """Get current status of agent orchestrator.

        Returns:
            Dictionary with orchestrator status information
        """
        return {
            'loaded_agents': len(self.agents),
            'agent_list': list(self.agents.keys()),
            'active_executions': len(self.active_executions),
            'max_concurrent_agents': self.max_concurrent_agents,
            'agent_timeout': self.agent_timeout,
            'configuration_paths': [
                str(self.config_loader.agents_dir),
                str(self.config_loader.alt_agents_dir)
            ]
        }


# Factory function for creating middleware instance
def create_agent_orchestrator_middleware(**kwargs) -> AgentOrchestrationMiddleware:
    """Factory function to create agent orchestrator middleware instance.

    Args:
        **kwargs: Additional configuration options

    Returns:
        AgentOrchestrationMiddleware instance
    """
    return AgentOrchestrationMiddleware(**kwargs)
