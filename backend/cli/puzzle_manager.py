#!/usr/bin/env python3
"""
CLI tool for bulk puzzle import and management.
Supports CSV import, validation, and duplicate detection.
"""

import asyncio
import csv
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import argparse

from app.models.puzzle import PuzzleCreate, Puzzle
from app.repositories.puzzle_repository import PuzzleRepository
from app.database.connection import get_cosmos_db
from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PuzzleManager:
    """CLI tool for managing puzzles"""
    
    def __init__(self):
        self.puzzle_repo = PuzzleRepository()
    
    async def import_from_csv(self, csv_file: Path, dry_run: bool = False) -> Dict[str, Any]:
        """
        Import puzzles from CSV file.
        
        Expected CSV format:
        universe,character,character_aliases,image_key,active_date
        
        Args:
            csv_file: Path to CSV file
            dry_run: If True, validate but don't create puzzles
            
        Returns:
            Import statistics
        """
        stats = {
            'total_rows': 0,
            'valid_puzzles': 0,
            'invalid_puzzles': 0,
            'duplicates': 0,
            'created': 0,
            'errors': []
        }
        
        if not csv_file.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_file}")
        
        logger.info(f"Starting puzzle import from {csv_file}")
        
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            # Validate CSV headers
            required_headers = {'universe', 'character', 'image_key', 'active_date'}
            if not required_headers.issubset(set(reader.fieldnames)):
                missing = required_headers - set(reader.fieldnames)
                raise ValueError(f"Missing required CSV headers: {missing}")
            
            puzzles_to_create = []
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 for header
                stats['total_rows'] += 1
                
                try:
                    # Parse character aliases (comma-separated in CSV)
                    aliases_str = row.get('character_aliases', '').strip()
                    character_aliases = []
                    if aliases_str:
                        character_aliases = [alias.strip() for alias in aliases_str.split(',') if alias.strip()]
                    
                    # Create puzzle data
                    puzzle_data = PuzzleCreate(
                        universe=row['universe'].strip(),
                        character=row['character'].strip(),
                        character_aliases=character_aliases,
                        image_key=row['image_key'].strip(),
                        active_date=row['active_date'].strip()
                    )
                    
                    # Check for duplicates in current batch
                    puzzle_id = self._generate_puzzle_id(puzzle_data.active_date, puzzle_data.universe)
                    if any(p.active_date == puzzle_data.active_date and p.universe == puzzle_data.universe 
                           for p in puzzles_to_create):
                        stats['duplicates'] += 1
                        stats['errors'].append(f"Row {row_num}: Duplicate puzzle for {puzzle_data.active_date}-{puzzle_data.universe}")
                        continue
                    
                    puzzles_to_create.append(puzzle_data)
                    stats['valid_puzzles'] += 1
                    
                except Exception as e:
                    stats['invalid_puzzles'] += 1
                    stats['errors'].append(f"Row {row_num}: {str(e)}")
        
        logger.info(f"Validation complete: {stats['valid_puzzles']} valid, {stats['invalid_puzzles']} invalid")
        
        if dry_run:
            logger.info("Dry run mode - no puzzles created")
            return stats
        
        # Create puzzles in database
        if puzzles_to_create:
            try:
                created_puzzles = await self.puzzle_repo.bulk_create_puzzles(puzzles_to_create)
                stats['created'] = len(created_puzzles)
                logger.info(f"Successfully created {stats['created']} puzzles")
            except Exception as e:
                logger.error(f"Error during bulk creation: {e}")
                stats['errors'].append(f"Bulk creation error: {str(e)}")
        
        return stats
    
    async def import_from_json(self, json_file: Path, dry_run: bool = False) -> Dict[str, Any]:
        """
        Import puzzles from JSON file.
        
        Expected JSON format:
        [
            {
                "universe": "marvel",
                "character": "Spider-Man",
                "character_aliases": ["Spiderman", "Peter Parker"],
                "image_key": "marvel/spider-man.jpg",
                "active_date": "2024-01-15"
            }
        ]
        """
        stats = {
            'total_puzzles': 0,
            'valid_puzzles': 0,
            'invalid_puzzles': 0,
            'duplicates': 0,
            'created': 0,
            'errors': []
        }
        
        if not json_file.exists():
            raise FileNotFoundError(f"JSON file not found: {json_file}")
        
        logger.info(f"Starting puzzle import from {json_file}")
        
        with open(json_file, 'r', encoding='utf-8') as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON format: {e}")
        
        if not isinstance(data, list):
            raise ValueError("JSON file must contain an array of puzzle objects")
        
        puzzles_to_create = []
        
        for idx, puzzle_data in enumerate(data):
            stats['total_puzzles'] += 1
            
            try:
                puzzle = PuzzleCreate(**puzzle_data)
                
                # Check for duplicates in current batch
                if any(p.active_date == puzzle.active_date and p.universe == puzzle.universe 
                       for p in puzzles_to_create):
                    stats['duplicates'] += 1
                    stats['errors'].append(f"Index {idx}: Duplicate puzzle for {puzzle.active_date}-{puzzle.universe}")
                    continue
                
                puzzles_to_create.append(puzzle)
                stats['valid_puzzles'] += 1
                
            except Exception as e:
                stats['invalid_puzzles'] += 1
                stats['errors'].append(f"Index {idx}: {str(e)}")
        
        logger.info(f"Validation complete: {stats['valid_puzzles']} valid, {stats['invalid_puzzles']} invalid")
        
        if dry_run:
            logger.info("Dry run mode - no puzzles created")
            return stats
        
        # Create puzzles in database
        if puzzles_to_create:
            try:
                created_puzzles = await self.puzzle_repo.bulk_create_puzzles(puzzles_to_create)
                stats['created'] = len(created_puzzles)
                logger.info(f"Successfully created {stats['created']} puzzles")
            except Exception as e:
                logger.error(f"Error during bulk creation: {e}")
                stats['errors'].append(f"Bulk creation error: {str(e)}")
        
        return stats
    
    async def export_puzzles(self, output_file: Path, universe: Optional[str] = None, 
                           start_date: Optional[str] = None, end_date: Optional[str] = None,
                           format_type: str = 'json') -> int:
        """
        Export puzzles to file.
        
        Args:
            output_file: Output file path
            universe: Filter by universe (optional)
            start_date: Start date filter (YYYY-MM-DD)
            end_date: End date filter (YYYY-MM-DD)
            format_type: Export format ('json' or 'csv')
            
        Returns:
            Number of puzzles exported
        """
        puzzles = []
        
        if universe and start_date and end_date:
            puzzles = await self.puzzle_repo.get_puzzles_by_date_range(universe, start_date, end_date)
        elif universe:
            puzzles = await self.puzzle_repo.get_puzzles_by_universe(universe, limit=1000)
        else:
            # Export all puzzles (this could be large)
            for univ in ['marvel', 'dc', 'image']:
                univ_puzzles = await self.puzzle_repo.get_puzzles_by_universe(univ, limit=1000)
                puzzles.extend(univ_puzzles)
        
        if format_type.lower() == 'csv':
            await self._export_to_csv(puzzles, output_file)
        else:
            await self._export_to_json(puzzles, output_file)
        
        logger.info(f"Exported {len(puzzles)} puzzles to {output_file}")
        return len(puzzles)
    
    async def _export_to_csv(self, puzzles: List[Puzzle], output_file: Path):
        """Export puzzles to CSV format"""
        with open(output_file, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            
            # Write header
            writer.writerow(['universe', 'character', 'character_aliases', 'image_key', 'active_date', 'created_at'])
            
            # Write puzzle data
            for puzzle in puzzles:
                aliases_str = ','.join(puzzle.character_aliases) if puzzle.character_aliases else ''
                writer.writerow([
                    puzzle.universe,
                    puzzle.character,
                    aliases_str,
                    puzzle.image_key,
                    puzzle.active_date,
                    puzzle.created_at.isoformat()
                ])
    
    async def _export_to_json(self, puzzles: List[Puzzle], output_file: Path):
        """Export puzzles to JSON format"""
        puzzle_data = []
        for puzzle in puzzles:
            puzzle_data.append({
                'universe': puzzle.universe,
                'character': puzzle.character,
                'character_aliases': puzzle.character_aliases,
                'image_key': puzzle.image_key,
                'active_date': puzzle.active_date,
                'created_at': puzzle.created_at.isoformat()
            })
        
        with open(output_file, 'w', encoding='utf-8') as file:
            json.dump(puzzle_data, file, indent=2, ensure_ascii=False)
    
    async def validate_puzzles(self, universe: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate existing puzzles in database.
        
        Args:
            universe: Validate specific universe (optional)
            
        Returns:
            Validation results
        """
        results = {
            'total_checked': 0,
            'valid_puzzles': 0,
            'invalid_puzzles': 0,
            'missing_images': 0,
            'duplicate_dates': 0,
            'errors': []
        }
        
        universes = [universe] if universe else ['marvel', 'dc', 'image']
        
        for univ in universes:
            puzzles = await self.puzzle_repo.get_puzzles_by_universe(univ, limit=1000)
            results['total_checked'] += len(puzzles)
            
            # Check for duplicate dates
            dates_seen = set()
            for puzzle in puzzles:
                if puzzle.active_date in dates_seen:
                    results['duplicate_dates'] += 1
                    results['errors'].append(f"Duplicate date {puzzle.active_date} in {univ} universe")
                dates_seen.add(puzzle.active_date)
            
            # Validate each puzzle
            for puzzle in puzzles:
                try:
                    # Re-validate the puzzle model
                    Puzzle(**puzzle.model_dump())
                    results['valid_puzzles'] += 1
                    
                    # TODO: Check if image exists in blob storage
                    # This would require integration with BlobStorageService
                    
                except Exception as e:
                    results['invalid_puzzles'] += 1
                    results['errors'].append(f"Invalid puzzle {puzzle.id}: {str(e)}")
        
        return results
    
    async def delete_puzzles(self, universe: str, start_date: str, end_date: str, 
                           confirm: bool = False) -> int:
        """
        Delete puzzles in date range.
        
        Args:
            universe: Universe to delete from
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            confirm: Must be True to actually delete
            
        Returns:
            Number of puzzles deleted
        """
        if not confirm:
            logger.warning("Delete operation requires confirm=True")
            return 0
        
        puzzles = await self.puzzle_repo.get_puzzles_by_date_range(universe, start_date, end_date)
        deleted_count = 0
        
        for puzzle in puzzles:
            if await self.puzzle_repo.delete_puzzle(puzzle.id):
                deleted_count += 1
        
        logger.info(f"Deleted {deleted_count} puzzles from {universe} universe")
        return deleted_count
    
    def _generate_puzzle_id(self, active_date: str, universe: str) -> str:
        """Generate puzzle ID in format YYYYMMDD-universe"""
        date_obj = datetime.strptime(active_date, '%Y-%m-%d')
        date_str = date_obj.strftime('%Y%m%d')
        return f"{date_str}-{universe}"

async def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description='ComicGuess Puzzle Management CLI')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Import command
    import_parser = subparsers.add_parser('import', help='Import puzzles from file')
    import_parser.add_argument('file', type=Path, help='Input file (CSV or JSON)')
    import_parser.add_argument('--dry-run', action='store_true', help='Validate only, do not create')
    import_parser.add_argument('--format', choices=['csv', 'json'], help='File format (auto-detected if not specified)')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export puzzles to file')
    export_parser.add_argument('file', type=Path, help='Output file')
    export_parser.add_argument('--universe', choices=['marvel', 'dc', 'image'], help='Filter by universe')
    export_parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    export_parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')
    export_parser.add_argument('--format', choices=['csv', 'json'], default='json', help='Output format')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate existing puzzles')
    validate_parser.add_argument('--universe', choices=['marvel', 'dc', 'image'], help='Validate specific universe')
    
    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete puzzles in date range')
    delete_parser.add_argument('universe', choices=['marvel', 'dc', 'image'], help='Universe to delete from')
    delete_parser.add_argument('start_date', help='Start date (YYYY-MM-DD)')
    delete_parser.add_argument('end_date', help='End date (YYYY-MM-DD)')
    delete_parser.add_argument('--confirm', action='store_true', help='Confirm deletion')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize database connection
    await get_cosmos_db()
    
    manager = PuzzleManager()
    
    try:
        if args.command == 'import':
            # Auto-detect format if not specified
            format_type = args.format
            if not format_type:
                format_type = 'json' if args.file.suffix.lower() == '.json' else 'csv'
            
            if format_type == 'csv':
                stats = await manager.import_from_csv(args.file, args.dry_run)
            else:
                stats = await manager.import_from_json(args.file, args.dry_run)
            
            print(f"Import Results:")
            print(f"  Total rows/items: {stats.get('total_rows', stats.get('total_puzzles', 0))}")
            print(f"  Valid puzzles: {stats['valid_puzzles']}")
            print(f"  Invalid puzzles: {stats['invalid_puzzles']}")
            print(f"  Duplicates: {stats['duplicates']}")
            print(f"  Created: {stats['created']}")
            
            if stats['errors']:
                print(f"\nErrors:")
                for error in stats['errors'][:10]:  # Show first 10 errors
                    print(f"  {error}")
                if len(stats['errors']) > 10:
                    print(f"  ... and {len(stats['errors']) - 10} more errors")
        
        elif args.command == 'export':
            count = await manager.export_puzzles(
                args.file, args.universe, args.start_date, args.end_date, args.format
            )
            print(f"Exported {count} puzzles to {args.file}")
        
        elif args.command == 'validate':
            results = await manager.validate_puzzles(args.universe)
            print(f"Validation Results:")
            print(f"  Total checked: {results['total_checked']}")
            print(f"  Valid puzzles: {results['valid_puzzles']}")
            print(f"  Invalid puzzles: {results['invalid_puzzles']}")
            print(f"  Duplicate dates: {results['duplicate_dates']}")
            
            if results['errors']:
                print(f"\nErrors:")
                for error in results['errors'][:10]:
                    print(f"  {error}")
                if len(results['errors']) > 10:
                    print(f"  ... and {len(results['errors']) - 10} more errors")
        
        elif args.command == 'delete':
            count = await manager.delete_puzzles(
                args.universe, args.start_date, args.end_date, args.confirm
            )
            if args.confirm:
                print(f"Deleted {count} puzzles")
            else:
                print("Use --confirm to actually delete puzzles")
    
    except Exception as e:
        logger.error(f"Command failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())