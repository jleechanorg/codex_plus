"""
Performance Monitoring Module for TaskExecutionEngine

Provides comprehensive performance tracking, baseline establishment,
and automated validation for the TaskExecutionEngine system.
"""

import asyncio
import json
import logging
import statistics
import time
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class PerformanceLevel(Enum):
    """Performance level classifications."""
    EXCELLENT = "excellent"  # < 100ms
    GOOD = "good"           # 100-150ms
    ACCEPTABLE = "acceptable"  # 150-200ms
    POOR = "poor"           # 200-300ms
    CRITICAL = "critical"   # > 300ms


class MetricType(Enum):
    """Types of performance metrics."""
    COORDINATION_OVERHEAD = "coordination_overhead"
    TASK_EXECUTION_TIME = "task_execution_time"
    AGENT_INITIALIZATION = "agent_initialization"
    RESULT_PROCESSING = "result_processing"
    PARALLEL_COORDINATION = "parallel_coordination"
    MEMORY_USAGE = "memory_usage"
    ERROR_RECOVERY_TIME = "error_recovery_time"


@dataclass
class PerformanceMetric:
    """Individual performance measurement."""

    metric_type: MetricType
    timestamp: datetime
    value: float
    unit: str
    agent_id: Optional[str] = None
    task_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "metric_type": self.metric_type.value,
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "unit": self.unit,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "context": self.context
        }


@dataclass
class PerformanceBaseline:
    """Performance baseline measurements."""

    coordination_overhead_ms: float
    task_execution_ms: float
    agent_init_ms: float
    result_processing_ms: float
    parallel_overhead_ms: float
    memory_usage_mb: float

    # Statistical metrics
    samples_count: int
    measurement_period_hours: float
    confidence_interval: float

    established_at: datetime
    last_updated: datetime

    def is_within_threshold(self, metric_type: MetricType, value: float) -> Tuple[bool, PerformanceLevel]:
        """Check if a metric value is within acceptable thresholds."""
        if metric_type == MetricType.COORDINATION_OVERHEAD:
            baseline_value = self.coordination_overhead_ms
        elif metric_type == MetricType.TASK_EXECUTION_TIME:
            baseline_value = self.task_execution_ms
        elif metric_type == MetricType.AGENT_INITIALIZATION:
            baseline_value = self.agent_init_ms
        elif metric_type == MetricType.RESULT_PROCESSING:
            baseline_value = self.result_processing_ms
        elif metric_type == MetricType.PARALLEL_COORDINATION:
            baseline_value = self.parallel_overhead_ms
        elif metric_type == MetricType.MEMORY_USAGE:
            baseline_value = self.memory_usage_mb
        else:
            return True, PerformanceLevel.ACCEPTABLE

        # Calculate performance level based on deviation from baseline
        ratio = value / baseline_value if baseline_value > 0 else 1.0

        if ratio <= 1.2:  # Within 20% of baseline
            if value < 100:
                return True, PerformanceLevel.EXCELLENT
            elif value < 150:
                return True, PerformanceLevel.GOOD
            else:
                return True, PerformanceLevel.ACCEPTABLE
        elif ratio <= 1.5:  # Within 50% of baseline
            return False, PerformanceLevel.POOR
        else:
            return False, PerformanceLevel.CRITICAL

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "coordination_overhead_ms": self.coordination_overhead_ms,
            "task_execution_ms": self.task_execution_ms,
            "agent_init_ms": self.agent_init_ms,
            "result_processing_ms": self.result_processing_ms,
            "parallel_overhead_ms": self.parallel_overhead_ms,
            "memory_usage_mb": self.memory_usage_mb,
            "samples_count": self.samples_count,
            "measurement_period_hours": self.measurement_period_hours,
            "confidence_interval": self.confidence_interval,
            "established_at": self.established_at.isoformat(),
            "last_updated": self.last_updated.isoformat()
        }


@dataclass
class PerformanceReport:
    """Comprehensive performance analysis report."""

    report_id: str
    generated_at: datetime
    baseline: PerformanceBaseline
    recent_metrics: List[PerformanceMetric]

    # Analysis results
    avg_coordination_overhead: float
    p95_coordination_overhead: float
    p99_coordination_overhead: float

    total_tasks_executed: int
    successful_tasks: int
    failed_tasks: int
    timeout_tasks: int

    performance_trends: Dict[str, List[float]]
    threshold_violations: List[Dict[str, Any]]
    recommendations: List[str]

    overall_health: PerformanceLevel

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "baseline": self.baseline.to_dict(),
            "recent_metrics": [m.to_dict() for m in self.recent_metrics],
            "avg_coordination_overhead": self.avg_coordination_overhead,
            "p95_coordination_overhead": self.p95_coordination_overhead,
            "p99_coordination_overhead": self.p99_coordination_overhead,
            "total_tasks_executed": self.total_tasks_executed,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "timeout_tasks": self.timeout_tasks,
            "performance_trends": self.performance_trends,
            "threshold_violations": self.threshold_violations,
            "recommendations": self.recommendations,
            "overall_health": self.overall_health.value
        }


class PerformanceMonitor:
    """
    Comprehensive performance monitoring system for TaskExecutionEngine.

    Features:
    - Real-time metric collection
    - Baseline establishment and validation
    - Automated threshold checking
    - Historical trend analysis
    - Performance reporting
    - CI/CD integration support
    """

    def __init__(self, storage_dir: Optional[str] = None, max_metrics_memory: int = 10000):
        """
        Initialize performance monitor.

        Args:
            storage_dir: Directory for storing metrics and baselines
            max_metrics_memory: Maximum metrics to keep in memory
        """
        self.storage_dir = Path(storage_dir or ".codexplus/performance")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # In-memory metrics storage with size limit
        self.metrics: deque[PerformanceMetric] = deque(maxlen=max_metrics_memory)
        self.baseline: Optional[PerformanceBaseline] = None

        # Thread safety
        self.lock = threading.RLock()

        # Metric aggregation by type
        self.metric_aggregator: Dict[MetricType, List[float]] = defaultdict(list)

        # Async event loop for background tasks
        self.background_tasks: List[asyncio.Task] = []
        self.monitoring_enabled = True

        # Load existing baseline if available
        self._load_baseline()

        # Background monitoring will be started when needed
        self._background_task = None

    def record_metric(
        self,
        metric_type: MetricType,
        value: float,
        unit: str = "ms",
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> PerformanceMetric:
        """
        Record a performance metric.

        Args:
            metric_type: Type of metric
            value: Measured value
            unit: Unit of measurement
            agent_id: Optional agent identifier
            task_id: Optional task identifier
            context: Optional additional context

        Returns:
            PerformanceMetric: The recorded metric
        """
        if not self.monitoring_enabled:
            return

        # Start background monitoring if not already running
        self._start_background_monitoring()

        metric = PerformanceMetric(
            metric_type=metric_type,
            timestamp=datetime.now(),
            value=value,
            unit=unit,
            agent_id=agent_id,
            task_id=task_id,
            context=context or {}
        )

        with self.lock:
            self.metrics.append(metric)
            self.metric_aggregator[metric_type].append(value)

            # Check thresholds if baseline exists
            if self.baseline:
                self._check_threshold_violation(metric)

        # Log significant metrics
        if metric_type == MetricType.COORDINATION_OVERHEAD and value > 200:
            logger.warning(f"High coordination overhead: {value}ms for task {task_id}")

        return metric

    def record_coordination_overhead(
        self,
        start_time: float,
        end_time: float,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> PerformanceMetric:
        """
        Record coordination overhead measurement.

        Args:
            start_time: Start timestamp
            end_time: End timestamp
            agent_id: Agent identifier
            task_id: Task identifier
            context: Additional context

        Returns:
            PerformanceMetric: The recorded metric
        """
        overhead_ms = (end_time - start_time) * 1000
        return self.record_metric(
            MetricType.COORDINATION_OVERHEAD,
            overhead_ms,
            "ms",
            agent_id,
            task_id,
            context
        )

    def establish_baseline(
        self,
        measurement_period_hours: float = 1.0,
        min_samples: int = 100,
        confidence_interval: float = 0.95
    ) -> Optional[PerformanceBaseline]:
        """
        Establish performance baseline from collected metrics.

        Args:
            measurement_period_hours: Period over which to collect baseline metrics
            min_samples: Minimum number of samples required
            confidence_interval: Statistical confidence interval

        Returns:
            PerformanceBaseline: Established baseline or None if insufficient data
        """
        with self.lock:
            # Filter metrics within measurement period
            cutoff_time = datetime.now() - timedelta(hours=measurement_period_hours)
            recent_metrics = [m for m in self.metrics if m.timestamp >= cutoff_time]

            if len(recent_metrics) < min_samples:
                logger.warning(f"Insufficient metrics for baseline ({len(recent_metrics)} < {min_samples})")
                return None

            # Calculate baseline values by metric type
            metric_values = defaultdict(list)
            for metric in recent_metrics:
                metric_values[metric.metric_type].append(metric.value)

            # Calculate averages with fallbacks
            coordination_overhead = statistics.mean(
                metric_values.get(MetricType.COORDINATION_OVERHEAD, [50.0])
            )
            task_execution = statistics.mean(
                metric_values.get(MetricType.TASK_EXECUTION_TIME, [500.0])
            )
            agent_init = statistics.mean(
                metric_values.get(MetricType.AGENT_INITIALIZATION, [25.0])
            )
            result_processing = statistics.mean(
                metric_values.get(MetricType.RESULT_PROCESSING, [15.0])
            )
            parallel_overhead = statistics.mean(
                metric_values.get(MetricType.PARALLEL_COORDINATION, [75.0])
            )
            memory_usage = statistics.mean(
                metric_values.get(MetricType.MEMORY_USAGE, [256.0])
            )

            self.baseline = PerformanceBaseline(
                coordination_overhead_ms=coordination_overhead,
                task_execution_ms=task_execution,
                agent_init_ms=agent_init,
                result_processing_ms=result_processing,
                parallel_overhead_ms=parallel_overhead,
                memory_usage_mb=memory_usage,
                samples_count=len(recent_metrics),
                measurement_period_hours=measurement_period_hours,
                confidence_interval=confidence_interval,
                established_at=datetime.now(),
                last_updated=datetime.now()
            )

            self._save_baseline()

            logger.info(f"Established performance baseline with {len(recent_metrics)} samples")
            logger.info(f"Coordination overhead baseline: {coordination_overhead:.2f}ms")

            return self.baseline

    def validate_performance_requirements(self) -> Dict[str, Any]:
        """
        Validate system meets performance requirements.

        Returns:
            Dict containing validation results
        """
        with self.lock:
            if not self.baseline:
                return {
                    "validated": False,
                    "error": "No baseline established",
                    "recommendations": ["Run establish_baseline() first"]
                }

            # Get recent coordination overhead metrics
            recent_overhead = [
                m.value for m in self.metrics
                if m.metric_type == MetricType.COORDINATION_OVERHEAD
                and m.timestamp >= datetime.now() - timedelta(minutes=30)
            ]

            if not recent_overhead:
                return {
                    "validated": False,
                    "error": "No recent coordination overhead metrics",
                    "recommendations": ["Execute tasks to generate metrics"]
                }

            avg_overhead = statistics.mean(recent_overhead)
            p95_overhead = sorted(recent_overhead)[int(len(recent_overhead) * 0.95)] if len(recent_overhead) > 20 else avg_overhead

            # Validation criteria
            sub_200ms_requirement = avg_overhead < 200.0
            p95_under_250ms = p95_overhead < 250.0
            consistency_check = statistics.stdev(recent_overhead) < 50.0 if len(recent_overhead) > 1 else True

            validation_passed = sub_200ms_requirement and p95_under_250ms and consistency_check

            recommendations = []
            if not sub_200ms_requirement:
                recommendations.append(f"Average coordination overhead ({avg_overhead:.1f}ms) exceeds 200ms threshold")
            if not p95_under_250ms:
                recommendations.append(f"95th percentile coordination overhead ({p95_overhead:.1f}ms) exceeds 250ms")
            if not consistency_check:
                recommendations.append("High variance in coordination overhead indicates instability")

            return {
                "validated": validation_passed,
                "avg_coordination_overhead_ms": avg_overhead,
                "p95_coordination_overhead_ms": p95_overhead,
                "samples_analyzed": len(recent_overhead),
                "baseline_overhead_ms": self.baseline.coordination_overhead_ms,
                "meets_sub_200ms_requirement": sub_200ms_requirement,
                "meets_consistency_requirement": consistency_check,
                "recommendations": recommendations,
                "baseline_established_at": self.baseline.established_at.isoformat(),
                "validation_timestamp": datetime.now().isoformat()
            }

    def generate_performance_report(self, include_trends: bool = True) -> PerformanceReport:
        """
        Generate comprehensive performance report.

        Args:
            include_trends: Include trend analysis

        Returns:
            PerformanceReport: Complete performance analysis
        """
        with self.lock:
            recent_metrics = list(self.metrics)[-1000:]  # Last 1000 metrics

            # Calculate coordination overhead statistics
            overhead_values = [
                m.value for m in recent_metrics
                if m.metric_type == MetricType.COORDINATION_OVERHEAD
            ]

            avg_overhead = statistics.mean(overhead_values) if overhead_values else 0.0
            p95_overhead = (
                sorted(overhead_values)[int(len(overhead_values) * 0.95)]
                if len(overhead_values) > 20 else avg_overhead
            )
            p99_overhead = (
                sorted(overhead_values)[int(len(overhead_values) * 0.99)]
                if len(overhead_values) > 100 else p95_overhead
            )

            # Task execution statistics
            task_metrics = [m for m in recent_metrics if m.task_id]
            total_tasks = len(set(m.task_id for m in task_metrics))

            # Determine overall health
            if avg_overhead < 100:
                overall_health = PerformanceLevel.EXCELLENT
            elif avg_overhead < 150:
                overall_health = PerformanceLevel.GOOD
            elif avg_overhead < 200:
                overall_health = PerformanceLevel.ACCEPTABLE
            elif avg_overhead < 300:
                overall_health = PerformanceLevel.POOR
            else:
                overall_health = PerformanceLevel.CRITICAL

            # Generate recommendations
            recommendations = []
            if avg_overhead > 200:
                recommendations.append("Consider optimizing coordination overhead")
            if p95_overhead > 250:
                recommendations.append("High tail latency detected - investigate bottlenecks")
            if len(overhead_values) < 50:
                recommendations.append("Collect more metrics for better analysis")

            # Performance trends (simplified)
            trends = {}
            if include_trends:
                for metric_type in MetricType:
                    type_values = [m.value for m in recent_metrics if m.metric_type == metric_type]
                    if type_values:
                        trends[metric_type.value] = type_values[-50:]  # Last 50 values

            return PerformanceReport(
                report_id=f"perf_report_{int(time.time())}",
                generated_at=datetime.now(),
                baseline=self.baseline or self._create_default_baseline(),
                recent_metrics=recent_metrics[-100:],  # Last 100 metrics
                avg_coordination_overhead=avg_overhead,
                p95_coordination_overhead=p95_overhead,
                p99_coordination_overhead=p99_overhead,
                total_tasks_executed=total_tasks,
                successful_tasks=total_tasks,  # Simplified
                failed_tasks=0,               # Simplified
                timeout_tasks=0,              # Simplified
                performance_trends=trends,
                threshold_violations=[],      # Simplified
                recommendations=recommendations,
                overall_health=overall_health
            )

    def export_metrics_for_ci(self, output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Export metrics in CI/CD friendly format.

        Args:
            output_file: Optional file path to write metrics

        Returns:
            Dict: CI/CD compatible metrics
        """
        validation_results = self.validate_performance_requirements()
        report = self.generate_performance_report(include_trends=False)

        ci_metrics = {
            "performance_validation": validation_results,
            "coordination_overhead_ms": report.avg_coordination_overhead,
            "p95_coordination_overhead_ms": report.p95_coordination_overhead,
            "overall_health": report.overall_health.value,
            "baseline_established": self.baseline is not None,
            "total_metrics_collected": len(self.metrics),
            "export_timestamp": datetime.now().isoformat(),
            "meets_requirements": validation_results.get("validated", False)
        }

        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(ci_metrics, f, indent=2)
            logger.info(f"Exported CI metrics to {output_path}")

        return ci_metrics

    async def _background_monitor(self):
        """Background monitoring task for maintenance and cleanup."""
        while self.monitoring_enabled:
            try:
                # Periodic baseline updates
                if self.baseline and len(self.metrics) >= 500:
                    if datetime.now() - self.baseline.last_updated > timedelta(hours=6):
                        self.establish_baseline()

                # Cleanup old metrics from aggregator
                with self.lock:
                    for metric_type in self.metric_aggregator:
                        # Keep only recent values (simplified cleanup)
                        if len(self.metric_aggregator[metric_type]) > 1000:
                            self.metric_aggregator[metric_type] = self.metric_aggregator[metric_type][-500:]

                await asyncio.sleep(300)  # Run every 5 minutes

            except Exception as e:
                logger.error(f"Background monitor error: {e}")
                await asyncio.sleep(60)  # Retry after 1 minute

    def _check_threshold_violation(self, metric: PerformanceMetric):
        """Check if metric violates performance thresholds."""
        if not self.baseline:
            return

        within_threshold, level = self.baseline.is_within_threshold(
            metric.metric_type, metric.value
        )

        if not within_threshold or level in [PerformanceLevel.POOR, PerformanceLevel.CRITICAL]:
            logger.warning(
                f"Performance threshold violation: {metric.metric_type.value} "
                f"= {metric.value}{metric.unit} (Level: {level.value})"
            )

    def _save_baseline(self):
        """Save baseline to persistent storage."""
        if not self.baseline:
            return

        baseline_file = self.storage_dir / "baseline.json"
        with open(baseline_file, 'w') as f:
            json.dump(self.baseline.to_dict(), f, indent=2)

    def _load_baseline(self):
        """Load baseline from persistent storage."""
        baseline_file = self.storage_dir / "baseline.json"
        if baseline_file.exists():
            try:
                with open(baseline_file) as f:
                    data = json.load(f)

                self.baseline = PerformanceBaseline(
                    coordination_overhead_ms=data["coordination_overhead_ms"],
                    task_execution_ms=data["task_execution_ms"],
                    agent_init_ms=data["agent_init_ms"],
                    result_processing_ms=data["result_processing_ms"],
                    parallel_overhead_ms=data["parallel_overhead_ms"],
                    memory_usage_mb=data["memory_usage_mb"],
                    samples_count=data["samples_count"],
                    measurement_period_hours=data["measurement_period_hours"],
                    confidence_interval=data["confidence_interval"],
                    established_at=datetime.fromisoformat(data["established_at"]),
                    last_updated=datetime.fromisoformat(data["last_updated"])
                )

                logger.info("Loaded existing performance baseline")

            except Exception as e:
                logger.error(f"Failed to load baseline: {e}")

    def _create_default_baseline(self) -> PerformanceBaseline:
        """Create a default baseline for reporting purposes."""
        return PerformanceBaseline(
            coordination_overhead_ms=100.0,
            task_execution_ms=500.0,
            agent_init_ms=25.0,
            result_processing_ms=15.0,
            parallel_overhead_ms=75.0,
            memory_usage_mb=256.0,
            samples_count=0,
            measurement_period_hours=0.0,
            confidence_interval=0.95,
            established_at=datetime.now(),
            last_updated=datetime.now()
        )

    def _start_background_monitoring(self):
        """Start background monitoring if not already running and event loop is available."""
        if self._background_task is None and self.monitoring_enabled:
            try:
                loop = asyncio.get_running_loop()
                self._background_task = loop.create_task(self._background_monitor())
                logger.debug("Started background monitoring task")
            except RuntimeError:
                # No event loop running, background monitoring will start later
                logger.debug("No event loop available, background monitoring deferred")

    def stop_monitoring(self):
        """Stop background monitoring."""
        self.monitoring_enabled = False
        if self._background_task:
            self._background_task.cancel()
            self._background_task = None
        for task in self.background_tasks:
            task.cancel()


# Global performance monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get or create the global performance monitor instance."""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


# Context manager for performance measurement
class performance_timer:
    """Context manager for measuring performance."""

    def __init__(
        self,
        metric_type: MetricType,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        self.metric_type = metric_type
        self.agent_id = agent_id
        self.task_id = task_id
        self.context = context or {}
        self.start_time = None
        self.monitor = get_performance_monitor()

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration_ms = (time.time() - self.start_time) * 1000
            self.monitor.record_metric(
                self.metric_type,
                duration_ms,
                "ms",
                self.agent_id,
                self.task_id,
                self.context
            )


# Export main classes and functions
__all__ = [
    "PerformanceMonitor",
    "PerformanceMetric",
    "PerformanceBaseline",
    "PerformanceReport",
    "PerformanceLevel",
    "MetricType",
    "get_performance_monitor",
    "performance_timer"
]