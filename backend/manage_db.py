#!/usr/bin/env python3
"""Database management CLI script"""

import asyncio
import argparse
import sys
import os
import json
from typing import Dict, Any

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import initialize_database, cleanup_database, get_database


async def init_command() -> None:
    """Initialize the database"""
    print("Initializing database...")
    result = await initialize_database()
    print(json.dumps(result, indent=2))


async def cleanup_command() -> None:
    """Clean up the database"""
    print("WARNING: This will delete all database data!")
    confirm = input("Type 'DELETE' to confirm: ")
    
    if confirm != "DELETE":
        print("Cleanup cancelled")
        return
    
    print("Cleaning up database...")
    result = await cleanup_database()
    print(json.dumps(result, indent=2))


async def health_command() -> None:
    """Check database health"""
    print("Checking database health...")
    
    try:
        database = await get_database()
        health_result = await database.health_check()
        print(json.dumps(health_result, indent=2))
    except Exception as e:
        print(f"Health check failed: {e}")
        sys.exit(1)


async def status_command() -> None:
    """Show database status"""
    print("Database Status:")
    print("=" * 50)
    
    try:
        from app.config import settings
        
        print(f"Database URL: {settings.database_url}")
        print(f"Database: {settings.database_name}")
        print(f"Collections:")
        print(f"  - Users: {settings.users_collection}")
        print(f"  - Puzzles: {settings.puzzles_collection}")
        print(f"  - Guesses: {settings.guesses_collection}")
        print(f"  - Streaks: {settings.streaks_collection}")
        
        # Try to connect and get health status
        database = await get_database()
        health_result = await database.health_check()
        
        print(f"\nConnection Status: {health_result['status']}")
        
        if health_result['status'] == 'healthy':
            print("Container Status:")
            for container, status in health_result.get('containers', {}).items():
                print(f"  - {container}: {status}")
        else:
            print(f"Error: {health_result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"Failed to get status: {e}")
        sys.exit(1)


async def test_connection_command() -> None:
    """Test database connection"""
    print("Testing database connection...")
    
    try:
        database = await get_database()
        print("✓ Successfully connected to database")
        
        # Test each collection
        collections = [
            ("users", database.users_collection),
            ("puzzles", database.puzzles_collection),
            ("guesses", database.guesses_collection)
        ]
        
        for name, container in containers:
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, container.read
                )
                print(f"✓ {name} container accessible")
            except Exception as e:
                print(f"❌ {name} container error: {e}")
        
        print("\nConnection test completed")
        
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        sys.exit(1)


def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(description="Database management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Initialize command
    subparsers.add_parser("init", help="Initialize database and containers")
    
    # Cleanup command
    subparsers.add_parser("cleanup", help="Clean up database (WARNING: deletes all data)")
    
    # Health command
    subparsers.add_parser("health", help="Check database health")
    
    # Status command
    subparsers.add_parser("status", help="Show database status")
    
    # Test connection command
    subparsers.add_parser("test", help="Test database connection")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Run the appropriate command
    if args.command == "init":
        asyncio.run(init_command())
    elif args.command == "cleanup":
        asyncio.run(cleanup_command())
    elif args.command == "health":
        asyncio.run(health_command())
    elif args.command == "status":
        asyncio.run(status_command())
    elif args.command == "test":
        asyncio.run(test_connection_command())
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()