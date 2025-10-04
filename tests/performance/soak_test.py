"""
Soak testing suite for ComicGuess application.
Tests system stability under sustained load over extended periods.
"""

import asyncio
import aiohttp
import time
import json
import logging
import psutil
import statistics
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import random
import gc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SoakTestMetrics:
    """Metrics collected during soak testing."""
    timestamp: str
    response_time: float
    memory_usage_mb: float
    cpu_usage_percent: float
    active_connections: int
    error_count: int
    success_count: int

@dataclass
class SoakTestResult:
    """Results from a soak test run."""
    test_name: str
    duration_hours: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    p95_response_time: float
    p99_response_time: float
    memory_leak_detected: bool
    performance_degradation: bool
    stability_score: float
    metrics_timeline: List[SoakTestMetrics]

class SoakTester:
    """Soak testing utility for long-running performance tests."""
    
    def __init__(self, base_url: str, max_concurrent: int = 20):
        self.base_url = base_url.rstrip('/')
        self.max_concurrent = max_concurrent
        self.session = None
        self.metrics_history = []
        self.start_time = None
        
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=self.max_concurrent,
            keepalive_timeout=300,  # Keep connections alive longer for soak tests
            enable_cleanup_closed=True
        )
        timeout = aiohttp.ClientTimeout(total=60)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        )
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def collect_system_metrics(self) -> Dict[str, float]:
        """Collect system performance metrics."""
        process = psutil.Process()
        
        return {
            'memory_usage_mb': process.memory_info().rss / 1024 / 1024,
            'cpu_usage_percent': process.cpu_percent(),
            'open_files': len(process.open_files()),
            'connections': len(process.connections())
        }
    
    async def make_request_with_metrics(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make a request and collect performance metrics."""
        start_time = time.time()
        system_metrics = self.collect_system_metrics()
        
        try:
            url = f"{self.base_url}{endpoint}"
            async with self.session.request(method, url, **kwargs) as response:
                response_time = time.time() - start_time
                content = await response.text()
                
                # Record metrics
                metrics = SoakTestMetrics(
                    timestamp=datetime.utcnow().isoformat(),
                    response_time=response_time,
                    memory_usage_mb=system_metrics['memory_usage_mb'],
                    cpu_usage_percent=system_metrics['cpu_usage_percent'],
                    active_connections=system_metrics['connections'],
                    error_count=0 if response.status < 400 else 1,
                    success_count=1 if response.status < 400 else 0
                )
                self.metrics_history.append(metrics)
                
                return {
                    'success': response.status < 400,
                    'status_code': response.status,
                    'response_time': response_time,
                    'content_length': len(content),
                    'error': None
                }
                
        except Exception as e:
            response_time = time.time() - start_time
            system_metrics = self.collect_system_metrics()
            
            # Record error metrics
            metrics = SoakTestMetrics(
                timestamp=datetime.utcnow().isoformat(),
                response_time=response_time,
                memory_usage_mb=system_metrics['memory_usage_mb'],
                cpu_usage_percent=system_metrics['cpu_usage_percent'],
                active_connections=system_metrics['connections'],
                error_count=1,
                success_count=0
            )
            self.metrics_history.append(metrics)
            
            return {
                'success': False,
                'status_code': 0,
                'response_time': response_time,
                'content_length': 0,
                'error': str(e)
            }
    
    def detect_memory_leak(self, window_hours: float = 1.0) -> bool:
        """Detect potential memory leaks by analyzing memory usage trends."""
        if len(self.metrics_history) < 100:
            return False
        
        # Get metrics from the last window_hours
        cutoff_time = datetime.utcnow() - timedelta(hours=window_hours)
        recent_metrics = [
            m for m in self.metrics_history[-1000:]  # Last 1000 metrics
            if datetime.fromisoformat(m.timestamp) > cutoff_time
        ]
        
        if len(recent_metrics) < 50:
            return False
        
        # Calculate memory usage trend
        memory_values = [m.memory_usage_mb for m in recent_metrics]
        
        # Simple linear regression to detect upward trend
        n = len(memory_values)
        x_values = list(range(n))
        
        sum_x = sum(x_values)
        sum_y = sum(memory_values)
        sum_xy = sum(x * y for x, y in zip(x_values, memory_values))
        sum_x2 = sum(x * x for x in x_values)
        
        # Calculate slope
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        
        # Memory leak if slope > 1MB per 100 requests and memory increased by >20%
        initial_memory = statistics.mean(memory_values[:10])
        final_memory = statistics.mean(memory_values[-10:])
        memory_increase_percent = ((final_memory - initial_memory) / initial_memory) * 100
        
        return slope > 0.01 and memory_increase_percent > 20
    
    def detect_performance_degradation(self, window_hours: float = 1.0) -> bool:
        """Detect performance degradation over time."""
        if len(self.metrics_history) < 100:
            return False
        
        # Compare first hour vs last hour response times
        first_hour_metrics = self.metrics_history[:min(100, len(self.metrics_history) // 4)]
        last_hour_metrics = self.metrics_history[-min(100, len(self.metrics_history) // 4):]
        
        first_hour_avg = statistics.mean(m.response_time for m in first_hour_metrics)
        last_hour_avg = statistics.mean(m.response_time for m in last_hour_metrics)
        
        # Performance degradation if response time increased by >50%
        degradation_percent = ((last_hour_avg - first_hour_avg) / first_hour_avg) * 100
        return degradation_percent > 50
    
    def calculate_stability_score(self) -> float:
        """Calculate overall stability score (0-100)."""
        if not self.metrics_history:
            return 0.0
        
        # Factors affecting stability score
        total_requests = len(self.metrics_history)
        error_count = sum(m.error_count for m in self.metrics_history)
        error_rate = (error_count / total_requests) * 100 if total_requests > 0 else 0
        
        # Response time consistency
        response_times = [m.response_time for m in self.metrics_history]
        response_time_std = statistics.stdev(response_times) if len(response_times) > 1 else 0
        response_time_cv = (response_time_std / statistics.mean(response_times)) * 100 if response_times else 0
        
        # Memory stability
        memory_leak = self.detect_memory_leak()
        performance_degradation = self.detect_performance_degradation()
        
        # Calculate score (higher is better)
        score = 100.0
        score -= min(error_rate * 2, 50)  # Penalize errors heavily
        score -= min(response_time_cv, 30)  # Penalize inconsistent response times
        score -= 25 if memory_leak else 0  # Major penalty for memory leaks
        score -= 20 if performance_degradation else 0  # Penalty for performance degradation
        
        return max(0.0, score)

class ComicGuessSoakTest:
    """Soak tests specific to ComicGuess application."""
    
    def __init__(self, api_base_url: str):
        self.api_base_url = api_base_url
        self.test_users = [f"soak-test-user-{i:04d}" for i in range(100)]
        self.universes = ['marvel', 'DC', 'image']
    
    async def run_daily_usage_simulation(self, duration_hours: float = 8.0) -> SoakTestResult:
        """Simulate daily usage patterns over extended period."""
        logger.info(f"Starting daily usage simulation for {duration_hours} hours")
        
        async with SoakTester(self.api_base_url, max_concurrent=15) as tester:
            end_time = time.time() + (duration_hours * 3600)
            request_count = 0
            
            while time.time() < end_time:
                # Simulate realistic usage patterns
                tasks = []
                
                # Morning rush (higher activity)
                current_hour = datetime.now().hour
                if 8 <= current_hour <= 10 or 19 <= current_hour <= 22:
                    concurrent_users = 10
                    request_interval = 2.0
                else:
                    concurrent_users = 5
                    request_interval = 5.0
                
                # Create concurrent user sessions
                for _ in range(concurrent_users):
                    task = asyncio.create_task(self._simulate_user_session(tester))
                    tasks.append(task)
                
                # Wait for requests to complete
                await asyncio.gather(*tasks, return_exceptions=True)
                request_count += len(tasks)
                
                # Periodic cleanup
                if request_count % 1000 == 0:
                    gc.collect()  # Force garbage collection
                    logger.info(f"Completed {request_count} requests, {(time.time() - tester.start_time) / 3600:.1f} hours elapsed")
                
                await asyncio.sleep(request_interval)
            
            # Analyze results
            total_requests = len(tester.metrics_history)
            successful_requests = sum(m.success_count for m in tester.metrics_history)
            failed_requests = sum(m.error_count for m in tester.metrics_history)
            
            response_times = [m.response_time for m in tester.metrics_history]
            avg_response_time = statistics.mean(response_times) if response_times else 0
            p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) > 20 else 0
            p99_response_time = statistics.quantiles(response_times, n=100)[98] if len(response_times) > 100 else 0
            
            memory_leak_detected = tester.detect_memory_leak()
            performance_degradation = tester.detect_performance_degradation()
            stability_score = tester.calculate_stability_score()
            
            return SoakTestResult(
                test_name="daily_usage_simulation",
                duration_hours=duration_hours,
                total_requests=total_requests,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                avg_response_time=avg_response_time,
                p95_response_time=p95_response_time,
                p99_response_time=p99_response_time,
                memory_leak_detected=memory_leak_detected,
                performance_degradation=performance_degradation,
                stability_score=stability_score,
                metrics_timeline=tester.metrics_history[-100:]  # Keep last 100 metrics
            )
    
    async def _simulate_user_session(self, tester: SoakTester):
        """Simulate a realistic user session."""
        user_id = random.choice(self.test_users)
        universe = random.choice(self.universes)
        
        # Typical user flow: get puzzle -> make guesses -> check stats
        try:
            # Get today's puzzle
            await tester.make_request_with_metrics('GET', f'/puzzle/today?universe={universe}')
            await asyncio.sleep(random.uniform(1, 3))  # User thinking time
            
            # Make 1-6 guesses (realistic user behavior)
            num_guesses = random.randint(1, 6)
            for _ in range(num_guesses):
                guess_data = {
                    'userId': user_id,
                    'universe': universe,
                    'guess': self._get_random_guess()
                }
                
                await tester.make_request_with_metrics(
                    'POST', '/guess',
                    json=guess_data,
                    headers={'Content-Type': 'application/json'}
                )
                await asyncio.sleep(random.uniform(5, 15))  # Time between guesses
            
            # Check stats (30% of users)
            if random.random() < 0.3:
                await tester.make_request_with_metrics('GET', f'/user/{user_id}/stats')
            
        except Exception as e:
            logger.warning(f"Error in user session simulation: {e}")
    
    def _get_random_guess(self) -> str:
        """Get a random character guess."""
        characters = [
            'Spider-Man', 'Batman', 'Superman', 'Wonder Woman', 'Iron Man',
            'Captain America', 'The Flash', 'Green Lantern', 'Wolverine',
            'Deadpool', 'Spawn', 'Invincible', 'Hulk', 'Thor', 'Aquaman'
        ]
        return random.choice(characters)

async def main():
    """Main function to run soak tests."""
    import os
    
    api_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
    duration = float(os.getenv('SOAK_TEST_DURATION_HOURS', '2.0'))
    
    soak_test = ComicGuessSoakTest(api_url)
    result = await soak_test.run_daily_usage_simulation(duration_hours=duration)
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    results_file = f'soak-test-results-{timestamp}.json'
    
    with open(results_file, 'w') as f:
        json.dump(asdict(result), f, indent=2, default=str)
    
    logger.info(f"Soak test results saved to {results_file}")
    
    # Print summary
    print("\n=== SOAK TEST SUMMARY ===")
    print(f"Test duration: {result.duration_hours:.1f} hours")
    print(f"Total requests: {result.total_requests}")
    print(f"Success rate: {(result.successful_requests / result.total_requests * 100):.1f}%")
    print(f"Average response time: {result.avg_response_time:.3f}s")
    print(f"P95 response time: {result.p95_response_time:.3f}s")
    print(f"P99 response time: {result.p99_response_time:.3f}s")
    print(f"Memory leak detected: {'YES' if result.memory_leak_detected else 'NO'}")
    print(f"Performance degradation: {'YES' if result.performance_degradation else 'NO'}")
    print(f"Stability score: {result.stability_score:.1f}/100")
    
    # Exit with error code if stability issues detected
    if result.stability_score < 70:
        print("\nWARNING: Low stability score detected!")
        exit(1)
    elif result.memory_leak_detected or result.performance_degradation:
        print("\nWARNING: Stability issues detected!")
        exit(1)
    else:
        print("\nSoak test passed successfully!")

if __name__ == "__main__":
    asyncio.run(main())