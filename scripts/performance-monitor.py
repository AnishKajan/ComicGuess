#!/usr/bin/env python3
"""
Performance monitoring and optimization script for ComicGuess.
Monitors application performance and provides optimization recommendations.
"""

import asyncio
import aiohttp
import time
import json
import logging
import statistics
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetric:
    """Individual performance metric measurement."""
    timestamp: str
    endpoint: str
    response_time: float
    status_code: int
    cache_hit: bool
    content_length: int

@dataclass
class PerformanceReport:
    """Performance analysis report."""
    generated_at: str
    test_duration_minutes: float
    endpoints_tested: List[str]
    total_requests: int
    avg_response_time: float
    p95_response_time: float
    p99_response_time: float
    cache_hit_rate: float
    error_rate: float
    recommendations: List[str]
    detailed_metrics: Dict[str, Any]

class PerformanceMonitor:
    """Performance monitoring utility."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = None
        self.metrics = []
        
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=10)
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def measure_endpoint_performance(
        self,
        endpoint: str,
        method: str = 'GET',
        samples: int = 100,
        **kwargs
    ) -> List[PerformanceMetric]:
        """Measure performance of a specific endpoint."""
        logger.info(f"Measuring performance: {method} {endpoint} ({samples} samples)")
        
        endpoint_metrics = []
        
        for i in range(samples):
            start_time = time.time()
            
            try:
                url = f"{self.base_url}{endpoint}"
                async with self.session.request(method, url, **kwargs) as response:
                    content = await response.text()
                    response_time = time.time() - start_time
                    
                    # Detect cache hits by response time and headers
                    cache_hit = (
                        response_time < 0.1 or  # Very fast response likely cached
                        'x-cache' in response.headers or
                        'cf-cache-status' in response.headers
                    )
                    
                    metric = PerformanceMetric(
                        timestamp=datetime.utcnow().isoformat(),
                        endpoint=endpoint,
                        response_time=response_time,
                        status_code=response.status,
                        cache_hit=cache_hit,
                        content_length=len(content)
                    )
                    
                    endpoint_metrics.append(metric)
                    self.metrics.append(metric)
                    
            except Exception as e:
                logger.warning(f"Request failed: {e}")
                metric = PerformanceMetric(
                    timestamp=datetime.utcnow().isoformat(),
                    endpoint=endpoint,
                    response_time=time.time() - start_time,
                    status_code=0,
                    cache_hit=False,
                    content_length=0
                )
                endpoint_metrics.append(metric)
                self.metrics.append(metric)
            
            # Small delay between requests
            if i < samples - 1:
                await asyncio.sleep(0.1)
        
        return endpoint_metrics
    
    def analyze_cache_performance(self, endpoint_metrics: List[PerformanceMetric]) -> Dict[str, Any]:
        """Analyze cache performance for an endpoint."""
        if not endpoint_metrics:
            return {}
        
        cache_hits = [m for m in endpoint_metrics if m.cache_hit]
        cache_misses = [m for m in endpoint_metrics if not m.cache_hit]
        
        cache_hit_rate = (len(cache_hits) / len(endpoint_metrics)) * 100
        
        avg_cache_hit_time = statistics.mean([m.response_time for m in cache_hits]) if cache_hits else 0
        avg_cache_miss_time = statistics.mean([m.response_time for m in cache_misses]) if cache_misses else 0
        
        cache_improvement = 0
        if avg_cache_miss_time > 0:
            cache_improvement = ((avg_cache_miss_time - avg_cache_hit_time) / avg_cache_miss_time) * 100
        
        return {
            'cache_hit_rate': cache_hit_rate,
            'avg_cache_hit_time': avg_cache_hit_time,
            'avg_cache_miss_time': avg_cache_miss_time,
            'cache_improvement_percent': cache_improvement,
            'total_requests': len(endpoint_metrics),
            'cache_hits': len(cache_hits),
            'cache_misses': len(cache_misses)
        }
    
    def generate_recommendations(self, metrics_by_endpoint: Dict[str, List[PerformanceMetric]]) -> List[str]:
        """Generate performance optimization recommendations."""
        recommendations = []
        
        for endpoint, metrics in metrics_by_endpoint.items():
            if not metrics:
                continue
            
            response_times = [m.response_time for m in metrics if m.status_code < 400]
            error_rate = (len([m for m in metrics if m.status_code >= 400]) / len(metrics)) * 100
            
            if not response_times:
                continue
            
            avg_response_time = statistics.mean(response_times)
            p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) > 20 else 0
            
            # Response time recommendations
            if avg_response_time > 1.0:
                recommendations.append(f"{endpoint}: High average response time ({avg_response_time:.3f}s). Consider caching or optimization.")
            
            if p95_response_time > 2.0:
                recommendations.append(f"{endpoint}: High P95 response time ({p95_response_time:.3f}s). Investigate slow queries or operations.")
            
            # Error rate recommendations
            if error_rate > 5.0:
                recommendations.append(f"{endpoint}: High error rate ({error_rate:.1f}%). Check error handling and system stability.")
            
            # Cache recommendations
            cache_analysis = self.analyze_cache_performance(metrics)
            if cache_analysis.get('cache_hit_rate', 0) < 50:
                recommendations.append(f"{endpoint}: Low cache hit rate ({cache_analysis.get('cache_hit_rate', 0):.1f}%). Review caching strategy.")
            
            # Content size recommendations
            avg_content_size = statistics.mean([m.content_length for m in metrics])
            if avg_content_size > 100000:  # 100KB
                recommendations.append(f"{endpoint}: Large response size ({avg_content_size/1024:.1f}KB). Consider response compression or pagination.")
        
        return recommendations
    
    async def run_comprehensive_performance_test(self, duration_minutes: float = 10.0) -> PerformanceReport:
        """Run comprehensive performance test across all endpoints."""
        logger.info(f"Starting comprehensive performance test ({duration_minutes} minutes)")
        
        # Define endpoints to test
        test_endpoints = [
            {'endpoint': '/puzzle/today?universe=marvel', 'method': 'GET'},
            {'endpoint': '/puzzle/today?universe=DC', 'method': 'GET'},
            {'endpoint': '/puzzle/today?universe=image', 'method': 'GET'},
            {
                'endpoint': '/guess',
                'method': 'POST',
                'json': {
                    'userId': 'perf-test-user',
                    'universe': 'marvel',
                    'guess': 'Spider-Man'
                },
                'headers': {'Content-Type': 'application/json'}
            },
            {'endpoint': '/user/perf-test-user/stats', 'method': 'GET'}
        ]
        
        # Calculate samples per endpoint based on duration
        samples_per_endpoint = max(10, int((duration_minutes * 60) / (len(test_endpoints) * 0.2)))
        
        metrics_by_endpoint = {}
        
        for test_config in test_endpoints:
            endpoint = test_config['endpoint']
            method = test_config.get('method', 'GET')
            
            # Extract request parameters
            request_params = {k: v for k, v in test_config.items() if k not in ['endpoint', 'method']}
            
            endpoint_metrics = await self.measure_endpoint_performance(
                endpoint, method, samples_per_endpoint, **request_params
            )
            metrics_by_endpoint[endpoint] = endpoint_metrics
        
        # Analyze overall performance
        all_successful_metrics = [
            m for metrics in metrics_by_endpoint.values()
            for m in metrics if m.status_code < 400
        ]
        
        if not all_successful_metrics:
            logger.error("No successful requests recorded")
            return PerformanceReport(
                generated_at=datetime.utcnow().isoformat(),
                test_duration_minutes=duration_minutes,
                endpoints_tested=[],
                total_requests=0,
                avg_response_time=0,
                p95_response_time=0,
                p99_response_time=0,
                cache_hit_rate=0,
                error_rate=100,
                recommendations=["Critical: No successful requests. Check system availability."],
                detailed_metrics={}
            )
        
        response_times = [m.response_time for m in all_successful_metrics]
        avg_response_time = statistics.mean(response_times)
        p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) > 20 else 0
        p99_response_time = statistics.quantiles(response_times, n=100)[98] if len(response_times) > 100 else 0
        
        # Calculate cache hit rate
        total_requests = len(self.metrics)
        cache_hits = len([m for m in self.metrics if m.cache_hit])
        cache_hit_rate = (cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        # Calculate error rate
        error_requests = len([m for m in self.metrics if m.status_code >= 400])
        error_rate = (error_requests / total_requests * 100) if total_requests > 0 else 0
        
        # Generate recommendations
        recommendations = self.generate_recommendations(metrics_by_endpoint)
        
        # Detailed metrics by endpoint
        detailed_metrics = {}
        for endpoint, metrics in metrics_by_endpoint.items():
            if metrics:
                successful_metrics = [m for m in metrics if m.status_code < 400]
                if successful_metrics:
                    endpoint_response_times = [m.response_time for m in successful_metrics]
                    detailed_metrics[endpoint] = {
                        'total_requests': len(metrics),
                        'successful_requests': len(successful_metrics),
                        'avg_response_time': statistics.mean(endpoint_response_times),
                        'p95_response_time': statistics.quantiles(endpoint_response_times, n=20)[18] if len(endpoint_response_times) > 20 else 0,
                        'cache_analysis': self.analyze_cache_performance(metrics)
                    }
        
        return PerformanceReport(
            generated_at=datetime.utcnow().isoformat(),
            test_duration_minutes=duration_minutes,
            endpoints_tested=list(metrics_by_endpoint.keys()),
            total_requests=total_requests,
            avg_response_time=avg_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            cache_hit_rate=cache_hit_rate,
            error_rate=error_rate,
            recommendations=recommendations,
            detailed_metrics=detailed_metrics
        )

async def main():
    """Main function to run performance monitoring."""
    api_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
    duration = float(os.getenv('PERF_TEST_DURATION_MINUTES', '5.0'))
    
    async with PerformanceMonitor(api_url) as monitor:
        report = await monitor.run_comprehensive_performance_test(duration_minutes=duration)
    
    # Save report
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    report_file = f'performance-report-{timestamp}.json'
    
    with open(report_file, 'w') as f:
        json.dump(asdict(report), f, indent=2, default=str)
    
    logger.info(f"Performance report saved to {report_file}")
    
    # Print summary
    print("\n=== PERFORMANCE REPORT SUMMARY ===")
    print(f"Test duration: {report.test_duration_minutes:.1f} minutes")
    print(f"Total requests: {report.total_requests}")
    print(f"Average response time: {report.avg_response_time:.3f}s")
    print(f"P95 response time: {report.p95_response_time:.3f}s")
    print(f"P99 response time: {report.p99_response_time:.3f}s")
    print(f"Cache hit rate: {report.cache_hit_rate:.1f}%")
    print(f"Error rate: {report.error_rate:.1f}%")
    
    if report.recommendations:
        print("\nRECOMMENDATIONS:")
        for i, rec in enumerate(report.recommendations, 1):
            print(f"{i}. {rec}")
    else:
        print("\nNo performance issues detected!")
    
    # Print detailed endpoint metrics
    print("\nENDPOINT DETAILS:")
    for endpoint, metrics in report.detailed_metrics.items():
        print(f"\n{endpoint}:")
        print(f"  Requests: {metrics['successful_requests']}/{metrics['total_requests']}")
        print(f"  Avg response time: {metrics['avg_response_time']:.3f}s")
        print(f"  P95 response time: {metrics['p95_response_time']:.3f}s")
        if 'cache_analysis' in metrics:
            cache = metrics['cache_analysis']
            print(f"  Cache hit rate: {cache.get('cache_hit_rate', 0):.1f}%")

if __name__ == "__main__":
    asyncio.run(main())