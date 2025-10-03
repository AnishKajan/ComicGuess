#!/usr/bin/env python3
"""
Main CLI entry point for ComicGuess content management tools.
Provides unified access to puzzle and image management commands.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from cli.puzzle_manager import PuzzleManager
from cli.image_manager import ImageManager
from cli.admin_utils import AdminUtils
from cli.backup_manager import backup_cli
from cli.storage_reliability import storage_cli
from cli.health_monitor import health_cli
from app.database.connection import get_cosmos_db


async def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='ComicGuess Content Management CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import puzzles from CSV
  python -m cli.main puzzle import puzzles.csv
  
  # Export puzzles to JSON
  python -m cli.main puzzle export output.json --universe marvel
  
  # Upload single image
  python -m cli.main image upload marvel "Spider-Man" spider-man.jpg
  
  # Bulk upload images
  python -m cli.main image bulk-upload marvel ./images/marvel/
  
  # List images in universe
  python -m cli.main image list dc
  
  # Validate puzzles
  python -m cli.main puzzle validate --universe image
        """
    )
    
    subparsers = parser.add_subparsers(dest='tool', help='Management tools')
    
    # Puzzle management commands
    puzzle_parser = subparsers.add_parser('puzzle', help='Puzzle management commands')
    puzzle_subparsers = puzzle_parser.add_subparsers(dest='puzzle_command', help='Puzzle commands')
    
    # Puzzle import
    puzzle_import = puzzle_subparsers.add_parser('import', help='Import puzzles from file')
    puzzle_import.add_argument('file', type=Path, help='Input file (CSV or JSON)')
    puzzle_import.add_argument('--dry-run', action='store_true', help='Validate only, do not create')
    puzzle_import.add_argument('--format', choices=['csv', 'json'], help='File format (auto-detected if not specified)')
    
    # Puzzle export
    puzzle_export = puzzle_subparsers.add_parser('export', help='Export puzzles to file')
    puzzle_export.add_argument('file', type=Path, help='Output file')
    puzzle_export.add_argument('--universe', choices=['marvel', 'dc', 'image'], help='Filter by universe')
    puzzle_export.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    puzzle_export.add_argument('--end-date', help='End date (YYYY-MM-DD)')
    puzzle_export.add_argument('--format', choices=['csv', 'json'], default='json', help='Output format')
    
    # Puzzle validate
    puzzle_validate = puzzle_subparsers.add_parser('validate', help='Validate existing puzzles')
    puzzle_validate.add_argument('--universe', choices=['marvel', 'dc', 'image'], help='Validate specific universe')
    
    # Puzzle delete
    puzzle_delete = puzzle_subparsers.add_parser('delete', help='Delete puzzles in date range')
    puzzle_delete.add_argument('universe', choices=['marvel', 'dc', 'image'], help='Universe to delete from')
    puzzle_delete.add_argument('start_date', help='Start date (YYYY-MM-DD)')
    puzzle_delete.add_argument('end_date', help='End date (YYYY-MM-DD)')
    puzzle_delete.add_argument('--confirm', action='store_true', help='Confirm deletion')
    
    # Image management commands
    image_parser = subparsers.add_parser('image', help='Image management commands')
    image_subparsers = image_parser.add_subparsers(dest='image_command', help='Image commands')
    
    # Backup management commands
    backup_parser = subparsers.add_parser('backup', help='Database backup and recovery commands')
    
    # Storage reliability commands
    storage_parser = subparsers.add_parser('storage', help='Storage reliability and disaster recovery commands')
    
    # Health monitoring commands
    health_parser = subparsers.add_parser('health', help='Health monitoring and resilience commands')
    
    # Administrative commands
    admin_parser = subparsers.add_parser('admin', help='Administrative commands')
    admin_subparsers = admin_parser.add_subparsers(dest='admin_command', help='Admin commands')
    
    # Image upload
    image_upload = image_subparsers.add_parser('upload', help='Upload a single image')
    image_upload.add_argument('universe', choices=['marvel', 'dc', 'image'], help='Comic universe')
    image_upload.add_argument('character', help='Character name')
    image_upload.add_argument('image', type=Path, help='Image file path')
    image_upload.add_argument('--no-optimize', action='store_true', help='Skip image optimization')
    image_upload.add_argument('--overwrite', action='store_true', help='Overwrite existing image')
    
    # Image bulk upload
    image_bulk = image_subparsers.add_parser('bulk-upload', help='Upload multiple images from directory')
    image_bulk.add_argument('universe', choices=['marvel', 'dc', 'image'], help='Comic universe')
    image_bulk.add_argument('directory', type=Path, help='Directory containing images')
    image_bulk.add_argument('--no-optimize', action='store_true', help='Skip image optimization')
    image_bulk.add_argument('--overwrite', action='store_true', help='Overwrite existing images')
    image_bulk.add_argument('--dry-run', action='store_true', help='Validate only, do not upload')
    
    # Image list
    image_list = image_subparsers.add_parser('list', help='List images in universe')
    image_list.add_argument('universe', choices=['marvel', 'dc', 'image'], help='Comic universe')
    
    # Image validate
    image_validate = image_subparsers.add_parser('validate', help='Validate images in storage')
    image_validate.add_argument('--universe', choices=['marvel', 'dc', 'image'], help='Validate specific universe')
    
    # Image delete
    image_delete = image_subparsers.add_parser('delete', help='Delete a character image')
    image_delete.add_argument('universe', choices=['marvel', 'dc', 'image'], help='Comic universe')
    image_delete.add_argument('character', help='Character name')
    image_delete.add_argument('--confirm', action='store_true', help='Confirm deletion')
    
    # Admin seed
    admin_seed = admin_subparsers.add_parser('seed', help='Seed database with initial data')
    admin_seed.add_argument('--file', type=Path, help='JSON file containing seed data')
    admin_seed.add_argument('--sample', action='store_true', help='Create sample data')
    
    # Admin backup
    admin_backup = admin_subparsers.add_parser('backup', help='Backup database')
    admin_backup.add_argument('directory', type=Path, help='Backup directory')
    admin_backup.add_argument('--include-blobs', action='store_true', help='Include blob storage in backup')
    
    # Admin restore
    admin_restore = admin_subparsers.add_parser('restore', help='Restore database from backup')
    admin_restore.add_argument('backup_file', type=Path, help='Backup file to restore')
    admin_restore.add_argument('--restore-blobs', action='store_true', help='Restore blob storage')
    admin_restore.add_argument('--confirm', action='store_true', help='Confirm restore operation')
    
    # Admin migrate
    admin_migrate = admin_subparsers.add_parser('migrate', help='Run database migration')
    admin_migrate.add_argument('migration', help='Migration name to run')
    admin_migrate.add_argument('--dry-run', action='store_true', help='Show what would be migrated')
    
    # Admin health
    admin_health = admin_subparsers.add_parser('health', help='Perform health check')
    
    args = parser.parse_args()
    
    if not args.tool:
        parser.print_help()
        return
    
    try:
        # Handle backup commands (delegate to backup CLI)
        if args.tool == 'backup':
            # Pass remaining args to backup CLI
            import sys
            sys.argv = ['backup'] + sys.argv[2:]  # Remove 'main.py backup' and keep rest
            backup_cli()
            return
        
        # Handle storage commands (delegate to storage CLI)
        if args.tool == 'storage':
            # Pass remaining args to storage CLI
            import sys
            sys.argv = ['storage'] + sys.argv[2:]  # Remove 'main.py storage' and keep rest
            storage_cli()
            return
        
        # Handle health commands (delegate to health CLI)
        if args.tool == 'health':
            # Pass remaining args to health CLI
            import sys
            sys.argv = ['health'] + sys.argv[2:]  # Remove 'main.py health' and keep rest
            health_cli()
            return
        
        # Initialize database connection for puzzle and admin operations
        if args.tool in ['puzzle', 'admin']:
            await get_cosmos_db()
        
        # Handle puzzle commands
        if args.tool == 'puzzle':
            if not args.puzzle_command:
                puzzle_parser.print_help()
                return
            
            manager = PuzzleManager()
            
            if args.puzzle_command == 'import':
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
            
            elif args.puzzle_command == 'export':
                count = await manager.export_puzzles(
                    args.file, args.universe, args.start_date, args.end_date, args.format
                )
                print(f"Exported {count} puzzles to {args.file}")
            
            elif args.puzzle_command == 'validate':
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
            
            elif args.puzzle_command == 'delete':
                count = await manager.delete_puzzles(
                    args.universe, args.start_date, args.end_date, args.confirm
                )
                if args.confirm:
                    print(f"Deleted {count} puzzles")
                else:
                    print("Use --confirm to actually delete puzzles")
        
        # Handle image commands
        elif args.tool == 'image':
            if not args.image_command:
                image_parser.print_help()
                return
            
            manager = ImageManager()
            
            if args.image_command == 'upload':
                result = await manager.upload_image(
                    args.universe, args.character, args.image,
                    optimize=not args.no_optimize, overwrite=args.overwrite
                )
                
                if result['success']:
                    print(f"Successfully uploaded {args.character}")
                    print(f"  Original size: {result['original_size']} bytes")
                    print(f"  Final size: {result['final_size']} bytes")
                    print(f"  Blob path: {result['blob_path']}")
                else:
                    print(f"Upload failed: {result['error']}")
                    sys.exit(1)
            
            elif args.image_command == 'bulk-upload':
                stats = await manager.bulk_upload(
                    args.universe, args.directory,
                    optimize=not args.no_optimize, overwrite=args.overwrite,
                    dry_run=args.dry_run
                )
                
                print(f"Bulk Upload Results:")
                print(f"  Total files: {stats['total_files']}")
                print(f"  Valid images: {stats['valid_images']}")
                print(f"  Invalid images: {stats['invalid_images']}")
                print(f"  Uploaded: {stats['uploaded']}")
                print(f"  Skipped: {stats['skipped']}")
                print(f"  Original size: {stats['total_original_size']} bytes")
                print(f"  Final size: {stats['total_final_size']} bytes")
                
                if stats['errors']:
                    print(f"\nErrors:")
                    for error in stats['errors'][:10]:
                        print(f"  {error}")
                    if len(stats['errors']) > 10:
                        print(f"  ... and {len(stats['errors']) - 10} more errors")
            
            elif args.image_command == 'list':
                characters = await manager.list_images(args.universe)
                print(f"Images in {args.universe} universe ({len(characters)} total):")
                for character in sorted(characters):
                    print(f"  {character}")
            
            elif args.image_command == 'validate':
                results = await manager.validate_images(args.universe)
                print(f"Image Validation Results:")
                print(f"  Total images: {results['total_images']}")
                print(f"  Accessible: {results['accessible_images']}")
                print(f"  Inaccessible: {results['inaccessible_images']}")
                
                if results['errors']:
                    print(f"\nErrors:")
                    for error in results['errors']:
                        print(f"  {error}")
            
            elif args.image_command == 'delete':
                success = await manager.delete_image(args.universe, args.character, args.confirm)
                if args.confirm:
                    if success:
                        print(f"Deleted image for {args.character}")
                    else:
                        print(f"Failed to delete image for {args.character}")
                        sys.exit(1)
                else:
                    print("Use --confirm to actually delete the image")
        
        # Handle admin commands
        elif args.tool == 'admin':
            if not args.admin_command:
                admin_parser.print_help()
                return
            
            manager = AdminUtils()
            
            if args.admin_command == 'seed':
                stats = await manager.seed_database(args.file, args.sample)
                print(f"Database Seeding Results:")
                print(f"  Users created: {stats['users_created']}")
                print(f"  Puzzles created: {stats['puzzles_created']}")
                print(f"  Guesses created: {stats['guesses_created']}")
                
                if stats['errors']:
                    print(f"\nErrors:")
                    for error in stats['errors'][:10]:
                        print(f"  {error}")
            
            elif args.admin_command == 'backup':
                stats = await manager.backup_database(args.directory, args.include_blobs)
                print(f"Backup Results:")
                print(f"  Backup file: {stats['backup_file']}")
                print(f"  Users backed up: {stats['users_backed_up']}")
                print(f"  Puzzles backed up: {stats['puzzles_backed_up']}")
                print(f"  Guesses backed up: {stats['guesses_backed_up']}")
                print(f"  Blobs backed up: {stats['blobs_backed_up']}")
            
            elif args.admin_command == 'restore':
                stats = await manager.restore_database(args.backup_file, args.restore_blobs, args.confirm)
                if args.confirm:
                    print(f"Restore Results:")
                    print(f"  Users restored: {stats['users_restored']}")
                    print(f"  Puzzles restored: {stats['puzzles_restored']}")
                    print(f"  Guesses restored: {stats['guesses_restored']}")
                    print(f"  Blobs restored: {stats['blobs_restored']}")
                else:
                    print("Use --confirm to actually restore the database")
            
            elif args.admin_command == 'migrate':
                stats = await manager.migrate_schema(args.migration, args.dry_run)
                print(f"Migration Results:")
                print(f"  Migration: {stats['migration']}")
                print(f"  Items migrated: {stats['items_migrated']}")
                
                if args.dry_run:
                    print("  (Dry run - no changes made)")
            
            elif args.admin_command == 'health':
                health = await manager.health_check()
                print(f"Health Check Results:")
                print(f"  Overall Status: {health['overall_status']}")
                print(f"  Timestamp: {health['timestamp']}")
                
                for component, status in health['components'].items():
                    print(f"  {component}: {status['status']}")
                    if 'error' in status:
                        print(f"    Error: {status['error']}")
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())