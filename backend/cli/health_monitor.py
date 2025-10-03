"""
CLI tool for health monitoring and resilience management
"""

import asyncio
import click
import json
from datetime import datetime
from typing import Optional

from app.monitoring.health import health_monitor, idempotency_manager


@click.group()
def health_cli():
    """Health monitoring and resilience management commands"""
    pass


@health_cli.command()
@click.option('--component', '-c', help='Check specific component only')
@click.option('--format', '-f', type=click.Choice(['table', 'json']), default='table', help='Output format')
def check(component: Optional[str], format: str):
    """Perform health checks"""
    async def _health_check():
        try:
            if component:
                click.echo(f"Checking health of component: {component}")
                result = await health_monitor.perform_health_check(component)
                
                if format == 'json':
                    health_data = {
                        "component": result.component,
                        "status": result.status.value,
                        "timestamp": result.timestamp.isoformat(),
                        "response_time_ms": result.response_time_ms,
                        "details": result.details,
                        "error": result.error
                    }
                    click.echo(json.dumps(health_data, indent=2))
                    return
                
                # Table format for single component
                status_icon = {
                    'healthy': '✅',
                    'degraded': '⚠️',
                    'unhealthy': '❌',
                    'unknown': '❓'
                }.get(result.status.value, '❓')
                
                click.echo(f"{status_icon} {result.component}: {result.status.value}")
                click.echo(f"   Response time: {result.response_time_ms:.1f}ms")
                click.echo(f"   Timestamp: {result.timestamp.isoformat()}")
                
                if result.error:
                    click.echo(f"   Error: {result.error}")
                
                if result.details:
                    click.echo(f"   Details: {json.dumps(result.details, indent=4)}")
            
            else:
                click.echo("Performing overall health check...")
                overall_health = await health_monitor.get_overall_health()
                
                if format == 'json':
                    click.echo(json.dumps(overall_health, indent=2))
                    return
                
                # Table format for overall health
                status_icon = {
                    'healthy': '✅',
                    'degraded': '⚠️',
                    'unhealthy': '❌'
                }.get(overall_health['status'], '❓')
                
                click.echo(f"\nOverall Health: {status_icon} {overall_health['status'].upper()}")
                click.echo(f"Timestamp: {overall_health['timestamp']}")
                
                # Component breakdown
                click.echo(f"\nComponent Health:")
                for comp_name, comp_info in overall_health.get('components', {}).items():
                    comp_status = comp_info.get('status', 'unknown')
                    comp_icon = {
                        'healthy': '✅',
                        'degraded': '⚠️',
                        'unhealthy': '❌',
                        'unknown': '❓'
                    }.get(comp_status, '❓')
                    
                    response_time = comp_info.get('response_time_ms', 0)
                    click.echo(f"  {comp_icon} {comp_name}: {comp_status} ({response_time:.1f}ms)")
                    
                    if comp_info.get('error'):
                        click.echo(f"    Error: {comp_info['error']}")
                
                # Circuit breaker status
                if 'circuit_breakers' in overall_health:
                    click.echo(f"\nCircuit Breakers:")
                    for cb_name, cb_info in overall_health['circuit_breakers'].items():
                        cb_state = cb_info.get('state', 'unknown')
                        cb_icon = {
                            'closed': '✅',
                            'half_open': '⚠️',
                            'open': '❌'
                        }.get(cb_state, '❓')
                        
                        failure_count = cb_info.get('failure_count', 0)
                        click.echo(f"  {cb_icon} {cb_name}: {cb_state} (failures: {failure_count})")
            
        except Exception as e:
            click.echo(f"❌ Health check failed: {e}")
            raise click.Abort()
    
    asyncio.run(_health_check())


@health_cli.command()
@click.option('--format', '-f', type=click.Choice(['table', 'json']), default='table', help='Output format')
def readiness(format: str):
    """Check application readiness"""
    async def _readiness_check():
        try:
            click.echo("Checking application readiness...")
            readiness_status = await health_monitor.check_readiness()
            
            if format == 'json':
                click.echo(json.dumps(readiness_status, indent=2))
                return
            
            # Table format
            ready_icon = "✅" if readiness_status["ready"] else "❌"
            click.echo(f"\nReadiness Status: {ready_icon} {'READY' if readiness_status['ready'] else 'NOT READY'}")
            click.echo(f"Timestamp: {readiness_status['timestamp']}")
            
            click.echo(f"\nReadiness Checks:")
            for check in readiness_status.get('checks', []):
                check_ready = check.get('ready', False)
                check_icon = "✅" if check_ready else "❌"
                check_name = check.get('check', 'unknown')
                
                click.echo(f"  {check_icon} {check_name}: {'ready' if check_ready else 'not ready'}")
                
                if check.get('error'):
                    click.echo(f"    Error: {check['error']}")
            
        except Exception as e:
            click.echo(f"❌ Readiness check failed: {e}")
            raise click.Abort()
    
    asyncio.run(_readiness_check())


@health_cli.command()
@click.option('--format', '-f', type=click.Choice(['table', 'json']), default='table', help='Output format')
def liveness(format: str):
    """Check application liveness"""
    async def _liveness_check():
        try:
            click.echo("Checking application liveness...")
            liveness_status = await health_monitor.check_liveness()
            
            if format == 'json':
                click.echo(json.dumps(liveness_status, indent=2))
                return
            
            # Table format
            alive_icon = "✅" if liveness_status["alive"] else "❌"
            click.echo(f"\nLiveness Status: {alive_icon} {'ALIVE' if liveness_status['alive'] else 'NOT ALIVE'}")
            click.echo(f"Timestamp: {liveness_status['timestamp']}")
            
            click.echo(f"\nLiveness Checks:")
            for check in liveness_status.get('checks', []):
                check_alive = check.get('alive', False)
                check_icon = "✅" if check_alive else "❌"
                check_name = check.get('check', 'unknown')
                
                click.echo(f"  {check_icon} {check_name}: {'alive' if check_alive else 'not alive'}")
                
                if check.get('error'):
                    click.echo(f"    Error: {check['error']}")
            
        except Exception as e:
            click.echo(f"❌ Liveness check failed: {e}")
            raise click.Abort()
    
    asyncio.run(_liveness_check())


@health_cli.command()
@click.argument('circuit_breaker_name')
def reset_circuit_breaker(circuit_breaker_name: str):
    """Reset a circuit breaker"""
    try:
        if circuit_breaker_name not in health_monitor.circuit_breakers:
            click.echo(f"❌ Circuit breaker '{circuit_breaker_name}' not found")
            available_cbs = list(health_monitor.circuit_breakers.keys())
            if available_cbs:
                click.echo(f"Available circuit breakers: {', '.join(available_cbs)}")
            raise click.Abort()
        
        cb = health_monitor.circuit_breakers[circuit_breaker_name]
        old_state = cb.state.value
        old_failures = cb.failure_count
        
        # Reset circuit breaker
        from app.monitoring.health import CircuitBreakerState
        cb.state = CircuitBreakerState.CLOSED
        cb.failure_count = 0
        cb.last_failure_time = None
        
        click.echo(f"✅ Circuit breaker '{circuit_breaker_name}' reset successfully")
        click.echo(f"   Previous state: {old_state} (failures: {old_failures})")
        click.echo(f"   New state: {cb.state.value} (failures: {cb.failure_count})")
        
    except Exception as e:
        click.echo(f"❌ Failed to reset circuit breaker: {e}")
        raise click.Abort()


@health_cli.command()
@click.option('--format', '-f', type=click.Choice(['table', 'json']), default='table', help='Output format')
def circuit_breakers(format: str):
    """List all circuit breakers and their status"""
    try:
        if format == 'json':
            cb_data = {}
            for name, cb in health_monitor.circuit_breakers.items():
                cb_data[name] = {
                    "state": cb.state.value,
                    "failure_count": cb.failure_count,
                    "failure_threshold": cb.failure_threshold,
                    "recovery_timeout_seconds": cb.recovery_timeout_seconds,
                    "last_failure": cb.last_failure_time.isoformat() if cb.last_failure_time else None,
                    "last_success": cb.last_success_time.isoformat() if cb.last_success_time else None
                }
            click.echo(json.dumps(cb_data, indent=2))
            return
        
        # Table format
        if not health_monitor.circuit_breakers:
            click.echo("No circuit breakers configured")
            return
        
        click.echo(f"{'Name':<20} {'State':<12} {'Failures':<10} {'Threshold':<10} {'Last Failure':<20}")
        click.echo("-" * 80)
        
        for name, cb in health_monitor.circuit_breakers.items():
            state_icon = {
                'closed': '✅',
                'half_open': '⚠️',
                'open': '❌'
            }.get(cb.state.value, '❓')
            
            last_failure = cb.last_failure_time.strftime('%Y-%m-%d %H:%M:%S') if cb.last_failure_time else 'Never'
            
            click.echo(
                f"{name:<20} "
                f"{state_icon} {cb.state.value:<10} "
                f"{cb.failure_count:<10} "
                f"{cb.failure_threshold:<10} "
                f"{last_failure:<20}"
            )
        
    except Exception as e:
        click.echo(f"❌ Failed to list circuit breakers: {e}")
        raise click.Abort()


@health_cli.command()
@click.option('--format', '-f', type=click.Choice(['table', 'json']), default='table', help='Output format')
def retry_policies(format: str):
    """List all retry policies"""
    try:
        if format == 'json':
            policy_data = {}
            for name, policy in health_monitor.retry_policies.items():
                policy_data[name] = {
                    "max_attempts": policy.max_attempts,
                    "base_delay_ms": policy.base_delay_ms,
                    "max_delay_ms": policy.max_delay_ms,
                    "exponential_base": policy.exponential_base,
                    "jitter": policy.jitter
                }
            click.echo(json.dumps(policy_data, indent=2))
            return
        
        # Table format
        if not health_monitor.retry_policies:
            click.echo("No retry policies configured")
            return
        
        click.echo(f"{'Name':<15} {'Max Attempts':<12} {'Base Delay':<12} {'Max Delay':<12} {'Jitter':<8}")
        click.echo("-" * 70)
        
        for name, policy in health_monitor.retry_policies.items():
            click.echo(
                f"{name:<15} "
                f"{policy.max_attempts:<12} "
                f"{policy.base_delay_ms}ms{'':<8} "
                f"{policy.max_delay_ms}ms{'':<8} "
                f"{'Yes' if policy.jitter else 'No':<8}"
            )
        
    except Exception as e:
        click.echo(f"❌ Failed to list retry policies: {e}")
        raise click.Abort()


@health_cli.command()
def idempotency_status():
    """Show idempotency manager status"""
    try:
        cached_operations = len(idempotency_manager.processed_keys)
        
        click.echo(f"Idempotency Manager Status:")
        click.echo(f"  Cached operations: {cached_operations}")
        click.echo(f"  Key expiry hours: {idempotency_manager.key_expiry_hours}")
        
        if cached_operations > 0:
            click.echo(f"\nCached Operations:")
            for key, data in list(idempotency_manager.processed_keys.items())[:10]:  # Show first 10
                operation = data.get('operation', 'unknown')
                timestamp = data.get('timestamp', 'unknown')
                click.echo(f"  {key[:16]}... - {operation} ({timestamp})")
            
            if cached_operations > 10:
                click.echo(f"  ... and {cached_operations - 10} more operations")
        
    except Exception as e:
        click.echo(f"❌ Failed to get idempotency status: {e}")
        raise click.Abort()


@health_cli.command()
def cleanup_idempotency():
    """Clean up expired idempotency keys"""
    try:
        before_count = len(idempotency_manager.processed_keys)
        idempotency_manager.cleanup_expired_keys()
        after_count = len(idempotency_manager.processed_keys)
        
        cleaned_count = before_count - after_count
        
        click.echo(f"✅ Idempotency cleanup completed")
        click.echo(f"   Keys before cleanup: {before_count}")
        click.echo(f"   Keys after cleanup: {after_count}")
        click.echo(f"   Keys cleaned: {cleaned_count}")
        
    except Exception as e:
        click.echo(f"❌ Idempotency cleanup failed: {e}")
        raise click.Abort()


@health_cli.command()
def test_resilience():
    """Test resilience patterns (circuit breaker and retry)"""
    async def _test_resilience():
        try:
            click.echo("Testing resilience patterns...")
            
            # Test retry mechanism
            click.echo("\n1. Testing retry mechanism...")
            call_count = 0
            
            async def flaky_operation():
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise Exception("Temporary failure")
                return "success"
            
            try:
                result = await health_monitor.retry_with_backoff(flaky_operation, "test")
                click.echo(f"   ✅ Retry test passed: {result} (attempts: {call_count})")
            except Exception as e:
                click.echo(f"   ❌ Retry test failed: {e}")
            
            # Test circuit breaker
            click.echo("\n2. Testing circuit breaker...")
            
            # Register test circuit breaker
            from app.monitoring.health import CircuitBreaker
            test_cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout_seconds=1)
            health_monitor.register_circuit_breaker("test", test_cb)
            
            failure_count = 0
            
            # Cause failures to open circuit breaker
            for i in range(3):
                try:
                    async with health_monitor.circuit_breaker("test"):
                        failure_count += 1
                        raise Exception(f"Test failure {failure_count}")
                except Exception as e:
                    if "Circuit breaker test is OPEN" in str(e):
                        click.echo(f"   ✅ Circuit breaker opened after {failure_count - 1} failures")
                        break
                    elif failure_count >= 2:
                        click.echo(f"   ✅ Circuit breaker should open after this failure")
            
            # Check circuit breaker state
            cb_state = test_cb.state.value
            click.echo(f"   Circuit breaker state: {cb_state}")
            
            # Test recovery
            click.echo("\n3. Testing circuit breaker recovery...")
            await asyncio.sleep(1.1)  # Wait for recovery timeout
            
            try:
                async with health_monitor.circuit_breaker("test"):
                    click.echo("   ✅ Circuit breaker recovered and allowed operation")
            except Exception as e:
                click.echo(f"   ❌ Circuit breaker recovery failed: {e}")
            
            click.echo(f"\n✅ Resilience pattern testing completed")
            
        except Exception as e:
            click.echo(f"❌ Resilience testing failed: {e}")
            raise click.Abort()
    
    asyncio.run(_test_resilience())


if __name__ == '__main__':
    health_cli()