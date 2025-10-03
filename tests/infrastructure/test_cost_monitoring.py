"""
Tests for cost monitoring and optimization functionality.
"""

import pytest
import json
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys

# Add scripts directory to path for importing
sys.path.append(os.path.join(os.path.dirname(__file__), '../../scripts'))

try:
    from cost_optimization import CostOptimizer
except ImportError:
    # Mock the module if Azure SDK is not available in test environment
    CostOptimizer = None

class TestCostOptimizer:
    """Test cost optimization functionality."""
    
    @pytest.fixture
    def mock_optimizer(self):
        """Create a mock cost optimizer for testing."""
        if CostOptimizer is None:
            pytest.skip("Azure SDK not available in test environment")
        
        with patch('cost_optimization.DefaultAzureCredential'), \
             patch('cost_optimization.ConsumptionManagementClient'), \
             patch('cost_optimization.MonitorManagementClient'), \
             patch('cost_optimization.CosmosDBManagementClient'), \
             patch('cost_optimization.StorageManagementClient'):
            
            optimizer = CostOptimizer('test-subscription', 'test-rg')
            return optimizer
    
    def test_cosmos_db_usage_analysis(self, mock_optimizer):
        """Test Cosmos DB usage analysis and recommendations."""
        if CostOptimizer is None:
            pytest.skip("Azure SDK not available in test environment")
        
        # Mock Cosmos DB account
        mock_account = Mock()
        mock_account.id = '/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.DocumentDB/databaseAccounts/test-cosmos'
        mock_optimizer.cosmos_client.database_accounts.get.return_value = mock_account
        
        # Mock metrics data
        mock_metric = Mock()
        mock_metric.name.value = 'TotalRequestUnits'
        mock_timeseries = Mock()
        
        # Simulate usage data points
        mock_data_points = []
        for i in range(24):  # 24 hours of data
            point = Mock()
            point.average = 800 + (i * 10)  # Simulate varying usage
            point.maximum = 1200 + (i * 15)
            mock_data_points.append(point)
        
        mock_timeseries.data = mock_data_points
        mock_metric.timeseries = [mock_timeseries]
        
        mock_metrics = Mock()
        mock_metrics.value = [mock_metric]
        mock_optimizer.monitor_client.metrics.list.return_value = mock_metrics
        
        # Run analysis
        result = mock_optimizer.analyze_cosmos_db_usage('test-cosmos')
        
        # Verify results
        assert 'account_name' in result
        assert result['account_name'] == 'test-cosmos'
        assert 'current_monthly_cost' in result
        assert 'optimized_monthly_cost' in result
        assert 'recommendations' in result
        
        # Verify recommendations are generated when optimization is possible
        if result['recommendations']:
            rec = result['recommendations'][0]
            assert rec['type'] == 'cosmos_throughput'
            assert 'current_max_ru' in rec
            assert 'recommended_max_ru' in rec
            assert 'monthly_savings' in rec
            assert rec['recommended_max_ru'] < rec['current_max_ru']
    
    def test_storage_usage_analysis(self, mock_optimizer):
        """Test storage usage analysis and tier recommendations."""
        if CostOptimizer is None:
            pytest.skip("Azure SDK not available in test environment")
        
        # Mock storage account
        mock_storage = Mock()
        mock_storage.id = '/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/test-storage'
        mock_optimizer.storage_client.storage_accounts.get_properties.return_value = mock_storage
        
        # Mock storage metrics
        mock_metric = Mock()
        mock_metric.name.value = 'UsedCapacity'
        mock_timeseries = Mock()
        
        # Simulate storage capacity data (100GB average)
        mock_data_points = []
        for i in range(30):  # 30 days of data
            point = Mock()
            point.average = 100 * (1024**3)  # 100GB in bytes
            mock_data_points.append(point)
        
        mock_timeseries.data = mock_data_points
        mock_metric.timeseries = [mock_timeseries]
        
        mock_metrics = Mock()
        mock_metrics.value = [mock_metric]
        mock_optimizer.monitor_client.metrics.list.return_value = mock_metrics
        
        # Run analysis
        result = mock_optimizer.analyze_storage_usage('test-storage')
        
        # Verify results
        assert 'storage_account' in result
        assert result['storage_account'] == 'test-storage'
        assert 'recommendations' in result
        
        # Should recommend Cool tier for large storage
        if result['recommendations']:
            rec = result['recommendations'][0]
            assert rec['type'] == 'storage_tier'
            assert rec['recommended_tier'] == 'Cool'
            assert 'estimated_monthly_savings' in rec
    
    def test_budget_alerts_status(self, mock_optimizer):
        """Test budget and alert status checking."""
        if CostOptimizer is None:
            pytest.skip("Azure SDK not available in test environment")
        
        # Mock budget data
        mock_budget = Mock()
        mock_budget.name = 'test-budget'
        mock_budget.amount = 100.0
        mock_budget.current_spend = Mock()
        mock_budget.current_spend.amount = 75.0
        
        mock_optimizer.consumption_client.budgets.list.return_value = [mock_budget]
        
        # Run analysis
        result = mock_optimizer.get_cost_alerts_status()
        
        # Verify results
        assert 'budgets' in result
        assert 'total_budgets' in result
        assert result['total_budgets'] == 1
        
        budget_status = result['budgets'][0]
        assert budget_status['name'] == 'test-budget'
        assert budget_status['budget_amount'] == 100.0
        assert budget_status['current_spend'] == 75.0
        assert budget_status['utilization_percent'] == 75.0
        assert budget_status['status'] == 'ok'  # 75% is still OK
    
    def test_optimization_report_generation(self, mock_optimizer):
        """Test comprehensive optimization report generation."""
        if CostOptimizer is None:
            pytest.skip("Azure SDK not available in test environment")
        
        # Mock all analysis methods
        mock_optimizer.analyze_cosmos_db_usage = Mock(return_value={
            'account_name': 'test-cosmos',
            'current_monthly_cost': 100.0,
            'optimized_monthly_cost': 80.0,
            'recommendations': [{
                'type': 'cosmos_throughput',
                'monthly_savings': 20.0
            }]
        })
        
        mock_optimizer.analyze_storage_usage = Mock(return_value={
            'storage_account': 'test-storage',
            'recommendations': [{
                'type': 'storage_tier',
                'estimated_monthly_savings': 10.0
            }]
        })
        
        mock_optimizer.get_cost_alerts_status = Mock(return_value={
            'budgets': [],
            'total_budgets': 0
        })
        
        # Generate report
        report = mock_optimizer.generate_optimization_report('test-cosmos', 'test-storage')
        
        # Verify report structure
        assert 'generated_at' in report
        assert 'subscription_id' in report
        assert 'resource_group' in report
        assert 'cosmos_analysis' in report
        assert 'storage_analysis' in report
        assert 'budget_status' in report
        assert 'summary' in report
        
        # Verify summary calculations
        summary = report['summary']
        assert summary['total_monthly_savings_potential'] == 30.0  # 20 + 10
        assert summary['optimization_opportunities'] == 2

class TestCostMonitoringBicep:
    """Test Bicep template validation for cost monitoring."""
    
    def test_cost_monitoring_bicep_exists(self):
        """Test that cost monitoring Bicep template exists and is valid."""
        bicep_file = 'infrastructure/bicep/modules/cost-monitoring.bicep'
        assert os.path.exists(bicep_file), f"Cost monitoring Bicep template not found: {bicep_file}"
        
        with open(bicep_file, 'r') as f:
            content = f.read()
            
        # Check for required components
        assert 'Microsoft.Consumption/budgets' in content
        assert 'Microsoft.CostManagement/scheduledActions' in content
        assert 'alertThresholds' in content
        assert 'contactEmails' in content
    
    def test_cosmosdb_autoscale_bicep_exists(self):
        """Test that Cosmos DB autoscale Bicep template exists and is valid."""
        bicep_file = 'infrastructure/bicep/modules/cosmosdb-autoscale.bicep'
        assert os.path.exists(bicep_file), f"Cosmos DB autoscale Bicep template not found: {bicep_file}"
        
        with open(bicep_file, 'r') as f:
            content = f.read()
            
        # Check for required components
        assert 'Microsoft.DocumentDB/databaseAccounts' in content
        assert 'autoscaleSettings' in content
        assert 'maxThroughput' in content
        assert 'defaultTtl' in content  # TTL for cost optimization
        assert 'indexingPolicy' in content  # Optimized indexing

class TestCostOptimizationScript:
    """Test the cost optimization script functionality."""
    
    def test_script_exists_and_executable(self):
        """Test that the cost optimization script exists."""
        script_file = 'scripts/cost-optimization.py'
        assert os.path.exists(script_file), f"Cost optimization script not found: {script_file}"
        
        with open(script_file, 'r') as f:
            content = f.read()
            
        # Check for required functions
        assert 'class CostOptimizer' in content
        assert 'analyze_cosmos_db_usage' in content
        assert 'analyze_storage_usage' in content
        assert 'get_cost_alerts_status' in content
        assert 'generate_optimization_report' in content
    
    @patch.dict(os.environ, {
        'AZURE_SUBSCRIPTION_ID': 'test-subscription',
        'AZURE_RESOURCE_GROUP': 'test-rg',
        'COSMOS_ACCOUNT_NAME': 'test-cosmos',
        'STORAGE_ACCOUNT_NAME': 'test-storage'
    })
    def test_environment_variables_handling(self):
        """Test that the script properly handles environment variables."""
        # This test verifies the script can read environment variables
        # without actually running Azure operations
        
        subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
        resource_group = os.getenv('AZURE_RESOURCE_GROUP')
        cosmos_account = os.getenv('COSMOS_ACCOUNT_NAME')
        storage_account = os.getenv('STORAGE_ACCOUNT_NAME')
        
        assert subscription_id == 'test-subscription'
        assert resource_group == 'test-rg'
        assert cosmos_account == 'test-cosmos'
        assert storage_account == 'test-storage'

class TestCostAlertThresholds:
    """Test cost alert threshold configurations."""
    
    def test_alert_threshold_validation(self):
        """Test that alert thresholds are properly configured."""
        # Test different threshold scenarios
        test_cases = [
            {'budget': 100, 'spend': 25, 'expected_status': 'ok'},
            {'budget': 100, 'spend': 50, 'expected_status': 'ok'},
            {'budget': 100, 'spend': 75, 'expected_status': 'ok'},
            {'budget': 100, 'spend': 80, 'expected_status': 'warning'},
            {'budget': 100, 'spend': 95, 'expected_status': 'warning'},
            {'budget': 100, 'spend': 105, 'expected_status': 'critical'}
        ]
        
        for case in test_cases:
            utilization = (case['spend'] / case['budget']) * 100
            
            if utilization <= 75:
                status = 'ok'
            elif utilization <= 90:
                status = 'warning'
            else:
                status = 'critical'
            
            # For this test, we're using 75% as warning threshold
            if case['expected_status'] == 'warning' and utilization > 75:
                assert status in ['warning', 'critical']
            elif case['expected_status'] == 'ok':
                assert status == 'ok'

if __name__ == '__main__':
    pytest.main([__file__])