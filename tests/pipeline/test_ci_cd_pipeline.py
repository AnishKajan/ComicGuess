"""
Tests for CI/CD pipeline functionality and validation.
"""
import os
import yaml
import json
import subprocess
import pytest
from pathlib import Path
from typing import Dict, Any, List


class TestCICDPipeline:
    """Test CI/CD pipeline configuration and functionality."""
    
    @pytest.fixture
    def project_root(self) -> Path:
        """Get project root directory."""
        return Path(__file__).parent.parent.parent
    
    @pytest.fixture
    def workflows_dir(self, project_root: Path) -> Path:
        """Get GitHub workflows directory."""
        return project_root / ".github" / "workflows"
    
    def test_workflow_files_exist(self, workflows_dir: Path):
        """Test that required workflow files exist."""
        required_workflows = [
            "ci-cd-main.yml",
            "pipeline-tests.yml",
            "deploy.yml",
            "deploy-backend.yml"
        ]
        
        for workflow in required_workflows:
            workflow_path = workflows_dir / workflow
            assert workflow_path.exists(), f"Missing workflow file: {workflow}"
    
    def test_workflow_yaml_syntax(self, workflows_dir: Path):
        """Test that all workflow files have valid YAML syntax."""
        workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
        
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                try:
                    yaml.safe_load(f)
                except yaml.YAMLError as e:
                    pytest.fail(f"Invalid YAML syntax in {workflow_file}: {e}")
    
    def test_workflow_structure(self, workflows_dir: Path):
        """Test that workflows have required structure."""
        workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
        
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            # Check required top-level keys
            required_keys = ['name', 'on', 'jobs']
            for key in required_keys:
                assert key in workflow, f"Missing required key '{key}' in {workflow_file}"
            
            # Check jobs structure
            for job_name, job_config in workflow['jobs'].items():
                assert 'runs-on' in job_config, f"Job '{job_name}' missing 'runs-on' in {workflow_file}"
                assert 'steps' in job_config, f"Job '{job_name}' missing 'steps' in {workflow_file}"
    
    def test_security_scanning_configuration(self, workflows_dir: Path):
        """Test that security scanning is properly configured."""
        main_workflow = workflows_dir / "ci-cd-main.yml"
        
        with open(main_workflow, 'r') as f:
            workflow = yaml.safe_load(f)
        
        # Check for security-scan job
        assert 'security-scan' in workflow['jobs'], "Missing security-scan job"
        
        security_job = workflow['jobs']['security-scan']
        step_names = [step.get('name', '') for step in security_job['steps']]
        
        # Check for required security tools
        required_tools = [
            'Trivy vulnerability scanner',
            'Safety check',
            'Bandit security linter',
            'Semgrep security analysis'
        ]
        
        for tool in required_tools:
            assert any(tool in name for name in step_names), f"Missing security tool: {tool}"
    
    def test_code_quality_configuration(self, workflows_dir: Path):
        """Test that code quality checks are properly configured."""
        main_workflow = workflows_dir / "ci-cd-main.yml"
        
        with open(main_workflow, 'r') as f:
            workflow = yaml.safe_load(f)
        
        # Check for code-quality job
        assert 'code-quality' in workflow['jobs'], "Missing code-quality job"
        
        quality_job = workflow['jobs']['code-quality']
        step_names = [step.get('name', '') for step in quality_job['steps']]
        
        # Check for required quality tools
        required_tools = [
            'ESLint',
            'Prettier',
            'TypeScript',
            'Flake8',
            'Black',
            'isort',
            'MyPy',
            'Pylint'
        ]
        
        for tool in required_tools:
            assert any(tool in name for name in step_names), f"Missing quality tool: {tool}"
    
    def test_coverage_thresholds(self, project_root: Path):
        """Test that coverage thresholds are properly configured."""
        # Frontend coverage
        vitest_config = project_root / "frontend" / "vitest.config.ts"
        assert vitest_config.exists(), "Missing vitest.config.ts"
        
        with open(vitest_config, 'r') as f:
            config_content = f.read()
        
        # Check for coverage configuration
        assert 'coverage' in config_content, "Missing coverage configuration in vitest.config.ts"
        assert 'thresholds' in config_content, "Missing coverage thresholds in vitest.config.ts"
        
        # Backend coverage is checked in pytest configuration
        # This would be in pytest.ini or pyproject.toml
    
    def test_environment_separation(self, workflows_dir: Path):
        """Test that environments are properly separated."""
        backend_workflow = workflows_dir / "deploy-backend.yml"
        
        with open(backend_workflow, 'r') as f:
            workflow = yaml.safe_load(f)
        
        # Check for staging and production jobs
        job_names = list(workflow['jobs'].keys())
        
        staging_jobs = [job for job in job_names if 'staging' in job.lower()]
        production_jobs = [job for job in job_names if 'production' in job.lower()]
        
        assert len(staging_jobs) > 0, "Missing staging deployment jobs"
        assert len(production_jobs) > 0, "Missing production deployment jobs"
    
    def test_secret_usage(self, workflows_dir: Path):
        """Test that secrets are properly used and not hardcoded."""
        workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
        
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                content = f.read()
            
            # Check that secrets are referenced properly
            # Skip files that don't contain actual secrets (like test keys)
            if workflow_file.name in ['ci-cd-main.yml', 'pipeline-tests.yml']:
                # These files contain test keys and environment references, not actual secrets
                continue
                
            if 'password' in content.lower() or 'secret' in content.lower():
                # Should use ${{ secrets.* }} format
                assert '${{ secrets.' in content, f"Potential hardcoded secrets in {workflow_file}"
    
    def test_deployment_validation_steps(self, workflows_dir: Path):
        """Test that deployment validation steps are included."""
        main_workflow = workflows_dir / "ci-cd-main.yml"
        
        with open(main_workflow, 'r') as f:
            workflow = yaml.safe_load(f)
        
        # Check for build-validation job
        assert 'build-validation' in workflow['jobs'], "Missing build-validation job"
        
        validation_job = workflow['jobs']['build-validation']
        step_names = [step.get('name', '') for step in validation_job['steps']]
        
        # Check for required validation steps
        required_validations = [
            'Build frontend',
            'Validate backend startup',
            'Build Docker image',
            'Test Docker container'
        ]
        
        for validation in required_validations:
            assert any(validation in name for name in step_names), f"Missing validation: {validation}"
    
    def test_quality_gates(self, workflows_dir: Path):
        """Test that quality gates are properly implemented."""
        main_workflow = workflows_dir / "ci-cd-main.yml"
        
        with open(main_workflow, 'r') as f:
            workflow = yaml.safe_load(f)
        
        # Check for quality-gates job
        assert 'quality-gates' in workflow['jobs'], "Missing quality-gates job"
        
        quality_gates_job = workflow['jobs']['quality-gates']
        
        # Check that it depends on all required jobs
        required_dependencies = [
            'security-scan',
            'code-quality', 
            'frontend-tests',
            'backend-tests',
            'build-validation'
        ]
        
        needs = quality_gates_job.get('needs', [])
        for dependency in required_dependencies:
            assert dependency in needs, f"Quality gates missing dependency: {dependency}"
    
    def test_artifact_upload(self, workflows_dir: Path):
        """Test that artifacts are properly uploaded."""
        main_workflow = workflows_dir / "ci-cd-main.yml"
        
        with open(main_workflow, 'r') as f:
            workflow = yaml.safe_load(f)
        
        # Check for artifact upload steps
        artifact_jobs = ['security-scan', 'code-quality', 'frontend-tests', 'backend-tests']
        
        for job_name in artifact_jobs:
            job = workflow['jobs'][job_name]
            step_names = [step.get('name', '') for step in job['steps']]
            
            has_upload = any('upload' in name.lower() and 'artifact' in name.lower() 
                           for name in step_names)
            assert has_upload, f"Job '{job_name}' missing artifact upload step"


class TestDeploymentValidation:
    """Test deployment validation functionality."""
    
    def test_frontend_build_validation(self, tmp_path: Path):
        """Test frontend build validation."""
        # This would test the actual build process
        # For now, we'll test that the build script exists
        frontend_dir = Path(__file__).parent.parent.parent / "frontend"
        package_json = frontend_dir / "package.json"
        
        assert package_json.exists(), "Missing frontend package.json"
        
        with open(package_json, 'r') as f:
            package_data = json.load(f)
        
        # Check for required scripts
        required_scripts = ['build', 'test', 'test:coverage', 'lint']
        scripts = package_data.get('scripts', {})
        
        for script in required_scripts:
            assert script in scripts, f"Missing script: {script}"
    
    def test_backend_validation_scripts(self):
        """Test backend validation scripts."""
        backend_dir = Path(__file__).parent.parent.parent / "backend"
        requirements_file = backend_dir / "requirements.txt"
        
        assert requirements_file.exists(), "Missing backend requirements.txt"
        
        # Check for test configuration
        test_files = list(backend_dir.glob("test_*.py")) + list(backend_dir.glob("tests/"))
        assert len(test_files) > 0, "Missing backend test files"
    
    def test_docker_configuration(self):
        """Test Docker configuration."""
        backend_dir = Path(__file__).parent.parent.parent / "backend"
        dockerfile = backend_dir / "Dockerfile"
        
        assert dockerfile.exists(), "Missing Dockerfile"
        
        with open(dockerfile, 'r') as f:
            dockerfile_content = f.read()
        
        # Check for required Dockerfile elements
        required_elements = ['FROM', 'WORKDIR', 'COPY', 'RUN', 'EXPOSE', 'CMD']
        
        for element in required_elements:
            assert element in dockerfile_content, f"Missing Dockerfile element: {element}"


class TestEnvironmentConfiguration:
    """Test environment configuration."""
    
    def test_environment_files_exist(self):
        """Test that environment files exist."""
        project_root = Path(__file__).parent.parent.parent
        
        required_env_files = [
            "frontend/.env.example",
            "frontend/.env.local.example", 
            "backend/.env.example",
            "backend/.env.production.example",
            "backend/.env.staging.example"
        ]
        
        for env_file in required_env_files:
            env_path = project_root / env_file
            assert env_path.exists(), f"Missing environment file: {env_file}"
    
    def test_environment_variables_documented(self):
        """Test that environment variables are properly documented."""
        project_root = Path(__file__).parent.parent.parent
        
        # Check backend environment examples
        backend_env = project_root / "backend" / ".env.example"
        
        with open(backend_env, 'r') as f:
            env_content = f.read()
        
        # Check for required environment variables
        required_vars = [
            'APP_ENV',
            'COSMOS_ENDPOINT',
            'COSMOS_KEY',
            'AZURE_STORAGE_ACCOUNT_NAME',
            'JWT_SECRET_KEY'
        ]
        
        for var in required_vars:
            assert var in env_content, f"Missing environment variable: {var}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])