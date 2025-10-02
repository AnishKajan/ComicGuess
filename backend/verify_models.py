#!/usr/bin/env python3
"""Simple verification script for models"""

def main():
    try:
        print("Testing User model...")
        from app.models.user import User
        
        user = User(
            username="test_user",
            email="test@example.com"
        )
        print(f"✓ User created: {user.username} ({user.email})")
        
        print("\nTesting Puzzle model...")
        from app.models.puzzle import Puzzle
        
        puzzle = Puzzle(
            id="20240115-marvel",
            universe="marvel",
            character="Spider-Man",
            character_aliases=["Spiderman", "Peter Parker"],
            image_key="marvel/spider-man-001.jpg",
            active_date="2024-01-15"
        )
        print(f"✓ Puzzle created: {puzzle.character} in {puzzle.universe}")
        
        # Test guess validation
        assert puzzle.is_correct_guess("Spider-Man") == True
        assert puzzle.is_correct_guess("spiderman") == True
        assert puzzle.is_correct_guess("Iron Man") == False
        print("✓ Guess validation working")
        
        print("\nTesting Guess model...")
        from app.models.guess import Guess
        
        guess = Guess(
            user_id="user-123",
            puzzle_id="20240115-marvel",
            guess="Spider-Man",
            is_correct=True,
            attempt_number=1
        )
        print(f"✓ Guess created: {guess.guess} (correct: {guess.is_correct})")
        
        print("\n🎉 All models working correctly!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    main()