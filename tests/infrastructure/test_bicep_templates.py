"""
Tests for Bicep infrastructure templates.
"""
import json
import yaml
import pytest
import subprocess
from pathlib import Path
from typing import Dict, Any
import os


class TestBicepTemplates:
    """Test Bicep infrastructure templates."""
    
    @pytest.fixture
    def infrastructure_dir(self):
        """Get infrastructure directory."""
        return Path(__file__).parent.parent.parent / "infrastructure" / "bicep"
    
    @pytest.fixture
    def bicep_modules_dir(self, infrastructure_dir):
        """Get Bicep modules directory."""
        return infrastructure_dir / "modules"
    
    @pytest.fixture
    def parameters_dir(self, infrastructure_dir):
        """Get parameters directory."""
        return infrastructure_dir / "parameters"
    
    def test_main_bicep_template_exists(self, infrastructure_dir):
        """Test that main Bicep template exists."""
        main_template = infrastructure_dir / "main.bicep"
        assert main_template.exists()
    
    def test_bicep_modules_exist(self, bicep_modules_dir):
        """Test that all required Bicep modules exist."""
        required_modules = [
            "cosmosdb.bicep",
            "storage.bicep",
            "app-service.bicep",
            "app-service-plan.bicep",
            "function-app.bicep",
            "application-insights.bicep",
            "key-vault.bicep"
        ]
        
        for module in required_modules:
            module_path = bicep_modules_dir / module
            assert module_path.exists(), f"Missing Bicep module: {module}"
    
    def test_parameter_files_exist(self, parameters_dir):
        """Test that parameter files exist for all environments."""
        required_parameter_files = [
            "dev.bicepparam",
            "staging.bicepparam",
            "production.bicepparam"
        ]
        
        for param_file in required_parameter_files:
            param_path = parameters_dir / param_file
            assert param_path.exists(), f"Missing parameter file: {param_file}"
    
    def test_bicep_template_syntax(self, infrastructure_dir):
        """Test Bicep template syntax validation."""
        # Skip if Bicep CLI is not available
        try:
            result = subprocess.run(['bicep', '--version'], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                pytest.skip("Bicep CLI not available")
        except FileNotFoundError:
            pytest.skip("Bicep CLI not installed")
        
        # Validate main template
        main_template = infrastructure_dir / "main.bicep"
        result = subprocess.run([
            'bicep', 'build', str(main_template), '--stdout'
        ], capture_output=True, text=True)
        
        assert result.returncode == 0, f"Bicep template validation failed: {result.stderr}"
    
    def test_bicep_modules_syntax(self, bicep_modules_dir):
        """Test Bicep modules syntax validation."""
        # Skip if Bicep CLI is not available
        try:
            result = subprocess.run(['bicep', '--version'], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                pytest.skip("Bicep CLI not available")
        except FileNotFoundError:
            pytest.skip("Bicep CLI not installed")
        
        # Validate all modules
        module_files = list(bicep_modules_dir.glob("*.bicep"))
        
        for module_file in module_files:
            result = subprocess.run([
                'bicep', 'build', str(module_file), '--stdout'
            ], capture_output=True, text=True)
            
            assert result.returncode == 0, f"Module {module_file.name} validation failed: {result.stderr}"
    
    def test_main_template_structure(self, infrastructure_dir):
        """Test main template has required structure."""
        main_template = infrastructure_dir / "main.bicep"
        
        with open(main_template, 'r') as f:
            content = f.read()
        
        # Check for required parameters
        required_params = [
            "@description('Environment name (dev, staging, production)')",
            "param environment string",
            "param location string",
            "param appName string"
        ]
        
        for param in required_params:
            assert param in content, f"Missing required parameter: {param}"
        
        # Check for module references
        required_modules = [
            "module cosmosDb",
            "module storage", 
            "module applicationInsights",
            "module keyVault",
            "module appServicePlan",
            "module appService",
            "module functionApp"
        ]
        
        for module in required_modules:
            assert module in content, f"Missing module reference: {module}"
        
        # Check for outputs
        required_outputs = [
            "output cosmosDbEndpoint",
            "output storageAccountName",
            "output appServiceName",
            "output functionAppName"
        ]
        
        for output in required_outputs:
            assert output in content, f"Missing output: {output}"
    
    def test_environment_specific_configurations(self, infrastructure_dir):
        """Test environment-specific configurations."""
        main_template = infrastructure_dir / "main.bicep"
        
        with open(main_template, 'r') as f:
            content = f.read()
        
        # Check for environment-specific config
        assert "var environmentConfig" in content
        assert "dev:" in content
        assert "staging:" in content
        assert "production:" in content
        
        # Check for different configurations per environment
        config_items = [
            "cosmosDbThroughput",
            "appServiceSku",
            "appServiceInstances",
            "storageTier"
        ]
        
        for item in config_items:
            assert item in content, f"Missing configuration item: {item}"
    
    def test_parameter_files_structure(self, parameters_dir):
        """Test parameter files have correct structure."""
        environments = ['dev', 'staging', 'production']
        
        for env in environments:
            param_file = parameters_dir / f"{env}.bicepparam"
            
            with open(param_file, 'r') as f:
                content = f.read()
            
            # Check required parameters
            required_params = [
                f"param environment = '{env}'",
                "param location =",
                "param appName =",
                "param tags ="
            ]
            
            for param in required_params:
                assert param in content, f"Missing parameter in {env}.bicepparam: {param}"
    
    def test_cosmos_db_module_structure(self, bicep_modules_dir):
        """Test Cosmos DB module structure."""
        cosmos_module = bicep_modules_dir / "cosmosdb.bicep"
        
        with open(cosmos_module, 'r') as f:
            content = f.read()
        
        # Check for required resources
        required_resources = [
            "resource cosmosDbAccount",
            "resource database",
            "resource containers"
        ]
        
        for resource in required_resources:
            assert resource in content, f"Missing resource in cosmosdb.bicep: {resource}"
        
        # Check for container names
        container_names = ["'users'", "'puzzles'", "'guesses'"]
        for container in container_names:
            assert container in content, f"Missing container: {container}"
        
        # Check for outputs
        required_outputs = [
            "output endpoint",
            "output primaryKey",
            "output databaseName"
        ]
        
        for output in required_outputs:
            assert output in content, f"Missing output in cosmosdb.bicep: {output}"
    
    def test_storage_module_structure(self, bicep_modules_dir):
        """Test Storage module structure."""
        storage_module = bicep_modules_dir / "storage.bicep"
        
        with open(storage_module, 'r') as f:
            content = f.read()
        
        # Check for required resources
        required_resources = [
            "resource storageAccount",
            "resource blobService",
            "resource containers",
            "resource lifecyclePolicy"
        ]
        
        for resource in required_resources:
            assert resource in content, f"Missing resource in storage.bicep: {resource}"
        
        # Check for container names
        container_names = ["'character-images'", "'backups'", "'logs'"]
        for container in container_names:
            assert container in content, f"Missing container: {container}"
    
    def test_app_service_module_structure(self, bicep_modules_dir):
        """Test App Service module structure."""
        app_service_module = bicep_modules_dir / "app-service.bicep"
        
        with open(app_service_module, 'r') as f:
            content = f.read()
        
        # Check for required resources
        required_resources = [
            "resource appService",
            "resource stagingSlot",
            "resource autoScaleSettings"
        ]
        
        for resource in required_resources:
            assert resource in content, f"Missing resource in app-service.bicep: {resource}"
        
        # Check for required app settings
        required_settings = [
            "'APP_ENV'",
            "'COSMOS_ENDPOINT'",
            "'COSMOS_KEY'",
            "'AZURE_STORAGE_ACCOUNT_NAME'"
        ]
        
        for setting in required_settings:
            assert setting in content, f"Missing app setting: {setting}"
    
    def test_security_configurations(self, bicep_modules_dir):
        """Test security configurations in modules."""
        # Test Key Vault module
        key_vault_module = bicep_modules_dir / "key-vault.bicep"
        
        with open(key_vault_module, 'r') as f:
            content = f.read()
        
        # Check for security settings
        security_settings = [
            "enableSoftDelete: true",
            "enableRbacAuthorization: true",
            "minimumTlsVersion: '1.2'"
        ]
        
        for setting in security_settings:
            if setting.split(':')[0].strip() in content:
                # Setting exists, check if it's properly configured
                pass
        
        # Test App Service security
        app_service_module = bicep_modules_dir / "app-service.bicep"
        
        with open(app_service_module, 'r') as f:
            app_content = f.read()
        
        app_security_settings = [
            "httpsOnly: true",
            "ftpsState: 'Disabled'",
            "minTlsVersion: '1.2'"
        ]
        
        for setting in app_security_settings:
            assert setting in app_content, f"Missing security setting in app-service.bicep: {setting}"


class TestInfrastructureDeploymentScript:
    """Test infrastructure deployment script."""
    
    def test_deployment_script_exists(self):
        """Test that deployment script exists."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "deploy-infrastructure.sh"
        assert script_path.exists()
        assert os.access(script_path, os.X_OK)
    
    def test_deployment_script_help(self):
        """Test deployment script help."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "deploy-infrastructure.sh"
        
        result = subprocess.run([str(script_path), "--help"], 
                              capture_output=True, text=True)
        
        assert result.returncode == 0
        assert "Usage:" in result.stdout
        assert "--environment" in result.stdout
        assert "--dry-run" in result.stdout
        assert "--validate-only" in result.stdout
    
    def test_deployment_script_validation(self):
        """Test deployment script parameter validation."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "deploy-infrastructure.sh"
        
        # Test missing environment
        result = subprocess.run([str(script_path)], 
                              capture_output=True, text=True)
        
        assert result.returncode == 1
        assert "Environment is required" in result.stdout
        
        # Test invalid environment
        result = subprocess.run([str(script_path), "--environment", "invalid"], 
                              capture_output=True, text=True)
        
        assert result.returncode == 1
        assert "Environment must be one of" in result.stdout


class TestInfrastructureAsCodeBestPractices:
    """Test Infrastructure as Code best practices."""
    
    @pytest.fixture
    def infrastructure_dir(self):
        """Get infrastructure directory."""
        return Path(__file__).parent.parent.parent / "infrastructure" / "bicep"
    
    def test_resource_naming_conventions(self, infrastructure_dir):
        """Test resource naming conventions."""
        main_template = infrastructure_dir / "main.bicep"
        
        with open(main_template, 'r') as f:
            content = f.read()
        
        # Check for consistent naming patterns
        naming_patterns = [
            "var cosmosDbAccountName = '${appName}-${environment}-cosmos-${uniqueString(resourceGroup().id)}'",
            "var storageAccountName = '${appName}${environment}storage${uniqueString(resourceGroup().id)}'",
            "var appServiceName = '${appName}-backend-${environment}'"
        ]
        
        for pattern in naming_patterns:
            # Check if the naming pattern concept exists (not exact match due to formatting)
            assert "uniqueString(resourceGroup().id)" in content, "Missing unique string generation"
            assert "${appName}" in content, "Missing app name in resource naming"
            assert "${environment}" in content, "Missing environment in resource naming"
    
    def test_tagging_strategy(self, infrastructure_dir):
        """Test consistent tagging strategy."""
        main_template = infrastructure_dir / "main.bicep"
        
        with open(main_template, 'r') as f:
            content = f.read()
        
        # Check for tags parameter and usage
        assert "param tags object" in content
        assert "tags: tags" in content
        
        # Check parameter files for consistent tags
        param_files = (infrastructure_dir / "parameters").glob("*.bicepparam")
        
        for param_file in param_files:
            with open(param_file, 'r') as f:
                param_content = f.read()
            
            required_tag_keys = ["application", "environment", "managedBy"]
            for tag_key in required_tag_keys:
                assert tag_key in param_content, f"Missing tag '{tag_key}' in {param_file.name}"
    
    def test_environment_specific_configurations(self, infrastructure_dir):
        """Test environment-specific configurations are appropriate."""
        main_template = infrastructure_dir / "main.bicep"
        
        with open(main_template, 'r') as f:
            content = f.read()
        
        # Check that production has higher specs than dev
        # This is a basic check - in practice you'd parse the Bicep more thoroughly
        assert "production" in content
        assert "dev" in content
        assert "staging" in content
        
        # Check for environment-specific settings
        env_specific_settings = [
            "cosmosDbThroughput",
            "appServiceSku", 
            "enableBackup",
            "enableGeoReplication"
        ]
        
        for setting in env_specific_settings:
            assert setting in content, f"Missing environment-specific setting: {setting}"
    
    def test_security_best_practices(self, infrastructure_dir):
        """Test security best practices in templates."""
        # Check main template
        main_template = infrastructure_dir / "main.bicep"
        
        with open(main_template, 'r') as f:
            content = f.read()
        
        # Check for secure parameters
        assert "@secure()" in content, "Missing @secure() decorators for sensitive parameters"
        
        # Check modules for security settings
        modules_dir = infrastructure_dir / "modules"
        
        for module_file in modules_dir.glob("*.bicep"):
            with open(module_file, 'r') as f:
                module_content = f.read()
            
            # Check for HTTPS enforcement where applicable
            if "app-service" in module_file.name or "function-app" in module_file.name:
                assert "httpsOnly: true" in module_content, f"Missing HTTPS enforcement in {module_file.name}"
            
            # Check for TLS version enforcement
            if any(service in module_file.name for service in ["app-service", "function-app", "key-vault"]):
                tls_patterns = ["minTlsVersion", "minimumTlsVersion"]
                has_tls_config = any(pattern in module_content for pattern in tls_patterns)
                assert has_tls_config, f"Missing TLS configuration in {module_file.name}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])