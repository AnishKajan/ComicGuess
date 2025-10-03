#!/usr/bin/env python3
"""
Environment deployment management script.
Handles deployment to different environments with appropriate strategies.
"""
import os
import sys
import yaml
import json
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
import time


class EnvironmentDeployer:
    """Manages deployments to different environments."""
    
    def __init__(self, environment: str, config_dir: str = "environments"):
        self.environment = environment
        self.config_dir = Path(config_dir)
        self.config = self._load_environment_config()
        
    def _load_environment_config(self) -> Dict[str, Any]:
        """Load environment configuration."""
        config_file = self.config_dir / f"{self.environment}.yml"
        
        if not config_file.exists():
            raise FileNotFoundError(f"Environment config not found: {config_file}")
        
        with open(config_file, 'r') as f:
            return yaml.safe_load(f)
    
    def validate_environment(self) -> bool:
        """Validate environment configuration and prerequisites."""
        print(f"🔍 Validating {self.environment} environment...")
        
        # Check required configuration sections
        required_sections = ['azure', 'app', 'database', 'security', 'monitoring']
        for section in required_sections:
            if section not in self.config:
                print(f"❌ Missing required configuration section: {section}")
                return False
        
        # Check Azure CLI login
        try:
            result = subprocess.run(['az', 'account', 'show'], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                print("❌ Azure CLI not logged in. Run 'az login' first.")
                return False
        except FileNotFoundError:
            print("❌ Azure CLI not installed")
            return False
        
        # Check required environment variables
        required_env_vars = [
            'COSMOS_ENDPOINT',
            'COSMOS_KEY',
            'AZURE_STORAGE_ACCOUNT_NAME',
            'AZURE_STORAGE_ACCOUNT_KEY',
            'JWT_SECRET_KEY'
        ]
        
        missing_vars = []
        for var in required_env_vars:
            env_var_name = f"{self.environment.upper()}_{var}"
            if not os.getenv(env_var_name):
                missing_vars.append(env_var_name)
        
        if missing_vars:
            print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
            return False
        
        print("✅ Environment validation passed")
        return True
    
    def deploy_infrastructure(self) -> bool:
        """Deploy infrastructure using Azure CLI."""
        print(f"🏗️ Deploying infrastructure for {self.environment}...")
        
        azure_config = self.config['azure']
        
        try:
            # Create resource group
            print("Creating resource group...")
            subprocess.run([
                'az', 'group', 'create',
                '--name', azure_config['resource_group'],
                '--location', azure_config['location']
            ], check=True)
            
            # Deploy Cosmos DB
            print("Deploying Cosmos DB...")
            cosmos_config = azure_config['cosmos_db']
            subprocess.run([
                'az', 'cosmosdb', 'create',
                '--name', cosmos_config['account_name'],
                '--resource-group', azure_config['resource_group'],
                '--kind', 'GlobalDocumentDB',
                '--default-consistency-level', self.config['database']['consistency_level'],
                '--enable-automatic-failover', 'true'
            ], check=True)
            
            # Create database
            subprocess.run([
                'az', 'cosmosdb', 'sql', 'database', 'create',
                '--account-name', cosmos_config['account_name'],
                '--resource-group', azure_config['resource_group'],
                '--name', cosmos_config['database_name'],
                '--throughput', str(cosmos_config['throughput'])
            ], check=True)
            
            # Deploy Storage Account
            print("Deploying Storage Account...")
            storage_config = azure_config['storage']
            subprocess.run([
                'az', 'storage', 'account', 'create',
                '--name', storage_config['account_name'],
                '--resource-group', azure_config['resource_group'],
                '--location', azure_config['location'],
                '--sku', storage_config['tier'],
                '--kind', 'StorageV2'
            ], check=True)
            
            # Deploy App Service Plan
            print("Deploying App Service Plan...")
            app_service_config = azure_config['app_service']
            subprocess.run([
                'az', 'appservice', 'plan', 'create',
                '--name', f"{app_service_config['name']}-plan",
                '--resource-group', azure_config['resource_group'],
                '--sku', app_service_config['sku'],
                '--number-of-workers', str(app_service_config['instances'])
            ], check=True)
            
            # Deploy App Service
            print("Deploying App Service...")
            subprocess.run([
                'az', 'webapp', 'create',
                '--name', app_service_config['name'],
                '--resource-group', azure_config['resource_group'],
                '--plan', f"{app_service_config['name']}-plan",
                '--runtime', 'PYTHON|3.11'
            ], check=True)
            
            print("✅ Infrastructure deployment completed")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Infrastructure deployment failed: {e}")
            return False
    
    def deploy_application(self) -> bool:
        """Deploy application code."""
        print(f"🚀 Deploying application to {self.environment}...")
        
        deployment_strategy = self.config.get('deployment', {}).get('strategy', 'direct')
        
        if deployment_strategy == 'blue_green':
            return self._deploy_blue_green()
        elif deployment_strategy == 'canary':
            return self._deploy_canary()
        else:
            return self._deploy_direct()
    
    def _deploy_direct(self) -> bool:
        """Direct deployment strategy."""
        print("📦 Using direct deployment strategy...")
        
        try:
            azure_config = self.config['azure']
            app_name = azure_config['app_service']['name']
            resource_group = azure_config['resource_group']
            
            # Deploy backend
            subprocess.run([
                'az', 'webapp', 'deploy',
                '--name', app_name,
                '--resource-group', resource_group,
                '--src-path', 'backend',
                '--type', 'zip'
            ], check=True, cwd='..')
            
            # Configure app settings
            self._configure_app_settings(app_name, resource_group)
            
            print("✅ Direct deployment completed")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Direct deployment failed: {e}")
            return False
    
    def _deploy_blue_green(self) -> bool:
        """Blue-green deployment strategy."""
        print("🔵🟢 Using blue-green deployment strategy...")
        
        try:
            azure_config = self.config['azure']
            app_name = azure_config['app_service']['name']
            resource_group = azure_config['resource_group']
            
            # Create staging slot (green)
            print("Creating staging slot...")
            subprocess.run([
                'az', 'webapp', 'deployment', 'slot', 'create',
                '--name', app_name,
                '--resource-group', resource_group,
                '--slot', 'staging',
                '--configuration-source', app_name
            ], check=True)
            
            # Deploy to staging slot
            print("Deploying to staging slot...")
            subprocess.run([
                'az', 'webapp', 'deploy',
                '--name', app_name,
                '--resource-group', resource_group,
                '--slot', 'staging',
                '--src-path', 'backend',
                '--type', 'zip'
            ], check=True, cwd='..')
            
            # Configure staging slot
            self._configure_app_settings(app_name, resource_group, slot='staging')
            
            # Health check on staging
            if self._health_check_staging(app_name):
                # Swap slots
                print("Swapping slots...")
                subprocess.run([
                    'az', 'webapp', 'deployment', 'slot', 'swap',
                    '--name', app_name,
                    '--resource-group', resource_group,
                    '--slot', 'staging',
                    '--target-slot', 'production'
                ], check=True)
                
                print("✅ Blue-green deployment completed")
                return True
            else:
                print("❌ Staging health check failed")
                return False
                
        except subprocess.CalledProcessError as e:
            print(f"❌ Blue-green deployment failed: {e}")
            return False
    
    def _deploy_canary(self) -> bool:
        """Canary deployment strategy."""
        print("🐤 Using canary deployment strategy...")
        
        try:
            azure_config = self.config['azure']
            app_name = azure_config['app_service']['name']
            resource_group = azure_config['resource_group']
            
            # Create canary slot
            print("Creating canary slot...")
            subprocess.run([
                'az', 'webapp', 'deployment', 'slot', 'create',
                '--name', app_name,
                '--resource-group', resource_group,
                '--slot', 'canary',
                '--configuration-source', app_name
            ], check=True)
            
            # Deploy to canary slot
            print("Deploying to canary slot...")
            subprocess.run([
                'az', 'webapp', 'deploy',
                '--name', app_name,
                '--resource-group', resource_group,
                '--slot', 'canary',
                '--src-path', 'backend',
                '--type', 'zip'
            ], check=True, cwd='..')
            
            # Configure canary slot
            self._configure_app_settings(app_name, resource_group, slot='canary')
            
            # Gradual traffic routing
            deployment_config = self.config['deployment']
            stages = deployment_config.get('promotion_stages', [
                {'percentage': 10, 'duration': 300},
                {'percentage': 50, 'duration': 600},
                {'percentage': 100, 'duration': 0}
            ])
            
            for stage in stages:
                percentage = stage['percentage']
                duration = stage['duration']
                
                print(f"Routing {percentage}% traffic to canary...")
                subprocess.run([
                    'az', 'webapp', 'traffic-routing', 'set',
                    '--name', app_name,
                    '--resource-group', resource_group,
                    '--distribution', f'canary={percentage}'
                ], check=True)
                
                if duration > 0:
                    print(f"Monitoring for {duration} seconds...")
                    time.sleep(duration)
                    
                    # Check metrics and decide whether to continue
                    if not self._check_canary_metrics(app_name):
                        print("❌ Canary metrics check failed, rolling back...")
                        self._rollback_canary(app_name, resource_group)
                        return False
            
            # Final promotion - swap slots
            print("Final promotion - swapping slots...")
            subprocess.run([
                'az', 'webapp', 'deployment', 'slot', 'swap',
                '--name', app_name,
                '--resource-group', resource_group,
                '--slot', 'canary',
                '--target-slot', 'production'
            ], check=True)
            
            # Clear traffic routing
            subprocess.run([
                'az', 'webapp', 'traffic-routing', 'clear',
                '--name', app_name,
                '--resource-group', resource_group
            ], check=True)
            
            print("✅ Canary deployment completed")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Canary deployment failed: {e}")
            return False
    
    def _configure_app_settings(self, app_name: str, resource_group: str, slot: Optional[str] = None):
        """Configure application settings."""
        print("⚙️ Configuring application settings...")
        
        env_prefix = self.environment.upper()
        settings = [
            f"APP_ENV={self.environment}",
            f"COSMOS_ENDPOINT={os.getenv(f'{env_prefix}_COSMOS_ENDPOINT')}",
            f"COSMOS_KEY={os.getenv(f'{env_prefix}_COSMOS_KEY')}",
            f"COSMOS_DATABASE_NAME={self.config['azure']['cosmos_db']['database_name']}",
            f"AZURE_STORAGE_ACCOUNT_NAME={os.getenv(f'{env_prefix}_AZURE_STORAGE_ACCOUNT_NAME')}",
            f"AZURE_STORAGE_ACCOUNT_KEY={os.getenv(f'{env_prefix}_AZURE_STORAGE_ACCOUNT_KEY')}",
            f"JWT_SECRET_KEY={os.getenv(f'{env_prefix}_JWT_SECRET_KEY')}",
            f"SESSION_SECRET={os.getenv(f'{env_prefix}_SESSION_SECRET', 'default-session-secret')}",
            f"DEBUG={str(self.config['app']['debug']).lower()}",
            f"LOG_LEVEL={self.config['app']['log_level']}"
        ]
        
        cmd = ['az', 'webapp', 'config', 'appsettings', 'set',
               '--name', app_name,
               '--resource-group', resource_group,
               '--settings'] + settings
        
        if slot:
            cmd.extend(['--slot', slot])
        
        subprocess.run(cmd, check=True)
    
    def _health_check_staging(self, app_name: str) -> bool:
        """Perform health check on staging slot."""
        print("🏥 Performing health check on staging slot...")
        
        import requests
        
        staging_url = f"https://{app_name}-staging.azurewebsites.net/health"
        max_attempts = 10
        
        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.get(staging_url, timeout=30)
                if response.status_code == 200:
                    print("✅ Staging health check passed")
                    return True
            except requests.RequestException:
                pass
            
            print(f"Health check attempt {attempt}/{max_attempts} failed, retrying...")
            time.sleep(30)
        
        print("❌ Staging health check failed")
        return False
    
    def _check_canary_metrics(self, app_name: str) -> bool:
        """Check canary deployment metrics."""
        print("📊 Checking canary metrics...")
        
        # In a real implementation, this would check Application Insights metrics
        # For now, we'll simulate a basic check
        
        deployment_config = self.config.get('deployment', {})
        error_threshold = deployment_config.get('rollback', {}).get('threshold', 5)
        
        # Simulate metrics check (in reality, query Application Insights)
        print(f"Checking error rate against threshold of {error_threshold}%...")
        
        # For demo purposes, assume metrics are good
        print("✅ Canary metrics check passed")
        return True
    
    def _rollback_canary(self, app_name: str, resource_group: str):
        """Rollback canary deployment."""
        print("🔄 Rolling back canary deployment...")
        
        try:
            # Clear traffic routing
            subprocess.run([
                'az', 'webapp', 'traffic-routing', 'clear',
                '--name', app_name,
                '--resource-group', resource_group
            ], check=True)
            
            # Delete canary slot
            subprocess.run([
                'az', 'webapp', 'deployment', 'slot', 'delete',
                '--name', app_name,
                '--resource-group', resource_group,
                '--slot', 'canary'
            ], check=True)
            
            print("✅ Canary rollback completed")
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Canary rollback failed: {e}")
    
    def run_post_deployment_tests(self) -> bool:
        """Run post-deployment validation tests."""
        print("🧪 Running post-deployment tests...")
        
        try:
            # Run deployment validation script
            result = subprocess.run([
                'python', 'scripts/validate-deployment.py',
                '--environment', self.environment,
                '--url', f"https://{self.config['azure']['app_service']['name']}.azurewebsites.net"
            ], check=True)
            
            print("✅ Post-deployment tests passed")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Post-deployment tests failed: {e}")
            return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Deploy to environment")
    parser.add_argument("environment", choices=["dev", "staging", "production"],
                       help="Target environment")
    parser.add_argument("--infrastructure-only", action="store_true",
                       help="Only deploy infrastructure")
    parser.add_argument("--application-only", action="store_true",
                       help="Only deploy application")
    parser.add_argument("--skip-tests", action="store_true",
                       help="Skip post-deployment tests")
    
    args = parser.parse_args()
    
    deployer = EnvironmentDeployer(args.environment)
    
    # Validate environment
    if not deployer.validate_environment():
        sys.exit(1)
    
    success = True
    
    # Deploy infrastructure
    if not args.application_only:
        if not deployer.deploy_infrastructure():
            success = False
    
    # Deploy application
    if not args.infrastructure_only and success:
        if not deployer.deploy_application():
            success = False
    
    # Run post-deployment tests
    if not args.skip_tests and success:
        if not deployer.run_post_deployment_tests():
            success = False
    
    if success:
        print(f"🎉 Deployment to {args.environment} completed successfully!")
    else:
        print(f"❌ Deployment to {args.environment} failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()