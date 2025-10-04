"""Tests for puzzle service"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from app.services.puzzle_service import PuzzleService
from app.models.puzzle import Puzzle, PuzzleCreate, PuzzleResponse
from app.database.exceptions import ItemNotFoundError, DuplicateItemError

class TestPuzzleService:
    """Test cases for PuzzleService"""
    
    @pytest.fixture
    def puzzle_service(self):
        """Create puzzle service instance"""
        return PuzzleService()
    
    @pytest.fixture
    def sample_puzzle_data(self):
        """Sample puzzle data for testing"""
        return {
            "marvel": {
                "character": "Spider-Man",
                "aliases": ["Spidey", "Web-Slinger"],
                "image_key": "marvel/spiderman.jpg"
            },
            "DC": {
                "character": "Batman",
                "aliases": ["Dark Knight", "Caped Crusader"],
                "image_key": "DC/batman.jpg"
            },
            "image": {
                "character": "Spawn",
                "aliases": ["Al Simmons"],
                "image_key": "image/spawn.jpg"
            }
        }
    
    @pytest.fixture
    def sample_puzzle(self):
        """Sample puzzle for testing"""
        return Puzzle(
            id="20240115-marvel",
            universe="marvel",
            character="Spider-Man",
            character_aliases=["Spidey", "Web-Slinger"],
            image_key="marvel/spiderman.jpg",
            active_date="2024-01-15"
        )
    
    def test_generate_puzzle_id(self, puzzle_service):
        """Test puzzle ID generation"""
        puzzle_id = puzzle_service.generate_puzzle_id("2024-01-15", "marvel")
        assert puzzle_id == "20240115-marvel"
        
        puzzle_id = puzzle_service.generate_puzzle_id("2024-12-31", "DC")
        assert puzzle_id == "20241231-DC"
    
    def test_get_today_date(self, puzzle_service):
        """Test getting today's date"""
        today = puzzle_service.get_today_date()
        expected = datetime.utcnow().strftime('%Y-%m-%d')
        assert today == expected
    
    def test_get_date_for_offset(self, puzzle_service):
        """Test getting date with offset"""
        # Test positive offset
        future_date = puzzle_service.get_date_for_offset(7)
        expected = (datetime.utcnow() + timedelta(days=7)).strftime('%Y-%m-%d')
        assert future_date == expected
        
        # Test negative offset
        past_date = puzzle_service.get_date_for_offset(-3)
        expected = (datetime.utcnow() - timedelta(days=3)).strftime('%Y-%m-%d')
        assert past_date == expected
        
        # Test zero offset
        today = puzzle_service.get_date_for_offset(0)
        expected = datetime.utcnow().strftime('%Y-%m-%d')
        assert today == expected
    
    @pytest.mark.asyncio
    async def test_create_daily_puzzle(self, puzzle_service, sample_puzzle):
        """Test creating a daily puzzle"""
        with patch.object(puzzle_service.puzzle_repository, 'create_puzzle', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = sample_puzzle
            
            result = await puzzle_service.create_daily_puzzle(
                universe="marvel",
                character="Spider-Man",
                character_aliases=["Spidey", "Web-Slinger"],
                image_key="marvel/spiderman.jpg",
                active_date="2024-01-15"
            )
            
            assert result == sample_puzzle
            mock_create.assert_called_once()
            
            # Check the PuzzleCreate object passed to repository
            call_args = mock_create.call_args[0][0]
            assert call_args.universe == "marvel"
            assert call_args.character == "Spider-Man"
            assert call_args.character_aliases == ["Spidey", "Web-Slinger"]
            assert call_args.image_key == "marvel/spiderman.jpg"
            assert call_args.active_date == "2024-01-15"
    
    @pytest.mark.asyncio
    async def test_create_daily_puzzle_default_date(self, puzzle_service, sample_puzzle):
        """Test creating daily puzzle with default date"""
        with patch.object(puzzle_service.puzzle_repository, 'create_puzzle', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = sample_puzzle
            
            with patch.object(puzzle_service, 'get_today_date', return_value="2024-01-15"):
                result = await puzzle_service.create_daily_puzzle(
                    universe="marvel",
                    character="Spider-Man",
                    character_aliases=["Spidey"],
                    image_key="marvel/spiderman.jpg"
                )
                
                call_args = mock_create.call_args[0][0]
                assert call_args.active_date == "2024-01-15"
    
    @pytest.mark.asyncio
    async def test_get_daily_puzzle(self, puzzle_service, sample_puzzle):
        """Test getting daily puzzle"""
        with patch.object(puzzle_service.puzzle_repository, 'get_daily_puzzle', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_puzzle
            
            result = await puzzle_service.get_daily_puzzle("marvel", "2024-01-15")
            
            assert result == sample_puzzle
            mock_get.assert_called_once_with("marvel", "2024-01-15")
    
    @pytest.mark.asyncio
    async def test_get_daily_puzzle_default_date(self, puzzle_service, sample_puzzle):
        """Test getting daily puzzle with default date"""
        with patch.object(puzzle_service.puzzle_repository, 'get_daily_puzzle', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_puzzle
            
            with patch.object(puzzle_service, 'get_today_date', return_value="2024-01-15"):
                result = await puzzle_service.get_daily_puzzle("marvel")
                
                mock_get.assert_called_once_with("marvel", "2024-01-15")
    
    @pytest.mark.asyncio
    async def test_get_daily_puzzle_response(self, puzzle_service):
        """Test getting daily puzzle response"""
        expected_response = PuzzleResponse(
            id="20240115-marvel",
            universe="marvel",
            active_date="2024-01-15"
        )
        
        with patch.object(puzzle_service.puzzle_repository, 'get_puzzle_response', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = expected_response
            
            result = await puzzle_service.get_daily_puzzle_response("marvel", "2024-01-15")
            
            assert result == expected_response
            mock_get.assert_called_once_with("marvel", "2024-01-15")
    
    @pytest.mark.asyncio
    async def test_validate_puzzle_guess_correct(self, puzzle_service, sample_puzzle):
        """Test validating correct guess"""
        with patch.object(puzzle_service.puzzle_repository, 'get_puzzle_by_id', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_puzzle
            
            is_correct, character, image_key = await puzzle_service.validate_puzzle_guess(
                "20240115-marvel", "Spider-Man"
            )
            
            assert is_correct is True
            assert character == "Spider-Man"
            assert image_key == "marvel/spiderman.jpg"
    
    @pytest.mark.asyncio
    async def test_validate_puzzle_guess_incorrect(self, puzzle_service, sample_puzzle):
        """Test validating incorrect guess"""
        with patch.object(puzzle_service.puzzle_repository, 'get_puzzle_by_id', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_puzzle
            
            is_correct, character, image_key = await puzzle_service.validate_puzzle_guess(
                "20240115-marvel", "Iron Man"
            )
            
            assert is_correct is False
            assert character is None
            assert image_key is None
    
    @pytest.mark.asyncio
    async def test_validate_puzzle_guess_alias(self, puzzle_service, sample_puzzle):
        """Test validating guess with alias"""
        with patch.object(puzzle_service.puzzle_repository, 'get_puzzle_by_id', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_puzzle
            
            is_correct, character, image_key = await puzzle_service.validate_puzzle_guess(
                "20240115-marvel", "Spidey"
            )
            
            assert is_correct is True
            assert character == "Spider-Man"
            assert image_key == "marvel/spiderman.jpg"
    
    @pytest.mark.asyncio
    async def test_validate_puzzle_guess_not_found(self, puzzle_service):
        """Test validating guess for non-existent puzzle"""
        with patch.object(puzzle_service.puzzle_repository, 'get_puzzle_by_id', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            
            with pytest.raises(ItemNotFoundError):
                await puzzle_service.validate_puzzle_guess("20240115-marvel", "Spider-Man")
    
    @pytest.mark.asyncio
    async def test_generate_daily_puzzles_for_all_universes(self, puzzle_service, sample_puzzle_data):
        """Test generating puzzles for all universes"""
        sample_puzzles = [
            Puzzle(id="20240115-marvel", universe="marvel", character="Spider-Man", 
                  character_aliases=["Spidey"], image_key="marvel/spiderman.jpg", active_date="2024-01-15"),
            Puzzle(id="20240115-DC", universe="DC", character="Batman", 
                  character_aliases=["Dark Knight"], image_key="DC/batman.jpg", active_date="2024-01-15"),
            Puzzle(id="20240115-image", universe="image", character="Spawn", 
                  character_aliases=["Al Simmons"], image_key="image/spawn.jpg", active_date="2024-01-15")
        ]
        
        with patch.object(puzzle_service, 'create_daily_puzzle', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = sample_puzzles
            
            result = await puzzle_service.generate_daily_puzzles_for_all_universes(
                sample_puzzle_data, "2024-01-15"
            )
            
            assert len(result) == 3
            assert mock_create.call_count == 3
            
            # Verify each universe was called
            call_args_list = [call[1] for call in mock_create.call_args_list]
            universes_called = [args['universe'] for args in call_args_list]
            assert set(universes_called) == {"marvel", "DC", "image"}
    
    @pytest.mark.asyncio
    async def test_generate_daily_puzzles_with_duplicate(self, puzzle_service, sample_puzzle_data):
        """Test generating puzzles when duplicate exists"""
        sample_puzzle = Puzzle(
            id="20240115-marvel", universe="marvel", character="Spider-Man",
            character_aliases=["Spidey"], image_key="marvel/spiderman.jpg", active_date="2024-01-15"
        )
        
        with patch.object(puzzle_service, 'create_daily_puzzle', new_callable=AsyncMock) as mock_create:
            with patch.object(puzzle_service, 'get_daily_puzzle', new_callable=AsyncMock) as mock_get:
                # First call raises duplicate error, others succeed
                mock_create.side_effect = [DuplicateItemError("Duplicate"), sample_puzzle, sample_puzzle]
                mock_get.return_value = sample_puzzle
                
                result = await puzzle_service.generate_daily_puzzles_for_all_universes(
                    sample_puzzle_data, "2024-01-15"
                )
                
                assert len(result) == 3  # Should still return 3 puzzles (1 existing + 2 new)
    
    @pytest.mark.asyncio
    async def test_get_puzzle_metadata(self, puzzle_service, sample_puzzle):
        """Test getting puzzle metadata"""
        with patch.object(puzzle_service.puzzle_repository, 'get_puzzle_by_id', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_puzzle
            
            metadata = await puzzle_service.get_puzzle_metadata("20240115-marvel")
            
            assert metadata["id"] == "20240115-marvel"
            assert metadata["universe"] == "marvel"
            assert metadata["active_date"] == "2024-01-15"
            assert metadata["has_aliases"] is True
            assert metadata["alias_count"] == 2
            assert "character" not in metadata  # Should not reveal answer
    
    @pytest.mark.asyncio
    async def test_check_puzzle_availability(self, puzzle_service, sample_puzzle):
        """Test checking puzzle availability"""
        with patch.object(puzzle_service.puzzle_repository, 'get_daily_puzzle', new_callable=AsyncMock) as mock_get:
            # Test puzzle exists
            mock_get.return_value = sample_puzzle
            result = await puzzle_service.check_puzzle_availability("marvel", "2024-01-15")
            assert result is True
            
            # Test puzzle doesn't exist
            mock_get.return_value = None
            result = await puzzle_service.check_puzzle_availability("marvel", "2024-01-16")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_missing_puzzles(self, puzzle_service):
        """Test getting missing puzzles in date range"""
        # Mock availability checks
        availability_map = {
            ("marvel", "2024-01-15"): True,
            ("marvel", "2024-01-16"): False,
            ("DC", "2024-01-15"): False,
            ("DC", "2024-01-16"): True,
            ("image", "2024-01-15"): True,
            ("image", "2024-01-16"): True,
        }
        
        async def mock_check_availability(universe, date):
            return availability_map.get((universe, date), False)
        
        with patch.object(puzzle_service, 'check_puzzle_availability', side_effect=mock_check_availability):
            missing = await puzzle_service.get_missing_puzzles("2024-01-15", "2024-01-16")
            
            assert "2024-01-16" in missing["marvel"]
            assert "2024-01-15" in missing["DC"]
            assert len(missing["image"]) == 0
    
    @pytest.mark.asyncio
    async def test_bulk_create_puzzles(self, puzzle_service):
        """Test bulk creating puzzles"""
        puzzles_data = [
            {
                "universe": "marvel",
                "character": "Spider-Man",
                "aliases": ["Spidey"],
                "image_key": "marvel/spiderman.jpg",
                "active_date": "2024-01-15"
            },
            {
                "universe": "DC",
                "character": "Batman",
                "aliases": ["Dark Knight"],
                "image_key": "DC/batman.jpg",
                "active_date": "2024-01-15"
            }
        ]
        
        expected_puzzles = [
            Puzzle(id="20240115-marvel", universe="marvel", character="Spider-Man", 
                  character_aliases=["Spidey"], image_key="marvel/spiderman.jpg", active_date="2024-01-15"),
            Puzzle(id="20240115-DC", universe="DC", character="Batman", 
                  character_aliases=["Dark Knight"], image_key="DC/batman.jpg", active_date="2024-01-15")
        ]
        
        with patch.object(puzzle_service.puzzle_repository, 'bulk_create_puzzles', new_callable=AsyncMock) as mock_bulk:
            mock_bulk.return_value = expected_puzzles
            
            result = await puzzle_service.bulk_create_puzzles(puzzles_data)
            
            assert len(result) == 2
            assert result == expected_puzzles
            
            # Verify PuzzleCreate objects were created correctly
            call_args = mock_bulk.call_args[0][0]
            assert len(call_args) == 2
            assert all(isinstance(pc, PuzzleCreate) for pc in call_args)
    
    @pytest.mark.asyncio
    async def test_update_puzzle_metadata(self, puzzle_service, sample_puzzle):
        """Test updating puzzle metadata"""
        updates = {
            "image_key": "marvel/spiderman_new.jpg",
            "active_date": "2024-01-16",
            "character": "Iron Man"  # This should be filtered out
        }
        
        expected_safe_updates = {
            "image_key": "marvel/spiderman_new.jpg",
            "active_date": "2024-01-16"
        }
        
        with patch.object(puzzle_service.puzzle_repository, 'update_puzzle', new_callable=AsyncMock) as mock_update:
            mock_update.return_value = sample_puzzle
            
            result = await puzzle_service.update_puzzle_metadata("20240115-marvel", updates)
            
            assert result == sample_puzzle
            mock_update.assert_called_once_with("20240115-marvel", expected_safe_updates)
    
    @pytest.mark.asyncio
    async def test_update_puzzle_metadata_no_valid_fields(self, puzzle_service):
        """Test updating puzzle metadata with no valid fields"""
        updates = {
            "character": "Iron Man",  # Not allowed
            "character_aliases": ["Tony Stark"]  # Not allowed
        }
        
        with pytest.raises(ValueError, match="No valid fields to update"):
            await puzzle_service.update_puzzle_metadata("20240115-marvel", updates)
    
    @pytest.mark.asyncio
    async def test_get_recent_puzzles(self, puzzle_service):
        """Test getting recent puzzles"""
        sample_puzzles = [
            Puzzle(id="20240115-marvel", universe="marvel", character="Spider-Man", 
                  character_aliases=["Spidey"], image_key="marvel/spiderman.jpg", active_date="2024-01-15"),
            Puzzle(id="20240114-marvel", universe="marvel", character="Iron Man", 
                  character_aliases=["Tony Stark"], image_key="marvel/ironman.jpg", active_date="2024-01-14")
        ]
        
        with patch.object(puzzle_service.puzzle_repository, 'get_puzzles_by_universe', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_puzzles
            
            result = await puzzle_service.get_recent_puzzles("marvel", 10)
            
            assert len(result) == 2
            assert all(isinstance(pr, PuzzleResponse) for pr in result)
            assert result[0].id == "20240115-marvel"
            assert result[1].id == "20240114-marvel"
            
            # Verify no character info is exposed
            for puzzle_response in result:
                assert not hasattr(puzzle_response, 'character')
                assert not hasattr(puzzle_response, 'character_aliases')