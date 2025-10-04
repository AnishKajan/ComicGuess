#!/usr/bin/env python3
"""
Deployment validation script for ComicGuess application.
Tests deployment readiness and validates deployed services.
"""
import os
import sys
import json
import time
import requests
import subprocess
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin
import argparse


class DeploymentValidator:
    """Validates deployment readiness and deployed services."""
    
    def __init__(self, environment: str = "staging"):
        self.environment = environment
        self.results: List[Dict] = []
        
    def log_result(self, test_name: str, passed: bool, message: str = "", details: Dict = None):
        """Log test result."""
        result = {
            "test": test_name,
            "passed": passed,
            "message": message,
            "details": details or {},
            "environment": self.environment
        }
        self.results.append(result)
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        
        if details:
            for key, value in details.items():
                print(f"  {key}: {value}")
    
    def validate_frontend_build(self) -> bool:
        """Validate frontend build process."""
        print("\n🔍 Validating frontend build...")
        
        try:
            # Change to frontend directory
            os.chdir("frontend")
            
            # Install dependencies
            result = subprocess.run(["npm", "ci"], capture_output=True, text=True)
            if result.returncode != 0:
                self.log_result("Frontend Dependencies", False, "Failed to install dependencies", 
                              {"error": result.stderr})
                return False
            
            self.log_result("Frontend Dependencies", True, "Dependencies installed successfully")
            
            # Run linting
            result = subprocess.run(["npm", "run", "lint"], capture_output=True, text=True)
            if result.returncode != 0:
                self.log_result("Frontend Linting", False, "Linting failed", 
                              {"error": result.stderr})
                return False
            
            self.log_result("Frontend Linting", True, "Linting passed")
            
            # Run type checking
            result = subprocess.run(["npx", "tsc", "--noEmit"], capture_output=True, text=True)
            if result.returncode != 0:
                self.log_result("Frontend Type Check", False, "Type checking failed", 
                              {"error": result.stderr})
                return False
            
            self.log_result("Frontend Type Check", True, "Type checking passed")
            
            # Run tests
            result = subprocess.run(["npm", "run", "test:run"], capture_output=True, text=True)
            if result.returncode != 0:
                self.log_result("Frontend Tests", False, "Tests failed", 
                              {"error": result.stderr})
                return False
            
            self.log_result("Frontend Tests", True, "Tests passed")
            
            # Build application
            env = os.environ.copy()
            env["NEXT_PUBLIC_API_URL"] = "https://api.example.com"
            env["NEXT_PUBLIC_APP_ENV"] = self.environment
            
            result = subprocess.run(["npm", "run", "build"], capture_output=True, text=True, env=env)
            if result.returncode != 0:
                self.log_result("Frontend Build", False, "Build failed", 
                              {"error": result.stderr})
                return False
            
            self.log_result("Frontend Build", True, "Build completed successfully")
            
            # Check build output
            if not os.path.exists(".next"):
                self.log_result("Frontend Build Output", False, "Build output directory not found")
                return False
            
            self.log_result("Frontend Build Output", True, "Build output directory exists")
            
            return True
            
        except Exception as e:
            self.log_result("Frontend Build", False, f"Unexpected error: {str(e)}")
            return False
        finally:
            os.chdir("..")
    
    def validate_backend_build(self) -> bool:
        """Validate backend build process."""
        print("\n🔍 Validating backend build...")
        
        try:
            # Change to backend directory
            os.chdir("backend")
            
            # Install dependencies
            result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                self.log_result("Backend Dependencies", False, "Failed to install dependencies", 
                              {"error": result.stderr})
                return False
            
            self.log_result("Backend Dependencies", True, "Dependencies installed successfully")
            
            # Run linting
            subprocess.run([sys.executable, "-m", "pip", "install", "flake8", "black", "isort"], 
                         capture_output=True)
            
            result = subprocess.run(["flake8", ".", "--count", "--select=E9,F63,F7,F82", 
                                   "--show-source", "--statistics"], capture_output=True, text=True)
            if result.returncode != 0:
                self.log_result("Backend Linting", False, "Linting failed", 
                              {"error": result.stderr})
                return False
            
            self.log_result("Backend Linting", True, "Linting passed")
            
            # Check code formatting
            result = subprocess.run(["black", "--check", "."], capture_output=True, text=True)
            if result.returncode != 0:
                self.log_result("Backend Formatting", False, "Code formatting check failed")
                return False
            
            self.log_result("Backend Formatting", True, "Code formatting check passed")
            
            # Run tests
            result = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v"], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                self.log_result("Backend Tests", False, "Tests failed", 
                              {"error": result.stderr})
                return False
            
            self.log_result("Backend Tests", True, "Tests passed")
            
            return True
            
        except Exception as e:
            self.log_result("Backend Build", False, f"Unexpected error: {str(e)}")
            return False
        finally:
            os.chdir("..")
    
    def validate_docker_build(self) -> bool:
        """Validate Docker build process."""
        print("\n🔍 Validating Docker build...")
        
        try:
            os.chdir("backend")
            
            # Build Docker image
            result = subprocess.run(["docker", "build", "-t", "comicguess-backend:test", "."], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                self.log_result("Docker Build", False, "Docker build failed", 
                              {"error": result.stderr})
                return False
            
            self.log_result("Docker Build", True, "Docker image built successfully")
            
            # Test Docker container
            container_name = f"test-container-{int(time.time())}"
            
            # Start container
            result = subprocess.run(["docker", "run", "-d", "--name", container_name, 
                                   "-p", "8001:8000", "comicguess-backend:test"], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                self.log_result("Docker Container Start", False, "Failed to start container", 
                              {"error": result.stderr})
                return False
            
            # Wait for container to start
            time.sleep(10)
            
            try:
                # Test health endpoint
                response = requests.get("http://localhost:8001/health", timeout=10)
                if response.status_code == 200:
                    self.log_result("Docker Container Health", True, "Health check passed")
                else:
                    self.log_result("Docker Container Health", False, 
                                  f"Health check failed with status {response.status_code}")
                    return False
            
            except requests.RequestException as e:
                self.log_result("Docker Container Health", False, f"Health check failed: {str(e)}")
                return False
            
            finally:
                # Clean up container
                subprocess.run(["docker", "stop", container_name], capture_output=True)
                subprocess.run(["docker", "rm", container_name], capture_output=True)
            
            return True
            
        except Exception as e:
            self.log_result("Docker Build", False, f"Unexpected error: {str(e)}")
            return False
        finally:
            os.chdir("..")
    
    def validate_deployed_service(self, base_url: str) -> bool:
        """Validate deployed service endpoints."""
        print(f"\n🔍 Validating deployed service at {base_url}...")
        
        try:
            # Test health endpoint
            health_url = urljoin(base_url, "/health")
            response = requests.get(health_url, timeout=30)
            
            if response.status_code == 200:
                health_data = response.json()
                self.log_result("Service Health", True, "Health endpoint accessible", 
                              {"response": health_data})
            else:
                self.log_result("Service Health", False, 
                              f"Health endpoint returned {response.status_code}")
                return False
            
            # Test API endpoints
            endpoints_to_test = [
                ("/puzzle/today?universe=marvel", "GET"),
                ("/puzzle/today?universe=DC", "GET"),
                ("/puzzle/today?universe=image", "GET"),
            ]
            
            for endpoint, method in endpoints_to_test:
                url = urljoin(base_url, endpoint)
                
                try:
                    if method == "GET":
                        response = requests.get(url, timeout=10)
                    else:
                        continue  # Skip non-GET for now
                    
                    # We expect 401 or 404 for unauthorized requests, not 500
                    if response.status_code in [200, 401, 404]:
                        self.log_result(f"Endpoint {endpoint}", True, 
                                      f"Endpoint accessible (status: {response.status_code})")
                    else:
                        self.log_result(f"Endpoint {endpoint}", False, 
                                      f"Unexpected status: {response.status_code}")
                
                except requests.RequestException as e:
                    self.log_result(f"Endpoint {endpoint}", False, f"Request failed: {str(e)}")
            
            return True
            
        except Exception as e:
            self.log_result("Service Validation", False, f"Unexpected error: {str(e)}")
            return False
    
    def validate_security_headers(self, base_url: str) -> bool:
        """Validate security headers."""
        print(f"\n🔍 Validating security headers for {base_url}...")
        
        try:
            response = requests.get(base_url, timeout=10)
            headers = response.headers
            
            # Check for security headers
            security_headers = {
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": ["DENY", "SAMEORIGIN"],
                "X-XSS-Protection": "1; mode=block",
                "Strict-Transport-Security": None,  # Should exist
                "Content-Security-Policy": None,    # Should exist
            }
            
            for header, expected_value in security_headers.items():
                if header in headers:
                    if expected_value is None:
                        self.log_result(f"Security Header {header}", True, "Header present")
                    elif isinstance(expected_value, list):
                        if headers[header] in expected_value:
                            self.log_result(f"Security Header {header}", True, 
                                          f"Header value: {headers[header]}")
                        else:
                            self.log_result(f"Security Header {header}", False, 
                                          f"Unexpected value: {headers[header]}")
                    else:
                        if headers[header] == expected_value:
                            self.log_result(f"Security Header {header}", True, 
                                          f"Header value: {headers[header]}")
                        else:
                            self.log_result(f"Security Header {header}", False, 
                                          f"Expected: {expected_value}, Got: {headers[header]}")
                else:
                    self.log_result(f"Security Header {header}", False, "Header missing")
            
            return True
            
        except Exception as e:
            self.log_result("Security Headers", False, f"Unexpected error: {str(e)}")
            return False
    
    def generate_report(self) -> Dict:
        """Generate validation report."""
        passed_tests = [r for r in self.results if r["passed"]]
        failed_tests = [r for r in self.results if not r["passed"]]
        
        report = {
            "environment": self.environment,
            "timestamp": time.time(),
            "summary": {
                "total_tests": len(self.results),
                "passed": len(passed_tests),
                "failed": len(failed_tests),
                "success_rate": len(passed_tests) / len(self.results) * 100 if self.results else 0
            },
            "results": self.results,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests
        }
        
        return report
    
    def run_all_validations(self, deployed_url: Optional[str] = None) -> bool:
        """Run all validation tests."""
        print(f"🚀 Starting deployment validation for {self.environment} environment")
        
        # Build validations
        frontend_ok = self.validate_frontend_build()
        backend_ok = self.validate_backend_build()
        docker_ok = self.validate_docker_build()
        
        # Service validations (if URL provided)
        service_ok = True
        security_ok = True
        
        if deployed_url:
            service_ok = self.validate_deployed_service(deployed_url)
            security_ok = self.validate_security_headers(deployed_url)
        
        # Generate report
        report = self.generate_report()
        
        # Save report
        report_file = f"deployment-validation-{self.environment}-{int(time.time())}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📊 Validation Report:")
        print(f"Total Tests: {report['summary']['total_tests']}")
        print(f"Passed: {report['summary']['passed']}")
        print(f"Failed: {report['summary']['failed']}")
        print(f"Success Rate: {report['summary']['success_rate']:.1f}%")
        print(f"Report saved to: {report_file}")
        
        # Return overall success
        all_validations_passed = all([frontend_ok, backend_ok, docker_ok, service_ok, security_ok])
        
        if all_validations_passed:
            print("\n✅ All validations passed! Deployment is ready.")
        else:
            print("\n❌ Some validations failed. Please review and fix issues.")
        
        return all_validations_passed


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Validate deployment readiness")
    parser.add_argument("--environment", default="staging", 
                       choices=["staging", "production", "test"],
                       help="Environment to validate")
    parser.add_argument("--url", help="URL of deployed service to validate")
    parser.add_argument("--build-only", action="store_true", 
                       help="Only run build validations")
    
    args = parser.parse_args()
    
    validator = DeploymentValidator(args.environment)
    
    if args.build_only:
        # Only run build validations
        frontend_ok = validator.validate_frontend_build()
        backend_ok = validator.validate_backend_build()
        docker_ok = validator.validate_docker_build()
        
        success = all([frontend_ok, backend_ok, docker_ok])
    else:
        # Run all validations
        success = validator.run_all_validations(args.url)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()