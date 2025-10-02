#!/usr/bin/env python3
"""
TaskExecutionEngine API Test Suite

Comprehensive tests for the Task API with performance monitoring integration.
Validates sub-200ms coordination overhead claims and baseline establishment.
"""

import sys
import time
import unittest
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from codex_plus import Task, TaskResult, list_available_agents
from codex_plus.performance_monitor import get_performance_monitor
from codex_plus.performance_config import get_performance_config, set_development_mode


class TestTaskAPIPerformance(unittest.TestCase):
    """Test Task API performance and monitoring integration."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        # Configure for development testing
        set_development_mode()
        cls.performance_monitor = get_performance_monitor()
    
    def test_task_api_availability(self):
        """Test that Task API is available and functional."""
        agents_info = list_available_agents()
        self.assertTrue(agents_info.get("success", False), "Should have available agents")
        self.assertIsInstance(agents_info.get("agents", []), list, "Should return list of agents")
        self.assertGreater(len(agents_info["agents"]), 0, "Should have at least one agent")
    
    def test_single_task_coordination_overhead(self):
        """Test coordination overhead for single task execution."""
        agents_info = list_available_agents()
        self.assertTrue(agents_info.get("success", False))
        
        agent_id = agents_info["agents"][0]["id"]
        task_prompt = "Test coordination overhead measurement"
        
        # Measure coordination overhead
        start_time = time.time()
        result = Task(agent_id, task_prompt, "Single task test")
        end_time = time.time()
        
        coordination_time_ms = (end_time - start_time) * 1000
        
        # Validate result structure
        self.assertIsInstance(result, TaskResult)
        self.assertIsInstance(result.success, bool)
        
        # Validate coordination overhead
        self.assertLess(coordination_time_ms, 200.0, 
                       f"Coordination overhead {coordination_time_ms:.2f}ms exceeds 200ms threshold")
        
        print(f"Single task coordination overhead: {coordination_time_ms:.2f}ms")
    
    def test_multiple_task_coordination_consistency(self):
        """Test coordination overhead consistency across multiple tasks."""
        agents_info = list_available_agents()
        self.assertTrue(agents_info.get("success", False))
        
        agents = [agent["id"] for agent in agents_info["agents"][:3]]
        coordination_times = []
        
        # Execute 20 tasks to test consistency
        for i in range(20):
            agent_id = agents[i % len(agents)]
            task_prompt = f"Consistency test task {i+1}"
            
            start_time = time.time()
            result = Task(agent_id, task_prompt, f"Consistency test {i+1}")
            end_time = time.time()

            self.assertTrue(result.success, 'Task execution should succeed')

            coordination_time_ms = (end_time - start_time) * 1000
            coordination_times.append(coordination_time_ms)
            
            # Each individual task should meet requirement
            self.assertLess(coordination_time_ms, 200.0, 
                           f"Task {i+1} coordination overhead {coordination_time_ms:.2f}ms exceeds threshold")
        
        # Validate consistency
        avg_time = sum(coordination_times) / len(coordination_times)
        max_time = max(coordination_times)
        min_time = min(coordination_times)
        
        self.assertLess(avg_time, 200.0, f"Average coordination time {avg_time:.2f}ms exceeds 200ms")
        self.assertLess(max_time, 250.0, f"Maximum coordination time {max_time:.2f}ms exceeds 250ms")
        
        print(f"Multiple task coordination - Avg: {avg_time:.2f}ms, Min: {min_time:.2f}ms, Max: {max_time:.2f}ms")
    
    def test_performance_baseline_establishment(self):
        """Test automated performance baseline establishment."""
        # Generate sufficient metrics for baseline
        agents_info = list_available_agents()
        self.assertTrue(agents_info.get("success", False))
        
        agent_id = agents_info["agents"][0]["id"]
        
        # Execute multiple tasks to generate metrics
        for i in range(15):
            task_prompt = f"Baseline generation task {i+1}"
            result = Task(agent_id, task_prompt, f"Baseline test {i+1}")
            self.assertIsInstance(result, TaskResult)
        
        # Establish baseline
        baseline = self.performance_monitor.establish_baseline(
            measurement_period_hours=1.0,
            min_samples=10,  # Lower requirement for testing
            confidence_interval=0.95
        )
        
        self.assertIsNotNone(baseline, "Should establish performance baseline")
        self.assertLess(baseline.coordination_overhead_ms, 200.0, 
                       f"Baseline coordination overhead {baseline.coordination_overhead_ms:.2f}ms exceeds 200ms")
        
        print(f"Established baseline coordination overhead: {baseline.coordination_overhead_ms:.2f}ms")
    
    def test_performance_validation(self):
        """Test performance requirement validation."""
        # Execute tasks to generate recent metrics
        agents_info = list_available_agents()
        self.assertTrue(agents_info.get("success", False))
        
        agent_id = agents_info["agents"][0]["id"]
        
        for i in range(10):
            Task(agent_id, f"Validation test task {i+1}", f"Validation test {i+1}")
        
        # Validate performance
        validation_results = self.performance_monitor.validate_performance_requirements()
        
        self.assertIsInstance(validation_results, dict, "Should return validation results")
        
        # Check if validation passed (may not pass if no baseline or insufficient metrics)
        if validation_results.get("validated"):
            avg_overhead = validation_results.get("avg_coordination_overhead_ms", 0)
            self.assertLess(avg_overhead, 200.0, 
                           f"Validated average coordination overhead {avg_overhead:.2f}ms exceeds 200ms")
            
            meets_requirement = validation_results.get("meets_sub_200ms_requirement", False)
            self.assertTrue(meets_requirement, "Should meet sub-200ms requirement")
            
            print(f"Performance validation PASSED - Average overhead: {avg_overhead:.2f}ms")
        else:
            print("Performance validation skipped - insufficient metrics or no baseline")
    
    def test_task_result_structure(self):
        """Test TaskResult structure and metadata."""
        agents_info = list_available_agents()
        self.assertTrue(agents_info.get("success", False))
        
        agent_id = agents_info["agents"][0]["id"]
        result = Task(agent_id, "Test result structure", "Structure test")
        
        # Validate TaskResult structure
        self.assertIsInstance(result, TaskResult)
        self.assertIsInstance(result.success, bool)
        self.assertIsInstance(result.metadata, dict)
        
        # Check for performance metadata
        if result.metadata:
            self.assertIn("agent_id", result.metadata)
            self.assertIn("task_id", result.metadata)
            self.assertIn("execution_time", result.metadata)
            
            execution_time = result.metadata.get("execution_time", 0)
            self.assertIsInstance(execution_time, (int, float))
            self.assertGreaterEqual(execution_time, 0)
    
    def test_error_handling_performance(self):
        """Test performance monitoring during error conditions."""
        # Test with invalid agent
        start_time = time.time()
        result = Task("invalid-agent", "Test error handling", "Error test")
        end_time = time.time()
        
        coordination_time_ms = (end_time - start_time) * 1000
        
        # Should handle errors quickly
        self.assertLess(coordination_time_ms, 100.0, 
                       f"Error handling took {coordination_time_ms:.2f}ms, should be faster")
        self.assertFalse(result.success, "Should indicate failure for invalid agent")
        self.assertIsNotNone(result.error, "Should provide error message")
        
        # Test with empty prompt
        start_time = time.time()
        result = Task("test-agent", "", "Empty prompt test")
        end_time = time.time()
        
        coordination_time_ms = (end_time - start_time) * 1000
        self.assertLess(coordination_time_ms, 100.0, "Empty prompt handling should be fast")


class TestPerformanceMonitoringIntegration(unittest.TestCase):
    """Test performance monitoring integration with TaskExecutionEngine."""
    
    def setUp(self):
        """Set up test environment."""
        self.performance_monitor = get_performance_monitor()
    
    def test_performance_monitor_availability(self):
        """Test that performance monitor is available and configured."""
        self.assertIsNotNone(self.performance_monitor)
        
        # Test configuration
        config = get_performance_config()
        self.assertIsNotNone(config)
        self.assertTrue(config.monitoring.enabled)
    
    def test_metric_collection(self):
        """Test that metrics are being collected."""
        initial_count = len(self.performance_monitor.metrics)
        
        # Execute a task to generate metrics
        agents_info = list_available_agents()
        if agents_info.get("success"):
            agent_id = agents_info["agents"][0]["id"]
            Task(agent_id, "Metric collection test", "Metric test")
            
            # Check that metrics were collected
            final_count = len(self.performance_monitor.metrics)
            self.assertGreater(final_count, initial_count, "Should collect performance metrics")
    
    def test_ci_export_functionality(self):
        """Test CI/CD metrics export functionality."""
        # Execute some tasks to generate metrics
        agents_info = list_available_agents()
        if agents_info.get("success"):
            agent_id = agents_info["agents"][0]["id"]
            for i in range(5):
                Task(agent_id, f"CI export test {i+1}", f"CI test {i+1}")
        
        # Export metrics
        ci_metrics = self.performance_monitor.export_metrics_for_ci("test_ci_metrics.json")
        
        self.assertIsInstance(ci_metrics, dict)
        self.assertIn("coordination_overhead_ms", ci_metrics)
        self.assertIn("overall_health", ci_metrics)
        self.assertIn("meets_requirements", ci_metrics)
        
        # Validate CI-friendly structure
        coordination_overhead = ci_metrics.get("coordination_overhead_ms", float('inf'))
        if coordination_overhead != float('inf'):
            self.assertLess(coordination_overhead, 200.0, 
                           f"CI metrics show coordination overhead {coordination_overhead:.2f}ms exceeds 200ms")


def run_performance_validation_suite():
    """Run comprehensive performance validation test suite."""
    print("🚀 TaskExecutionEngine Performance Validation Test Suite")
    print("=" * 60)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestTaskAPIPerformance))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceMonitoringIntegration))
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 60)
    print("🎯 Performance Validation Summary")
    print("=" * 60)
    
    if result.wasSuccessful():
        print("✅ All performance validation tests PASSED")
        print(f"   Tests run: {result.testsRun}")
        print(f"   Failures: {len(result.failures)}")
        print(f"   Errors: {len(result.errors)}")
        print("\n🎉 TaskExecutionEngine meets sub-200ms coordination overhead requirement!")
        return 0
    else:
        print("❌ Performance validation tests FAILED")
        print(f"   Tests run: {result.testsRun}")
        print(f"   Failures: {len(result.failures)}")
        print(f"   Errors: {len(result.errors)}")
        
        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"  - {test}: {traceback}")
        
        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"  - {test}: {traceback}")
        
        return 1


if __name__ == "__main__":
    exit_code = run_performance_validation_suite()
    sys.exit(exit_code)