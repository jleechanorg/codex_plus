"""
Task API - Claude Code Compatible Interface

Provides a Task() function that is 100% API compatible with Claude Code's Task tool
while leveraging the existing SubAgentManager infrastructure.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional

from .subagents import SubAgentManager, AgentContext, AgentResult, AgentStatus

# Import performance monitoring
try:
    from .performance_monitor import get_performance_monitor, MetricType
    PERFORMANCE_MONITORING_AVAILABLE = True
except ImportError:
    PERFORMANCE_MONITORING_AVAILABLE = False
    logging.warning("Performance monitoring not available in task_api")

logger = logging.getLogger(__name__)

# Global manager instance
_manager: Optional[SubAgentManager] = None


@dataclass
class TaskResult:
    """
    Result from Task execution - API compatible with Claude Code.
    
    This class provides the exact same interface as Claude Code's TaskResult
    while internally using our SubAgentManager system.
    """
    
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


def _get_manager() -> SubAgentManager:
    """Get or create the global SubAgentManager instance."""
    global _manager
    if _manager is None:
        _manager = SubAgentManager()
    return _manager


def _map_agent_result_to_task_result(result: AgentResult) -> TaskResult:
    """Convert AgentResult to TaskResult for API compatibility."""
    success = result.status == AgentStatus.COMPLETED
    
    metadata = {
        "agent_id": result.agent_id,
        "task_id": result.task_id,
        "status": result.status.value,
        "execution_time": result.execution_time,
        "iterations_used": result.iterations_used,
        **result.metadata
    }
    
    return TaskResult(
        success=success,
        output=result.output,
        error=result.error,
        metadata=metadata
    )


def Task(subagent_type: str, prompt: str, description: str = None) -> TaskResult:
    """
    Execute a task using specified subagent type.

    This function provides 100% API compatibility with Claude Code's Task tool
    while leveraging our existing SubAgentManager infrastructure.

    Args:
        subagent_type: Type of subagent to use (e.g., "code-reviewer", "test-runner")
        prompt: The task prompt to execute
        description: Optional description of the task

    Returns:
        TaskResult: Result of task execution

    Raises:
        ValueError: If subagent_type is invalid or prompt is empty
        RuntimeError: If task execution fails critically
    """
    api_start_time = time.time()

    # Validate parameters
    if not subagent_type or not isinstance(subagent_type, str):
        return TaskResult(
            success=False,
            error="subagent_type must be a non-empty string"
        )

    if not prompt or not isinstance(prompt, str):
        return TaskResult(
            success=False,
            error="prompt must be a non-empty string"
        )

    try:
        # Get manager and execute task
        manager = _get_manager()

        # Create execution context
        context = AgentContext()
        if description:
            context.parent_context["description"] = description

        # Record API coordination overhead if monitoring is available
        performance_monitor = None
        if PERFORMANCE_MONITORING_AVAILABLE:
            try:
                performance_monitor = get_performance_monitor()
                performance_monitor.record_coordination_overhead(
                    api_start_time,
                    time.time(),
                    subagent_type,
                    context.task_id,
                    {"api": "Task", "operation": "parameter_validation_and_setup"}
                )
            except Exception as e:
                logger.debug(f"Performance monitoring error: {e}")

        # Execute task synchronously (Claude Code API is synchronous)
        try:
            if performance_monitor:
                # Time the entire async execution
                async_execution_start = time.time()

            # Use asyncio.run to handle the async execution cleanly
            result = asyncio.run(
                manager.execute_task(subagent_type, prompt, context)
            )

            if performance_monitor:
                async_execution_end = time.time()
                performance_monitor.record_metric(
                    MetricType.COORDINATION_OVERHEAD,
                    (async_execution_end - async_execution_start) * 1000,
                    "ms",
                    subagent_type,
                    context.task_id,
                    {"api": "Task", "operation": "async_execution_wrapper"}
                )

        except Exception as e:
            logger.error(f"Task execution failed: {e}")

            # Record error recovery time if monitoring is available
            if performance_monitor:
                error_recovery_time = (time.time() - api_start_time) * 1000
                performance_monitor.record_metric(
                    MetricType.ERROR_RECOVERY_TIME,
                    error_recovery_time,
                    "ms",
                    subagent_type,
                    context.task_id,
                    {"error_type": type(e).__name__, "api": "Task"}
                )

            return TaskResult(
                success=False,
                error=f"Task execution failed: {str(e)}"
            )

        # Convert result to Claude Code compatible format
        task_result = _map_agent_result_to_task_result(result)

        # Record total API execution time
        if performance_monitor:
            total_api_time = (time.time() - api_start_time) * 1000
            performance_monitor.record_metric(
                MetricType.COORDINATION_OVERHEAD,
                total_api_time,
                "ms",
                subagent_type,
                context.task_id,
                {
                    "api": "Task",
                    "operation": "complete_task_execution",
                    "success": task_result.success,
                    "prompt_length": len(prompt)
                }
            )

        return task_result

    except Exception as e:
        logger.error(f"Critical error in Task function: {e}")

        # Record critical error if monitoring is available
        if PERFORMANCE_MONITORING_AVAILABLE:
            try:
                performance_monitor = get_performance_monitor()
                critical_error_time = (time.time() - api_start_time) * 1000
                performance_monitor.record_metric(
                    MetricType.ERROR_RECOVERY_TIME,
                    critical_error_time,
                    "ms",
                    subagent_type,
                    "unknown",
                    {"error_type": "critical_error", "api": "Task"}
                )
            except Exception:
                pass  # Don't let monitoring errors propagate

        return TaskResult(
            success=False,
            error=f"Critical error: {str(e)}"
        )


def list_available_agents() -> Dict[str, Any]:
    """
    List all available subagent types.

    Returns:
        Dict containing agent information
    """
    try:
        manager = _get_manager()
        agents = manager.list_agents()
        return {
            "success": True,
            "agents": agents
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def get_performance_statistics() -> Dict[str, Any]:
    """
    Get comprehensive performance statistics for the TaskExecutionEngine.

    Returns:
        Dict containing performance metrics and validation results
    """
    try:
        manager = _get_manager()

        # Get statistics from manager
        manager_stats = manager.get_performance_statistics()

        if not manager_stats:
            return {
                "performance_monitoring": False,
                "message": "Performance monitoring not available or not enabled"
            }

        # Add API-level statistics
        api_stats = {
            "api_level": "Task API",
            "manager_statistics": manager_stats,
            "performance_monitoring": True
        }

        # Add monitoring availability info
        if PERFORMANCE_MONITORING_AVAILABLE:
            try:
                performance_monitor = get_performance_monitor()
                validation_results = performance_monitor.validate_performance_requirements()
                api_stats["validation_results"] = validation_results
                api_stats["baseline_established"] = performance_monitor.baseline is not None
            except Exception as e:
                api_stats["monitoring_error"] = str(e)

        return api_stats

    except Exception as e:
        return {
            "performance_monitoring": False,
            "error": str(e)
        }


def establish_performance_baseline() -> Dict[str, Any]:
    """
    Establish performance baseline for the TaskExecutionEngine.

    This function collects metrics and establishes performance thresholds
    for coordination overhead, task execution times, and other key metrics.

    Returns:
        Dict containing baseline establishment results
    """
    try:
        manager = _get_manager()

        # Establish baseline through manager
        baseline_result = manager.establish_performance_baseline()

        if not baseline_result:
            return {
                "success": False,
                "message": "Performance monitoring not available or not enabled"
            }

        # Add API-level validation
        if baseline_result.get("success", False) and PERFORMANCE_MONITORING_AVAILABLE:
            try:
                performance_monitor = get_performance_monitor()
                validation_results = performance_monitor.validate_performance_requirements()

                baseline_result["validation_after_baseline"] = validation_results
                baseline_result["meets_200ms_requirement"] = validation_results.get("meets_sub_200ms_requirement", False)

            except Exception as e:
                baseline_result["validation_error"] = str(e)

        return baseline_result

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def export_performance_metrics(output_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Export performance metrics in CI/CD friendly format.

    Args:
        output_file: Optional file path to save metrics

    Returns:
        Dict containing exported metrics
    """
    if not PERFORMANCE_MONITORING_AVAILABLE:
        return {
            "success": False,
            "error": "Performance monitoring not available"
        }

    try:
        performance_monitor = get_performance_monitor()
        return performance_monitor.export_metrics_for_ci(output_file)

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# Export the main API
__all__ = [
    "Task",
    "TaskResult",
    "list_available_agents",
    "get_performance_statistics",
    "establish_performance_baseline",
    "export_performance_metrics"
]