#!/usr/bin/env python3
"""Simple test script to verify models work correctly"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_models():
    """Test basic model functionality"""
    try:
        # Test User model
        from app.models.user import User, UserCreate
        
        user_data = {
            "username": "test_user",
            "email": "test@example.com"
        }
        user = User(**user_data)
        print(f"✓ User model created: {user.username}")
        
        # Test Puzzle model
        from app.models.puzzle import Puzzle
        
        puzzle_data = {
            "id": "20240115-marvel",
            "universe": "marvel",
            "character": "Spider-Man",
            "character_aliases": ["Spiderman", "Peter Parker"],
            "image_key": "marvel/spider-man-001.jpg",
            "active_date": "2024-01-15"
        }
        puzzle = Puzzle(**puzzle_data)
        print(f"✓ Puzzle model created: {puzzle.character}")
        
        # Test guess validation
        assert puzzle.is_correct_guess("Spider-Man")
        assert puzzle.is_correct_guess("spiderman")
        assert not puzzle.is_correct_guess("Iron Man")
        print("✓ Puzzle guess validation works")
        
        # Test Guess model
        from app.models.guess import Guess
        
        guess_data = {
            "user_id": "user-123",
            "puzzle_id": "20240115-marvel",
            "guess": "Spider-Man",
            "is_correct": True,
            "attempt_number": 1
        }
        guess = Guess(**guess_data)
        print(f"✓ Guess model created: {guess.guess}")
        
        print("\n🎉 All models working correctly!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing models: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_models()
    sys.exit(0 if success else 1)