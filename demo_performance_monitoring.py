#!/usr/bin/env python3
"""
Performance Monitoring Demo Script

A demonstration of the TaskExecutionEngine performance monitoring capabilities
with automated baseline establishment and sub-200ms coordination overhead validation.

This script showcases:
- Real-time performance metric collection
- Automated baseline establishment
- Performance validation against requirements
- CI/CD friendly reporting

Usage:
    python demo_performance_monitoring.py
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from codex_plus import Task, list_available_agents
from codex_plus.performance_monitor import (
    get_performance_monitor, 
    MetricType,
    performance_timer
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def demo_basic_performance_monitoring():
    """Demonstrate basic performance monitoring capabilities."""
    logger.info("🚀 TaskExecutionEngine Performance Monitoring Demo")
    logger.info("=" * 60)
    
    # Initialize performance monitor
    performance_monitor = get_performance_monitor()
    
    # Get available agents
    logger.info("📋 Getting available agents...")
    agents_info = list_available_agents()
    
    if not agents_info.get("success"):
        logger.error("❌ No agents available for demo")
        return {"error": "No agents available"}
    
    agents = [agent["id"] for agent in agents_info["agents"][:3]]  # Use first 3 agents
    logger.info(f"✅ Found {len(agents)} agents: {', '.join(agents)}")
    
    # Demo 1: Basic coordination overhead measurement
    logger.info("\n📊 Demo 1: Basic Coordination Overhead Measurement")
    logger.info("-" * 50)
    
    coordination_times = []
    demo_tasks = [
        "Analyze code structure",
        "Review function implementation", 
        "Check for potential issues",
        "Validate coding standards",
        "Generate summary report"
    ]
    
    for i, task_description in enumerate(demo_tasks):
        agent_id = agents[i % len(agents)]
        logger.info(f"Task {i+1}: {task_description} (Agent: {agent_id})")
        
        # Measure coordination with performance timer
        start_time = time.time()
        
        with performance_timer(
            MetricType.COORDINATION_OVERHEAD,
            agent_id,
            f"demo_task_{i+1}",
            {"demo_phase": "basic_measurement", "task_description": task_description}
        ):
            try:
                result = Task(agent_id, task_description, f"Demo task {i+1}")
                success = result.success
            except Exception as e:
                logger.error(f"  ❌ Task failed: {e}")
                success = False
        
        end_time = time.time()
        coordination_time_ms = (end_time - start_time) * 1000
        coordination_times.append(coordination_time_ms)
        
        status_icon = "✅" if success else "❌"
        logger.info(f"  {status_icon} Coordination time: {coordination_time_ms:.2f}ms")
    
    # Calculate basic statistics
    avg_coordination = sum(coordination_times) / len(coordination_times)
    max_coordination = max(coordination_times)
    min_coordination = min(coordination_times)
    meets_requirement = avg_coordination < 200.0
    
    logger.info("\n📈 Basic Performance Results:")
    logger.info(f"  Average coordination time: {avg_coordination:.2f}ms")
    logger.info(f"  Min coordination time: {min_coordination:.2f}ms")
    logger.info(f"  Max coordination time: {max_coordination:.2f}ms")
    logger.info(f"  Meets sub-200ms requirement: {'✅' if meets_requirement else '❌'} {meets_requirement}")
    
    # Demo 2: Establish performance baseline
    logger.info("\n🎯 Demo 2: Performance Baseline Establishment")
    logger.info("-" * 50)
    
    # Generate more metrics for baseline
    logger.info("Collecting additional metrics for baseline establishment...")
    for i in range(15):  # Add 15 more tasks for better baseline
        agent_id = agents[i % len(agents)]
        task_description = f"Baseline collection task {i+1}"
        
        with performance_timer(
            MetricType.COORDINATION_OVERHEAD,
            agent_id,
            f"baseline_task_{i+1}",
            {"demo_phase": "baseline_collection"}
        ):
            try:
                result = Task(agent_id, task_description, f"Baseline task {i+1}")
            except Exception as e:
                logger.debug(f"Baseline task {i+1} failed: {e}")
        
        # Brief delay to avoid overwhelming system
        await asyncio.sleep(0.1)
    
    # Establish baseline
    logger.info("Establishing performance baseline...")
    baseline = performance_monitor.establish_baseline(
        measurement_period_hours=1.0,
        min_samples=10,  # Lower requirement for demo
        confidence_interval=0.95
    )
    
    if baseline:
        logger.info("✅ Performance baseline established successfully:")
        logger.info(f"  Coordination overhead baseline: {baseline.coordination_overhead_ms:.2f}ms")
        logger.info(f"  Task execution baseline: {baseline.task_execution_ms:.2f}ms")
        logger.info(f"  Agent initialization baseline: {baseline.agent_init_ms:.2f}ms")
        logger.info(f"  Sample count: {baseline.samples_count}")
        logger.info(f"  Confidence interval: {baseline.confidence_interval * 100}%")
    else:
        logger.warning("⚠️ Could not establish baseline (insufficient metrics)")
    
    # Demo 3: Performance validation
    logger.info("\n✅ Demo 3: Performance Requirements Validation")
    logger.info("-" * 50)
    
    validation_results = performance_monitor.validate_performance_requirements()
    
    if validation_results.get("validated"):
        logger.info("🎉 Performance validation PASSED!")
        logger.info(f"  Average coordination overhead: {validation_results.get('avg_coordination_overhead_ms', 0):.2f}ms")
        logger.info(f"  P95 coordination overhead: {validation_results.get('p95_coordination_overhead_ms', 0):.2f}ms")
        logger.info(f"  Meets sub-200ms requirement: ✅ {validation_results.get('meets_sub_200ms_requirement', False)}")
        logger.info(f"  Samples analyzed: {validation_results.get('samples_analyzed', 0)}")
    else:
        logger.warning("⚠️ Performance validation issues detected:")
        for recommendation in validation_results.get("recommendations", []):
            logger.warning(f"  - {recommendation}")
    
    # Demo 4: Performance report generation
    logger.info("\n📋 Demo 4: Comprehensive Performance Report")
    logger.info("-" * 50)
    
    report = performance_monitor.generate_performance_report(include_trends=True)
    
    logger.info(f"Performance Report (ID: {report.report_id}):")
    logger.info(f"  Overall health: {report.overall_health.value.upper()}")
    logger.info(f"  Average coordination overhead: {report.avg_coordination_overhead:.2f}ms")
    logger.info(f"  P95 coordination overhead: {report.p95_coordination_overhead:.2f}ms")
    logger.info(f"  P99 coordination overhead: {report.p99_coordination_overhead:.2f}ms")
    logger.info(f"  Total tasks analyzed: {report.total_tasks_executed}")
    logger.info(f"  Successful tasks: {report.successful_tasks}")
    
    if report.recommendations:
        logger.info("  Recommendations:")
        for rec in report.recommendations:
            logger.info(f"    - {rec}")
    
    # Demo 5: CI/CD metrics export
    logger.info("\n🔄 Demo 5: CI/CD Metrics Export")
    logger.info("-" * 50)
    
    ci_output_file = "demo_ci_metrics.json"
    ci_metrics = performance_monitor.export_metrics_for_ci(ci_output_file)
    
    logger.info(f"CI/CD metrics exported to: {ci_output_file}")
    logger.info(f"  Performance validation: {'PASSED' if ci_metrics.get('performance_validation', {}).get('validated', False) else 'FAILED'}")
    logger.info(f"  Overall health: {ci_metrics.get('overall_health', 'unknown').upper()}")
    logger.info(f"  Meets requirements: {'✅' if ci_metrics.get('meets_requirements', False) else '❌'} {ci_metrics.get('meets_requirements', False)}")
    logger.info(f"  Baseline established: {'✅' if ci_metrics.get('baseline_established', False) else '❌'} {ci_metrics.get('baseline_established', False)}")
    logger.info(f"  Total metrics collected: {ci_metrics.get('total_metrics_collected', 0)}")
    
    # Demo 6: Real-time monitoring capabilities
    logger.info("\n⏱️ Demo 6: Real-time Performance Monitoring")
    logger.info("-" * 50)
    
    logger.info("Demonstrating real-time monitoring with concurrent tasks...")
    
    # Create some concurrent tasks to show parallel monitoring
    concurrent_tasks = []
    for i in range(3):
        agent_id = agents[i % len(agents)]
        task_prompt = f"Real-time monitoring demo task {i+1}"
        
        # Create async task wrapper
        task = asyncio.create_task(
            demo_async_task_wrapper(agent_id, task_prompt, f"realtime_demo_{i+1}")
        )
        concurrent_tasks.append(task)
    
    # Execute tasks concurrently and measure
    start_time = time.time()
    results = await asyncio.gather(*concurrent_tasks, return_exceptions=True)
    end_time = time.time()
    
    parallel_time_ms = (end_time - start_time) * 1000
    successful_tasks = len([r for r in results if not isinstance(r, Exception)])
    
    logger.info("  Parallel execution completed:")
    logger.info(f"    Total time: {parallel_time_ms:.2f}ms")
    logger.info(f"    Successful tasks: {successful_tasks}/3")
    logger.info(f"    Average per-task overhead: {parallel_time_ms / 3:.2f}ms")
    
    # Record parallel coordination metric
    performance_monitor.record_metric(
        MetricType.PARALLEL_COORDINATION,
        parallel_time_ms,
        "ms",
        context={
            "demo_phase": "real_time_monitoring",
            "task_count": 3,
            "successful_tasks": successful_tasks
        }
    )
    
    # Final summary
    logger.info("\n🎯 Demo Summary")
    logger.info("=" * 60)
    
    # Get final statistics
    final_validation = performance_monitor.validate_performance_requirements()
    final_metrics = performance_monitor.export_metrics_for_ci()
    
    summary_data = {
        "demo_completed": True,
        "performance_monitoring_active": True,
        "baseline_established": baseline is not None,
        "coordination_overhead_ms": final_validation.get("avg_coordination_overhead_ms", 0),
        "meets_sub_200ms_requirement": final_validation.get("meets_sub_200ms_requirement", False),
        "overall_health": final_metrics.get("overall_health", "unknown"),
        "total_metrics_collected": final_metrics.get("total_metrics_collected", 0),
        "validation_passed": final_validation.get("validated", False),
        "demo_timestamp": time.time()
    }
    
    logger.info("📊 Final Performance Status:")
    logger.info(f"  Baseline established: {'✅' if summary_data['baseline_established'] else '❌'}")
    logger.info(f"  Sub-200ms requirement: {'✅' if summary_data['meets_sub_200ms_requirement'] else '❌'}")
    logger.info(f"  Overall health: {summary_data['overall_health'].upper()}")
    logger.info(f"  Validation status: {'PASSED ✅' if summary_data['validation_passed'] else 'FAILED ❌'}")
    logger.info(f"  Metrics collected: {summary_data['total_metrics_collected']}")
    
    # Save demo results
    with open("demo_performance_monitoring.json", "w") as f:
        json.dump(summary_data, f, indent=2)
    
    logger.info("\n🔚 Performance monitoring demo completed successfully!")
    logger.info("Demo results saved to: demo_performance_monitoring.json")
    
    return summary_data


async def demo_async_task_wrapper(agent_id: str, task_prompt: str, task_id: str) -> Dict:
    """Async wrapper for Task execution in demo."""
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, Task, agent_id, task_prompt, f"Async demo: {task_id}")
        return {"success": result.success, "task_id": task_id, "agent_id": agent_id}
    except Exception as e:
        return {"success": False, "error": str(e), "task_id": task_id, "agent_id": agent_id}


def main():
    """Main demo function."""
    try:
        # Run the async demo
        summary = asyncio.run(demo_basic_performance_monitoring())
        
        # Exit with appropriate code based on validation results
        if summary.get("validation_passed", False):
            logger.info("✅ Demo completed successfully with validation PASSED")
            return 0
        else:
            logger.warning("⚠️ Demo completed but validation had issues")
            return 1
            
    except Exception as e:
        logger.error(f"❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    exit_code = main()
    sys.exit(exit_code)
