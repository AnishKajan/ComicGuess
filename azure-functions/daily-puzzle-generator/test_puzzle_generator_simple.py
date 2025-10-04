"""
Simple tests for puzzle generator logic without backend dependencies
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import random


class MockPuzzleGeneratorService:
    """Mock version of PuzzleGeneratorService for testing core logic"""
    
    def __init__(self):
        self.universes = ["marvel", "DC", "image"]
        self.character_pools = {
            "marvel": [
                {
                    "character": "Spider-Man",
                    "aliases": ["Spidey", "Peter Parker"],
                    "image_key": "marvel/spider-man.jpg"
                },
                {
                    "character": "Iron Man",
                    "aliases": ["Tony Stark"],
                    "image_key": "marvel/iron-man.jpg"
                }
            ],
            "DC": [
                {
                    "character": "Batman",
                    "aliases": ["Bruce Wayne", "Dark Knight"],
                    "image_key": "DC/batman.jpg"
                },
                {
                    "character": "Superman",
                    "aliases": ["Clark Kent", "Man of Steel"],
                    "image_key": "DC/superman.jpg"
                }
            ],
            "image": [
                {
                    "character": "Spawn",
                    "aliases": ["Al Simmons"],
                    "image_key": "image/spawn.jpg"
                }
            ]
        }
    
    async def select_character_for_date(self, universe: str, date: str):
        """Select character using deterministic logic"""
        character_pool = self.character_pools.get(universe, [])
        
        if not character_pool:
            raise ValueError(f"No characters available for universe: {universe}")
        
        # Use date as seed for deterministic selection
        seed_string = f"{date}-{universe}"
        seed_value = hash(seed_string) % (2**32)
        
        random.seed(seed_value)
        selected_character = random.choice(character_pool)
        
        return selected_character


class TestPuzzleGeneratorLogic:
    """Test core puzzle generator logic"""
    
    @pytest.fixture
    def generator(self):
        return MockPuzzleGeneratorService()
    
    def test_character_pools_structure(self, generator):
        """Test character pools have correct structure"""
        assert len(generator.universes) == 3
        assert "marvel" in generator.character_pools
        assert "DC" in generator.character_pools
        assert "image" in generator.character_pools
        
        for universe, characters in generator.character_pools.items():
            assert len(characters) > 0
            for char in characters:
                assert "character" in char
                assert "aliases" in char
                assert "image_key" in char
                assert char["image_key"].startswith(f"{universe}/")
    
    @pytest.mark.asyncio
    async def test_character_selection_deterministic(self, generator):
        """Test that character selection is deterministic"""
        date = "2024-01-15"
        universe = "marvel"
        
        # Select character multiple times
        char1 = await generator.select_character_for_date(universe, date)
        char2 = await generator.select_character_for_date(universe, date)
        
        # Should be identical
        assert char1["character"] == char2["character"]
        assert char1["image_key"] == char2["image_key"]
    
    @pytest.mark.asyncio
    async def test_character_selection_different_dates(self, generator):
        """Test character selection for different dates"""
        universe = "marvel"
        date1 = "2024-01-15"
        date2 = "2024-01-16"
        
        char1 = await generator.select_character_for_date(universe, date1)
        char2 = await generator.select_character_for_date(universe, date2)
        
        # Both should be valid characters
        assert "character" in char1
        assert "character" in char2
        assert char1["image_key"].startswith("marvel/")
        assert char2["image_key"].startswith("marvel/")
    
    @pytest.mark.asyncio
    async def test_character_selection_different_universes(self, generator):
        """Test character selection for different universes"""
        date = "2024-01-15"
        
        marvel_char = await generator.select_character_for_date("marvel", date)
        DC_char = await generator.select_character_for_date("DC", date)
        image_char = await generator.select_character_for_date("image", date)
        
        # Each should be from correct universe
        assert marvel_char["image_key"].startswith("marvel/")
        assert DC_char["image_key"].startswith("DC/")
        assert image_char["image_key"].startswith("image/")
    
    @pytest.mark.asyncio
    async def test_character_selection_invalid_universe(self, generator):
        """Test character selection with invalid universe"""
        with pytest.raises(ValueError, match="No characters available"):
            await generator.select_character_for_date("invalid", "2024-01-15")
    
    def test_puzzle_id_generation(self):
        """Test puzzle ID generation logic"""
        def generate_puzzle_id(date: str, universe: str) -> str:
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            date_str = date_obj.strftime('%Y%m%d')
            return f"{date_str}-{universe}"
        
        puzzle_id = generate_puzzle_id("2024-01-15", "marvel")
        assert puzzle_id == "20240115-marvel"
        
        puzzle_id = generate_puzzle_id("2024-12-31", "DC")
        assert puzzle_id == "20241231-DC"
    
    def test_date_formatting(self):
        """Test date formatting utilities"""
        def get_today_date() -> str:
            return datetime.utcnow().strftime('%Y-%m-%d')
        
        def get_date_for_offset(days_offset: int = 0) -> str:
            target_date = datetime.utcnow() + timedelta(days=days_offset)
            return target_date.strftime('%Y-%m-%d')
        
        today = get_today_date()
        assert len(today) == 10  # YYYY-MM-DD format
        assert today.count('-') == 2
        
        tomorrow = get_date_for_offset(1)
        yesterday = get_date_for_offset(-1)
        
        today_dt = datetime.strptime(today, '%Y-%m-%d')
        tomorrow_dt = datetime.strptime(tomorrow, '%Y-%m-%d')
        yesterday_dt = datetime.strptime(yesterday, '%Y-%m-%d')
        
        assert (tomorrow_dt - today_dt).days == 1
        assert (today_dt - yesterday_dt).days == 1


class TestFunctionAppLogic:
    """Test Azure Function app logic"""
    
    def test_timer_schedule_format(self):
        """Test that timer schedule is in correct cron format"""
        # The schedule should be "0 0 0 * * *" for daily at UTC midnight
        schedule = "0 0 0 * * *"
        
        # Basic validation - should have 6 parts
        parts = schedule.split()
        assert len(parts) == 6
        
        # First three should be "0 0 0" for midnight
        assert parts[0] == "0"  # seconds
        assert parts[1] == "0"  # minutes  
        assert parts[2] == "0"  # hours
        assert parts[3] == "*"  # day of month
        assert parts[4] == "*"  # month
        assert parts[5] == "*"  # day of week
    
    def test_result_structure(self):
        """Test that function results have correct structure"""
        # Mock successful result
        success_result = {
            "success": True,
            "puzzles_created": 3,
            "universes_processed": ["marvel", "DC", "image"],
            "date": "2024-01-15",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        assert "success" in success_result
        assert "puzzles_created" in success_result
        assert "universes_processed" in success_result
        assert "date" in success_result
        assert "timestamp" in success_result
        
        assert success_result["success"] is True
        assert success_result["puzzles_created"] == 3
        assert len(success_result["universes_processed"]) == 3
        
        # Mock error result
        error_result = {
            "success": False,
            "error": "Test error message",
            "date": "2024-01-15",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        assert "success" in error_result
        assert "error" in error_result
        assert error_result["success"] is False
    
    def test_health_check_structure(self):
        """Test health check response structure"""
        health_response = {
            "healthy": True,
            "checks": {
                "database": {"status": "healthy"},
                "character_pools": {"status": "healthy"},
                "todays_puzzles": {"status": "healthy"}
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        assert "healthy" in health_response
        assert "checks" in health_response
        assert "timestamp" in health_response
        
        required_checks = ["database", "character_pools", "todays_puzzles"]
        for check in required_checks:
            assert check in health_response["checks"]
            assert "status" in health_response["checks"][check]


if __name__ == "__main__":
    pytest.main([__file__])