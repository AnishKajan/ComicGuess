#!/usr/bin/env python3
"""
Generate OpenAPI specification from FastAPI application.
"""
import json
import yaml
import sys
import os
from pathlib import Path
import argparse

# Add backend to path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

try:
    from main import app
    from fastapi.openapi.utils import get_openapi
except ImportError as e:
    print(f"❌ Failed to import FastAPI app: {e}")
    print("Make sure you're running this from the project root and backend dependencies are installed")
    sys.exit(1)


def generate_openapi_spec(output_format: str = "json", output_file: str = None) -> dict:
    """Generate OpenAPI specification."""
    print("🔧 Generating OpenAPI specification...")
    
    # Generate OpenAPI schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        servers=app.servers if hasattr(app, 'servers') else None,
        tags=app.openapi_tags if hasattr(app, 'openapi_tags') else None
    )
    
    # Add additional metadata
    openapi_schema["info"]["contact"] = {
        "name": "ComicGuess Support",
        "url": "https://comicguess.com/support",
        "email": "support@comicguess.com"
    }
    
    openapi_schema["info"]["license"] = {
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    }
    
    # Add security schemes
    openapi_schema["components"] = openapi_schema.get("components", {})
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token for authentication"
        },
        "CSRFToken": {
            "type": "apiKey",
            "in": "header",
            "name": "X-CSRF-Token",
            "description": "CSRF protection token"
        }
    }
    
    # Add global security requirement
    openapi_schema["security"] = [
        {"BearerAuth": []},
        {"CSRFToken": []}
    ]
    
    # Save to file if specified
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if output_format.lower() == "yaml":
            with open(output_path, 'w') as f:
                yaml.dump(openapi_schema, f, default_flow_style=False, sort_keys=False)
        else:
            with open(output_path, 'w') as f:
                json.dump(openapi_schema, f, indent=2)
        
        print(f"✅ OpenAPI specification saved to {output_path}")
    
    return openapi_schema


def validate_openapi_spec(spec: dict) -> bool:
    """Validate OpenAPI specification."""
    print("🔍 Validating OpenAPI specification...")
    
    errors = []
    
    # Check required top-level fields
    required_fields = ["openapi", "info", "paths"]
    for field in required_fields:
        if field not in spec:
            errors.append(f"Missing required field: {field}")
    
    # Check info section
    if "info" in spec:
        info = spec["info"]
        required_info_fields = ["title", "version"]
        for field in required_info_fields:
            if field not in info:
                errors.append(f"Missing required info field: {field}")
    
    # Check paths
    if "paths" in spec:
        paths = spec["paths"]
        if not paths:
            errors.append("No paths defined in specification")
        
        # Check each path
        for path, methods in paths.items():
            if not isinstance(methods, dict):
                errors.append(f"Invalid path definition for {path}")
                continue
            
            for method, operation in methods.items():
                if method.lower() in ["get", "post", "put", "delete", "patch", "options", "head"]:
                    # Check operation has required fields
                    if "responses" not in operation:
                        errors.append(f"Missing responses for {method.upper()} {path}")
                    
                    # Check for proper tags
                    if "tags" not in operation:
                        errors.append(f"Missing tags for {method.upper()} {path}")
    
    # Check components
    if "components" in spec:
        components = spec["components"]
        
        # Check security schemes
        if "securitySchemes" in components:
            security_schemes = components["securitySchemes"]
            if not security_schemes:
                errors.append("No security schemes defined")
    
    if errors:
        print("❌ OpenAPI specification validation failed:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("✅ OpenAPI specification validation passed")
        return True


def generate_api_documentation(spec: dict, output_dir: str = "docs/api"):
    """Generate API documentation from OpenAPI spec."""
    print("📚 Generating API documentation...")
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate README for API
    readme_content = f"""# {spec['info']['title']} Documentation

{spec['info'].get('description', '')}

## Version
{spec['info']['version']}

## Base URLs

"""
    
    if 'servers' in spec:
        for server in spec['servers']:
            readme_content += f"- **{server.get('description', 'Server')}**: `{server['url']}`\n"
    
    readme_content += """
## Authentication

This API uses JWT Bearer token authentication. Include your token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

## Rate Limiting

The API implements rate limiting to prevent abuse:
- Guess submissions: 30 requests per minute
- General API requests: 200 requests per minute

Rate limit information is included in response headers:
- `X-RateLimit-Limit`: Request limit per window
- `X-RateLimit-Remaining`: Remaining requests in current window
- `X-RateLimit-Reset`: Time when the rate limit resets

## Error Responses

The API uses standard HTTP status codes and returns error details in JSON format:

```json
{
  "detail": "Error description",
  "error_code": "SPECIFIC_ERROR_CODE",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Endpoints

"""
    
    # Group endpoints by tags
    endpoints_by_tag = {}
    
    for path, methods in spec.get('paths', {}).items():
        for method, operation in methods.items():
            if method.lower() in ["get", "post", "put", "delete", "patch"]:
                tags = operation.get('tags', ['untagged'])
                tag = tags[0] if tags else 'untagged'
                
                if tag not in endpoints_by_tag:
                    endpoints_by_tag[tag] = []
                
                endpoints_by_tag[tag].append({
                    'method': method.upper(),
                    'path': path,
                    'summary': operation.get('summary', ''),
                    'description': operation.get('description', ''),
                    'operation': operation
                })
    
    # Generate documentation for each tag
    for tag, endpoints in endpoints_by_tag.items():
        readme_content += f"\n### {tag.title()}\n\n"
        
        for endpoint in endpoints:
            readme_content += f"#### {endpoint['method']} {endpoint['path']}\n\n"
            
            if endpoint['summary']:
                readme_content += f"{endpoint['summary']}\n\n"
            
            if endpoint['description']:
                readme_content += f"{endpoint['description']}\n\n"
            
            # Add parameters if any
            operation = endpoint['operation']
            if 'parameters' in operation:
                readme_content += "**Parameters:**\n\n"
                for param in operation['parameters']:
                    required = " (required)" if param.get('required', False) else ""
                    readme_content += f"- `{param['name']}` ({param['in']}){required}: {param.get('description', '')}\n"
                readme_content += "\n"
            
            # Add request body if any
            if 'requestBody' in operation:
                readme_content += "**Request Body:**\n\n"
                request_body = operation['requestBody']
                if 'description' in request_body:
                    readme_content += f"{request_body['description']}\n\n"
            
            # Add responses
            if 'responses' in operation:
                readme_content += "**Responses:**\n\n"
                for status_code, response in operation['responses'].items():
                    description = response.get('description', '')
                    readme_content += f"- `{status_code}`: {description}\n"
                readme_content += "\n"
            
            readme_content += "---\n\n"
    
    # Save README
    readme_path = output_path / "README.md"
    with open(readme_path, 'w') as f:
        f.write(readme_content)
    
    print(f"✅ API documentation generated at {readme_path}")
    
    # Generate examples
    examples_dir = output_path / "examples"
    examples_dir.mkdir(exist_ok=True)
    
    # Generate curl examples
    curl_examples = "# API Examples\n\n"
    curl_examples += "## Authentication\n\n"
    curl_examples += "```bash\n"
    curl_examples += "# Get JWT token (replace with actual auth endpoint)\n"
    curl_examples += "TOKEN=$(curl -X POST https://api.comicguess.com/auth/login \\\n"
    curl_examples += "  -H \"Content-Type: application/json\" \\\n"
    curl_examples += "  -d '{\"username\":\"your-username\",\"password\":\"your-password\"}' | jq -r '.access_token')\n"
    curl_examples += "```\n\n"
    
    # Add examples for key endpoints
    key_endpoints = [
        ("GET", "/puzzle/today", "Get today's puzzle"),
        ("POST", "/guess", "Submit a guess"),
        ("GET", "/user/{user_id}", "Get user information"),
        ("GET", "/health", "Health check")
    ]
    
    for method, path, description in key_endpoints:
        curl_examples += f"## {description}\n\n"
        curl_examples += "```bash\n"
        
        if method == "GET":
            if "{user_id}" in path:
                example_path = path.replace("{user_id}", "123")
            else:
                example_path = path
            
            if path == "/health":
                curl_examples += f"curl -X {method} https://api.comicguess.com{example_path}\n"
            else:
                curl_examples += f"curl -X {method} https://api.comicguess.com{example_path} \\\n"
                curl_examples += "  -H \"Authorization: Bearer $TOKEN\"\n"
        
        elif method == "POST":
            curl_examples += f"curl -X {method} https://api.comicguess.com{path} \\\n"
            curl_examples += "  -H \"Authorization: Bearer $TOKEN\" \\\n"
            curl_examples += "  -H \"Content-Type: application/json\" \\\n"
            
            if path == "/guess":
                curl_examples += "  -d '{\"user_id\":\"123\",\"universe\":\"marvel\",\"guess\":\"Spider-Man\"}'\n"
        
        curl_examples += "```\n\n"
    
    examples_path = examples_dir / "curl-examples.md"
    with open(examples_path, 'w') as f:
        f.write(curl_examples)
    
    print(f"✅ API examples generated at {examples_path}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Generate OpenAPI specification")
    parser.add_argument("--format", choices=["json", "yaml"], default="json",
                       help="Output format")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--docs", help="Generate documentation in specified directory")
    parser.add_argument("--validate", action="store_true",
                       help="Validate the generated specification")
    
    args = parser.parse_args()
    
    try:
        # Generate OpenAPI spec
        spec = generate_openapi_spec(args.format, args.output)
        
        # Validate if requested
        if args.validate:
            if not validate_openapi_spec(spec):
                sys.exit(1)
        
        # Generate documentation if requested
        if args.docs:
            generate_api_documentation(spec, args.docs)
        
        # Print summary
        print(f"\n📊 OpenAPI Specification Summary:")
        print(f"  - Title: {spec['info']['title']}")
        print(f"  - Version: {spec['info']['version']}")
        print(f"  - Paths: {len(spec.get('paths', {}))}")
        print(f"  - Components: {len(spec.get('components', {}).get('schemas', {}))}")
        
        if not args.output:
            # Print to stdout if no output file specified
            if args.format.lower() == "yaml":
                print("\n" + yaml.dump(spec, default_flow_style=False, sort_keys=False))
            else:
                print("\n" + json.dumps(spec, indent=2))
    
    except Exception as e:
        print(f"❌ Error generating OpenAPI specification: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()