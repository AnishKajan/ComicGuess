"""
Tests for deployment validation script.
"""
import os
import json
import pytest
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# Add the scripts directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from validate_deployment import DeploymentValidator


class TestDeploymentValidator:
    """Test the DeploymentValidator class."""
    
    @pytest.fixture
    def validator(self):
        """Create a DeploymentValidator instance."""
        return DeploymentValidator("test")
    
    def test_init(self, validator):
        """Test validator initialization."""
        assert validator.environment == "test"
        assert validator.results == []
    
    def test_log_result(self, validator):
        """Test result logging."""
        validator.log_result("Test Case", True, "Test message", {"key": "value"})
        
        assert len(validator.results) == 1
        result = validator.results[0]
        
        assert result["test"] == "Test Case"
        assert result["passed"] is True
        assert result["message"] == "Test message"
        assert result["details"] == {"key": "value"}
        assert result["environment"] == "test"
    
    @patch('subprocess.run')
    @patch('os.chdir')
    @patch('os.path.exists')
    def test_validate_frontend_build_success(self, mock_exists, mock_chdir, mock_run, validator):
        """Test successful frontend build validation."""
        # Mock successful subprocess calls
        mock_run.return_value = Mock(returncode=0, stderr="")
        mock_exists.return_value = True
        
        result = validator.validate_frontend_build()
        
        assert result is True
        
        # Check that all expected commands were called
        expected_commands = [
            ["npm", "ci"],
            ["npm", "run", "lint"],
            ["npx", "tsc", "--noEmit"],
            ["npm", "run", "test:run"],
            ["npm", "run", "build"]
        ]
        
        actual_commands = [call[0][0] for call in mock_run.call_args_list]
        for expected_cmd in expected_commands:
            assert expected_cmd in actual_commands
    
    @patch('subprocess.run')
    @patch('os.chdir')
    def test_validate_frontend_build_failure(self, mock_chdir, mock_run, validator):
        """Test frontend build validation failure."""
        # Mock failed subprocess call
        mock_run.return_value = Mock(returncode=1, stderr="Build failed")
        
        result = validator.validate_frontend_build()
        
        assert result is False
        
        # Check that failure was logged
        failed_results = [r for r in validator.results if not r["passed"]]
        assert len(failed_results) > 0
    
    @patch('subprocess.run')
    @patch('os.chdir')
    def test_validate_backend_build_success(self, mock_chdir, mock_run, validator):
        """Test successful backend build validation."""
        # Mock successful subprocess calls
        mock_run.return_value = Mock(returncode=0, stderr="")
        
        result = validator.validate_backend_build()
        
        assert result is True
        
        # Check that pytest was called
        pytest_calls = [call for call in mock_run.call_args_list 
                       if any("pytest" in str(arg) for arg in call[0][0])]
        assert len(pytest_calls) > 0
    
    @patch('subprocess.run')
    @patch('os.chdir')
    @patch('time.sleep')
    def test_validate_docker_build_success(self, mock_sleep, mock_chdir, mock_run, validator):
        """Test successful Docker build validation."""
        # Mock successful subprocess calls
        mock_run.return_value = Mock(returncode=0, stderr="")
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            result = validator.validate_docker_build()
            
            assert result is True
            
            # Check that Docker commands were called
            docker_calls = [call for call in mock_run.call_args_list 
                           if any("docker" in str(arg) for arg in call[0][0])]
            assert len(docker_calls) >= 3  # build, run, stop, rm
    
    @patch('requests.get')
    def test_validate_deployed_service_success(self, mock_get, validator):
        """Test successful deployed service validation."""
        # Mock successful HTTP responses
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy"}
        mock_get.return_value = mock_response
        
        result = validator.validate_deployed_service("https://api.example.com")
        
        assert result is True
        
        # Check that health endpoint was called
        mock_get.assert_called()
        
        # Check that results were logged
        health_results = [r for r in validator.results if "Health" in r["test"]]
        assert len(health_results) > 0
    
    @patch('requests.get')
    def test_validate_security_headers(self, mock_get, validator):
        """Test security headers validation."""
        # Mock response with security headers
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000",
            "Content-Security-Policy": "default-src 'self'"
        }
        mock_get.return_value = mock_response
        
        result = validator.validate_security_headers("https://api.example.com")
        
        assert result is True
        
        # Check that security header results were logged
        security_results = [r for r in validator.results if "Security Header" in r["test"]]
        assert len(security_results) > 0
    
    def test_generate_report(self, validator):
        """Test report generation."""
        # Add some test results
        validator.log_result("Test 1", True, "Success")
        validator.log_result("Test 2", False, "Failure")
        validator.log_result("Test 3", True, "Success")
        
        report = validator.generate_report()
        
        assert report["environment"] == "test"
        assert "timestamp" in report
        assert report["summary"]["total_tests"] == 3
        assert report["summary"]["passed"] == 2
        assert report["summary"]["failed"] == 1
        assert report["summary"]["success_rate"] == 66.66666666666666
        assert len(report["results"]) == 3
        assert len(report["passed_tests"]) == 2
        assert len(report["failed_tests"]) == 1


class TestDeploymentValidationScript:
    """Test the deployment validation script as a whole."""
    
    def test_script_exists(self):
        """Test that the deployment validation script exists."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "validate-deployment.py"
        assert script_path.exists()
        assert script_path.is_file()
    
    def test_script_is_executable(self):
        """Test that the script is executable."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "validate-deployment.py"
        assert os.access(script_path, os.X_OK)
    
    def test_script_help(self):
        """Test that the script shows help."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "validate-deployment.py"
        
        result = subprocess.run([str(script_path), "--help"], 
                              capture_output=True, text=True)
        
        assert result.returncode == 0
        assert "validate deployment readiness" in result.stdout.lower()
        assert "--environment" in result.stdout
        assert "--url" in result.stdout
        assert "--build-only" in result.stdout
    
    @patch('validate_deployment.DeploymentValidator')
    def test_script_main_build_only(self, mock_validator_class):
        """Test script main function with build-only flag."""
        # Mock the validator
        mock_validator = Mock()
        mock_validator.validate_frontend_build.return_value = True
        mock_validator.validate_backend_build.return_value = True
        mock_validator.validate_docker_build.return_value = True
        mock_validator_class.return_value = mock_validator
        
        # Import and run main function
        from validate_deployment import main
        
        with patch('sys.argv', ['validate-deployment.py', '--build-only', '--environment', 'test']):
            with patch('sys.exit') as mock_exit:
                main()
                mock_exit.assert_called_with(0)
        
        # Check that validator methods were called
        mock_validator.validate_frontend_build.assert_called_once()
        mock_validator.validate_backend_build.assert_called_once()
        mock_validator.validate_docker_build.assert_called_once()
    
    @patch('validate_deployment.DeploymentValidator')
    def test_script_main_full_validation(self, mock_validator_class):
        """Test script main function with full validation."""
        # Mock the validator
        mock_validator = Mock()
        mock_validator.run_all_validations.return_value = True
        mock_validator_class.return_value = mock_validator
        
        # Import and run main function
        from validate_deployment import main
        
        test_url = "https://api.example.com"
        with patch('sys.argv', ['validate-deployment.py', '--url', test_url]):
            with patch('sys.exit') as mock_exit:
                main()
                mock_exit.assert_called_with(0)
        
        # Check that run_all_validations was called with URL
        mock_validator.run_all_validations.assert_called_once_with(test_url)


class TestPipelineIntegration:
    """Test pipeline integration functionality."""
    
    def test_pipeline_test_file_exists(self):
        """Test that pipeline test files exist."""
        test_file = Path(__file__).parent / "test_ci_cd_pipeline.py"
        assert test_file.exists()
    
    def test_workflow_files_exist(self):
        """Test that workflow files exist."""
        workflows_dir = Path(__file__).parent.parent.parent / ".github" / "workflows"
        
        required_workflows = [
            "ci-cd-main.yml",
            "pipeline-tests.yml"
        ]
        
        for workflow in required_workflows:
            workflow_path = workflows_dir / workflow
            assert workflow_path.exists(), f"Missing workflow: {workflow}"
    
    def test_coverage_configuration(self):
        """Test that coverage is properly configured."""
        # Check frontend coverage configuration
        vitest_config = Path(__file__).parent.parent.parent / "frontend" / "vitest.config.ts"
        assert vitest_config.exists()
        
        with open(vitest_config, 'r') as f:
            config_content = f.read()
        
        assert 'coverage' in config_content
        assert 'thresholds' in config_content
        
        # Check frontend package.json has coverage scripts
        package_json = Path(__file__).parent.parent.parent / "frontend" / "package.json"
        assert package_json.exists()
        
        with open(package_json, 'r') as f:
            package_data = json.load(f)
        
        scripts = package_data.get('scripts', {})
        assert 'test:coverage' in scripts
        assert 'test:coverage:json' in scripts


if __name__ == "__main__":
    pytest.main([__file__, "-v"])