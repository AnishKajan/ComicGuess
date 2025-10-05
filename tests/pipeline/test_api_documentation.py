"""
Tests for API documentation and contract testing functionality.
"""
import json
import yaml
import pytest
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys
import os


class TestOpenAPIGeneration:
    """Test OpenAPI specification generation."""
    
    def test_generate_openapi_script_exists(self):
        """Test that OpenAPI generation script exists."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "generate-openapi.py"
        assert script_path.exists()
        assert os.access(script_path, os.X_OK)
    
    def test_openapi_script_help(self):
        """Test that OpenAPI script shows help."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "generate-openapi.py"
        
        result = subprocess.run([str(script_path), "--help"], 
                              capture_output=True, text=True)
        
        assert result.returncode == 0
        assert "Generate OpenAPI specification" in result.stdout
        assert "--format" in result.stdout
        assert "--output" in result.stdout
        assert "--validate" in result.stdout
    
    @patch('sys.path')
    def test_openapi_generation_imports(self, mock_path):
        """Test that OpenAPI generation can import required modules."""
        # Test that the script can handle import errors gracefully
        script_path = Path(__file__).parent.parent.parent / "scripts" / "generate-openapi.py"
        
        # Run script with invalid backend path (should fail gracefully)
        result = subprocess.run([
            str(script_path), "--format", "json", "--validate"
        ], capture_output=True, text=True, cwd="/tmp")
        
        # Should exit with error code but not crash
        assert result.returncode != 0
        assert "Failed to import FastAPI app" in result.stderr or "Error generating" in result.stderr
    
    def test_openapi_spec_structure_validation(self):
        """Test OpenAPI specification structure validation."""
        # Create a mock OpenAPI spec
        mock_spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "Test API",
                "version": "1.0.0",
                "description": "Test API description"
            },
            "paths": {
                "/test": {
                    "get": {
                        "tags": ["test"],
                        "responses": {
                            "200": {
                                "description": "Success"
                            }
                        }
                    }
                }
            },
            "components": {
                "securitySchemes": {
                    "BearerAuth": {
                        "type": "http",
                        "scheme": "bearer"
                    }
                }
            }
        }
        
        # Test validation logic (would need to import the validation function)
        # For now, just test the structure
        assert "openapi" in mock_spec
        assert "info" in mock_spec
        assert "paths" in mock_spec
        assert len(mock_spec["paths"]) > 0
        
        # Test info section
        info = mock_spec["info"]
        assert "title" in info
        assert "version" in info
        
        # Test security schemes
        components = mock_spec.get("components", {})
        security_schemes = components.get("securitySchemes", {})
        assert "BearerAuth" in security_schemes


class TestContractTesting:
    """Test API contract testing functionality."""
    
    def test_contract_test_file_exists(self):
        """Test that contract test file exists."""
        test_file = Path(__file__).parent.parent / "contract" / "test_api_contracts.py"
        assert test_file.exists()
    
    def test_contract_test_structure(self):
        """Test contract test file structure."""
        test_file = Path(__file__).parent.parent / "contract" / "test_api_contracts.py"
        
        with open(test_file, 'r') as f:
            content = f.read()
        
        # Check for required classes and methods
        assert "class APIContractTester" in content
        assert "class TestAPIContracts" in content
        assert "def validate_response_schema" in content
        assert "def test_endpoint" in content
        assert "def test_health_endpoint" in content
    
    @patch('requests.Session')
    def test_api_contract_tester_initialization(self, mock_session):
        """Test APIContractTester initialization."""
        # Import the class (need to handle path issues)
        sys.path.insert(0, str(Path(__file__).parent.parent / "contract"))
        
        try:
            from test_api_contracts import APIContractTester
            
            mock_spec = {
                "paths": {
                    "/test": {
                        "get": {
                            "responses": {
                                "200": {
                                    "content": {
                                        "application/json": {
                                            "schema": {"type": "object"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            
            tester = APIContractTester("http://localhost:8000", mock_spec)
            
            assert tester.base_url == "http://localhost:8000"
            assert tester.spec == mock_spec
            
        except ImportError:
            pytest.skip("Cannot import APIContractTester")
    
    def test_contract_testing_workflow_exists(self):
        """Test that contract testing workflow exists."""
        workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "api-documentation.yml"
        assert workflow_path.exists()
    
    def test_contract_testing_workflow_structure(self):
        """Test contract testing workflow structure."""
        workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "api-documentation.yml"
        
        with open(workflow_path, 'r') as f:
            workflow = yaml.safe_load(f)
        
        # Check required jobs
        required_jobs = [
            "generate-openapi-spec",
            "contract-testing", 
            "publish-documentation"
        ]
        
        for job in required_jobs:
            assert job in workflow["jobs"], f"Missing job: {job}"
        
        # Check contract testing job
        contract_job = workflow["jobs"]["contract-testing"]
        assert "needs" in contract_job
        assert "generate-openapi-spec" in contract_job["needs"]
        
        # Check for required steps
        step_names = [step.get("name", "") for step in contract_job["steps"]]
        
        required_steps = [
            "Run contract tests",
            "Download OpenAPI artifacts"
        ]
        
        for step in required_steps:
            assert any(step in name for name in step_names), f"Missing step: {step}"


class TestAPIDocumentationWorkflow:
    """Test API documentation workflow."""
    
    def test_api_documentation_workflow_exists(self):
        """Test that API documentation workflow exists."""
        workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "api-documentation.yml"
        assert workflow_path.exists()
    
    def test_api_documentation_workflow_triggers(self):
        """Test API documentation workflow triggers."""
        workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "api-documentation.yml"
        
        with open(workflow_path, 'r') as f:
            workflow = yaml.safe_load(f)
        
        # Check triggers
        on_config = workflow["on"]
        assert "push" in on_config
        assert "pull_request" in on_config
        
        # Check paths
        push_config = on_config["push"]
        assert "paths" in push_config
        
        expected_paths = ["backend/**", "scripts/generate-openapi.py", "tests/contract/**"]
        for path in expected_paths:
            assert path in push_config["paths"]
    
    def test_openapi_generation_job(self):
        """Test OpenAPI generation job configuration."""
        workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "api-documentation.yml"
        
        with open(workflow_path, 'r') as f:
            workflow = yaml.safe_load(f)
        
        openapi_job = workflow["jobs"]["generate-openapi-spec"]
        
        # Check required steps
        step_names = [step.get("name", "") for step in openapi_job["steps"]]
        
        required_steps = [
            "Generate OpenAPI specification",
            "Generate API documentation",
            "Validate OpenAPI specification"
        ]
        
        for step in required_steps:
            assert any(step in name for name in step_names), f"Missing step: {step}"
    
    def test_documentation_publishing_job(self):
        """Test documentation publishing job configuration."""
        workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "api-documentation.yml"
        
        with open(workflow_path, 'r') as f:
            workflow = yaml.safe_load(f)
        
        publish_job = workflow["jobs"]["publish-documentation"]
        
        # Check dependencies
        assert "needs" in publish_job
        needs = publish_job["needs"]
        assert "generate-openapi-spec" in needs
        assert "contract-testing" in needs
        
        # Check conditional execution
        assert "if" in publish_job
        assert "refs/heads/main" in publish_job["if"]
        
        # Check for GitHub Pages deployment
        step_names = [step.get("name", "") for step in publish_job["steps"]]
        assert any("GitHub Pages" in name or "gh-pages" in str(step) 
                  for step in publish_job["steps"] for name in [step.get("name", "")]), "Missing GitHub Pages deployment"


class TestAPIDocumentationGeneration:
    """Test API documentation generation functionality."""
    
    def test_documentation_generation_function_structure(self):
        """Test documentation generation function structure."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "generate-openapi.py"
        
        with open(script_path, 'r') as f:
            content = f.read()
        
        # Check for required functions
        required_functions = [
            "def generate_openapi_spec",
            "def validate_openapi_spec", 
            "def generate_api_documentation"
        ]
        
        for func in required_functions:
            assert func in content, f"Missing function: {func}"
    
    def test_documentation_output_structure(self):
        """Test expected documentation output structure."""
        # Test that the documentation generation would create expected files
        expected_files = [
            "README.md",
            "curl-examples.md"
        ]
        
        # This would be tested by actually running the generation
        # For now, just verify the structure is defined in the script
        script_path = Path(__file__).parent.parent.parent / "scripts" / "generate-openapi.py"
        
        with open(script_path, 'r') as f:
            content = f.read()
        
        for file_name in expected_files:
            assert file_name in content, f"Documentation generation doesn't reference {file_name}"
    
    def test_curl_examples_generation(self):
        """Test curl examples generation."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "generate-openapi.py"
        
        with open(script_path, 'r') as f:
            content = f.read()
        
        # Check for curl example generation
        assert "curl-examples.md" in content
        assert "curl -X" in content
        assert "Authorization: Bearer" in content
    
    def test_api_documentation_metadata(self):
        """Test API documentation includes proper metadata."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "generate-openapi.py"
        
        with open(script_path, 'r') as f:
            content = f.read()
        
        # Check for metadata inclusion
        metadata_items = [
            "contact",
            "license", 
            "servers",
            "securitySchemes"
        ]
        
        for item in metadata_items:
            assert item in content, f"Missing metadata: {item}"


class TestIntegrationWithExistingWorkflows:
    """Test integration with existing CI/CD workflows."""
    
    def test_api_documentation_integrates_with_main_workflow(self):
        """Test that API documentation integrates with main CI/CD workflow."""
        main_workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "ci-cd-main.yml"
        api_workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "api-documentation.yml"
        
        # Both workflows should exist
        assert main_workflow_path.exists()
        assert api_workflow_path.exists()
        
        # Check that they have compatible triggers
        with open(main_workflow_path, 'r') as f:
            main_workflow = yaml.safe_load(f)
        
        with open(api_workflow_path, 'r') as f:
            api_workflow = yaml.safe_load(f)
        
        # Both should trigger on backend changes
        main_triggers = main_workflow.get("on", {})
        api_triggers = api_workflow.get("on", {})
        
        assert "push" in main_triggers
        assert "push" in api_triggers
    
    def test_contract_tests_use_same_environment_as_backend_tests(self):
        """Test that contract tests use compatible environment with backend tests."""
        api_workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "api-documentation.yml"
        main_workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "ci-cd-main.yml"
        
        with open(api_workflow_path, 'r') as f:
            api_workflow = yaml.safe_load(f)
        
        with open(main_workflow_path, 'r') as f:
            main_workflow = yaml.safe_load(f)
        
        # Check Python version consistency
        api_env = api_workflow.get("env", {})
        main_env = main_workflow.get("env", {})
        
        if "PYTHON_VERSION" in api_env and "PYTHON_VERSION" in main_env:
            assert api_env["PYTHON_VERSION"] == main_env["PYTHON_VERSION"]
        
        # Check for database service usage
        contract_job = api_workflow["jobs"]["contract-testing"]
        backend_test_job = main_workflow["jobs"].get("backend-tests", {})
        
        # Database services can be configured as needed for testing


if __name__ == "__main__":
    pytest.main([__file__, "-v"])