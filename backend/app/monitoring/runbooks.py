"""
Incident response runbooks for ComicGuess application.
Provides automated diagnostics and response procedures for common issues.
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import json

from .logging_config import get_logger
from .metrics import metrics_registry, slo_monitor, alert_manager
from .log_aggregation import log_aggregator, search_logs

class IncidentSeverity(Enum):
    """Incident severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class RunbookStep:
    """Individual step in a runbook."""
    name: str
    description: str
    action: Callable
    timeout_seconds: int = 300
    required: bool = True

@dataclass
class RunbookResult:
    """Result of running a runbook."""
    runbook_name: str
    success: bool
    steps_completed: int
    total_steps: int
    execution_time_seconds: float
    results: Dict[str, Any]
    errors: List[str]

class IncidentRunbook:
    """Base class for incident response runbooks."""
    
    def __init__(self, name: str, description: str, severity: IncidentSeverity):
        self.name = name
        self.description = description
        self.severity = severity
        self.steps: List[RunbookStep] = []
        self.logger = get_logger(f"runbook.{name}")
    
    def add_step(self, step: RunbookStep):
        """Add a step to the runbook."""
        self.steps.append(step)
    
    async def execute(self) -> RunbookResult:
        """Execute the runbook."""
        start_time = time.time()
        results = {}
        errors = []
        steps_completed = 0
        
        self.logger.info(f"Starting runbook execution: {self.name}")
        
        for i, step in enumerate(self.steps):
            try:
                self.logger.info(f"Executing step {i+1}/{len(self.steps)}: {step.name}")
                
                # Execute step with timeout
                step_result = await asyncio.wait_for(
                    step.action(),
                    timeout=step.timeout_seconds
                )
                
                results[step.name] = step_result
                steps_completed += 1
                
                self.logger.info(f"Step completed: {step.name}")
                
            except asyncio.TimeoutError:
                error_msg = f"Step '{step.name}' timed out after {step.timeout_seconds} seconds"
                errors.append(error_msg)
                self.logger.error(error_msg)
                
                if step.required:
                    break
                    
            except Exception as e:
                error_msg = f"Step '{step.name}' failed: {str(e)}"
                errors.append(error_msg)
                self.logger.error(error_msg)
                
                if step.required:
                    break
        
        execution_time = time.time() - start_time
        success = steps_completed == len(self.steps) and len(errors) == 0
        
        result = RunbookResult(
            runbook_name=self.name,
            success=success,
            steps_completed=steps_completed,
            total_steps=len(self.steps),
            execution_time_seconds=execution_time,
            results=results,
            errors=errors
        )
        
        self.logger.info(f"Runbook execution completed: {self.name} - Success: {success}")
        return result

class HighLatencyRunbook(IncidentRunbook):
    """Runbook for high API latency incidents."""
    
    def __init__(self):
        super().__init__(
            name="high_latency_response",
            description="Diagnose and respond to high API latency",
            severity=IncidentSeverity.HIGH
        )
        
        self.add_step(RunbookStep(
            name="check_current_metrics",
            description="Check current latency metrics",
            action=self._check_current_metrics
        ))
        
        self.add_step(RunbookStep(
            name="analyze_slow_endpoints",
            description="Identify slowest endpoints",
            action=self._analyze_slow_endpoints
        ))
        
        self.add_step(RunbookStep(
            name="check_database_performance",
            description="Check database query performance",
            action=self._check_database_performance
        ))
        
        self.add_step(RunbookStep(
            name="check_external_dependencies",
            description="Check external API dependencies",
            action=self._check_external_dependencies
        ))
        
        self.add_step(RunbookStep(
            name="check_resource_utilization",
            description="Check CPU and memory utilization",
            action=self._check_resource_utilization
        ))
        
        self.add_step(RunbookStep(
            name="recommend_actions",
            description="Recommend remediation actions",
            action=self._recommend_actions
        ))
    
    async def _check_current_metrics(self) -> Dict[str, Any]:
        """Check current latency metrics."""
        metrics = metrics_registry.export_metrics()
        
        latency_metrics = {}
        for name, histogram in metrics.get('histograms', {}).items():
            if 'duration' in name or 'latency' in name:
                latency_metrics[name] = {
                    'p50': histogram['p50'],
                    'p95': histogram['p95'],
                    'p99': histogram['p99'],
                    'count': histogram['count']
                }
        
        return {
            'latency_metrics': latency_metrics,
            'timestamp': time.time()
        }
    
    async def _analyze_slow_endpoints(self) -> Dict[str, Any]:
        """Analyze which endpoints are slowest."""
        # Search for slow request logs
        slow_requests = search_logs(
            message_pattern="Slow request detected",
            hours_back=1,
            limit=50
        )
        
        endpoint_stats = {}
        for log in slow_requests:
            path = log.get('extra_fields', {}).get('path', 'unknown')
            duration = log.get('extra_fields', {}).get('duration_ms', 0)
            
            if path not in endpoint_stats:
                endpoint_stats[path] = {
                    'count': 0,
                    'total_duration': 0,
                    'max_duration': 0
                }
            
            endpoint_stats[path]['count'] += 1
            endpoint_stats[path]['total_duration'] += duration
            endpoint_stats[path]['max_duration'] = max(
                endpoint_stats[path]['max_duration'], 
                duration
            )
        
        # Calculate averages and sort by severity
        for path, stats in endpoint_stats.items():
            stats['avg_duration'] = stats['total_duration'] / stats['count']
        
        sorted_endpoints = sorted(
            endpoint_stats.items(),
            key=lambda x: x[1]['avg_duration'],
            reverse=True
        )
        
        return {
            'slow_endpoints': dict(sorted_endpoints[:10]),  # Top 10 slowest
            'total_slow_requests': len(slow_requests)
        }
    
    async def _check_database_performance(self) -> Dict[str, Any]:
        """Check database performance indicators."""
        # Search for database-related logs
        db_logs = search_logs(
            logger_pattern=".*database.*",
            hours_back=1,
            limit=100
        )
        
        db_errors = search_logs(
            logger_pattern=".*database.*",
            level="ERROR",
            hours_back=1,
            limit=50
        )
        
        # Look for specific database performance indicators
        slow_queries = [
            log for log in db_logs 
            if log.get('extra_fields', {}).get('duration_ms', 0) > 1000
        ]
        
        return {
            'total_db_operations': len(db_logs),
            'db_errors': len(db_errors),
            'slow_queries': len(slow_queries),
            'error_rate': len(db_errors) / max(len(db_logs), 1) * 100
        }
    
    async def _check_external_dependencies(self) -> Dict[str, Any]:
        """Check external API dependencies."""
        # Search for HTTP client logs
        http_logs = search_logs(
            message_pattern="http.*",
            hours_back=1,
            limit=100
        )
        
        external_errors = search_logs(
            message_pattern="http.*",
            level="ERROR",
            hours_back=1,
            limit=50
        )
        
        return {
            'external_requests': len(http_logs),
            'external_errors': len(external_errors),
            'external_error_rate': len(external_errors) / max(len(http_logs), 1) * 100
        }
    
    async def _check_resource_utilization(self) -> Dict[str, Any]:
        """Check system resource utilization."""
        # This would integrate with system monitoring
        # For now, return placeholder data
        return {
            'cpu_usage_percent': 75.0,  # Would come from system metrics
            'memory_usage_percent': 68.0,
            'disk_usage_percent': 45.0,
            'active_connections': 150
        }
    
    async def _recommend_actions(self) -> Dict[str, Any]:
        """Recommend remediation actions based on analysis."""
        recommendations = []
        
        # This would analyze the previous step results and recommend actions
        recommendations.append({
            'action': 'Scale up application instances',
            'priority': 'high',
            'description': 'Consider scaling horizontally to handle increased load'
        })
        
        recommendations.append({
            'action': 'Optimize database queries',
            'priority': 'medium',
            'description': 'Review and optimize slow database queries'
        })
        
        recommendations.append({
            'action': 'Enable caching',
            'priority': 'medium',
            'description': 'Implement or increase caching for frequently accessed data'
        })
        
        return {
            'recommendations': recommendations,
            'immediate_actions': [r for r in recommendations if r['priority'] == 'high']
        }

class HighErrorRateRunbook(IncidentRunbook):
    """Runbook for high error rate incidents."""
    
    def __init__(self):
        super().__init__(
            name="high_error_rate_response",
            description="Diagnose and respond to high error rates",
            severity=IncidentSeverity.CRITICAL
        )
        
        self.add_step(RunbookStep(
            name="check_error_metrics",
            description="Check current error rate metrics",
            action=self._check_error_metrics
        ))
        
        self.add_step(RunbookStep(
            name="analyze_error_patterns",
            description="Analyze error patterns and types",
            action=self._analyze_error_patterns
        ))
        
        self.add_step(RunbookStep(
            name="check_recent_deployments",
            description="Check for recent deployments or changes",
            action=self._check_recent_deployments
        ))
        
        self.add_step(RunbookStep(
            name="check_dependency_health",
            description="Check health of dependencies",
            action=self._check_dependency_health
        ))
        
        self.add_step(RunbookStep(
            name="recommend_immediate_actions",
            description="Recommend immediate remediation actions",
            action=self._recommend_immediate_actions
        ))
    
    async def _check_error_metrics(self) -> Dict[str, Any]:
        """Check current error rate metrics."""
        error_logs = search_logs(level="ERROR", hours_back=1, limit=500)
        total_logs = search_logs(hours_back=1, limit=5000)
        
        error_rate = len(error_logs) / max(len(total_logs), 1) * 100
        
        return {
            'error_count': len(error_logs),
            'total_requests': len(total_logs),
            'error_rate_percent': error_rate,
            'is_critical': error_rate > 5.0  # 5% error rate threshold
        }
    
    async def _analyze_error_patterns(self) -> Dict[str, Any]:
        """Analyze error patterns and types."""
        error_logs = search_logs(level="ERROR", hours_back=1, limit=500)
        
        error_types = {}
        error_endpoints = {}
        
        for log in error_logs:
            # Group by error type
            error_type = log.get('extra_fields', {}).get('error_type', 'unknown')
            error_types[error_type] = error_types.get(error_type, 0) + 1
            
            # Group by endpoint
            endpoint = log.get('extra_fields', {}).get('path', 'unknown')
            error_endpoints[endpoint] = error_endpoints.get(endpoint, 0) + 1
        
        return {
            'top_error_types': sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:10],
            'top_error_endpoints': sorted(error_endpoints.items(), key=lambda x: x[1], reverse=True)[:10]
        }
    
    async def _check_recent_deployments(self) -> Dict[str, Any]:
        """Check for recent deployments or changes."""
        # This would integrate with deployment tracking
        return {
            'recent_deployments': [],  # Would be populated from deployment logs
            'last_deployment_time': None,
            'deployment_correlation': False
        }
    
    async def _check_dependency_health(self) -> Dict[str, Any]:
        """Check health of external dependencies."""
        # Check for dependency-related errors
        dependency_errors = search_logs(
            message_pattern=".*connection.*|.*timeout.*|.*unavailable.*",
            level="ERROR",
            hours_back=1,
            limit=100
        )
        
        return {
            'dependency_errors': len(dependency_errors),
            'dependency_health_status': 'degraded' if len(dependency_errors) > 10 else 'healthy'
        }
    
    async def _recommend_immediate_actions(self) -> Dict[str, Any]:
        """Recommend immediate remediation actions."""
        actions = [
            {
                'action': 'Enable circuit breakers',
                'priority': 'critical',
                'description': 'Enable circuit breakers for failing dependencies'
            },
            {
                'action': 'Scale up instances',
                'priority': 'high',
                'description': 'Scale up to handle error recovery load'
            },
            {
                'action': 'Check recent changes',
                'priority': 'high',
                'description': 'Review and potentially rollback recent changes'
            }
        ]
        
        return {
            'immediate_actions': actions,
            'escalation_required': True
        }

class CachePerformanceRunbook(IncidentRunbook):
    """Runbook for cache performance issues."""
    
    def __init__(self):
        super().__init__(
            name="cache_performance_response",
            description="Diagnose and respond to cache performance issues",
            severity=IncidentSeverity.MEDIUM
        )
        
        self.add_step(RunbookStep(
            name="check_cache_metrics",
            description="Check cache hit rates and performance",
            action=self._check_cache_metrics
        ))
        
        self.add_step(RunbookStep(
            name="analyze_cache_patterns",
            description="Analyze cache usage patterns",
            action=self._analyze_cache_patterns
        ))
        
        self.add_step(RunbookStep(
            name="recommend_cache_optimizations",
            description="Recommend cache optimizations",
            action=self._recommend_cache_optimizations
        ))
    
    async def _check_cache_metrics(self) -> Dict[str, Any]:
        """Check cache performance metrics."""
        cache_logs = search_logs(
            logger_pattern=".*cache.*",
            hours_back=1,
            limit=1000
        )
        
        cache_hits = len([log for log in cache_logs if 'hit' in log.get('message', '').lower()])
        cache_misses = len([log for log in cache_logs if 'miss' in log.get('message', '').lower()])
        
        total_cache_operations = cache_hits + cache_misses
        hit_rate = cache_hits / max(total_cache_operations, 1) * 100
        
        return {
            'cache_hits': cache_hits,
            'cache_misses': cache_misses,
            'hit_rate_percent': hit_rate,
            'total_operations': total_cache_operations
        }
    
    async def _analyze_cache_patterns(self) -> Dict[str, Any]:
        """Analyze cache usage patterns."""
        return {
            'most_requested_keys': [],  # Would analyze cache key patterns
            'cache_size_utilization': 75.0,  # Would come from cache metrics
            'eviction_rate': 5.0  # Percentage of keys being evicted
        }
    
    async def _recommend_cache_optimizations(self) -> Dict[str, Any]:
        """Recommend cache optimizations."""
        recommendations = [
            {
                'action': 'Increase cache size',
                'priority': 'medium',
                'description': 'Consider increasing cache memory allocation'
            },
            {
                'action': 'Optimize cache keys',
                'priority': 'low',
                'description': 'Review and optimize cache key patterns'
            }
        ]
        
        return {'recommendations': recommendations}

class RunbookManager:
    """Manager for incident response runbooks."""
    
    def __init__(self):
        self.runbooks: Dict[str, IncidentRunbook] = {}
        self.execution_history: List[RunbookResult] = []
        self.logger = get_logger("runbook_manager")
        
        # Register default runbooks
        self._register_default_runbooks()
    
    def _register_default_runbooks(self):
        """Register default runbooks."""
        self.register_runbook(HighLatencyRunbook())
        self.register_runbook(HighErrorRateRunbook())
        self.register_runbook(CachePerformanceRunbook())
    
    def register_runbook(self, runbook: IncidentRunbook):
        """Register a runbook."""
        self.runbooks[runbook.name] = runbook
        self.logger.info(f"Registered runbook: {runbook.name}")
    
    async def execute_runbook(self, runbook_name: str) -> Optional[RunbookResult]:
        """Execute a specific runbook."""
        if runbook_name not in self.runbooks:
            self.logger.error(f"Runbook not found: {runbook_name}")
            return None
        
        runbook = self.runbooks[runbook_name]
        result = await runbook.execute()
        
        self.execution_history.append(result)
        return result
    
    def get_available_runbooks(self) -> List[Dict[str, Any]]:
        """Get list of available runbooks."""
        return [
            {
                'name': runbook.name,
                'description': runbook.description,
                'severity': runbook.severity.value,
                'steps': len(runbook.steps)
            }
            for runbook in self.runbooks.values()
        ]
    
    def get_execution_history(self, limit: int = 50) -> List[RunbookResult]:
        """Get runbook execution history."""
        return list(self.execution_history)[-limit:]

# Global runbook manager
runbook_manager = RunbookManager()

# Convenience functions
async def execute_incident_response(incident_type: str) -> Optional[RunbookResult]:
    """Execute incident response runbook based on incident type."""
    runbook_mapping = {
        'high_latency': 'high_latency_response',
        'high_error_rate': 'high_error_rate_response',
        'cache_issues': 'cache_performance_response'
    }
    
    runbook_name = runbook_mapping.get(incident_type)
    if runbook_name:
        return await runbook_manager.execute_runbook(runbook_name)
    
    return None

def get_incident_runbooks() -> List[Dict[str, Any]]:
    """Get available incident response runbooks."""
    return runbook_manager.get_available_runbooks()