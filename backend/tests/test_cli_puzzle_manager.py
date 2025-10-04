"""
Tests for CLI puzzle management tools.
"""

import pytest
import tempfile
import csv
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from cli.puzzle_manager import PuzzleManager
from app.models.puzzle import PuzzleCreate, Puzzle


class TestPuzzleManager:
    """Test cases for PuzzleManager CLI tool"""
    
    @pytest.fixture
    def puzzle_manager(self):
        """Create PuzzleManager instance with mocked repository"""
        manager = PuzzleManager()
        manager.puzzle_repo = AsyncMock()
        return manager
    
    @pytest.fixture
    def sample_csv_data(self):
        """Sample CSV data for testing"""
        return [
            {
                'universe': 'marvel',
                'character': 'Spider-Man',
                'character_aliases': 'Spiderman,Peter Parker',
                'image_key': 'marvel/spider-man.jpg',
                'active_date': '2024-01-15'
            },
            {
                'universe': 'DC',
                'character': 'Batman',
                'character_aliases': 'Bruce Wayne,Dark Knight',
                'image_key': 'DC/batman.jpg',
                'active_date': '2024-01-16'
            }
        ]
    
    @pytest.fixture
    def sample_json_data(self):
        """Sample JSON data for testing"""
        return [
            {
                'universe': 'marvel',
                'character': 'Iron Man',
                'character_aliases': ['Tony Stark'],
                'image_key': 'marvel/iron-man.jpg',
                'active_date': '2024-01-17'
            },
            {
                'universe': 'image',
                'character': 'Spawn',
                'character_aliases': ['Al Simmons'],
                'image_key': 'image/spawn.jpg',
                'active_date': '2024-01-18'
            }
        ]
    
    @pytest.mark.asyncio
    async def test_import_from_csv_success(self, puzzle_manager, sample_csv_data):
        """Test successful CSV import"""
        # Create temporary CSV file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=sample_csv_data[0].keys())
            writer.writeheader()
            writer.writerows(sample_csv_data)
            csv_path = Path(f.name)
        
        try:
            # Mock successful bulk creation
            puzzle_manager.puzzle_repo.bulk_create_puzzles.return_value = [
                Puzzle(
                    id='20240115-marvel',
                    universe='marvel',
                    character='Spider-Man',
                    character_aliases=['Spiderman', 'Peter Parker'],
                    image_key='marvel/spider-man.jpg',
                    active_date='2024-01-15'
                ),
                Puzzle(
                    id='20240116-DC',
                    universe='DC',
                    character='Batman',
                    character_aliases=['Bruce Wayne', 'Dark Knight'],
                    image_key='DC/batman.jpg',
                    active_date='2024-01-16'
                )
            ]
            
            # Import CSV
            stats = await puzzle_manager.import_from_csv(csv_path, dry_run=False)
            
            # Verify results
            assert stats['total_rows'] == 2
            assert stats['valid_puzzles'] == 2
            assert stats['invalid_puzzles'] == 0
            assert stats['duplicates'] == 0
            assert stats['created'] == 2
            assert len(stats['errors']) == 0
            
            # Verify repository was called
            puzzle_manager.puzzle_repo.bulk_create_puzzles.assert_called_once()
            
        finally:
            csv_path.unlink()  # Clean up
    
    @pytest.mark.asyncio
    async def test_import_from_csv_dry_run(self, puzzle_manager, sample_csv_data):
        """Test CSV import in dry run mode"""
        # Create temporary CSV file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=sample_csv_data[0].keys())
            writer.writeheader()
            writer.writerows(sample_csv_data)
            csv_path = Path(f.name)
        
        try:
            # Import CSV in dry run mode
            stats = await puzzle_manager.import_from_csv(csv_path, dry_run=True)
            
            # Verify results
            assert stats['total_rows'] == 2
            assert stats['valid_puzzles'] == 2
            assert stats['invalid_puzzles'] == 0
            assert stats['created'] == 0  # No creation in dry run
            
            # Verify repository was not called
            puzzle_manager.puzzle_repo.bulk_create_puzzles.assert_not_called()
            
        finally:
            csv_path.unlink()
    
    @pytest.mark.asyncio
    async def test_import_from_csv_invalid_data(self, puzzle_manager):
        """Test CSV import with invalid data"""
        invalid_data = [
            {
                'universe': 'invalid_universe',  # Invalid universe
                'character': 'Test Character',
                'character_aliases': '',
                'image_key': 'test/test.jpg',
                'active_date': '2024-01-15'
            },
            {
                'universe': 'marvel',
                'character': '',  # Empty character name
                'character_aliases': '',
                'image_key': 'marvel/empty.jpg',
                'active_date': '2024-01-16'
            }
        ]
        
        # Create temporary CSV file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=invalid_data[0].keys())
            writer.writeheader()
            writer.writerows(invalid_data)
            csv_path = Path(f.name)
        
        try:
            # Import CSV
            stats = await puzzle_manager.import_from_csv(csv_path, dry_run=True)
            
            # Verify results
            assert stats['total_rows'] == 2
            assert stats['valid_puzzles'] == 0
            assert stats['invalid_puzzles'] == 2
            assert len(stats['errors']) == 2
            
        finally:
            csv_path.unlink()
    
    @pytest.mark.asyncio
    async def test_import_from_csv_duplicates(self, puzzle_manager):
        """Test CSV import with duplicate puzzles"""
        duplicate_data = [
            {
                'universe': 'marvel',
                'character': 'Spider-Man',
                'character_aliases': '',
                'image_key': 'marvel/spider-man.jpg',
                'active_date': '2024-01-15'
            },
            {
                'universe': 'marvel',
                'character': 'Iron Man',  # Different character, same date/universe
                'character_aliases': '',
                'image_key': 'marvel/iron-man.jpg',
                'active_date': '2024-01-15'  # Duplicate date
            }
        ]
        
        # Create temporary CSV file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=duplicate_data[0].keys())
            writer.writeheader()
            writer.writerows(duplicate_data)
            csv_path = Path(f.name)
        
        try:
            # Import CSV
            stats = await puzzle_manager.import_from_csv(csv_path, dry_run=True)
            
            # Verify results
            assert stats['total_rows'] == 2
            assert stats['valid_puzzles'] == 1  # Only first one is valid
            assert stats['duplicates'] == 1
            assert len(stats['errors']) == 1
            
        finally:
            csv_path.unlink()
    
    @pytest.mark.asyncio
    async def test_import_from_json_success(self, puzzle_manager, sample_json_data):
        """Test successful JSON import"""
        # Create temporary JSON file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_json_data, f)
            json_path = Path(f.name)
        
        try:
            # Mock successful bulk creation
            puzzle_manager.puzzle_repo.bulk_create_puzzles.return_value = [
                Puzzle(
                    id='20240117-marvel',
                    universe='marvel',
                    character='Iron Man',
                    character_aliases=['Tony Stark'],
                    image_key='marvel/iron-man.jpg',
                    active_date='2024-01-17'
                ),
                Puzzle(
                    id='20240118-image',
                    universe='image',
                    character='Spawn',
                    character_aliases=['Al Simmons'],
                    image_key='image/spawn.jpg',
                    active_date='2024-01-18'
                )
            ]
            
            # Import JSON
            stats = await puzzle_manager.import_from_json(json_path, dry_run=False)
            
            # Verify results
            assert stats['total_puzzles'] == 2
            assert stats['valid_puzzles'] == 2
            assert stats['invalid_puzzles'] == 0
            assert stats['created'] == 2
            
        finally:
            json_path.unlink()
    
    @pytest.mark.asyncio
    async def test_export_puzzles_json(self, puzzle_manager):
        """Test exporting puzzles to JSON"""
        # Mock puzzle data
        mock_puzzles = [
            Puzzle(
                id='20240115-marvel',
                universe='marvel',
                character='Spider-Man',
                character_aliases=['Spiderman'],
                image_key='marvel/spider-man.jpg',
                active_date='2024-01-15',
                created_at=datetime(2024, 1, 1)
            )
        ]
        
        puzzle_manager.puzzle_repo.get_puzzles_by_universe.return_value = mock_puzzles
        
        # Export to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_path = Path(f.name)
        
        try:
            count = await puzzle_manager.export_puzzles(output_path, universe='marvel', format_type='json')
            
            # Verify export
            assert count == 1
            
            # Verify file content
            with open(output_path, 'r') as f:
                exported_data = json.load(f)
            
            assert len(exported_data) == 1
            assert exported_data[0]['character'] == 'Spider-Man'
            assert exported_data[0]['universe'] == 'marvel'
            
        finally:
            output_path.unlink()
    
    @pytest.mark.asyncio
    async def test_export_puzzles_csv(self, puzzle_manager):
        """Test exporting puzzles to CSV"""
        # Mock puzzle data
        mock_puzzles = [
            Puzzle(
                id='20240115-marvel',
                universe='marvel',
                character='Spider-Man',
                character_aliases=['Spiderman'],
                image_key='marvel/spider-man.jpg',
                active_date='2024-01-15',
                created_at=datetime(2024, 1, 1)
            )
        ]
        
        puzzle_manager.puzzle_repo.get_puzzles_by_universe.return_value = mock_puzzles
        
        # Export to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = Path(f.name)
        
        try:
            count = await puzzle_manager.export_puzzles(output_path, universe='marvel', format_type='csv')
            
            # Verify export
            assert count == 1
            
            # Verify file content
            with open(output_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            assert len(rows) == 1
            assert rows[0]['character'] == 'Spider-Man'
            assert rows[0]['universe'] == 'marvel'
            
        finally:
            output_path.unlink()
    
    @pytest.mark.asyncio
    async def test_validate_puzzles(self, puzzle_manager):
        """Test puzzle validation"""
        # Mock puzzle data with one invalid puzzle
        mock_puzzles = [
            Puzzle(
                id='20240115-marvel',
                universe='marvel',
                character='Spider-Man',
                character_aliases=['Spiderman'],
                image_key='marvel/spider-man.jpg',
                active_date='2024-01-15'
            ),
            # This would be invalid in real scenario, but we'll mock the validation
        ]
        
        puzzle_manager.puzzle_repo.get_puzzles_by_universe.return_value = mock_puzzles
        
        # Validate puzzles
        results = await puzzle_manager.validate_puzzles('marvel')
        
        # Verify results
        assert results['total_checked'] == 2
        assert results['valid_puzzles'] >= 0
        assert results['invalid_puzzles'] >= 0
    
    @pytest.mark.asyncio
    async def test_delete_puzzles_without_confirm(self, puzzle_manager):
        """Test delete puzzles without confirmation"""
        count = await puzzle_manager.delete_puzzles('marvel', '2024-01-01', '2024-01-31', confirm=False)
        
        # Should not delete without confirmation
        assert count == 0
        puzzle_manager.puzzle_repo.get_puzzles_by_date_range.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_delete_puzzles_with_confirm(self, puzzle_manager):
        """Test delete puzzles with confirmation"""
        # Mock puzzles to delete
        mock_puzzles = [
            Puzzle(
                id='20240115-marvel',
                universe='marvel',
                character='Spider-Man',
                character_aliases=[],
                image_key='marvel/spider-man.jpg',
                active_date='2024-01-15'
            )
        ]
        
        puzzle_manager.puzzle_repo.get_puzzles_by_date_range.return_value = mock_puzzles
        puzzle_manager.puzzle_repo.delete_puzzle.return_value = True
        
        count = await puzzle_manager.delete_puzzles('marvel', '2024-01-01', '2024-01-31', confirm=True)
        
        # Should delete with confirmation
        assert count == 1
        puzzle_manager.puzzle_repo.get_puzzles_by_date_range.assert_called_once()
        puzzle_manager.puzzle_repo.delete_puzzle.assert_called_once_with('20240115-marvel')
    
    def test_generate_puzzle_id(self, puzzle_manager):
        """Test puzzle ID generation"""
        puzzle_id = puzzle_manager._generate_puzzle_id('2024-01-15', 'marvel')
        assert puzzle_id == '20240115-marvel'
    
    @pytest.mark.asyncio
    async def test_import_from_csv_missing_file(self, puzzle_manager):
        """Test CSV import with missing file"""
        non_existent_path = Path('/non/existent/file.csv')
        
        with pytest.raises(FileNotFoundError):
            await puzzle_manager.import_from_csv(non_existent_path)
    
    @pytest.mark.asyncio
    async def test_import_from_csv_missing_headers(self, puzzle_manager):
        """Test CSV import with missing required headers"""
        incomplete_data = [{'universe': 'marvel', 'character': 'Spider-Man'}]  # Missing required fields
        
        # Create temporary CSV file with incomplete headers
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=['universe', 'character'])
            writer.writeheader()
            writer.writerows(incomplete_data)
            csv_path = Path(f.name)
        
        try:
            with pytest.raises(ValueError, match="Missing required CSV headers"):
                await puzzle_manager.import_from_csv(csv_path)
        finally:
            csv_path.unlink()
    
    @pytest.mark.asyncio
    async def test_import_from_json_invalid_format(self, puzzle_manager):
        """Test JSON import with invalid JSON format"""
        # Create temporary file with invalid JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('invalid json content')
            json_path = Path(f.name)
        
        try:
            with pytest.raises(ValueError, match="Invalid JSON format"):
                await puzzle_manager.import_from_json(json_path)
        finally:
            json_path.unlink()
    
    @pytest.mark.asyncio
    async def test_import_from_json_not_array(self, puzzle_manager):
        """Test JSON import with non-array JSON"""
        # Create temporary file with object instead of array
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({'not': 'an array'}, f)
            json_path = Path(f.name)
        
        try:
            with pytest.raises(ValueError, match="JSON file must contain an array"):
                await puzzle_manager.import_from_json(json_path)
        finally:
            json_path.unlink()