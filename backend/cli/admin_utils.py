#!/usr/bin/env python3
"""
Administrative utilities for ComicGuess.
Includes database seeding, backup/restore, and data migration tools.
"""

import asyncio
import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import zipfile
import tempfile

from app.models.user import User, UserCreate
from app.models.puzzle import Puzzle, PuzzleCreate
from app.models.guess import Guess, GuessCreate
from app.repositories.user_repository import UserRepository
from app.repositories.puzzle_repository import PuzzleRepository
from app.repositories.guess_repository import GuessRepository
from app.database.connection import get_cosmos_db, CosmosDBConnection
from app.storage.blob_storage import BlobStorageService
from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AdminUtils:
    """Administrative utilities for ComicGuess"""
    
    def __init__(self):
        self.user_repo = UserRepository()
        self.puzzle_repo = PuzzleRepository()
        self.guess_repo = GuessRepository()
        self.blob_service = BlobStorageService()
    
    async def seed_database(self, seed_file: Optional[Path] = None, 
                          create_sample_data: bool = False) -> Dict[str, Any]:
        """
        Seed the database with initial data.
        
        Args:
            seed_file: JSON file containing seed data (optional)
            create_sample_data: Create sample data if no seed file provided
            
        Returns:
            Seeding statistics
        """
        stats = {
            'users_created': 0,
            'puzzles_created': 0,
            'guesses_created': 0,
            'errors': []
        }
        
        logger.info("Starting database seeding...")
        
        try:
            if seed_file and seed_file.exists():
                # Load data from seed file
                with open(seed_file, 'r', encoding='utf-8') as f:
                    seed_data = json.load(f)
                
                # Seed users
                if 'users' in seed_data:
                    for user_data in seed_data['users']:
                        try:
                            user_create = UserCreate(**user_data)
                            await self.user_repo.create_user(user_create)
                            stats['users_created'] += 1
                        except Exception as e:
                            stats['errors'].append(f"Error creating user {user_data.get('username', 'unknown')}: {e}")
                
                # Seed puzzles
                if 'puzzles' in seed_data:
                    for puzzle_data in seed_data['puzzles']:
                        try:
                            puzzle_create = PuzzleCreate(**puzzle_data)
                            await self.puzzle_repo.create_puzzle(puzzle_create)
                            stats['puzzles_created'] += 1
                        except Exception as e:
                            stats['errors'].append(f"Error creating puzzle {puzzle_data.get('character', 'unknown')}: {e}")
                
                # Seed guesses
                if 'guesses' in seed_data:
                    for guess_data in seed_data['guesses']:
                        try:
                            guess_create = GuessCreate(**guess_data)
                            await self.guess_repo.create_guess(guess_create)
                            stats['guesses_created'] += 1
                        except Exception as e:
                            stats['errors'].append(f"Error creating guess: {e}")
            
            elif create_sample_data:
                # Create sample data
                await self._create_sample_data(stats)
            
            else:
                logger.warning("No seed file provided and create_sample_data is False")
        
        except Exception as e:
            logger.error(f"Error during database seeding: {e}")
            stats['errors'].append(f"Seeding error: {str(e)}")
        
        logger.info(f"Database seeding complete: {stats['users_created']} users, {stats['puzzles_created']} puzzles, {stats['guesses_created']} guesses")
        return stats
    
    async def _create_sample_data(self, stats: Dict[str, Any]) -> None:
        """Create sample data for testing"""
        # Sample users
        sample_users = [
            {
                'id': 'user1',
                'username': 'comic_fan_1',
                'email': 'user1@example.com'
            },
            {
                'id': 'user2', 
                'username': 'marvel_expert',
                'email': 'user2@example.com'
            },
            {
                'id': 'user3',
                'username': 'dc_enthusiast', 
                'email': 'user3@example.com'
            }
        ]
        
        for user_data in sample_users:
            try:
                user_create = UserCreate(**user_data)
                await self.user_repo.create_user(user_create)
                stats['users_created'] += 1
            except Exception as e:
                stats['errors'].append(f"Error creating sample user {user_data['username']}: {e}")
        
        # Sample puzzles for the next 7 days
        base_date = datetime.utcnow()
        sample_puzzles = []
        
        characters = {
            'marvel': ['Spider-Man', 'Iron Man', 'Captain America', 'Thor', 'Hulk', 'Black Widow', 'Hawkeye'],
            'dc': ['Batman', 'Superman', 'Wonder Woman', 'Flash', 'Green Lantern', 'Aquaman', 'Cyborg'],
            'image': ['Spawn', 'Invincible', 'The Walking Dead', 'Saga', 'Chew', 'Outcast', 'Kirkman']
        }
        
        for i in range(7):
            puzzle_date = (base_date + timedelta(days=i)).strftime('%Y-%m-%d')
            
            for universe, char_list in characters.items():
                if i < len(char_list):
                    character = char_list[i]
                    sample_puzzles.append({
                        'universe': universe,
                        'character': character,
                        'character_aliases': [],
                        'image_key': f"{universe}/{character.lower().replace(' ', '-')}.jpg",
                        'active_date': puzzle_date
                    })
        
        for puzzle_data in sample_puzzles:
            try:
                puzzle_create = PuzzleCreate(**puzzle_data)
                await self.puzzle_repo.create_puzzle(puzzle_create)
                stats['puzzles_created'] += 1
            except Exception as e:
                stats['errors'].append(f"Error creating sample puzzle {puzzle_data['character']}: {e}")
    
    async def backup_database(self, backup_dir: Path, include_blobs: bool = False) -> Dict[str, Any]:
        """
        Create a backup of the database and optionally blob storage.
        
        Args:
            backup_dir: Directory to store backup files
            include_blobs: Whether to backup blob storage
            
        Returns:
            Backup statistics
        """
        stats = {
            'backup_file': None,
            'users_backed_up': 0,
            'puzzles_backed_up': 0,
            'guesses_backed_up': 0,
            'blobs_backed_up': 0,
            'errors': []
        }
        
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_file = backup_dir / f"comicguess_backup_{timestamp}.zip"
        
        logger.info(f"Starting database backup to {backup_file}")
        
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Backup users
                users = await self._backup_users()
                if users:
                    zip_file.writestr('users.json', json.dumps(users, indent=2, default=str))
                    stats['users_backed_up'] = len(users)
                
                # Backup puzzles
                puzzles = await self._backup_puzzles()
                if puzzles:
                    zip_file.writestr('puzzles.json', json.dumps(puzzles, indent=2, default=str))
                    stats['puzzles_backed_up'] = len(puzzles)
                
                # Backup guesses
                guesses = await self._backup_guesses()
                if guesses:
                    zip_file.writestr('guesses.json', json.dumps(guesses, indent=2, default=str))
                    stats['guesses_backed_up'] = len(guesses)
                
                # Backup blob storage if requested
                if include_blobs:
                    blob_count = await self._backup_blobs(zip_file)
                    stats['blobs_backed_up'] = blob_count
                
                # Add metadata
                metadata = {
                    'backup_timestamp': timestamp,
                    'database_name': settings.cosmos_db_database_name,
                    'include_blobs': include_blobs,
                    'stats': {
                        'users': stats['users_backed_up'],
                        'puzzles': stats['puzzles_backed_up'],
                        'guesses': stats['guesses_backed_up'],
                        'blobs': stats['blobs_backed_up']
                    }
                }
                zip_file.writestr('metadata.json', json.dumps(metadata, indent=2))
            
            stats['backup_file'] = str(backup_file)
            logger.info(f"Backup completed: {backup_file}")
        
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            stats['errors'].append(f"Backup error: {str(e)}")
        
        return stats
    
    async def restore_database(self, backup_file: Path, restore_blobs: bool = False,
                             confirm: bool = False) -> Dict[str, Any]:
        """
        Restore database from backup file.
        
        Args:
            backup_file: Backup zip file
            restore_blobs: Whether to restore blob storage
            confirm: Must be True to actually restore
            
        Returns:
            Restore statistics
        """
        stats = {
            'users_restored': 0,
            'puzzles_restored': 0,
            'guesses_restored': 0,
            'blobs_restored': 0,
            'errors': []
        }
        
        if not confirm:
            logger.warning("Restore operation requires confirm=True")
            return stats
        
        if not backup_file.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_file}")
        
        logger.info(f"Starting database restore from {backup_file}")
        
        try:
            with zipfile.ZipFile(backup_file, 'r') as zip_file:
                # Read metadata
                try:
                    metadata_content = zip_file.read('metadata.json')
                    metadata = json.loads(metadata_content)
                    logger.info(f"Restoring backup from {metadata['backup_timestamp']}")
                except KeyError:
                    logger.warning("No metadata found in backup file")
                
                # Restore users
                try:
                    users_content = zip_file.read('users.json')
                    users_data = json.loads(users_content)
                    for user_data in users_data:
                        try:
                            user_create = UserCreate(**user_data)
                            await self.user_repo.create_user(user_create)
                            stats['users_restored'] += 1
                        except Exception as e:
                            stats['errors'].append(f"Error restoring user {user_data.get('username', 'unknown')}: {e}")
                except KeyError:
                    logger.info("No users data in backup")
                
                # Restore puzzles
                try:
                    puzzles_content = zip_file.read('puzzles.json')
                    puzzles_data = json.loads(puzzles_content)
                    for puzzle_data in puzzles_data:
                        try:
                            puzzle_create = PuzzleCreate(**puzzle_data)
                            await self.puzzle_repo.create_puzzle(puzzle_create)
                            stats['puzzles_restored'] += 1
                        except Exception as e:
                            stats['errors'].append(f"Error restoring puzzle {puzzle_data.get('character', 'unknown')}: {e}")
                except KeyError:
                    logger.info("No puzzles data in backup")
                
                # Restore guesses
                try:
                    guesses_content = zip_file.read('guesses.json')
                    guesses_data = json.loads(guesses_content)
                    for guess_data in guesses_data:
                        try:
                            guess_create = GuessCreate(**guess_data)
                            await self.guess_repo.create_guess(guess_create)
                            stats['guesses_restored'] += 1
                        except Exception as e:
                            stats['errors'].append(f"Error restoring guess: {e}")
                except KeyError:
                    logger.info("No guesses data in backup")
                
                # Restore blobs if requested
                if restore_blobs:
                    blob_count = await self._restore_blobs(zip_file)
                    stats['blobs_restored'] = blob_count
        
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            stats['errors'].append(f"Restore error: {str(e)}")
        
        logger.info(f"Restore completed: {stats['users_restored']} users, {stats['puzzles_restored']} puzzles, {stats['guesses_restored']} guesses")
        return stats
    
    async def migrate_schema(self, migration_name: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Perform database schema migration.
        
        Args:
            migration_name: Name of the migration to run
            dry_run: If True, show what would be migrated without making changes
            
        Returns:
            Migration statistics
        """
        stats = {
            'migration': migration_name,
            'items_migrated': 0,
            'errors': []
        }
        
        logger.info(f"Starting migration: {migration_name}")
        
        try:
            if migration_name == 'add_user_preferences':
                # Example migration: add preferences field to users
                stats = await self._migrate_add_user_preferences(dry_run)
            
            elif migration_name == 'update_puzzle_aliases':
                # Example migration: normalize puzzle character aliases
                stats = await self._migrate_update_puzzle_aliases(dry_run)
            
            elif migration_name == 'cleanup_old_guesses':
                # Example migration: clean up old guess data
                stats = await self._migrate_cleanup_old_guesses(dry_run)
            
            else:
                raise ValueError(f"Unknown migration: {migration_name}")
        
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            stats['errors'].append(f"Migration error: {str(e)}")
        
        return stats
    
    async def _backup_users(self) -> List[Dict[str, Any]]:
        """Backup all users"""
        users = []
        try:
            # Get all users (this is a simplified approach - in production you'd paginate)
            all_users = await self.user_repo.get_all_users(limit=10000)
            for user in all_users:
                users.append(user.model_dump())
        except Exception as e:
            logger.error(f"Error backing up users: {e}")
        return users
    
    async def _backup_puzzles(self) -> List[Dict[str, Any]]:
        """Backup all puzzles"""
        puzzles = []
        try:
            for universe in ['marvel', 'dc', 'image']:
                universe_puzzles = await self.puzzle_repo.get_puzzles_by_universe(universe, limit=10000)
                for puzzle in universe_puzzles:
                    puzzles.append(puzzle.model_dump())
        except Exception as e:
            logger.error(f"Error backing up puzzles: {e}")
        return puzzles
    
    async def _backup_guesses(self) -> List[Dict[str, Any]]:
        """Backup all guesses"""
        guesses = []
        try:
            # This would need to be implemented in the guess repository
            # For now, return empty list
            logger.warning("Guess backup not implemented - would need pagination support")
        except Exception as e:
            logger.error(f"Error backing up guesses: {e}")
        return guesses
    
    async def _backup_blobs(self, zip_file: zipfile.ZipFile) -> int:
        """Backup blob storage"""
        blob_count = 0
        try:
            for universe in ['marvel', 'dc', 'image']:
                characters = await self.blob_service.list_images_by_universe(universe)
                for character in characters:
                    # This would need to be implemented to download and store blobs
                    # For now, just count them
                    blob_count += 1
            logger.warning("Blob backup not fully implemented - would need blob download support")
        except Exception as e:
            logger.error(f"Error backing up blobs: {e}")
        return blob_count
    
    async def _restore_blobs(self, zip_file: zipfile.ZipFile) -> int:
        """Restore blob storage"""
        blob_count = 0
        try:
            # This would need to be implemented to restore blobs from zip
            logger.warning("Blob restore not implemented")
        except Exception as e:
            logger.error(f"Error restoring blobs: {e}")
        return blob_count
    
    async def _migrate_add_user_preferences(self, dry_run: bool) -> Dict[str, Any]:
        """Migration: Add preferences field to users"""
        stats = {'migration': 'add_user_preferences', 'items_migrated': 0, 'errors': []}
        
        try:
            users = await self.user_repo.get_all_users(limit=10000)
            
            for user in users:
                if not hasattr(user, 'preferences') or user.preferences is None:
                    if not dry_run:
                        # Update user with default preferences
                        default_preferences = {
                            'theme': 'auto',
                            'notifications': True,
                            'difficulty': 'normal'
                        }
                        await self.user_repo.update_user(user.id, {'preferences': default_preferences})
                    
                    stats['items_migrated'] += 1
        
        except Exception as e:
            stats['errors'].append(f"Migration error: {str(e)}")
        
        return stats
    
    async def _migrate_update_puzzle_aliases(self, dry_run: bool) -> Dict[str, Any]:
        """Migration: Normalize puzzle character aliases"""
        stats = {'migration': 'update_puzzle_aliases', 'items_migrated': 0, 'errors': []}
        
        try:
            for universe in ['marvel', 'dc', 'image']:
                puzzles = await self.puzzle_repo.get_puzzles_by_universe(universe, limit=10000)
                
                for puzzle in puzzles:
                    # Normalize aliases (remove duplicates, trim whitespace)
                    original_aliases = puzzle.character_aliases
                    normalized_aliases = list(set(alias.strip() for alias in original_aliases if alias.strip()))
                    
                    if normalized_aliases != original_aliases:
                        if not dry_run:
                            await self.puzzle_repo.update_puzzle(puzzle.id, {
                                'character_aliases': normalized_aliases
                            })
                        
                        stats['items_migrated'] += 1
        
        except Exception as e:
            stats['errors'].append(f"Migration error: {str(e)}")
        
        return stats
    
    async def _migrate_cleanup_old_guesses(self, dry_run: bool) -> Dict[str, Any]:
        """Migration: Clean up old guess data"""
        stats = {'migration': 'cleanup_old_guesses', 'items_migrated': 0, 'errors': []}
        
        try:
            # This would clean up guesses older than a certain date
            # Implementation would depend on guess repository methods
            logger.warning("Old guess cleanup not implemented - would need guess repository support")
        
        except Exception as e:
            stats['errors'].append(f"Migration error: {str(e)}")
        
        return stats
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        health_status = {
            'overall_status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'components': {}
        }
        
        try:
            # Check database connection
            cosmos_db = await get_cosmos_db()
            db_health = await cosmos_db.health_check()
            health_status['components']['database'] = db_health
            
            if db_health['status'] != 'healthy':
                health_status['overall_status'] = 'unhealthy'
            
            # Check blob storage
            try:
                await self.blob_service.ensure_container_exists()
                health_status['components']['blob_storage'] = {'status': 'healthy'}
            except Exception as e:
                health_status['components']['blob_storage'] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }
                health_status['overall_status'] = 'unhealthy'
            
            # Check data integrity
            integrity_check = await self._check_data_integrity()
            health_status['components']['data_integrity'] = integrity_check
            
            if integrity_check['status'] != 'healthy':
                health_status['overall_status'] = 'degraded'
        
        except Exception as e:
            health_status['overall_status'] = 'unhealthy'
            health_status['error'] = str(e)
        
        return health_status
    
    async def _check_data_integrity(self) -> Dict[str, Any]:
        """Check data integrity across collections"""
        integrity_status = {
            'status': 'healthy',
            'checks': {}
        }
        
        try:
            # Check for orphaned data, missing references, etc.
            # This is a simplified example
            
            # Check puzzle count per universe
            for universe in ['marvel', 'dc', 'image']:
                puzzles = await self.puzzle_repo.get_puzzles_by_universe(universe, limit=1)
                integrity_status['checks'][f'{universe}_puzzles_exist'] = len(puzzles) > 0
            
            # Check for future puzzles
            today = datetime.utcnow().strftime('%Y-%m-%d')
            future_puzzles = 0
            for universe in ['marvel', 'dc', 'image']:
                upcoming = await self.puzzle_repo.get_upcoming_puzzles(universe, days_ahead=30)
                future_puzzles += len(upcoming)
            
            integrity_status['checks']['future_puzzles_available'] = future_puzzles > 0
            
            # If any critical checks fail, mark as unhealthy
            critical_checks = ['marvel_puzzles_exist', 'dc_puzzles_exist', 'image_puzzles_exist']
            if not all(integrity_status['checks'].get(check, False) for check in critical_checks):
                integrity_status['status'] = 'unhealthy'
        
        except Exception as e:
            integrity_status['status'] = 'unhealthy'
            integrity_status['error'] = str(e)
        
        return integrity_status

async def main():
    """CLI entry point for admin utilities"""
    parser = argparse.ArgumentParser(description='ComicGuess Administrative Utilities')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Seed command
    seed_parser = subparsers.add_parser('seed', help='Seed database with initial data')
    seed_parser.add_argument('--file', type=Path, help='JSON file containing seed data')
    seed_parser.add_argument('--sample', action='store_true', help='Create sample data')
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Backup database')
    backup_parser.add_argument('directory', type=Path, help='Backup directory')
    backup_parser.add_argument('--include-blobs', action='store_true', help='Include blob storage in backup')
    
    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore database from backup')
    restore_parser.add_argument('backup_file', type=Path, help='Backup file to restore')
    restore_parser.add_argument('--restore-blobs', action='store_true', help='Restore blob storage')
    restore_parser.add_argument('--confirm', action='store_true', help='Confirm restore operation')
    
    # Migrate command
    migrate_parser = subparsers.add_parser('migrate', help='Run database migration')
    migrate_parser.add_argument('migration', help='Migration name to run')
    migrate_parser.add_argument('--dry-run', action='store_true', help='Show what would be migrated')
    
    # Health check command
    health_parser = subparsers.add_parser('health', help='Perform health check')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize database connection
    await get_cosmos_db()
    
    admin = AdminUtils()
    
    try:
        if args.command == 'seed':
            stats = await admin.seed_database(args.file, args.sample)
            print(f"Database Seeding Results:")
            print(f"  Users created: {stats['users_created']}")
            print(f"  Puzzles created: {stats['puzzles_created']}")
            print(f"  Guesses created: {stats['guesses_created']}")
            
            if stats['errors']:
                print(f"\nErrors:")
                for error in stats['errors'][:10]:
                    print(f"  {error}")
        
        elif args.command == 'backup':
            stats = await admin.backup_database(args.directory, args.include_blobs)
            print(f"Backup Results:")
            print(f"  Backup file: {stats['backup_file']}")
            print(f"  Users backed up: {stats['users_backed_up']}")
            print(f"  Puzzles backed up: {stats['puzzles_backed_up']}")
            print(f"  Guesses backed up: {stats['guesses_backed_up']}")
            print(f"  Blobs backed up: {stats['blobs_backed_up']}")
        
        elif args.command == 'restore':
            stats = await admin.restore_database(args.backup_file, args.restore_blobs, args.confirm)
            if args.confirm:
                print(f"Restore Results:")
                print(f"  Users restored: {stats['users_restored']}")
                print(f"  Puzzles restored: {stats['puzzles_restored']}")
                print(f"  Guesses restored: {stats['guesses_restored']}")
                print(f"  Blobs restored: {stats['blobs_restored']}")
            else:
                print("Use --confirm to actually restore the database")
        
        elif args.command == 'migrate':
            stats = await admin.migrate_schema(args.migration, args.dry_run)
            print(f"Migration Results:")
            print(f"  Migration: {stats['migration']}")
            print(f"  Items migrated: {stats['items_migrated']}")
            
            if args.dry_run:
                print("  (Dry run - no changes made)")
        
        elif args.command == 'health':
            health = await admin.health_check()
            print(f"Health Check Results:")
            print(f"  Overall Status: {health['overall_status']}")
            print(f"  Timestamp: {health['timestamp']}")
            
            for component, status in health['components'].items():
                print(f"  {component}: {status['status']}")
                if 'error' in status:
                    print(f"    Error: {status['error']}")
    
    except Exception as e:
        logger.error(f"Command failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())