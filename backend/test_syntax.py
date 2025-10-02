#!/usr/bin/env python3
"""Test script to verify model syntax and basic functionality"""

import sys
import os

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all models can be imported without syntax errors"""
    try:
        from app.models.user import User, UserCreate, UserUpdate, UserStats
        from app.models.puzzle import Puzzle, PuzzleCreate, PuzzleResponse
        from app.models.guess import Guess, GuessCreate, GuessResponse, GuessHistory
        from app.models.validation import (
            CharacterNameValidator, 
            UniverseValidator, 
            PuzzleIdValidator, 
            GuessValidator,
            validate_email,
            validate_username
        )
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_basic_model_creation():
    """Test basic model creation"""
    try:
        from app.models.user import User
        from app.models.puzzle import Puzzle
        from app.models.guess import Guess
        
        # Test User creation
        user = User(username="test_user", email="test@example.com")
        print(f"✅ User created: {user.username}")
        
        # Test Puzzle creation
        puzzle = Puzzle(
            id="20240115-marvel",
            universe="marvel",
            character="Spider-Man",
            character_aliases=["Spiderman", "Peter Parker"],
            image_key="marvel/spider-man.jpg",
            active_date="2024-01-15"
        )
        print(f"✅ Puzzle created: {puzzle.character}")
        
        # Test Guess creation
        guess = Guess(
            user_id=user.id,
            puzzle_id=puzzle.id,
            guess="Spider-Man",
            is_correct=True,
            attempt_number=1
        )
        print(f"✅ Guess created: {guess.guess}")
        
        return True
    except Exception as e:
        print(f"❌ Model creation error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_validation_utilities():
    """Test validation utility functions"""
    try:
        from app.models.validation import (
            CharacterNameValidator,
            UniverseValidator,
            PuzzleIdValidator,
            GuessValidator,
            validate_email,
            validate_username
        )
        
        # Test character name validation
        assert CharacterNameValidator.is_valid_character_name("Spider-Man") == True
        assert CharacterNameValidator.is_valid_character_name("") == False
        print("✅ Character name validation works")
        
        # Test universe validation
        assert UniverseValidator.is_valid_universe("marvel") == True
        assert UniverseValidator.is_valid_universe("invalid") == False
        print("✅ Universe validation works")
        
        # Test puzzle ID validation
        assert PuzzleIdValidator.is_valid_puzzle_id("20240115-marvel") == True
        assert PuzzleIdValidator.is_valid_puzzle_id("invalid") == False
        print("✅ Puzzle ID validation works")
        
        # Test guess validation
        assert GuessValidator.is_valid_guess("Spider-Man") == True
        assert GuessValidator.is_valid_guess("") == False
        print("✅ Guess validation works")
        
        # Test email validation
        assert validate_email("test@example.com") == True
        assert validate_email("invalid") == False
        print("✅ Email validation works")
        
        # Test username validation
        assert validate_username("test_user") == True
        assert validate_username("ab") == False  # Too short
        print("✅ Username validation works")
        
        return True
    except Exception as e:
        print(f"❌ Validation utility error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("🧪 Testing model syntax and functionality...\n")
    
    tests = [
        ("Import Test", test_imports),
        ("Model Creation Test", test_basic_model_creation),
        ("Validation Utilities Test", test_validation_utilities)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name}...")
        if test_func():
            passed += 1
            print(f"✅ {test_name} PASSED")
        else:
            print(f"❌ {test_name} FAILED")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Models are working correctly.")
        return 0
    else:
        print("💥 Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())