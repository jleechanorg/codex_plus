"""
Performance Monitoring Configuration Module

Provides configuration management for the TaskExecutionEngine performance monitoring system.
Handles settings for baseline establishment, thresholds, alerting, and monitoring behavior.
"""

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class PerformanceThresholds:
    """Performance threshold configurations."""
    
    # Coordination overhead thresholds (milliseconds)
    coordination_overhead_warning_ms: float = 150.0
    coordination_overhead_critical_ms: float = 200.0
    coordination_overhead_max_acceptable_ms: float = 250.0
    
    # Task execution thresholds
    task_execution_warning_ms: float = 1000.0
    task_execution_critical_ms: float = 2000.0
    
    # Agent initialization thresholds
    agent_init_warning_ms: float = 50.0
    agent_init_critical_ms: float = 100.0
    
    # Memory usage thresholds (MB)
    memory_warning_mb: float = 512.0
    memory_critical_mb: float = 1024.0
    
    # Performance consistency thresholds
    coordination_variance_threshold: float = 50.0  # Standard deviation threshold
    
    def to_dict(self) -> Dict[str, float]:
        """Convert thresholds to dictionary."""
        return asdict(self)


@dataclass
class BaselineConfig:
    """Configuration for baseline establishment."""
    
    # Baseline establishment parameters
    measurement_period_hours: float = 1.0
    min_samples_for_baseline: int = 100
    confidence_interval: float = 0.95
    
    # Baseline update behavior
    auto_update_baseline: bool = True
    update_frequency_hours: float = 6.0
    baseline_retention_days: int = 30
    
    # Quality requirements for baseline
    min_success_rate: float = 0.90  # 90% success rate required
    max_variance_coefficient: float = 0.5  # Max coefficient of variation
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self)


@dataclass
class MonitoringConfig:
    """Configuration for performance monitoring behavior."""
    
    # Monitoring enable/disable
    enabled: bool = True
    real_time_monitoring: bool = True
    background_monitoring: bool = True
    
    # Metric collection settings
    max_metrics_in_memory: int = 10000
    metric_retention_hours: float = 24.0
    aggregation_window_minutes: int = 5
    
    # Storage configuration
    storage_dir: str = ".codexplus/performance"
    export_metrics_to_file: bool = True
    export_frequency_minutes: int = 15
    
    # Alerting configuration
    enable_threshold_alerts: bool = True
    enable_performance_degradation_alerts: bool = True
    alert_cooldown_minutes: int = 10
    
    # CI/CD integration
    ci_export_enabled: bool = True
    ci_export_file: str = "performance_metrics.json"
    ci_fail_on_threshold_violation: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self)


@dataclass
class PerformanceConfig:
    """Complete performance monitoring configuration."""
    
    thresholds: PerformanceThresholds = field(default_factory=PerformanceThresholds)
    baseline: BaselineConfig = field(default_factory=BaselineConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entire configuration to dictionary."""
        return {
            "thresholds": self.thresholds.to_dict(),
            "baseline": self.baseline.to_dict(),
            "monitoring": self.monitoring.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PerformanceConfig":
        """Create configuration from dictionary."""
        config = cls()
        
        # Load thresholds
        if "thresholds" in data:
            thresholds_data = data["thresholds"]
            config.thresholds = PerformanceThresholds(**thresholds_data)
        
        # Load baseline config
        if "baseline" in data:
            baseline_data = data["baseline"]
            config.baseline = BaselineConfig(**baseline_data)
        
        # Load monitoring config
        if "monitoring" in data:
            monitoring_data = data["monitoring"]
            config.monitoring = MonitoringConfig(**monitoring_data)
        
        return config


class PerformanceConfigManager:
    """Manages performance monitoring configuration loading, saving, and updates."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = Path(config_path or ".codexplus/performance/config.json")
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._config: Optional[PerformanceConfig] = None
        self._load_config()
    
    def _load_config(self):
        """Load configuration from file or create default."""
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    data = json.load(f)
                self._config = PerformanceConfig.from_dict(data)
                logger.info(f"Loaded performance configuration from {self.config_path}")
            except Exception as e:
                logger.error(f"Failed to load performance config: {e}")
                logger.info("Using default performance configuration")
                self._config = PerformanceConfig()
        else:
            logger.info("No performance configuration found, creating default")
            self._config = PerformanceConfig()
            self.save_config()
    
    def save_config(self):
        """Save configuration to file."""
        if self._config:
            try:
                with open(self.config_path, 'w') as f:
                    json.dump(self._config.to_dict(), f, indent=2)
                logger.debug(f"Saved performance configuration to {self.config_path}")
            except Exception as e:
                logger.error(f"Failed to save performance config: {e}")
    
    def get_config(self) -> PerformanceConfig:
        """Get current configuration."""
        if self._config is None:
            self._load_config()
        return self._config
    
    def update_config(self, updates: Dict[str, Any]):
        """Update configuration with new values."""
        if self._config is None:
            self._load_config()
        
        # Apply updates
        if "thresholds" in updates:
            for key, value in updates["thresholds"].items():
                if hasattr(self._config.thresholds, key):
                    setattr(self._config.thresholds, key, value)
        
        if "baseline" in updates:
            for key, value in updates["baseline"].items():
                if hasattr(self._config.baseline, key):
                    setattr(self._config.baseline, key, value)
        
        if "monitoring" in updates:
            for key, value in updates["monitoring"].items():
                if hasattr(self._config.monitoring, key):
                    setattr(self._config.monitoring, key, value)
        
        # Save updated configuration
        self.save_config()
        logger.info("Performance configuration updated")
    
    def enable_monitoring(self, enabled: bool = True):
        """Enable or disable performance monitoring."""
        config = self.get_config()
        config.monitoring.enabled = enabled
        self.save_config()
        logger.info(f"Performance monitoring {'enabled' if enabled else 'disabled'}")
    
    def set_thresholds(
        self,
        coordination_warning_ms: Optional[float] = None,
        coordination_critical_ms: Optional[float] = None,
        task_execution_warning_ms: Optional[float] = None,
        task_execution_critical_ms: Optional[float] = None
    ):
        """Update performance thresholds."""
        config = self.get_config()
        
        if coordination_warning_ms is not None:
            config.thresholds.coordination_overhead_warning_ms = coordination_warning_ms
        if coordination_critical_ms is not None:
            config.thresholds.coordination_overhead_critical_ms = coordination_critical_ms
        if task_execution_warning_ms is not None:
            config.thresholds.task_execution_warning_ms = task_execution_warning_ms
        if task_execution_critical_ms is not None:
            config.thresholds.task_execution_critical_ms = task_execution_critical_ms
        
        self.save_config()
        logger.info("Performance thresholds updated")
    
    def configure_baseline(
        self,
        measurement_period_hours: Optional[float] = None,
        min_samples: Optional[int] = None,
        auto_update: Optional[bool] = None,
        update_frequency_hours: Optional[float] = None
    ):
        """Configure baseline establishment parameters."""
        config = self.get_config()
        
        if measurement_period_hours is not None:
            config.baseline.measurement_period_hours = measurement_period_hours
        if min_samples is not None:
            config.baseline.min_samples_for_baseline = min_samples
        if auto_update is not None:
            config.baseline.auto_update_baseline = auto_update
        if update_frequency_hours is not None:
            config.baseline.update_frequency_hours = update_frequency_hours
        
        self.save_config()
        logger.info("Baseline configuration updated")
    
    def get_environment_overrides(self) -> Dict[str, Any]:
        """Get configuration overrides from environment variables."""
        overrides = {}
        
        # Monitoring enable/disable
        if os.getenv("CODEX_PERFORMANCE_MONITORING"):
            enabled = os.getenv("CODEX_PERFORMANCE_MONITORING", "true").lower() == "true"
            overrides.setdefault("monitoring", {})["enabled"] = enabled
        
        # Threshold overrides
        if os.getenv("CODEX_COORDINATION_THRESHOLD_MS"):
            threshold_ms = float(os.getenv("CODEX_COORDINATION_THRESHOLD_MS"))
            overrides.setdefault("thresholds", {})["coordination_overhead_critical_ms"] = threshold_ms
        
        # Baseline configuration overrides
        if os.getenv("CODEX_BASELINE_MIN_SAMPLES"):
            min_samples = int(os.getenv("CODEX_BASELINE_MIN_SAMPLES"))
            overrides.setdefault("baseline", {})["min_samples_for_baseline"] = min_samples
        
        if os.getenv("CODEX_BASELINE_MEASUREMENT_HOURS"):
            hours = float(os.getenv("CODEX_BASELINE_MEASUREMENT_HOURS"))
            overrides.setdefault("baseline", {})["measurement_period_hours"] = hours
        
        # CI/CD configuration
        if os.getenv("CODEX_CI_EXPORT_FILE"):
            ci_file = os.getenv("CODEX_CI_EXPORT_FILE")
            overrides.setdefault("monitoring", {})["ci_export_file"] = ci_file
        
        if os.getenv("CODEX_CI_FAIL_ON_VIOLATION"):
            fail_on_violation = os.getenv("CODEX_CI_FAIL_ON_VIOLATION", "true").lower() == "true"
            overrides.setdefault("monitoring", {})["ci_fail_on_threshold_violation"] = fail_on_violation
        
        return overrides
    
    def apply_environment_overrides(self):
        """Apply environment variable overrides to configuration."""
        overrides = self.get_environment_overrides()
        if overrides:
            self.update_config(overrides)
            logger.info("Applied environment variable overrides to performance configuration")
    
    def create_development_config(self) -> PerformanceConfig:
        """Create a development-friendly configuration."""
        config = PerformanceConfig()
        
        # More permissive thresholds for development
        config.thresholds.coordination_overhead_warning_ms = 200.0
        config.thresholds.coordination_overhead_critical_ms = 300.0
        config.thresholds.coordination_overhead_max_acceptable_ms = 400.0
        
        # Faster baseline establishment for development
        config.baseline.measurement_period_hours = 0.5
        config.baseline.min_samples_for_baseline = 20
        config.baseline.update_frequency_hours = 2.0
        
        # More frequent monitoring and exports
        config.monitoring.export_frequency_minutes = 5
        config.monitoring.aggregation_window_minutes = 1
        
        return config
    
    def create_production_config(self) -> PerformanceConfig:
        """Create a production-optimized configuration."""
        config = PerformanceConfig()
        
        # Stricter thresholds for production
        config.thresholds.coordination_overhead_warning_ms = 100.0
        config.thresholds.coordination_overhead_critical_ms = 150.0
        config.thresholds.coordination_overhead_max_acceptable_ms = 200.0
        
        # More robust baseline establishment
        config.baseline.measurement_period_hours = 2.0
        config.baseline.min_samples_for_baseline = 200
        config.baseline.update_frequency_hours = 12.0
        
        # Conservative monitoring settings
        config.monitoring.max_metrics_in_memory = 5000
        config.monitoring.metric_retention_hours = 48.0
        config.monitoring.alert_cooldown_minutes = 30
        
        # Enable CI/CD integration
        config.monitoring.ci_export_enabled = True
        config.monitoring.ci_fail_on_threshold_violation = True
        
        return config


# Global configuration manager instance
_config_manager: Optional[PerformanceConfigManager] = None


def get_performance_config_manager() -> PerformanceConfigManager:
    """Get or create the global performance configuration manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = PerformanceConfigManager()
        # Apply environment overrides on first creation
        _config_manager.apply_environment_overrides()
    return _config_manager


def get_performance_config() -> PerformanceConfig:
    """Get current performance configuration."""
    return get_performance_config_manager().get_config()


# Convenience functions for common configuration tasks
def is_monitoring_enabled() -> bool:
    """Check if performance monitoring is enabled."""
    return get_performance_config().monitoring.enabled


def get_coordination_threshold() -> float:
    """Get coordination overhead critical threshold."""
    return get_performance_config().thresholds.coordination_overhead_critical_ms


def get_baseline_config() -> BaselineConfig:
    """Get baseline configuration."""
    return get_performance_config().baseline


def enable_performance_monitoring(enabled: bool = True):
    """Enable or disable performance monitoring."""
    get_performance_config_manager().enable_monitoring(enabled)


def set_development_mode():
    """Configure for development environment."""
    manager = get_performance_config_manager()
    dev_config = manager.create_development_config()
    manager._config = dev_config
    manager.save_config()
    logger.info("Switched to development performance configuration")


def set_production_mode():
    """Configure for production environment."""
    manager = get_performance_config_manager()
    prod_config = manager.create_production_config()
    manager._config = prod_config
    manager.save_config()
    logger.info("Switched to production performance configuration")


# Export main classes and functions
__all__ = [
    "PerformanceConfig",
    "PerformanceThresholds", 
    "BaselineConfig",
    "MonitoringConfig",
    "PerformanceConfigManager",
    "get_performance_config_manager",
    "get_performance_config",
    "is_monitoring_enabled",
    "get_coordination_threshold",
    "get_baseline_config",
    "enable_performance_monitoring",
    "set_development_mode",
    "set_production_mode"
]