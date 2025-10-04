"""
Load testing suite for ComicGuess application.
Tests API endpoints under realistic load conditions.
"""

import asyncio
import aiohttp
import time
import statistics
import json
import logging
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class LoadTestResult:
    """Results from a load test run."""
    endpoint: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    p95_response_time: float
    p99_response_time: float
    requests_per_second: float
    error_rate: float
    errors: List[str]

class LoadTester:
    """Load testing utility for ComicGuess API."""
    
    def __init__(self, base_url: str, max_concurrent: int = 50):
        self.base_url = base_url.rstrip('/')
        self.max_concurrent = max_concurrent
        self.session = None
        
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=self.max_concurrent)
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make a single HTTP request and measure response time."""
        start_time = time.time()
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with self.session.request(method, url, **kwargs) as response:
                response_time = time.time() - start_time
                content = await response.text()
                
                return {
                    'success': True,
                    'status_code': response.status,
                    'response_time': response_time,
                    'content_length': len(content),
                    'error': None
                }
        except Exception as e:
            response_time = time.time() - start_time
            return {
                'success': False,
                'status_code': 0,
                'response_time': response_time,
                'content_length': 0,
                'error': str(e)
            }
    
    async def run_load_test(
        self,
        endpoint: str,
        method: str = 'GET',
        duration_seconds: int = 60,
        requests_per_second: int = 10,
        **request_kwargs
    ) -> LoadTestResult:
        """Run a load test against a specific endpoint."""
        logger.info(f"Starting load test: {method} {endpoint}")
        logger.info(f"Duration: {duration_seconds}s, Target RPS: {requests_per_second}")
        
        results = []
        errors = []
        start_time = time.time()
        request_interval = 1.0 / requests_per_second
        
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def make_limited_request():
            async with semaphore:
                result = await self.make_request(method, endpoint, **request_kwargs)
                results.append(result)
                if not result['success']:
                    errors.append(result['error'])
                return result
        
        # Generate requests at target rate
        tasks = []
        while time.time() - start_time < duration_seconds:
            task = asyncio.create_task(make_limited_request())
            tasks.append(task)
            
            # Wait for next request interval
            await asyncio.sleep(request_interval)
        
        # Wait for all remaining requests to complete
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Calculate statistics
        total_requests = len(results)
        successful_requests = sum(1 for r in results if r['success'])
        failed_requests = total_requests - successful_requests
        
        response_times = [r['response_time'] for r in results]
        avg_response_time = statistics.mean(response_times) if response_times else 0
        p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) > 20 else 0
        p99_response_time = statistics.quantiles(response_times, n=100)[98] if len(response_times) > 100 else 0
        
        actual_duration = time.time() - start_time
        actual_rps = total_requests / actual_duration if actual_duration > 0 else 0
        error_rate = (failed_requests / total_requests * 100) if total_requests > 0 else 0
        
        return LoadTestResult(
            endpoint=endpoint,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time=avg_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            requests_per_second=actual_rps,
            error_rate=error_rate,
            errors=errors[:10]  # Keep only first 10 errors
        )

class ComicGuessLoadTest:
    """Specific load tests for ComicGuess application."""
    
    def __init__(self, api_base_url: str, frontend_base_url: str = None):
        self.api_base_url = api_base_url
        self.frontend_base_url = frontend_base_url
        self.test_users = self._generate_test_users()
        self.universes = ['marvel', 'DC', 'image']
        
    def _generate_test_users(self) -> List[str]:
        """Generate test user IDs for load testing."""
        return [f"load-test-user-{i:04d}" for i in range(1000)]
    
    def _get_random_guess(self) -> str:
        """Get a random character guess for testing."""
        characters = [
            'Spider-Man', 'Batman', 'Superman', 'Wonder Woman', 'Iron Man',
            'Captain America', 'The Flash', 'Green Lantern', 'Wolverine',
            'Deadpool', 'Spawn', 'Invincible', 'The Walking Dead'
        ]
        return random.choice(characters)
    
    async def test_puzzle_endpoint_load(self, duration: int = 300) -> LoadTestResult:
        """Test the daily puzzle endpoint under load."""
        async with LoadTester(self.api_base_url, max_concurrent=100) as tester:
            # Simulate realistic traffic: 50% Marvel, 30% DC, 20% Image
            universe_weights = {'marvel': 0.5, 'DC': 0.3, 'image': 0.2}
            universe = random.choices(
                list(universe_weights.keys()),
                weights=list(universe_weights.values())
            )[0]
            
            return await tester.run_load_test(
                endpoint=f'/puzzle/today?universe={universe}',
                method='GET',
                duration_seconds=duration,
                requests_per_second=20  # Target 20 RPS for puzzle fetching
            )
    
    async def test_guess_endpoint_load(self, duration: int = 300) -> LoadTestResult:
        """Test the guess submission endpoint under load."""
        async with LoadTester(self.api_base_url, max_concurrent=50) as tester:
            # Prepare request data
            user_id = random.choice(self.test_users)
            universe = random.choice(self.universes)
            guess = self._get_random_guess()
            
            request_data = {
                'userId': user_id,
                'universe': universe,
                'guess': guess
            }
            
            return await tester.run_load_test(
                endpoint='/guess',
                method='POST',
                duration_seconds=duration,
                requests_per_second=10,  # Target 10 RPS for guess submissions
                json=request_data,
                headers={'Content-Type': 'application/json'}
            )
    
    async def test_user_stats_load(self, duration: int = 180) -> LoadTestResult:
        """Test user statistics endpoint under load."""
        async with LoadTester(self.api_base_url, max_concurrent=30) as tester:
            user_id = random.choice(self.test_users)
            
            return await tester.run_load_test(
                endpoint=f'/user/{user_id}/stats',
                method='GET',
                duration_seconds=duration,
                requests_per_second=5  # Lower RPS for stats
            )
    
    async def test_cache_effectiveness(self, duration: int = 120) -> Dict[str, Any]:
        """Test cache effectiveness under load."""
        cache_results = {}
        
        # Test same puzzle endpoint repeatedly to measure cache hits
        async with LoadTester(self.api_base_url, max_concurrent=50) as tester:
            # First request (cache miss)
            start_time = time.time()
            first_result = await tester.make_request('GET', '/puzzle/today?universe=marvel')
            first_response_time = first_result['response_time']
            
            # Subsequent requests (should be cache hits)
            cache_hit_times = []
            for _ in range(100):
                result = await tester.make_request('GET', '/puzzle/today?universe=marvel')
                if result['success']:
                    cache_hit_times.append(result['response_time'])
                await asyncio.sleep(0.1)  # Small delay between requests
            
            avg_cache_hit_time = statistics.mean(cache_hit_times) if cache_hit_times else 0
            cache_improvement = ((first_response_time - avg_cache_hit_time) / first_response_time * 100) if first_response_time > 0 else 0
            
            cache_results = {
                'first_request_time': first_response_time,
                'avg_cache_hit_time': avg_cache_hit_time,
                'cache_improvement_percent': cache_improvement,
                'cache_hit_requests': len(cache_hit_times)
            }
        
        return cache_results
    
    async def run_comprehensive_load_test(self) -> Dict[str, Any]:
        """Run comprehensive load test suite."""
        logger.info("Starting comprehensive load test suite")
        
        results = {
            'test_start_time': datetime.utcnow().isoformat(),
            'test_configuration': {
                'api_base_url': self.api_base_url,
                'test_users_count': len(self.test_users),
                'universes': self.universes
            }
        }
        
        # Run individual load tests
        logger.info("Testing puzzle endpoint load...")
        results['puzzle_load_test'] = await self.test_puzzle_endpoint_load(duration=300)
        
        logger.info("Testing guess endpoint load...")
        results['guess_load_test'] = await self.test_guess_endpoint_load(duration=300)
        
        logger.info("Testing user stats load...")
        results['stats_load_test'] = await self.test_user_stats_load(duration=180)
        
        logger.info("Testing cache effectiveness...")
        results['cache_effectiveness'] = await self.test_cache_effectiveness(duration=120)
        
        # Calculate overall performance metrics
        all_tests = [results['puzzle_load_test'], results['guess_load_test'], results['stats_load_test']]
        
        results['summary'] = {
            'total_requests': sum(test.total_requests for test in all_tests),
            'total_successful': sum(test.successful_requests for test in all_tests),
            'overall_error_rate': sum(test.error_rate * test.total_requests for test in all_tests) / sum(test.total_requests for test in all_tests),
            'avg_response_time': sum(test.avg_response_time * test.total_requests for test in all_tests) / sum(test.total_requests for test in all_tests),
            'max_p99_response_time': max(test.p99_response_time for test in all_tests)
        }
        
        results['test_end_time'] = datetime.utcnow().isoformat()
        
        return results

async def main():
    """Main function to run load tests."""
    import os
    
    api_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
    frontend_url = os.getenv('FRONTEND_BASE_URL', 'http://localhost:3000')
    
    load_test = ComicGuessLoadTest(api_url, frontend_url)
    results = await load_test.run_comprehensive_load_test()
    
    # Save results to file
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    results_file = f'load-test-results-{timestamp}.json'
    
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    logger.info(f"Load test results saved to {results_file}")
    
    # Print summary
    print("\n=== LOAD TEST SUMMARY ===")
    summary = results['summary']
    print(f"Total requests: {summary['total_requests']}")
    print(f"Successful requests: {summary['total_successful']}")
    print(f"Overall error rate: {summary['overall_error_rate']:.2f}%")
    print(f"Average response time: {summary['avg_response_time']:.3f}s")
    print(f"Max P99 response time: {summary['max_p99_response_time']:.3f}s")
    
    # Cache effectiveness
    cache_info = results['cache_effectiveness']
    print(f"\nCache improvement: {cache_info['cache_improvement_percent']:.1f}%")
    print(f"First request: {cache_info['first_request_time']:.3f}s")
    print(f"Avg cache hit: {cache_info['avg_cache_hit_time']:.3f}s")

if __name__ == "__main__":
    asyncio.run(main())