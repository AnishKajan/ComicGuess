"""
Tests for performance testing suite functionality.
"""

import pytest
import asyncio
import json
import os
import tempfile
from unittest.mock import Mock, patch, AsyncMock
import sys

# Add scripts and performance test directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../scripts'))
sys.path.append(os.path.dirname(__file__))

try:
    from performance_monitor import PerformanceMonitor, PerformanceMetric, PerformanceReport
    from load_test import LoadTester, ComicGuessLoadTest
    from soak_test import SoakTester, ComicGuessSoakTest
except ImportError:
    # Mock modules if dependencies are not available
    PerformanceMonitor = None
    PerformanceMetric = None
    PerformanceReport = None
    LoadTester = None
    ComicGuessLoadTest = None
    SoakTester = None
    ComicGuessSoakTest = None

class TestPerformanceMonitor:
    """Test performance monitoring functionality."""
    
    @pytest.fixture
    def mock_monitor(self):
        """Create a mock performance monitor."""
        if PerformanceMonitor is None:
            pytest.skip("Performance monitoring dependencies not available")
        
        return PerformanceMonitor('http://localhost:8000')
    
    def test_performance_metric_creation(self):
        """Test performance metric data structure."""
        if PerformanceMetric is None:
            pytest.skip("Performance monitoring dependencies not available")
        
        metric = PerformanceMetric(
            timestamp='2024-01-01T00:00:00',
            endpoint='/test',
            response_time=0.5,
            status_code=200,
            cache_hit=True,
            content_length=1024
        )
        
        assert metric.endpoint == '/test'
        assert metric.response_time == 0.5
        assert metric.status_code == 200
        assert metric.cache_hit is True
        assert metric.content_length == 1024
    
    @pytest.mark.asyncio
    async def test_endpoint_performance_measurement(self, mock_monitor):
        """Test endpoint performance measurement."""
        if PerformanceMonitor is None:
            pytest.skip("Performance monitoring dependencies not available")
        
        # Mock aiohttp session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value='{"test": "data"}')
        mock_response.headers = {}
        
        mock_session = AsyncMock()
        mock_session.request = AsyncMock()
        mock_session.request.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.request.return_value.__aexit__ = AsyncMock(return_value=None)
        
        mock_monitor.session = mock_session
        
        # Test measurement
        metrics = await mock_monitor.measure_endpoint_performance('/test', samples=5)
        
        assert len(metrics) == 5
        assert all(isinstance(m, PerformanceMetric) for m in metrics)
        assert all(m.endpoint == '/test' for m in metrics)
        assert all(m.status_code == 200 for m in metrics)
    
    def test_cache_performance_analysis(self, mock_monitor):
        """Test cache performance analysis."""
        if PerformanceMonitor is None:
            pytest.skip("Performance monitoring dependencies not available")
        
        # Create test metrics with mix of cache hits and misses
        metrics = [
            PerformanceMetric('2024-01-01T00:00:00', '/test', 0.1, 200, True, 1024),   # Cache hit
            PerformanceMetric('2024-01-01T00:00:01', '/test', 0.5, 200, False, 1024),  # Cache miss
            PerformanceMetric('2024-01-01T00:00:02', '/test', 0.1, 200, True, 1024),   # Cache hit
            PerformanceMetric('2024-01-01T00:00:03', '/test', 0.6, 200, False, 1024),  # Cache miss
        ]
        
        analysis = mock_monitor.analyze_cache_performance(metrics)
        
        assert analysis['cache_hit_rate'] == 50.0  # 2 out of 4
        assert analysis['avg_cache_hit_time'] == 0.1
        assert analysis['avg_cache_miss_time'] == 0.55
        assert analysis['cache_improvement_percent'] > 80  # Significant improvement
        assert analysis['total_requests'] == 4
        assert analysis['cache_hits'] == 2
        assert analysis['cache_misses'] == 2
    
    def test_performance_recommendations(self, mock_monitor):
        """Test performance recommendation generation."""
        if PerformanceMonitor is None:
            pytest.skip("Performance monitoring dependencies not available")
        
        # Create metrics with performance issues
        slow_metrics = [
            PerformanceMetric('2024-01-01T00:00:00', '/slow', 2.0, 200, False, 1024),
            PerformanceMetric('2024-01-01T00:00:01', '/slow', 2.5, 200, False, 1024),
            PerformanceMetric('2024-01-01T00:00:02', '/slow', 3.0, 500, False, 1024),  # Error
        ]
        
        error_metrics = [
            PerformanceMetric('2024-01-01T00:00:00', '/error', 0.5, 500, False, 1024),
            PerformanceMetric('2024-01-01T00:00:01', '/error', 0.5, 404, False, 1024),
        ]
        
        metrics_by_endpoint = {
            '/slow': slow_metrics,
            '/error': error_metrics
        }
        
        recommendations = mock_monitor.generate_recommendations(metrics_by_endpoint)
        
        # Should have recommendations for slow endpoint and high error rate
        assert len(recommendations) > 0
        assert any('slow' in rec and 'response time' in rec for rec in recommendations)
        assert any('error' in rec and 'error rate' in rec for rec in recommendations)

class TestLoadTester:
    """Test load testing functionality."""
    
    @pytest.fixture
    def mock_load_tester(self):
        """Create a mock load tester."""
        if LoadTester is None:
            pytest.skip("Load testing dependencies not available")
        
        return LoadTester('http://localhost:8000', max_concurrent=10)
    
    @pytest.mark.asyncio
    async def test_load_test_request(self, mock_load_tester):
        """Test individual load test request."""
        if LoadTester is None:
            pytest.skip("Load testing dependencies not available")
        
        # Mock aiohttp session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value='test response')
        
        mock_session = AsyncMock()
        mock_session.request = AsyncMock()
        mock_session.request.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.request.return_value.__aexit__ = AsyncMock(return_value=None)
        
        mock_load_tester.session = mock_session
        
        result = await mock_load_tester.make_request('GET', '/test')
        
        assert result['success'] is True
        assert result['status_code'] == 200
        assert result['response_time'] > 0
        assert result['content_length'] > 0
        assert result['error'] is None
    
    def test_comic_guess_load_test_initialization(self):
        """Test ComicGuess load test initialization."""
        if ComicGuessLoadTest is None:
            pytest.skip("Load testing dependencies not available")
        
        load_test = ComicGuessLoadTest('http://localhost:8000')
        
        assert load_test.api_base_url == 'http://localhost:8000'
        assert len(load_test.test_users) == 1000
        assert load_test.universes == ['marvel', 'DC', 'image']
        assert len(load_test._get_random_guess()) > 0

class TestSoakTester:
    """Test soak testing functionality."""
    
    @pytest.fixture
    def mock_soak_tester(self):
        """Create a mock soak tester."""
        if SoakTester is None:
            pytest.skip("Soak testing dependencies not available")
        
        return SoakTester('http://localhost:8000', max_concurrent=5)
    
    def test_system_metrics_collection(self, mock_soak_tester):
        """Test system metrics collection."""
        if SoakTester is None:
            pytest.skip("Soak testing dependencies not available")
        
        with patch('psutil.Process') as mock_process:
            mock_proc_instance = Mock()
            mock_proc_instance.memory_info.return_value.rss = 100 * 1024 * 1024  # 100MB
            mock_proc_instance.cpu_percent.return_value = 25.0
            mock_proc_instance.open_files.return_value = []
            mock_proc_instance.connections.return_value = []
            mock_process.return_value = mock_proc_instance
            
            metrics = mock_soak_tester.collect_system_metrics()
            
            assert 'memory_usage_mb' in metrics
            assert 'cpu_usage_percent' in metrics
            assert 'open_files' in metrics
            assert 'connections' in metrics
            assert metrics['memory_usage_mb'] == 100.0
            assert metrics['cpu_usage_percent'] == 25.0
    
    def test_memory_leak_detection(self, mock_soak_tester):
        """Test memory leak detection algorithm."""
        if SoakTester is None:
            pytest.skip("Soak testing dependencies not available")
        
        from soak_test import SoakTestMetrics
        from datetime import datetime, timedelta
        
        # Create metrics showing memory increase over time
        base_time = datetime.utcnow()
        mock_soak_tester.metrics_history = []
        
        for i in range(100):
            timestamp = (base_time - timedelta(minutes=i)).isoformat()
            memory_usage = 100 + (i * 2)  # Increasing memory usage
            
            metric = SoakTestMetrics(
                timestamp=timestamp,
                response_time=0.5,
                memory_usage_mb=memory_usage,
                cpu_usage_percent=25.0,
                active_connections=10,
                error_count=0,
                success_count=1
            )
            mock_soak_tester.metrics_history.append(metric)
        
        # Should detect memory leak due to increasing trend
        leak_detected = mock_soak_tester.detect_memory_leak(window_hours=2.0)
        assert leak_detected is True
    
    def test_performance_degradation_detection(self, mock_soak_tester):
        """Test performance degradation detection."""
        if SoakTester is None:
            pytest.skip("Soak testing dependencies not available")
        
        from soak_test import SoakTestMetrics
        from datetime import datetime
        
        # Create metrics showing performance degradation
        mock_soak_tester.metrics_history = []
        
        # First hour: good performance
        for i in range(50):
            metric = SoakTestMetrics(
                timestamp=datetime.utcnow().isoformat(),
                response_time=0.2,  # Fast responses
                memory_usage_mb=100,
                cpu_usage_percent=25.0,
                active_connections=10,
                error_count=0,
                success_count=1
            )
            mock_soak_tester.metrics_history.append(metric)
        
        # Last hour: degraded performance
        for i in range(50):
            metric = SoakTestMetrics(
                timestamp=datetime.utcnow().isoformat(),
                response_time=1.0,  # Slow responses
                memory_usage_mb=100,
                cpu_usage_percent=25.0,
                active_connections=10,
                error_count=0,
                success_count=1
            )
            mock_soak_tester.metrics_history.append(metric)
        
        # Should detect performance degradation
        degradation_detected = mock_soak_tester.detect_performance_degradation()
        assert degradation_detected is True

class TestPerformanceTestFiles:
    """Test that performance test files exist and are properly structured."""
    
    def test_load_test_file_exists(self):
        """Test that load test file exists."""
        load_test_file = os.path.join(os.path.dirname(__file__), 'load_test.py')
        assert os.path.exists(load_test_file)
        
        with open(load_test_file, 'r') as f:
            content = f.read()
        
        # Check for required classes and functions
        assert 'class LoadTester' in content
        assert 'class ComicGuessLoadTest' in content
        assert 'async def run_load_test' in content
        assert 'async def test_puzzle_endpoint_load' in content
    
    def test_soak_test_file_exists(self):
        """Test that soak test file exists."""
        soak_test_file = os.path.join(os.path.dirname(__file__), 'soak_test.py')
        assert os.path.exists(soak_test_file)
        
        with open(soak_test_file, 'r') as f:
            content = f.read()
        
        # Check for required classes and functions
        assert 'class SoakTester' in content
        assert 'class ComicGuessSoakTest' in content
        assert 'detect_memory_leak' in content
        assert 'detect_performance_degradation' in content
    
    def test_performance_monitor_file_exists(self):
        """Test that performance monitor script exists."""
        monitor_file = os.path.join(os.path.dirname(__file__), '../../scripts/performance-monitor.py')
        assert os.path.exists(monitor_file)
        
        with open(monitor_file, 'r') as f:
            content = f.read()
        
        # Check for required classes and functions
        assert 'class PerformanceMonitor' in content
        assert 'async def measure_endpoint_performance' in content
        assert 'def analyze_cache_performance' in content
        assert 'def generate_recommendations' in content

class TestPerformanceBenchmarks:
    """Test performance benchmarks and thresholds."""
    
    def test_response_time_thresholds(self):
        """Test response time threshold validation."""
        # Define acceptable response time thresholds
        thresholds = {
            'excellent': 0.1,    # 100ms
            'good': 0.5,         # 500ms
            'acceptable': 1.0,   # 1s
            'poor': 2.0,         # 2s
            'unacceptable': 5.0  # 5s
        }
        
        test_cases = [
            {'response_time': 0.05, 'expected': 'excellent'},
            {'response_time': 0.3, 'expected': 'good'},
            {'response_time': 0.8, 'expected': 'acceptable'},
            {'response_time': 1.5, 'expected': 'poor'},
            {'response_time': 6.0, 'expected': 'unacceptable'}
        ]
        
        for case in test_cases:
            response_time = case['response_time']
            
            if response_time <= thresholds['excellent']:
                category = 'excellent'
            elif response_time <= thresholds['good']:
                category = 'good'
            elif response_time <= thresholds['acceptable']:
                category = 'acceptable'
            elif response_time <= thresholds['poor']:
                category = 'poor'
            else:
                category = 'unacceptable'
            
            assert category == case['expected'], f"Response time {response_time}s should be {case['expected']}, got {category}"
    
    def test_cache_hit_rate_thresholds(self):
        """Test cache hit rate threshold validation."""
        test_cases = [
            {'hit_rate': 95, 'expected': 'excellent'},
            {'hit_rate': 80, 'expected': 'good'},
            {'hit_rate': 60, 'expected': 'acceptable'},
            {'hit_rate': 30, 'expected': 'poor'},
            {'hit_rate': 10, 'expected': 'unacceptable'}
        ]
        
        for case in test_cases:
            hit_rate = case['hit_rate']
            
            if hit_rate >= 90:
                category = 'excellent'
            elif hit_rate >= 70:
                category = 'good'
            elif hit_rate >= 50:
                category = 'acceptable'
            elif hit_rate >= 25:
                category = 'poor'
            else:
                category = 'unacceptable'
            
            assert category == case['expected'], f"Cache hit rate {hit_rate}% should be {case['expected']}, got {category}"

if __name__ == '__main__':
    pytest.main([__file__])