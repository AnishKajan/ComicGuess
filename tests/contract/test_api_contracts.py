"""
API Contract Tests - Validate API responses against OpenAPI specification.
"""
import json
import pytest
import requests
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
from jsonschema import validate, ValidationError
import sys
import os

# Add backend to path for importing models
backend_dir = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_dir))


class APIContractTester:
    """Test API contracts against OpenAPI specification."""
    
    def __init__(self, base_url: str, openapi_spec: Dict[str, Any]):
        self.base_url = base_url.rstrip('/')
        self.spec = openapi_spec
        self.session = requests.Session()
        
    def set_auth_token(self, token: str):
        """Set authentication token for requests."""
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def get_endpoint_schema(self, path: str, method: str, response_code: str) -> Optional[Dict]:
        """Get response schema for endpoint from OpenAPI spec."""
        paths = self.spec.get('paths', {})
        
        if path not in paths:
            return None
        
        methods = paths[path]
        if method.lower() not in methods:
            return None
        
        operation = methods[method.lower()]
        responses = operation.get('responses', {})
        
        if response_code not in responses:
            return None
        
        response = responses[response_code]
        content = response.get('content', {})
        
        # Look for JSON content
        json_content = content.get('application/json', {})
        return json_content.get('schema')
    
    def validate_response_schema(self, response: requests.Response, 
                                path: str, method: str) -> bool:
        """Validate response against OpenAPI schema."""
        response_code = str(response.status_code)
        schema = self.get_endpoint_schema(path, method, response_code)
        
        if not schema:
            print(f"⚠️ No schema found for {method.upper()} {path} {response_code}")
            return True  # Skip validation if no schema
        
        try:
            response_data = response.json()
            validate(instance=response_data, schema=schema)
            return True
        except ValidationError as e:
            print(f"❌ Schema validation failed for {method.upper()} {path}: {e.message}")
            return False
        except json.JSONDecodeError:
            print(f"❌ Invalid JSON response for {method.upper()} {path}")
            return False
    
    def test_endpoint(self, path: str, method: str = "GET", 
                     data: Optional[Dict] = None, 
                     params: Optional[Dict] = None,
                     expected_status: int = 200) -> bool:
        """Test a single endpoint."""
        url = f"{self.base_url}{path}"
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=params)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data, params=params)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data, params=params)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, params=params)
            else:
                print(f"❌ Unsupported method: {method}")
                return False
            
            # Check status code
            if response.status_code != expected_status:
                print(f"❌ Expected status {expected_status}, got {response.status_code} for {method.upper()} {path}")
                return False
            
            # Validate response schema
            if not self.validate_response_schema(response, path, method):
                return False
            
            print(f"✅ {method.upper()} {path} - Status: {response.status_code}")
            return True
            
        except requests.RequestException as e:
            print(f"❌ Request failed for {method.upper()} {path}: {e}")
            return False


class TestAPIContracts:
    """Test API contracts against OpenAPI specification."""
    
    @pytest.fixture(scope="class")
    def openapi_spec(self):
        """Load OpenAPI specification."""
        # Try to load from generated file first
        spec_file = Path(__file__).parent.parent.parent / "docs" / "api" / "openapi.json"
        
        if not spec_file.exists():
            # Generate spec if it doesn't exist
            try:
                from scripts.generate_openapi import generate_openapi_spec
                spec = generate_openapi_spec()
                return spec
            except ImportError:
                pytest.skip("Cannot load or generate OpenAPI specification")
        
        with open(spec_file, 'r') as f:
            return json.load(f)
    
    @pytest.fixture(scope="class")
    def api_tester(self, openapi_spec):
        """Create API contract tester."""
        base_url = os.getenv("TEST_API_URL", "http://localhost:8000")
        return APIContractTester(base_url, openapi_spec)
    
    @pytest.fixture(scope="class")
    def auth_token(self, api_tester):
        """Get authentication token for testing."""
        # For testing, we'll use a mock token or skip auth-required tests
        token = os.getenv("TEST_AUTH_TOKEN")
        if token:
            api_tester.set_auth_token(token)
        return token
    
    def test_health_endpoint(self, api_tester):
        """Test health endpoint contract."""
        assert api_tester.test_endpoint("/health", "GET", expected_status=200)
    
    def test_root_endpoint(self, api_tester):
        """Test root endpoint contract."""
        assert api_tester.test_endpoint("/", "GET", expected_status=200)
    
    def test_puzzle_today_endpoint(self, api_tester, auth_token):
        """Test puzzle today endpoint contract."""
        if not auth_token:
            pytest.skip("No auth token provided")
        
        # Test with different universe parameters
        universes = ["marvel", "dc", "image"]
        
        for universe in universes:
            # This might return 404 if no puzzle exists, which is valid
            result = api_tester.test_endpoint(
                "/puzzle/today", 
                "GET", 
                params={"universe": universe},
                expected_status=200
            )
            
            if not result:
                # Try with 404 status (no puzzle available)
                result = api_tester.test_endpoint(
                    "/puzzle/today", 
                    "GET", 
                    params={"universe": universe},
                    expected_status=404
                )
            
            assert result, f"Puzzle endpoint failed for universe: {universe}"
    
    def test_guess_endpoint_schema(self, api_tester, auth_token):
        """Test guess endpoint contract (schema validation only)."""
        if not auth_token:
            pytest.skip("No auth token provided")
        
        # Test with valid guess data structure
        guess_data = {
            "user_id": "test-user-123",
            "universe": "marvel",
            "guess": "Spider-Man"
        }
        
        # This might fail with 404 (no puzzle) or 400 (invalid guess), but should have valid schema
        result = api_tester.test_endpoint(
            "/guess", 
            "POST", 
            data=guess_data,
            expected_status=200
        )
        
        if not result:
            # Try with expected error status codes
            for status in [400, 404, 422]:
                result = api_tester.test_endpoint(
                    "/guess", 
                    "POST", 
                    data=guess_data,
                    expected_status=status
                )
                if result:
                    break
        
        assert result, "Guess endpoint failed schema validation"
    
    def test_user_endpoint_schema(self, api_tester, auth_token):
        """Test user endpoint contract."""
        if not auth_token:
            pytest.skip("No auth token provided")
        
        # Test user endpoint with test user ID
        test_user_id = "test-user-123"
        
        result = api_tester.test_endpoint(
            f"/user/{test_user_id}", 
            "GET",
            expected_status=200
        )
        
        if not result:
            # Try with 404 status (user not found)
            result = api_tester.test_endpoint(
                f"/user/{test_user_id}", 
                "GET",
                expected_status=404
            )
        
        assert result, "User endpoint failed schema validation"
    
    def test_openapi_spec_completeness(self, openapi_spec):
        """Test that OpenAPI spec has required components."""
        # Check required top-level fields
        assert "openapi" in openapi_spec
        assert "info" in openapi_spec
        assert "paths" in openapi_spec
        
        # Check info section
        info = openapi_spec["info"]
        assert "title" in info
        assert "version" in info
        assert "description" in info
        
        # Check that we have some paths
        paths = openapi_spec["paths"]
        assert len(paths) > 0, "No API paths defined"
        
        # Check for key endpoints
        expected_paths = ["/health", "/puzzle/today", "/guess"]
        for path in expected_paths:
            assert any(path in p for p in paths.keys()), f"Missing expected path: {path}"
    
    def test_security_schemes(self, openapi_spec):
        """Test that security schemes are properly defined."""
        components = openapi_spec.get("components", {})
        security_schemes = components.get("securitySchemes", {})
        
        # Check for JWT authentication
        assert "BearerAuth" in security_schemes, "Missing BearerAuth security scheme"
        
        bearer_auth = security_schemes["BearerAuth"]
        assert bearer_auth["type"] == "http"
        assert bearer_auth["scheme"] == "bearer"
    
    def test_response_schemas(self, openapi_spec):
        """Test that endpoints have proper response schemas."""
        paths = openapi_spec.get("paths", {})
        
        for path, methods in paths.items():
            for method, operation in methods.items():
                if method.lower() in ["get", "post", "put", "delete", "patch"]:
                    responses = operation.get("responses", {})
                    assert len(responses) > 0, f"No responses defined for {method.upper()} {path}"
                    
                    # Check for success response
                    success_codes = ["200", "201", "204"]
                    has_success = any(code in responses for code in success_codes)
                    assert has_success, f"No success response defined for {method.upper()} {path}"


class TestContractGeneration:
    """Test contract generation functionality."""
    
    def test_openapi_generation_script_exists(self):
        """Test that OpenAPI generation script exists."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "generate-openapi.py"
        assert script_path.exists()
        assert os.access(script_path, os.X_OK)
    
    def test_openapi_spec_can_be_generated(self):
        """Test that OpenAPI spec can be generated."""
        try:
            # Try to import and run the generation function
            sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
            from generate_openapi import generate_openapi_spec
            
            spec = generate_openapi_spec()
            
            # Basic validation
            assert isinstance(spec, dict)
            assert "openapi" in spec
            assert "info" in spec
            assert "paths" in spec
            
        except ImportError:
            pytest.skip("Cannot import OpenAPI generation script")
        except Exception as e:
            pytest.fail(f"OpenAPI generation failed: {e}")
    
    def test_api_documentation_structure(self):
        """Test API documentation structure."""
        docs_dir = Path(__file__).parent.parent.parent / "docs" / "api"
        
        # Check if docs can be generated
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
            from generate_openapi import generate_openapi_spec, generate_api_documentation
            
            spec = generate_openapi_spec()
            
            # Generate docs in temporary directory
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                generate_api_documentation(spec, temp_dir)
                
                # Check generated files
                temp_path = Path(temp_dir)
                assert (temp_path / "README.md").exists()
                assert (temp_path / "examples" / "curl-examples.md").exists()
                
        except ImportError:
            pytest.skip("Cannot import documentation generation functions")


def run_contract_tests_against_live_api(base_url: str, auth_token: str = None):
    """Run contract tests against a live API instance."""
    print(f"🧪 Running contract tests against {base_url}")
    
    # Load OpenAPI spec
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
        from generate_openapi import generate_openapi_spec
        spec = generate_openapi_spec()
    except ImportError:
        print("❌ Cannot load OpenAPI specification")
        return False
    
    # Create tester
    tester = APIContractTester(base_url, spec)
    if auth_token:
        tester.set_auth_token(auth_token)
    
    # Test key endpoints
    test_cases = [
        ("/health", "GET", 200),
        ("/", "GET", 200),
    ]
    
    if auth_token:
        test_cases.extend([
            ("/puzzle/today?universe=marvel", "GET", [200, 404]),
            ("/user/test-user", "GET", [200, 404]),
        ])
    
    passed = 0
    total = len(test_cases)
    
    for path, method, expected_status in test_cases:
        if isinstance(expected_status, list):
            # Try multiple status codes
            success = False
            for status in expected_status:
                if tester.test_endpoint(path, method, expected_status=status):
                    success = True
                    break
            if success:
                passed += 1
        else:
            if tester.test_endpoint(path, method, expected_status=expected_status):
                passed += 1
    
    print(f"\n📊 Contract Test Results: {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run API contract tests")
    parser.add_argument("--url", default="http://localhost:8000", 
                       help="API base URL")
    parser.add_argument("--token", help="Authentication token")
    
    args = parser.parse_args()
    
    success = run_contract_tests_against_live_api(args.url, args.token)
    sys.exit(0 if success else 1)