#!/usr/bin/env python3
"""
Performance Monitoring Validation Script

This script validates the TaskExecutionEngine performance monitoring system by:
1. Running comprehensive performance tests
2. Establishing performance baselines
3. Validating sub-200ms coordination overhead claims
4. Testing under various load conditions
5. Generating CI/CD friendly performance reports

Usage:
    python test_performance_monitoring.py [--establish-baseline] [--validate] [--load-test] [--export-ci]
"""

import argparse
import asyncio
import json
import logging
import statistics
import sys
import time
from pathlib import Path
from typing import Dict

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from codex_plus import Task, TaskResult, list_available_agents
from codex_plus.performance_monitor import (
    get_performance_monitor,
    MetricType
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PerformanceValidator:
    """Comprehensive performance validation system."""

    def __init__(self):
        self.performance_monitor = get_performance_monitor()
        self.results = {}
        
    async def run_basic_coordination_test(self) -> Dict[str, any]:
        """Test basic coordination overhead with simple tasks."""
        logger.info("Running basic coordination overhead test...")
        
        # Get available agents
        agents_info = list_available_agents()
        if not agents_info.get("success"):
            return {"error": "No agents available for testing"}
            
        agents = [agent["id"] for agent in agents_info["agents"][:3]]  # Test with first 3 agents
        coordination_times = []
        
        # Test 50 simple tasks to establish baseline
        test_tasks = [
            "Simple echo test",
            "Check agent capabilities",
            "Validate agent configuration", 
            "Test task execution pipeline",
            "Measure response time"
        ]
        
        for i in range(50):
            agent_id = agents[i % len(agents)]
            task_prompt = test_tasks[i % len(test_tasks)] + f" (iteration {i+1})"
            
            # Measure coordination overhead
            start_time = time.time()
            
            try:
                result = Task(agent_id, task_prompt, f"Performance test task {i+1}")
                end_time = time.time()

                if not result.success:
                    logger.warning(f"Task {i+1} returned unsuccessful status")

                coordination_time_ms = (end_time - start_time) * 1000
                coordination_times.append(coordination_time_ms)
                
                # Record detailed timing
                self.performance_monitor.record_coordination_overhead(
                    start_time,
                    end_time,
                    agent_id,
                    f"perf_test_{i+1}",
                    {
                        "test_type": "basic_coordination",
                        "iteration": i + 1,
                        "agent_type": agent_id,
                        "task_length": len(task_prompt)
                    }
                )
                
                logger.debug(f"Task {i+1}: {coordination_time_ms:.2f}ms coordination time")
                
            except Exception as e:
                logger.error(f"Task {i+1} failed: {e}")
                coordination_times.append(float('inf'))  # Mark as failed
        
        # Filter out failed tasks
        valid_times = [t for t in coordination_times if t != float('inf')]
        
        if not valid_times:
            return {"error": "All coordination tests failed"}
            
        # Calculate statistics
        stats = {
            "total_tasks": 50,
            "successful_tasks": len(valid_times),
            "failed_tasks": 50 - len(valid_times),
            "avg_coordination_time_ms": statistics.mean(valid_times),
            "min_coordination_time_ms": min(valid_times),
            "max_coordination_time_ms": max(valid_times),
            "p95_coordination_time_ms": sorted(valid_times)[int(len(valid_times) * 0.95)] if len(valid_times) > 20 else statistics.mean(valid_times),
            "p99_coordination_time_ms": sorted(valid_times)[int(len(valid_times) * 0.99)] if len(valid_times) > 50 else sorted(valid_times)[int(len(valid_times) * 0.95)],
            "std_dev_ms": statistics.stdev(valid_times) if len(valid_times) > 1 else 0.0,
            "meets_200ms_requirement": statistics.mean(valid_times) < 200.0,
            "consistency_score": 100.0 - min(100.0, (statistics.stdev(valid_times) if len(valid_times) > 1 else 0.0) / statistics.mean(valid_times) * 100)
        }
        
        logger.info("Basic coordination test completed:")
        logger.info(f"  Average coordination time: {stats['avg_coordination_time_ms']:.2f}ms")
        logger.info(f"  P95 coordination time: {stats['p95_coordination_time_ms']:.2f}ms")
        logger.info(f"  Meets 200ms requirement: {stats['meets_200ms_requirement']}")
        logger.info(f"  Consistency score: {stats['consistency_score']:.1f}%")
        
        return stats
    
    async def run_parallel_coordination_test(self) -> Dict[str, any]:
        """Test coordination overhead with parallel task execution."""
        logger.info("Running parallel coordination overhead test...")
        
        agents_info = list_available_agents()
        if not agents_info.get("success"):
            return {"error": "No agents available for parallel testing"}
            
        agents = [agent["id"] for agent in agents_info["agents"][:5]]  # Use up to 5 agents
        
        # Test various parallel loads
        parallel_loads = [2, 3, 5, 8, 10]
        parallel_results = {}
        
        for load in parallel_loads:
            logger.info(f"Testing parallel load: {load} concurrent tasks")
            parallel_times = []
            
            # Run 10 iterations of parallel tasks
            for iteration in range(10):
                start_time = time.time()
                
                # Create concurrent tasks
                tasks = []
                for i in range(load):
                    agent_id = agents[i % len(agents)]
                    task_prompt = f"Parallel test task {iteration+1}.{i+1}"
                    
                    # Use asyncio to simulate parallel coordination
                    task_future = asyncio.create_task(
                        self._async_task_wrapper(agent_id, task_prompt, f"parallel_test_{iteration}_{i}")
                    )
                    tasks.append(task_future)
                
                # Wait for all tasks to complete
                try:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    end_time = time.time()
                    
                    parallel_coordination_time_ms = (end_time - start_time) * 1000
                    parallel_times.append(parallel_coordination_time_ms)
                    
                    # Record parallel coordination metric
                    self.performance_monitor.record_metric(
                        MetricType.PARALLEL_COORDINATION,
                        parallel_coordination_time_ms,
                        "ms",
                        context={
                            "parallel_load": load,
                            "iteration": iteration + 1,
                            "successful_tasks": len([r for r in results if not isinstance(r, Exception)])
                        }
                    )
                    
                    logger.debug(f"Parallel load {load}, iteration {iteration+1}: {parallel_coordination_time_ms:.2f}ms")
                    
                except Exception as e:
                    logger.error(f"Parallel test iteration {iteration+1} with load {load} failed: {e}")
                    parallel_times.append(float('inf'))
            
            # Calculate stats for this load level
            valid_times = [t for t in parallel_times if t != float('inf')]
            if valid_times:
                parallel_results[f"load_{load}"] = {
                    "avg_time_ms": statistics.mean(valid_times),
                    "p95_time_ms": sorted(valid_times)[int(len(valid_times) * 0.95)] if len(valid_times) > 2 else statistics.mean(valid_times),
                    "successful_iterations": len(valid_times),
                    "per_task_overhead_ms": statistics.mean(valid_times) / load,
                    "efficiency_score": max(0, 100 - (statistics.mean(valid_times) / load / 200 * 100))  # Efficiency relative to 200ms per task
                }
        
        logger.info("Parallel coordination test completed")
        for load, stats in parallel_results.items():
            logger.info(f"  Load {load}: {stats['avg_time_ms']:.2f}ms avg, {stats['per_task_overhead_ms']:.2f}ms per task")
        
        return parallel_results
    
    async def run_stress_test(self, duration_minutes: int = 5) -> Dict[str, any]:
        """Run sustained stress test to validate performance under load."""
        logger.info(f"Running {duration_minutes}-minute stress test...")
        
        agents_info = list_available_agents()
        if not agents_info.get("success"):
            return {"error": "No agents available for stress testing"}
            
        agents = [agent["id"] for agent in agents_info["agents"]]
        
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        
        task_count = 0
        coordination_times = []
        error_count = 0
        
        # Sustained task execution
        while time.time() < end_time:
            try:
                agent_id = agents[task_count % len(agents)]
                task_prompt = f"Stress test task {task_count + 1}: sustained load validation"
                
                task_start = time.time()
                result = Task(agent_id, task_prompt, f"Stress test task {task_count + 1}")
                task_end = time.time()

                if not result.success:
                    logger.warning(f"Stress test task {task_count + 1} returned unsuccessful status")

                coordination_time_ms = (task_end - task_start) * 1000
                coordination_times.append(coordination_time_ms)
                
                # Record stress test metric
                self.performance_monitor.record_metric(
                    MetricType.COORDINATION_OVERHEAD,
                    coordination_time_ms,
                    "ms",
                    agent_id,
                    f"stress_test_{task_count + 1}",
                    {
                        "test_type": "stress_test",
                        "elapsed_minutes": (time.time() - start_time) / 60,
                        "task_sequence": task_count + 1
                    }
                )
                
                task_count += 1
                
                # Brief pause to avoid overwhelming the system
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Stress test task {task_count + 1} failed: {e}")
                error_count += 1
                task_count += 1
        
        # Calculate stress test statistics
        if coordination_times:
            stress_stats = {
                "duration_minutes": duration_minutes,
                "total_tasks": task_count,
                "successful_tasks": len(coordination_times),
                "failed_tasks": error_count,
                "success_rate": len(coordination_times) / task_count * 100,
                "avg_coordination_time_ms": statistics.mean(coordination_times),
                "p95_coordination_time_ms": sorted(coordination_times)[int(len(coordination_times) * 0.95)] if len(coordination_times) > 20 else statistics.mean(coordination_times),
                "p99_coordination_time_ms": sorted(coordination_times)[int(len(coordination_times) * 0.99)] if len(coordination_times) > 100 else sorted(coordination_times)[int(len(coordination_times) * 0.95)],
                "max_coordination_time_ms": max(coordination_times),
                "min_coordination_time_ms": min(coordination_times),
                "throughput_tasks_per_minute": len(coordination_times) / duration_minutes,
                "performance_degradation": max(0, statistics.mean(coordination_times) - 100) / 100 * 100,  # Degradation from 100ms baseline
                "meets_sustained_200ms_requirement": statistics.mean(coordination_times) < 200.0
            }
            
            logger.info("Stress test completed:")
            logger.info(f"  Tasks executed: {stress_stats['total_tasks']}")
            logger.info(f"  Success rate: {stress_stats['success_rate']:.1f}%")
            logger.info(f"  Average coordination time: {stress_stats['avg_coordination_time_ms']:.2f}ms")
            logger.info(f"  Throughput: {stress_stats['throughput_tasks_per_minute']:.1f} tasks/min")
            logger.info(f"  Meets sustained 200ms requirement: {stress_stats['meets_sustained_200ms_requirement']}")
            
            return stress_stats
        else:
            return {"error": "No successful tasks in stress test"}
    
    async def _async_task_wrapper(self, agent_id: str, task_prompt: str, task_id: str) -> TaskResult:
        """Async wrapper for Task execution."""
        # Since Task() is synchronous, run it in a thread pool
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, Task, agent_id, task_prompt, f"Async task: {task_id}")
    
    def establish_baseline(self) -> Dict[str, any]:
        """Establish performance baseline from collected metrics."""
        logger.info("Establishing performance baseline...")
        
        baseline = self.performance_monitor.establish_baseline(
            measurement_period_hours=1.0,  # Use last hour of metrics
            min_samples=50,               # Require at least 50 samples
            confidence_interval=0.95      # 95% confidence
        )
        
        if baseline:
            logger.info("Performance baseline established successfully:")
            logger.info(f"  Coordination overhead baseline: {baseline.coordination_overhead_ms:.2f}ms")
            logger.info(f"  Task execution baseline: {baseline.task_execution_ms:.2f}ms")
            logger.info(f"  Agent initialization baseline: {baseline.agent_init_ms:.2f}ms")
            logger.info(f"  Samples used: {baseline.samples_count}")
            
            return {
                "baseline_established": True,
                "coordination_overhead_ms": baseline.coordination_overhead_ms,
                "task_execution_ms": baseline.task_execution_ms,
                "agent_init_ms": baseline.agent_init_ms,
                "samples_count": baseline.samples_count,
                "confidence_interval": baseline.confidence_interval,
                "established_at": baseline.established_at.isoformat()
            }
        else:
            logger.warning("Failed to establish baseline - insufficient metrics")
            return {
                "baseline_established": False,
                "error": "Insufficient metrics for baseline establishment"
            }
    
    def validate_performance_requirements(self) -> Dict[str, any]:
        """Validate that system meets performance requirements."""
        logger.info("Validating performance requirements...")
        
        validation_results = self.performance_monitor.validate_performance_requirements()
        
        logger.info("Performance validation results:")
        logger.info(f"  Validation passed: {validation_results.get('validated', False)}")
        logger.info(f"  Average coordination overhead: {validation_results.get('avg_coordination_overhead_ms', 0):.2f}ms")
        logger.info(f"  Meets sub-200ms requirement: {validation_results.get('meets_sub_200ms_requirement', False)}")
        
        if validation_results.get('recommendations'):
            logger.info("  Recommendations:")
            for rec in validation_results['recommendations']:
                logger.info(f"    - {rec}")
        
        return validation_results
    
    def generate_comprehensive_report(self) -> Dict[str, any]:
        """Generate comprehensive performance report."""
        logger.info("Generating comprehensive performance report...")
        
        report = self.performance_monitor.generate_performance_report(include_trends=True)
        
        report_dict = report.to_dict()
        
        logger.info("Performance Report Summary:")
        logger.info(f"  Overall health: {report.overall_health.value}")
        logger.info(f"  Average coordination overhead: {report.avg_coordination_overhead:.2f}ms")
        logger.info(f"  P95 coordination overhead: {report.p95_coordination_overhead:.2f}ms")
        logger.info(f"  Total tasks analyzed: {report.total_tasks_executed}")
        
        if report.recommendations:
            logger.info("  Recommendations:")
            for rec in report.recommendations:
                logger.info(f"    - {rec}")
        
        return report_dict
    
    def export_ci_metrics(self, output_file: str = "performance_monitoring_validation_results.json") -> Dict[str, any]:
        """Export CI/CD friendly metrics."""
        logger.info(f"Exporting CI/CD metrics to {output_file}...")
        
        ci_metrics = self.performance_monitor.export_metrics_for_ci(output_file)
        
        logger.info("CI/CD Metrics Summary:")
        logger.info(f"  Performance validation: {ci_metrics.get('performance_validation', {}).get('validated', False)}")
        logger.info(f"  Coordination overhead: {ci_metrics.get('coordination_overhead_ms', 0):.2f}ms")
        logger.info(f"  Overall health: {ci_metrics.get('overall_health', 'unknown')}")
        logger.info(f"  Meets requirements: {ci_metrics.get('meets_requirements', False)}")
        
        return ci_metrics


async def main():
    """Main validation function."""
    parser = argparse.ArgumentParser(description="TaskExecutionEngine Performance Validation")
    parser.add_argument("--establish-baseline", action="store_true", help="Establish performance baseline")
    parser.add_argument("--validate", action="store_true", help="Validate performance requirements")
    parser.add_argument("--load-test", action="store_true", help="Run comprehensive load tests")
    parser.add_argument("--stress-minutes", type=int, default=5, help="Stress test duration in minutes")
    parser.add_argument("--export-ci", action="store_true", help="Export CI/CD metrics")
    parser.add_argument("--output-file", default="performance_monitoring_validation_results.json", help="Output file for CI metrics")
    parser.add_argument("--all", action="store_true", help="Run all tests and validations")
    
    args = parser.parse_args()
    
    if not any([args.establish_baseline, args.validate, args.load_test, args.export_ci, args.all]):
        parser.print_help()
        return
    
    validator = PerformanceValidator()
    results = {}
    
    try:
        # Run basic coordination test first to generate some metrics
        if args.load_test or args.all:
            logger.info("=" * 60)
            logger.info("BASIC COORDINATION TEST")
            logger.info("=" * 60)
            results["basic_coordination"] = await validator.run_basic_coordination_test()
            
            logger.info("=" * 60) 
            logger.info("PARALLEL COORDINATION TEST")
            logger.info("=" * 60)
            results["parallel_coordination"] = await validator.run_parallel_coordination_test()
            
            logger.info("=" * 60)
            logger.info("STRESS TEST")
            logger.info("=" * 60)
            results["stress_test"] = await validator.run_stress_test(args.stress_minutes)
        
        # Establish baseline
        if args.establish_baseline or args.all:
            logger.info("=" * 60)
            logger.info("BASELINE ESTABLISHMENT")
            logger.info("=" * 60)
            results["baseline"] = validator.establish_baseline()
        
        # Validate performance
        if args.validate or args.all:
            logger.info("=" * 60)
            logger.info("PERFORMANCE VALIDATION")
            logger.info("=" * 60)
            results["validation"] = validator.validate_performance_requirements()
        
        # Generate comprehensive report
        if args.all:
            logger.info("=" * 60)
            logger.info("COMPREHENSIVE REPORT")
            logger.info("=" * 60)
            results["comprehensive_report"] = validator.generate_comprehensive_report()
        
        # Export CI metrics
        if args.export_ci or args.all:
            logger.info("=" * 60)
            logger.info("CI/CD METRICS EXPORT")
            logger.info("=" * 60)
            results["ci_metrics"] = validator.export_ci_metrics(args.output_file)
        
        # Summary
        logger.info("=" * 60)
        logger.info("VALIDATION SUMMARY")
        logger.info("=" * 60)
        
        if "basic_coordination" in results:
            basic_stats = results["basic_coordination"]
            logger.info(f"Basic coordination test: {basic_stats.get('avg_coordination_time_ms', 0):.2f}ms average")
            logger.info(f"Meets 200ms requirement: {basic_stats.get('meets_200ms_requirement', False)}")
        
        if "validation" in results:
            validation = results["validation"]
            logger.info(f"Performance validation: {'PASSED' if validation.get('validated', False) else 'FAILED'}")
        
        if "ci_metrics" in results:
            ci_metrics = results["ci_metrics"]
            logger.info(f"CI/CD requirements: {'PASSED' if ci_metrics.get('meets_requirements', False) else 'FAILED'}")
        
        # Save comprehensive results
        results_file = "demo_performance_monitoring.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"Detailed results saved to: {results_file}")
        
        # Exit with appropriate code
        if "validation" in results and results["validation"].get("validated", False):
            logger.info("✅ Performance validation PASSED")
            return 0
        elif "validation" in results:
            logger.error("❌ Performance validation FAILED")
            return 1
        else:
            logger.info("✅ Performance tests completed")
            return 0
    
    except Exception as e:
        logger.error(f"Performance validation failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)