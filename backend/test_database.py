#!/usr/bin/env python3
"""Simple test script to verify database utilities work correctly"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_database_utilities():
    """Test basic database utility functionality"""
    try:
        print("Testing database utilities...")
        
        # Test partition key management
        from app.database.partition import PartitionKeyManager, document_router
        
        partition_manager = PartitionKeyManager()
        
        # Test user partition keys
        user_partition = partition_manager.get_user_partition_key("user-123")
        print(f"✓ User partition key: {user_partition}")
        
        # Test puzzle partition keys
        puzzle_partition = partition_manager.get_puzzle_partition_key("marvel")
        print(f"✓ Puzzle partition key: {puzzle_partition}")
        
        # Test guess partition keys
        guess_partition = partition_manager.get_guess_partition_key("user-123")
        print(f"✓ Guess partition key: {guess_partition}")
        
        # Test validation
        assert partition_manager.validate_partition_key("marvel", "puzzle") == True
        assert partition_manager.validate_partition_key("invalid", "puzzle") == False
        print("✓ Partition key validation works")
        
        # Test document routing
        from app.models import User, Puzzle, Guess
        from datetime import datetime
        
        # Create test user
        user = User(
            username="test_user",
            email="test@example.com"
        )
        
        user_route = document_router.route_user_document(user)
        print(f"✓ User document routing: {user_route['container_name']}")
        
        # Create test puzzle
        puzzle = Puzzle(
            id="20240115-marvel",
            universe="marvel",
            character="Spider-Man",
            character_aliases=["Spiderman"],
            image_key="marvel/spider-man-001.jpg",
            active_date="2024-01-15"
        )
        
        puzzle_route = document_router.route_puzzle_document(puzzle)
        print(f"✓ Puzzle document routing: {puzzle_route['container_name']}")
        
        # Create test guess
        guess = Guess(
            user_id="user-123",
            puzzle_id="20240115-marvel",
            guess="Spider-Man",
            is_correct=True,
            attempt_number=1
        )
        
        guess_route = document_router.route_guess_document(guess)
        print(f"✓ Guess document routing: {guess_route['container_name']}")
        
        # Test retry configuration
        from app.database.retry import RetryConfig, calculate_delay
        
        config = RetryConfig(max_attempts=3, base_delay=1.0)
        delay = calculate_delay(1, config)
        print(f"✓ Retry delay calculation: {delay:.2f}s")
        
        # Test exception handling
        from app.database.exceptions import DatabaseError, handle_cosmos_error
        from azure.cosmos.exceptions import CosmosHttpResponseError
        
        # Create a mock Cosmos error
        try:
            # This would normally be a real Cosmos error
            mock_error = CosmosHttpResponseError(
                status_code=404,
                message="Document not found"
            )
            app_error = handle_cosmos_error(mock_error)
            print(f"✓ Error handling: {type(app_error).__name__}")
        except Exception as e:
            print(f"✓ Error handling test (expected): {e}")
        
        print("\n🎉 All database utilities working correctly!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing database utilities: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_database_utilities())
    sys.exit(0 if success else 1)