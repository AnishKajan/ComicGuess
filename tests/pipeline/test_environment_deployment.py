"""
Tests for environment deployment functionality.
"""
import os
import yaml
import pytest
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# Add the scripts directory to the path
scripts_dir = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

try:
    from deploy_environment import EnvironmentDeployer
except ImportError:
    # Create a mock class for testing if the module can't be imported
    class EnvironmentDeployer:
        def __init__(self, environment, config_dir="environments"):
            self.environment = environment
            self.config_dir = Path(config_dir)
            self.config = {'name': environment}


class TestEnvironmentDeployer:
    """Test the EnvironmentDeployer class."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock environment configuration."""
        return {
            'name': 'test',
            'azure': {
                'resource_group': 'test-rg',
                'location': 'eastus',
                'app_service': {
                    'name': 'test-app',
                    'sku': 'B1',
                    'instances': 1
                },
                'cosmos_db': {
                    'account_name': 'test-cosmos',
                    'database_name': 'test_db',
                    'throughput': 400
                },
                'storage': {
                    'account_name': 'teststorage',
                    'tier': 'Standard_LRS'
                }
            },
            'app': {
                'environment': 'test',
                'debug': True,
                'log_level': 'DEBUG'
            },
            'database': {
                'consistency_level': 'Session'
            },
            'security': {
                'jwt_expiration': 24
            },
            'monitoring': {
                'application_insights': True
            }
        }
    
    @pytest.fixture
    def deployer(self, mock_config, tmp_path):
        """Create a deployer with mocked config."""
        config_dir = tmp_path / "environments"
        config_dir.mkdir()
        
        config_file = config_dir / "test.yml"
        with open(config_file, 'w') as f:
            yaml.dump(mock_config, f)
        
        return EnvironmentDeployer("test", str(config_dir))
    
    def test_init(self, deployer):
        """Test deployer initialization."""
        assert deployer.environment == "test"
        assert deployer.config['name'] == 'test'
    
    def test_load_environment_config_missing_file(self, tmp_path):
        """Test loading missing environment config."""
        with pytest.raises(FileNotFoundError):
            EnvironmentDeployer("nonexistent", str(tmp_path))
    
    @patch('subprocess.run')
    @patch.dict(os.environ, {
        'TEST_COSMOS_ENDPOINT': 'https://test.cosmos.com',
        'TEST_COSMOS_KEY': 'test-key',
        'TEST_AZURE_STORAGE_ACCOUNT_NAME': 'teststorage',
        'TEST_AZURE_STORAGE_ACCOUNT_KEY': 'test-storage-key',
        'TEST_JWT_SECRET_KEY': 'test-jwt-secret'
    })
    def test_validate_environment_success(self, mock_run, deployer):
        """Test successful environment validation."""
        # Mock Azure CLI check
        mock_run.return_value = Mock(returncode=0)
        
        result = deployer.validate_environment()
        assert result is True
    
    @patch('subprocess.run')
    def test_validate_environment_azure_cli_not_logged_in(self, mock_run, deployer):
        """Test environment validation with Azure CLI not logged in."""
        # Mock Azure CLI check failure
        mock_run.return_value = Mock(returncode=1)
        
        result = deployer.validate_environment()
        assert result is False
    
    def test_validate_environment_missing_env_vars(self, deployer):
        """Test environment validation with missing environment variables."""
        result = deployer.validate_environment()
        assert result is False
    
    @patch('subprocess.run')
    def test_deploy_infrastructure_success(self, mock_run, deployer):
        """Test successful infrastructure deployment."""
        mock_run.return_value = Mock(returncode=0)
        
        result = deployer.deploy_infrastructure()
        assert result is True
        
        # Check that Azure CLI commands were called
        assert mock_run.call_count >= 5  # resource group, cosmos, database, storage, app service plan, app service
    
    @patch('subprocess.run')
    def test_deploy_infrastructure_failure(self, mock_run, deployer):
        """Test infrastructure deployment failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'az')
        
        result = deployer.deploy_infrastructure()
        assert result is False
    
    @patch('subprocess.run')
    def test_deploy_direct(self, mock_run, deployer):
        """Test direct deployment strategy."""
        mock_run.return_value = Mock(returncode=0)
        
        result = deployer._deploy_direct()
        assert result is True
    
    @patch('subprocess.run')
    @patch.object(EnvironmentDeployer, '_health_check_staging')
    def test_deploy_blue_green_success(self, mock_health_check, mock_run, deployer):
        """Test successful blue-green deployment."""
        mock_run.return_value = Mock(returncode=0)
        mock_health_check.return_value = True
        
        result = deployer._deploy_blue_green()
        assert result is True
        
        # Check that staging slot was created and swapped
        create_slot_calls = [call for call in mock_run.call_args_list 
                           if 'slot' in str(call) and 'create' in str(call)]
        assert len(create_slot_calls) > 0
        
        swap_calls = [call for call in mock_run.call_args_list 
                     if 'slot' in str(call) and 'swap' in str(call)]
        assert len(swap_calls) > 0
    
    @patch('subprocess.run')
    @patch.object(EnvironmentDeployer, '_health_check_staging')
    def test_deploy_blue_green_health_check_failure(self, mock_health_check, mock_run, deployer):
        """Test blue-green deployment with health check failure."""
        mock_run.return_value = Mock(returncode=0)
        mock_health_check.return_value = False
        
        result = deployer._deploy_blue_green()
        assert result is False
    
    @patch('subprocess.run')
    @patch.object(EnvironmentDeployer, '_check_canary_metrics')
    @patch('time.sleep')
    def test_deploy_canary_success(self, mock_sleep, mock_metrics_check, mock_run, deployer):
        """Test successful canary deployment."""
        mock_run.return_value = Mock(returncode=0)
        mock_metrics_check.return_value = True
        
        # Add deployment config for canary
        deployer.config['deployment'] = {
            'promotion_stages': [
                {'percentage': 10, 'duration': 1},
                {'percentage': 100, 'duration': 0}
            ]
        }
        
        result = deployer._deploy_canary()
        assert result is True
    
    @patch('subprocess.run')
    @patch.object(EnvironmentDeployer, '_check_canary_metrics')
    @patch.object(EnvironmentDeployer, '_rollback_canary')
    @patch('time.sleep')
    def test_deploy_canary_metrics_failure(self, mock_sleep, mock_rollback, mock_metrics_check, mock_run, deployer):
        """Test canary deployment with metrics failure."""
        mock_run.return_value = Mock(returncode=0)
        mock_metrics_check.return_value = False
        
        # Add deployment config for canary
        deployer.config['deployment'] = {
            'promotion_stages': [
                {'percentage': 10, 'duration': 1}
            ]
        }
        
        result = deployer._deploy_canary()
        assert result is False
        
        # Check that rollback was called
        mock_rollback.assert_called_once()
    
    @patch('requests.get')
    def test_health_check_staging_success(self, mock_get, deployer):
        """Test successful staging health check."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = deployer._health_check_staging('test-app')
        assert result is True
    
    @patch('requests.get')
    def test_health_check_staging_failure(self, mock_get, deployer):
        """Test staging health check failure."""
        mock_get.side_effect = Exception("Connection failed")
        
        result = deployer._health_check_staging('test-app')
        assert result is False
    
    def test_check_canary_metrics(self, deployer):
        """Test canary metrics check."""
        # Add deployment config
        deployer.config['deployment'] = {
            'rollback': {
                'threshold': 5
            }
        }
        
        result = deployer._check_canary_metrics('test-app')
        assert result is True  # Simulated success
    
    @patch('subprocess.run')
    def test_rollback_canary(self, mock_run, deployer):
        """Test canary rollback."""
        mock_run.return_value = Mock(returncode=0)
        
        deployer._rollback_canary('test-app', 'test-rg')
        
        # Check that traffic routing was cleared and slot was deleted
        clear_calls = [call for call in mock_run.call_args_list 
                      if 'traffic-routing' in str(call) and 'clear' in str(call)]
        assert len(clear_calls) > 0
        
        delete_calls = [call for call in mock_run.call_args_list 
                       if 'slot' in str(call) and 'delete' in str(call)]
        assert len(delete_calls) > 0
    
    @patch('subprocess.run')
    def test_run_post_deployment_tests_success(self, mock_run, deployer):
        """Test successful post-deployment tests."""
        mock_run.return_value = Mock(returncode=0)
        
        result = deployer.run_post_deployment_tests()
        assert result is True
    
    @patch('subprocess.run')
    def test_run_post_deployment_tests_failure(self, mock_run, deployer):
        """Test post-deployment tests failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'python')
        
        result = deployer.run_post_deployment_tests()
        assert result is False


class TestEnvironmentConfiguration:
    """Test environment configuration files."""
    
    def test_environment_config_files_exist(self):
        """Test that environment configuration files exist."""
        environments_dir = Path(__file__).parent.parent.parent / "environments"
        
        required_configs = ["dev.yml", "staging.yml", "production.yml"]
        
        for config_file in required_configs:
            config_path = environments_dir / config_file
            assert config_path.exists(), f"Missing environment config: {config_file}"
    
    def test_environment_config_structure(self):
        """Test that environment configs have required structure."""
        environments_dir = Path(__file__).parent.parent.parent / "environments"
        
        required_sections = [
            'name', 'azure', 'app', 'database', 
            'security', 'monitoring', 'features'
        ]
        
        for config_file in ["dev.yml", "staging.yml", "production.yml"]:
            config_path = environments_dir / config_file
            
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            for section in required_sections:
                assert section in config, f"Missing section '{section}' in {config_file}"
    
    def test_production_config_security(self):
        """Test that production config has appropriate security settings."""
        environments_dir = Path(__file__).parent.parent.parent / "environments"
        prod_config_path = environments_dir / "production.yml"
        
        with open(prod_config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Check security settings
        assert config['app']['debug'] is False, "Production should have debug disabled"
        assert config['app']['log_level'] in ['WARNING', 'ERROR'], "Production should have appropriate log level"
        assert config['security']['rate_limiting']['strict_mode'] is True, "Production should have strict rate limiting"
        assert config['deployment']['strategy'] in ['canary', 'blue_green'], "Production should use safe deployment strategy"
    
    def test_environment_specific_settings(self):
        """Test that environments have appropriate settings for their purpose."""
        environments_dir = Path(__file__).parent.parent.parent / "environments"
        
        # Load all configs
        configs = {}
        for env in ['dev', 'staging', 'production']:
            config_path = environments_dir / f"{env}.yml"
            with open(config_path, 'r') as f:
                configs[env] = yaml.safe_load(f)
        
        # Dev should be most permissive
        assert configs['dev']['app']['debug'] is True
        assert configs['dev']['app']['rate_limits']['guess_submissions'] >= configs['staging']['app']['rate_limits']['guess_submissions']
        
        # Production should be most restrictive
        assert configs['production']['app']['debug'] is False
        assert configs['production']['app']['rate_limits']['guess_submissions'] <= configs['staging']['app']['rate_limits']['guess_submissions']
        
        # Staging should be between dev and production
        assert configs['staging']['app']['debug'] is False
        assert configs['staging']['security']['rate_limiting']['strict_mode'] is True


class TestDeploymentWorkflows:
    """Test deployment workflow functionality."""
    
    def test_deploy_environments_workflow_exists(self):
        """Test that deploy-environments workflow exists."""
        workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "deploy-environments.yml"
        assert workflow_path.exists()
    
    def test_deploy_environments_workflow_structure(self):
        """Test deploy-environments workflow structure."""
        workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "deploy-environments.yml"
        
        with open(workflow_path, 'r') as f:
            workflow = yaml.safe_load(f)
        
        # Check workflow_call trigger
        assert 'workflow_call' in workflow['on']
        
        # Check required inputs
        inputs = workflow['on']['workflow_call']['inputs']
        assert 'environment' in inputs
        assert inputs['environment']['required'] is True
        
        # Check required secrets
        secrets = workflow['on']['workflow_call']['secrets']
        required_secrets = [
            'AZURE_CREDENTIALS', 'VERCEL_TOKEN', 'COSMOS_ENDPOINT',
            'COSMOS_KEY', 'STORAGE_ACCOUNT_NAME', 'JWT_SECRET_KEY'
        ]
        
        for secret in required_secrets:
            assert secret in secrets
            assert secrets[secret]['required'] is True
        
        # Check required jobs
        required_jobs = [
            'validate-environment', 'deploy-backend', 
            'deploy-frontend', 'post-deployment-validation'
        ]
        
        for job in required_jobs:
            assert job in workflow['jobs']
    
    def test_deployment_script_exists(self):
        """Test that deployment script exists and is executable."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "deploy-environment.py"
        assert script_path.exists()
        assert os.access(script_path, os.X_OK)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])