"""Validation script for authentication system"""

def validate_auth_structure():
    """Validate that authentication modules are properly structured"""
    
    print("Validating authentication system structure...")
    
    # Check JWT handler
    try:
        with open('app/auth/jwt_handler.py', 'r') as f:
            content = f.read()
            
        required_jwt_elements = [
            'class JWTHandler',
            'def create_access_token',
            'def create_refresh_token', 
            'def verify_token',
            'def get_user_id_from_token',
            'def refresh_access_token',
            'def create_token_pair'
        ]
        
        for element in required_jwt_elements:
            if element in content:
                print(f"✓ Found {element}")
            else:
                print(f"✗ Missing {element}")
                return False
                
    except FileNotFoundError:
        print("✗ JWT handler file not found")
        return False
    
    # Check session manager
    try:
        with open('app/auth/session.py', 'r') as f:
            content = f.read()
            
        required_session_elements = [
            'class UserSession',
            'class SessionManager',
            'def create_session',
            'def get_session',
            'def invalidate_session'
        ]
        
        for element in required_session_elements:
            if element in content:
                print(f"✓ Found {element}")
            else:
                print(f"✗ Missing {element}")
                return False
                
    except FileNotFoundError:
        print("✗ Session manager file not found")
        return False
    
    # Check middleware
    try:
        with open('app/auth/middleware.py', 'r') as f:
            content = f.read()
            
        required_middleware_elements = [
            'class AuthenticationError',
            'class AuthorizationError',
            'async def get_current_user_session',
            'async def get_current_user',
            'class AuthMiddleware'
        ]
        
        for element in required_middleware_elements:
            if element in content:
                print(f"✓ Found {element}")
            else:
                print(f"✗ Missing {element}")
                return False
                
    except FileNotFoundError:
        print("✗ Middleware file not found")
        return False
    
    # Check tests
    try:
        with open('tests/test_auth.py', 'r') as f:
            content = f.read()
            
        required_test_elements = [
            'class TestJWTHandler',
            'class TestSessionManager',
            'class TestUserSession',
            'def test_create_access_token',
            'def test_create_session'
        ]
        
        for element in required_test_elements:
            if element in content:
                print(f"✓ Found {element}")
            else:
                print(f"✗ Missing {element}")
                return False
                
    except FileNotFoundError:
        print("✗ Auth tests file not found")
        return False
    
    print("\n🎉 Authentication system structure validation passed!")
    return True

if __name__ == "__main__":
    success = validate_auth_structure()
    if not success:
        exit(1)