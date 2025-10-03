"""
Tests for the daily puzzle generator Azure Function
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import json
import sys
import os

# Mock the backend imports to avoid dependency issues in tests
sys.modules['app.models.puzzle'] = Mock()
sys.modules['app.repositories.puzzle_repository'] = Mock()
sys.modules['app.services.puzzle_service'] = Mock()
sys.modules['app.database.connection'] = Mock()
sys.modules['app.config'] = Mock()

from puzzle_generator import PuzzleGeneratorService


class TestPuzzleGeneratorService:
    """Test cases for PuzzleGeneratorService"""
    
    @pytest.fixture
    def generator_service(self):
        """Create a PuzzleGeneratorService instance for testing"""
        with patch('puzzle_generator.PuzzleService') as mock_puzzle_service:
            generator = PuzzleGeneratorService()
            generator.puzzle_service = mock_puzzle_service.return_value
            return generator
    
    @pytest.fixture
    def sample_character_data(self):
        """Sample character data for testing"""
        return {
            "character": "Spider-Man",
            "aliases": ["Spidey", "Peter Parker"],
            "image_key": "marvel/spider-man.jpg"
        }
    
    def test_load_character_pools(self, generator_service):
        """Test that character pools are loaded correctly"""
        pools = generator_service.character_pools
        
        assert "marvel" in pools
        assert "dc" in pools
        assert "image" in pools
        
        # Check that each pool has characters
        for universe, pool in pools.items():
            assert len(pool) > 0
            for character in pool:
                assert "character" in character
                assert "aliases" in character
                assert "image_key" in character
                assert character["image_key"].startswith(f"{universe}/")
    
    @pytest.mark.asyncio
    async def test_select_character_for_date_deterministic(self, generator_service):
        """Test that character selection is deterministic for the same date"""
        date = "2024-01-15"
        universe = "marvel"
        
        # Select character multiple times for same date
        char1 = await generator_service.select_character_for_date(universe, date)
        char2 = await generator_service.select_character_for_date(universe, date)
        
        # Should be the same character
        assert char1["character"] == char2["character"]
        assert char1["image_key"] == char2["image_key"]
    
    @pytest.mark.asyncio
    async def test_select_character_for_date_different_dates(self, generator_service):
        """Test that different dates can produce different characters"""
        universe = "marvel"
        date1 = "2024-01-15"
        date2 = "2024-01-16"
        
        char1 = await generator_service.select_character_for_date(universe, date1)
        char2 = await generator_service.select_character_for_date(universe, date2)
        
        # Characters might be different (not guaranteed, but likely with enough characters)
        # At minimum, the selection process should work for both dates
        assert "character" in char1
        assert "character" in char2
    
    @pytest.mark.asyncio
    async def test_select_character_invalid_universe(self, generator_service):
        """Test character selection with invalid universe"""
        with pytest.raises(ValueError, match="No characters available"):
            await generator_service.select_character_for_date("invalid", "2024-01-15")
    
    @pytest.mark.asyncio
    async def test_generate_puzzle_for_universe_success(self, generator_service, sample_character_data):
        """Test successful puzzle generation for a universe"""
        # Mock the puzzle service methods
        generator_service.puzzle_service.get_daily_puzzle = AsyncMock(return_value=None)
        
        mock_puzzle = Mock()
        mock_puzzle.id = "20240115-marvel"
        mock_puzzle.character = "Spider-Man"
        mock_puzzle.universe = "marvel"
        mock_puzzle.active_date = "2024-01-15"
        
        generator_service.puzzle_service.create_daily_puzzle = AsyncMock(return_value=mock_puzzle)
        
        # Mock character selection
        with patch.object(generator_service, 'select_character_for_date', 
                         return_value=sample_character_data):
            
            result = await generator_service.generate_puzzle_for_universe("marvel", "2024-01-15")
        
        assert result["success"] is True
        assert result["puzzle_id"] == "20240115-marvel"
        assert result["character"] == "Spider-Man"
        assert result["universe"] == "marvel"
    
    @pytest.mark.asyncio
    async def test_generate_puzzle_for_universe_already_exists(self, generator_service):
        """Test puzzle generation when puzzle already exists"""
        # Mock existing puzzle
        mock_existing_puzzle = Mock()
        mock_existing_puzzle.id = "20240115-marvel"
        mock_existing_puzzle.character = "Iron Man"
        
        generator_service.puzzle_service.get_daily_puzzle = AsyncMock(return_value=mock_existing_puzzle)
        
        result = await generator_service.generate_puzzle_for_universe("marvel", "2024-01-15")
        
        assert result["success"] is True
        assert result["puzzle_id"] == "20240115-marvel"
        assert result["character"] == "Iron Man"
        assert "already exists" in result["message"]
    
    @pytest.mark.asyncio
    async def test_generate_puzzle_for_universe_invalid_universe(self, generator_service):
        """Test puzzle generation with invalid universe"""
        result = await generator_service.generate_puzzle_for_universe("invalid", "2024-01-15")
        
        assert result["success"] is False
        assert "Invalid universe" in result["error"]
    
    @pytest.mark.asyncio
    async def test_generate_daily_puzzles_for_date_success(self, generator_service):
        """Test generating puzzles for all universes on a date"""
        # Mock successful puzzle generation for each universe
        with patch.object(generator_service, 'generate_puzzle_for_universe') as mock_generate:
            mock_generate.return_value = {
                "success": True,
                "puzzle_id": "test-puzzle-id",
                "character": "Test Character"
            }
            
            result = await generator_service.generate_daily_puzzles_for_date("2024-01-15")
        
        assert result["date"] == "2024-01-15"
        assert result["puzzles_created"] == 3  # All three universes
        assert len(result["universes_processed"]) == 3
        assert len(result["errors"]) == 0
    
    @pytest.mark.asyncio
    async def test_generate_daily_puzzles_for_date_partial_failure(self, generator_service):
        """Test puzzle generation with some failures"""
        def mock_generate_side_effect(universe, date):
            if universe == "marvel":
                return {"success": True, "puzzle_id": "test-id"}
            else:
                return {"success": False, "error": "Test error"}
        
        with patch.object(generator_service, 'generate_puzzle_for_universe', 
                         side_effect=mock_generate_side_effect):
            
            result = await generator_service.generate_daily_puzzles_for_date("2024-01-15")
        
        assert result["puzzles_created"] == 1  # Only marvel succeeded
        assert len(result["universes_processed"]) == 1
        assert len(result["errors"]) == 2  # dc and image failed
    
    @pytest.mark.asyncio
    async def test_validate_puzzle_generation_all_exist(self, generator_service):
        """Test puzzle validation when all puzzles exist"""
        # Mock puzzles exist for all universes
        mock_puzzle = Mock()
        mock_puzzle.id = "test-id"
        mock_puzzle.character = "Test Character"
        
        generator_service.puzzle_service.get_daily_puzzle = AsyncMock(return_value=mock_puzzle)
        
        result = await generator_service.validate_puzzle_generation("2024-01-15")
        
        assert result["all_puzzles_exist"] is True
        assert len(result["missing_puzzles"]) == 0
        assert len(result["existing_puzzles"]) == 3
    
    @pytest.mark.asyncio
    async def test_validate_puzzle_generation_some_missing(self, generator_service):
        """Test puzzle validation when some puzzles are missing"""
        def mock_get_puzzle_side_effect(universe, date):
            if universe == "marvel":
                mock_puzzle = Mock()
                mock_puzzle.id = "test-id"
                mock_puzzle.character = "Test Character"
                return mock_puzzle
            else:
                return None
        
        generator_service.puzzle_service.get_daily_puzzle = AsyncMock(
            side_effect=mock_get_puzzle_side_effect
        )
        
        result = await generator_service.validate_puzzle_generation("2024-01-15")
        
        assert result["all_puzzles_exist"] is False
        assert len(result["missing_puzzles"]) == 2  # dc and image missing
        assert len(result["existing_puzzles"]) == 1  # only marvel exists
    
    @pytest.mark.asyncio
    async def test_perform_health_check_healthy(self, generator_service):
        """Test health check when system is healthy"""
        # Mock successful database connection
        generator_service.puzzle_service.get_universe_statistics = AsyncMock(
            return_value={"total_puzzles": 10}
        )
        
        # Mock successful puzzle validation
        with patch.object(generator_service, 'validate_puzzle_generation') as mock_validate:
            mock_validate.return_value = {
                "all_puzzles_exist": True,
                "missing_puzzles": [],
                "existing_puzzles": [{"universe": "marvel"}, {"universe": "dc"}, {"universe": "image"}]
            }
            
            result = await generator_service.perform_health_check()
        
        assert result["healthy"] is True
        assert result["checks"]["database"]["status"] == "healthy"
        assert result["checks"]["character_pools"]["status"] == "healthy"
        assert result["checks"]["todays_puzzles"]["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_perform_health_check_database_error(self, generator_service):
        """Test health check when database is unhealthy"""
        # Mock database connection failure
        generator_service.puzzle_service.get_universe_statistics = AsyncMock(
            side_effect=Exception("Database connection failed")
        )
        
        result = await generator_service.perform_health_check()
        
        assert result["healthy"] is False
        assert result["checks"]["database"]["status"] == "unhealthy"
        assert "Database connection failed" in result["checks"]["database"]["error"]
    
    @pytest.mark.asyncio
    async def test_generate_future_puzzles(self, generator_service):
        """Test generating puzzles for future dates"""
        with patch.object(generator_service, 'generate_daily_puzzles_for_date') as mock_generate:
            mock_generate.return_value = {
                "puzzles_created": 3,
                "universes_processed": ["marvel", "dc", "image"],
                "errors": []
            }
            
            result = await generator_service.generate_future_puzzles(days_ahead=3)
        
        assert result["days_ahead"] == 3
        assert result["total_puzzles_created"] == 9  # 3 days * 3 puzzles per day
        assert len(result["dates_processed"]) == 3
        assert len(result["errors"]) == 0
    
    @pytest.mark.asyncio
    async def test_cleanup_old_puzzles_success(self, generator_service):
        """Test successful cleanup of old puzzles"""
        generator_service.puzzle_service.cleanup_old_puzzles = AsyncMock(return_value=50)
        
        result = await generator_service.cleanup_old_puzzles(days_to_keep=365)
        
        assert result["success"] is True
        assert result["deleted_count"] == 50
        assert result["days_to_keep"] == 365
    
    @pytest.mark.asyncio
    async def test_cleanup_old_puzzles_error(self, generator_service):
        """Test cleanup with error"""
        generator_service.puzzle_service.cleanup_old_puzzles = AsyncMock(
            side_effect=Exception("Cleanup failed")
        )
        
        result = await generator_service.cleanup_old_puzzles(days_to_keep=365)
        
        assert result["success"] is False
        assert "Cleanup failed" in result["error"]


class TestFunctionApp:
    """Test cases for the Azure Function app endpoints"""
    
    @pytest.mark.asyncio
    async def test_generate_daily_puzzles_function(self):
        """Test the main daily puzzle generation function logic"""
        with patch('puzzle_generator.PuzzleGeneratorService') as mock_service_class:
            mock_service = Mock()
            mock_service.generate_daily_puzzles_for_date = AsyncMock(return_value={
                "puzzles_created": 3,
                "universes_processed": ["marvel", "dc", "image"]
            })
            mock_service_class.return_value = mock_service
            
            # Import and test the function logic
            from function_app import generate_daily_puzzles
            
            result = await generate_daily_puzzles()
            
            assert result["success"] is True
            assert result["puzzles_created"] == 3
            assert len(result["universes_processed"]) == 3
    
    def test_character_pool_structure(self):
        """Test that character pools have the correct structure"""
        generator = PuzzleGeneratorService()
        
        for universe, characters in generator.character_pools.items():
            assert isinstance(characters, list)
            assert len(characters) > 0
            
            for character in characters:
                assert isinstance(character, dict)
                assert "character" in character
                assert "aliases" in character
                assert "image_key" in character
                
                assert isinstance(character["character"], str)
                assert len(character["character"]) > 0
                
                assert isinstance(character["aliases"], list)
                
                assert isinstance(character["image_key"], str)
                assert character["image_key"].startswith(f"{universe}/")
                assert character["image_key"].endswith(('.jpg', '.jpeg', '.png'))


if __name__ == "__main__":
    pytest.main([__file__])