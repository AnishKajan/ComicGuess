#!/usr/bin/env python3
"""Simple test script for authentication system"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def test_jwt_basic():
    """Test basic JWT functionality"""
    try:
        from app.auth.jwt_handler import create_access_token, verify_token, get_user_id_from_token
        
        user_id = "test-user-123"
        
        # Create token
        token = create_access_token(user_id)
        print(f"✓ Created access token: {token[:50]}...")
        
        # Verify token
        payload = verify_token(token)
        print(f"✓ Verified token payload: {payload}")
        
        # Extract user ID
        extracted_id = get_user_id_from_token(token)
        print(f"✓ Extracted user ID: {extracted_id}")
        
        assert extracted_id == user_id
        print("✓ JWT basic functionality test passed!")
        
    except Exception as e:
        print(f"✗ JWT test failed: {e}")
        return False
    
    return True

def test_session_basic():
    """Test basic session functionality"""
    try:
        from app.auth.session import create_session, get_session, invalidate_session
        from app.models.user import User
        
        # Create test user
        user = User(
            id="test-user-456",
            username="testuser",
            email="test@example.com"
        )
        
        # Create session
        session = create_session(user)
        print(f"✓ Created session for user: {session.user_id}")
        
        # Get session
        retrieved_session = get_session(user.id)
        print(f"✓ Retrieved session: {retrieved_session.user_id}")
        
        # Invalidate session
        result = invalidate_session(user.id)
        print(f"✓ Invalidated session: {result}")
        
        print("✓ Session basic functionality test passed!")
        
    except Exception as e:
        print(f"✗ Session test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("Testing authentication system...")
    
    jwt_success = test_jwt_basic()
    session_success = test_session_basic()
    
    if jwt_success and session_success:
        print("\n🎉 All authentication tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some authentication tests failed!")
        sys.exit(1)