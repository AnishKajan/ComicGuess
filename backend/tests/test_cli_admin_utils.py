"""
Tests for CLI administrative utilities.
"""

import pytest
import tempfile
import json
import zipfile
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from cli.admin_utils import AdminUtils
from app.models.user import User, UserCreate
from app.models.puzzle import Puzzle, PuzzleCreate
from app.models.guess import Guess, GuessCreate


class TestAdminUtils:
    """Test cases for AdminUtils CLI tool"""
    
    @pytest.fixture
    def admin_utils(self):
        """Create AdminUtils instance with mocked repositories"""
        admin = AdminUtils()
        admin.user_repo = AsyncMock()
        admin.puzzle_repo = AsyncMock()
        admin.guess_repo = AsyncMock()
        admin.blob_service = AsyncMock()
        return admin
    
    @pytest.fixture
    def sample_seed_data(self):
        """Sample seed data for testing"""
        return {
            'users': [
                {
                    'id': 'user1',
                    'username': 'testuser1',
                    'email': 'test1@example.com'
                },
                {
                    'id': 'user2',
                    'username': 'testuser2',
                    'email': 'test2@example.com'
                }
            ],
            'puzzles': [
                {
                    'universe': 'marvel',
                    'character': 'Spider-Man',
                    'character_aliases': ['Spiderman'],
                    'image_key': 'marvel/spider-man.jpg',
                    'active_date': '2024-01-15'
                },
                {
                    'universe': 'dc',
                    'character': 'Batman',
                    'character_aliases': ['Dark Knight'],
                    'image_key': 'dc/batman.jpg',
                    'active_date': '2024-01-16'
                }
            ],
            'guesses': [
                {
                    'user_id': 'user1',
                    'puzzle_id': '20240115-marvel',
                    'guess': 'Spider-Man',
                    'is_correct': True
                }
            ]
        }
    
    @pytest.mark.asyncio
    async def test_seed_database_from_file(self, admin_utils, sample_seed_data):
        """Test database seeding from file"""
        # Create temporary seed file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_seed_data, f)
            seed_file = Path(f.name)
        
        try:
            # Mock successful creation
            admin_utils.user_repo.create_user.return_value = User(
                id='user1', username='testuser1', email='test1@example.com'
            )
            admin_utils.puzzle_repo.create_puzzle.return_value = Puzzle(
                id='20240115-marvel', universe='marvel', character='Spider-Man',
                character_aliases=['Spiderman'], image_key='marvel/spider-man.jpg',
                active_date='2024-01-15'
            )
            admin_utils.guess_repo.create_guess.return_value = Guess(
                id='guess1', user_id='user1', puzzle_id='20240115-marvel',
                guess='Spider-Man', is_correct=True, timestamp=datetime.utcnow()
            )
            
            # Seed database
            stats = await admin_utils.seed_database(seed_file, create_sample_data=False)
            
            # Verify results
            assert stats['users_created'] == 2
            assert stats['puzzles_created'] == 2
            assert stats['guesses_created'] == 1
            assert len(stats['errors']) == 0
            
            # Verify repository calls
            assert admin_utils.user_repo.create_user.call_count == 2
            assert admin_utils.puzzle_repo.create_puzzle.call_count == 2
            assert admin_utils.guess_repo.create_guess.call_count == 1
            
        finally:
            seed_file.unlink()
    
    @pytest.mark.asyncio
    async def test_seed_database_create_sample_data(self, admin_utils):
        """Test database seeding with sample data creation"""
        # Mock successful creation
        admin_utils.user_repo.create_user.return_value = User(
            id='user1', username='comic_fan_1', email='user1@example.com'
        )
        admin_utils.puzzle_repo.create_puzzle.return_value = Puzzle(
            id='20240115-marvel', universe='marvel', character='Spider-Man',
            character_aliases=[], image_key='marvel/spider-man.jpg',
            active_date='2024-01-15'
        )
        
        # Seed with sample data
        stats = await admin_utils.seed_database(seed_file=None, create_sample_data=True)
        
        # Verify sample data was created
        assert stats['users_created'] > 0
        assert stats['puzzles_created'] > 0
        
        # Verify repository was called
        admin_utils.user_repo.create_user.assert_called()
        admin_utils.puzzle_repo.create_puzzle.assert_called()
    
    @pytest.mark.asyncio
    async def test_seed_database_no_file_no_sample(self, admin_utils):
        """Test seeding with no file and no sample data"""
        stats = await admin_utils.seed_database(seed_file=None, create_sample_data=False)
        
        # Should not create anything
        assert stats['users_created'] == 0
        assert stats['puzzles_created'] == 0
        assert stats['guesses_created'] == 0
        
        # Verify no repository calls
        admin_utils.user_repo.create_user.assert_not_called()
        admin_utils.puzzle_repo.create_puzzle.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_seed_database_with_errors(self, admin_utils, sample_seed_data):
        """Test seeding with some creation errors"""
        # Create temporary seed file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_seed_data, f)
            seed_file = Path(f.name)
        
        try:
            # Mock some failures
            admin_utils.user_repo.create_user.side_effect = [
                User(id='user1', username='testuser1', email='test1@example.com'),
                Exception("User creation failed")
            ]
            admin_utils.puzzle_repo.create_puzzle.side_effect = Exception("Puzzle creation failed")
            
            # Seed database
            stats = await admin_utils.seed_database(seed_file, create_sample_data=False)
            
            # Verify partial success
            assert stats['users_created'] == 1  # One succeeded, one failed
            assert stats['puzzles_created'] == 0  # Both failed
            assert len(stats['errors']) > 0
            
        finally:
            seed_file.unlink()
    
    @pytest.mark.asyncio
    async def test_backup_database(self, admin_utils):
        """Test database backup"""
        # Mock data to backup
        mock_users = [
            User(id='user1', username='testuser1', email='test1@example.com'),
            User(id='user2', username='testuser2', email='test2@example.com')
        ]
        mock_puzzles = [
            Puzzle(
                id='20240115-marvel', universe='marvel', character='Spider-Man',
                character_aliases=[], image_key='marvel/spider-man.jpg',
                active_date='2024-01-15'
            )
        ]
        
        admin_utils.user_repo.get_all_users.return_value = mock_users
        admin_utils.puzzle_repo.get_puzzles_by_universe.return_value = mock_puzzles
        
        # Create temporary backup directory
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir)
            
            # Perform backup
            stats = await admin_utils.backup_database(backup_dir, include_blobs=False)
            
            # Verify backup was created
            assert stats['backup_file'] is not None
            assert stats['users_backed_up'] == 2
            assert stats['puzzles_backed_up'] == 3  # One puzzle per universe
            
            # Verify backup file exists and contains data
            backup_file = Path(stats['backup_file'])
            assert backup_file.exists()
            
            with zipfile.ZipFile(backup_file, 'r') as zip_file:
                assert 'users.json' in zip_file.namelist()
                assert 'puzzles.json' in zip_file.namelist()
                assert 'metadata.json' in zip_file.namelist()
    
    @pytest.mark.asyncio
    async def test_restore_database_without_confirm(self, admin_utils):
        """Test restore without confirmation"""
        # Create dummy backup file
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as f:
            backup_file = Path(f.name)
        
        try:
            stats = await admin_utils.restore_database(backup_file, restore_blobs=False, confirm=False)
            
            # Should not restore without confirmation
            assert stats['users_restored'] == 0
            assert stats['puzzles_restored'] == 0
            
            # Verify no repository calls
            admin_utils.user_repo.create_user.assert_not_called()
            admin_utils.puzzle_repo.create_puzzle.assert_not_called()
            
        finally:
            backup_file.unlink()
    
    @pytest.mark.asyncio
    async def test_restore_database_missing_file(self, admin_utils):
        """Test restore with missing backup file"""
        non_existent_file = Path('/non/existent/backup.zip')
        
        with pytest.raises(FileNotFoundError):
            await admin_utils.restore_database(non_existent_file, confirm=True)
    
    @pytest.mark.asyncio
    async def test_restore_database_success(self, admin_utils, sample_seed_data):
        """Test successful database restore"""
        # Create backup file with sample data
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as f:
            backup_file = Path(f.name)
        
        try:
            # Create backup zip with sample data
            with zipfile.ZipFile(backup_file, 'w') as zip_file:
                zip_file.writestr('users.json', json.dumps(sample_seed_data['users']))
                zip_file.writestr('puzzles.json', json.dumps(sample_seed_data['puzzles']))
                zip_file.writestr('guesses.json', json.dumps(sample_seed_data['guesses']))
                zip_file.writestr('metadata.json', json.dumps({
                    'backup_timestamp': '20240115_120000',
                    'database_name': 'test_db'
                }))
            
            # Mock successful restoration
            admin_utils.user_repo.create_user.return_value = User(
                id='user1', username='testuser1', email='test1@example.com'
            )
            admin_utils.puzzle_repo.create_puzzle.return_value = Puzzle(
                id='20240115-marvel', universe='marvel', character='Spider-Man',
                character_aliases=[], image_key='marvel/spider-man.jpg',
                active_date='2024-01-15'
            )
            admin_utils.guess_repo.create_guess.return_value = Guess(
                id='guess1', user_id='user1', puzzle_id='20240115-marvel',
                guess='Spider-Man', is_correct=True, timestamp=datetime.utcnow()
            )
            
            # Restore database
            stats = await admin_utils.restore_database(backup_file, restore_blobs=False, confirm=True)
            
            # Verify restoration
            assert stats['users_restored'] == 2
            assert stats['puzzles_restored'] == 2
            assert stats['guesses_restored'] == 1
            
        finally:
            backup_file.unlink()
    
    @pytest.mark.asyncio
    async def test_migrate_schema_unknown_migration(self, admin_utils):
        """Test migration with unknown migration name"""
        stats = await admin_utils.migrate_schema('unknown_migration', dry_run=True)
        
        assert len(stats['errors']) > 0
        assert 'Unknown migration' in stats['errors'][0]
    
    @pytest.mark.asyncio
    async def test_migrate_add_user_preferences_dry_run(self, admin_utils):
        """Test user preferences migration in dry run mode"""
        # Mock users without preferences
        mock_users = [
            User(id='user1', username='testuser1', email='test1@example.com'),
            User(id='user2', username='testuser2', email='test2@example.com')
        ]
        admin_utils.user_repo.get_all_users.return_value = mock_users
        
        # Run migration in dry run mode
        stats = await admin_utils.migrate_schema('add_user_preferences', dry_run=True)
        
        # Should identify items to migrate but not actually migrate
        assert stats['items_migrated'] == 2
        admin_utils.user_repo.update_user.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_migrate_add_user_preferences_actual(self, admin_utils):
        """Test user preferences migration with actual changes"""
        # Mock users without preferences
        mock_users = [
            User(id='user1', username='testuser1', email='test1@example.com')
        ]
        admin_utils.user_repo.get_all_users.return_value = mock_users
        admin_utils.user_repo.update_user.return_value = User(
            id='user1', username='testuser1', email='test1@example.com'
        )
        
        # Run actual migration
        stats = await admin_utils.migrate_schema('add_user_preferences', dry_run=False)
        
        # Should migrate and update users
        assert stats['items_migrated'] == 1
        admin_utils.user_repo.update_user.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_migrate_update_puzzle_aliases(self, admin_utils):
        """Test puzzle aliases migration"""
        # Mock puzzles with unnormalized aliases
        mock_puzzles = [
            Puzzle(
                id='20240115-marvel', universe='marvel', character='Spider-Man',
                character_aliases=['Spiderman', ' Spider-Man ', 'Spiderman'],  # Has duplicates and whitespace
                image_key='marvel/spider-man.jpg', active_date='2024-01-15'
            )
        ]
        
        admin_utils.puzzle_repo.get_puzzles_by_universe.return_value = mock_puzzles
        admin_utils.puzzle_repo.update_puzzle.return_value = mock_puzzles[0]
        
        # Run migration
        stats = await admin_utils.migrate_schema('update_puzzle_aliases', dry_run=False)
        
        # Should normalize aliases
        assert stats['items_migrated'] == 1
        admin_utils.puzzle_repo.update_puzzle.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, admin_utils):
        """Test health check with all systems healthy"""
        # Mock healthy database
        with patch('cli.admin_utils.get_cosmos_db') as mock_get_db:
            mock_db = AsyncMock()
            mock_db.health_check.return_value = {'status': 'healthy'}
            mock_get_db.return_value = mock_db
            
            # Mock healthy blob storage
            admin_utils.blob_service.ensure_container_exists.return_value = True
            
            # Mock healthy data integrity
            admin_utils.puzzle_repo.get_puzzles_by_universe.return_value = [mock_puzzles[0] if 'mock_puzzles' in locals() else MagicMock()]
            admin_utils.puzzle_repo.get_upcoming_puzzles.return_value = [MagicMock()]
            
            # Perform health check
            health = await admin_utils.health_check()
            
            # Verify healthy status
            assert health['overall_status'] == 'healthy'
            assert health['components']['database']['status'] == 'healthy'
            assert health['components']['blob_storage']['status'] == 'healthy'
    
    @pytest.mark.asyncio
    async def test_health_check_unhealthy_database(self, admin_utils):
        """Test health check with unhealthy database"""
        # Mock unhealthy database
        with patch('cli.admin_utils.get_cosmos_db') as mock_get_db:
            mock_db = AsyncMock()
            mock_db.health_check.return_value = {'status': 'unhealthy', 'error': 'Connection failed'}
            mock_get_db.return_value = mock_db
            
            # Mock healthy blob storage
            admin_utils.blob_service.ensure_container_exists.return_value = True
            
            # Perform health check
            health = await admin_utils.health_check()
            
            # Verify unhealthy status
            assert health['overall_status'] == 'unhealthy'
            assert health['components']['database']['status'] == 'unhealthy'
    
    @pytest.mark.asyncio
    async def test_health_check_unhealthy_blob_storage(self, admin_utils):
        """Test health check with unhealthy blob storage"""
        # Mock healthy database
        with patch('cli.admin_utils.get_cosmos_db') as mock_get_db:
            mock_db = AsyncMock()
            mock_db.health_check.return_value = {'status': 'healthy'}
            mock_get_db.return_value = mock_db
            
            # Mock unhealthy blob storage
            admin_utils.blob_service.ensure_container_exists.side_effect = Exception("Storage error")
            
            # Perform health check
            health = await admin_utils.health_check()
            
            # Verify unhealthy status
            assert health['overall_status'] == 'unhealthy'
            assert health['components']['blob_storage']['status'] == 'unhealthy'
    
    @pytest.mark.asyncio
    async def test_check_data_integrity_healthy(self, admin_utils):
        """Test data integrity check with healthy data"""
        # Mock puzzles exist for all universes
        admin_utils.puzzle_repo.get_puzzles_by_universe.return_value = [MagicMock()]
        admin_utils.puzzle_repo.get_upcoming_puzzles.return_value = [MagicMock()]
        
        # Check data integrity
        integrity = await admin_utils._check_data_integrity()
        
        # Verify healthy integrity
        assert integrity['status'] == 'healthy'
        assert integrity['checks']['marvel_puzzles_exist'] is True
        assert integrity['checks']['dc_puzzles_exist'] is True
        assert integrity['checks']['image_puzzles_exist'] is True
        assert integrity['checks']['future_puzzles_available'] is True
    
    @pytest.mark.asyncio
    async def test_check_data_integrity_missing_puzzles(self, admin_utils):
        """Test data integrity check with missing puzzles"""
        # Mock no puzzles for some universes
        admin_utils.puzzle_repo.get_puzzles_by_universe.return_value = []
        admin_utils.puzzle_repo.get_upcoming_puzzles.return_value = []
        
        # Check data integrity
        integrity = await admin_utils._check_data_integrity()
        
        # Verify unhealthy integrity
        assert integrity['status'] == 'unhealthy'
        assert integrity['checks']['marvel_puzzles_exist'] is False
        assert integrity['checks']['future_puzzles_available'] is False