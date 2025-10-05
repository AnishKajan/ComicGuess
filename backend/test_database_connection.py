#!/usr/bin/env python3
"""
Fast smoke test to verify database connection.
"""
import asyncio
import sys
import os
import time

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def main():
    """Fast smoke test for database connection."""
    start_time = time.time()
    print("🔍 Running database smoke test...")
    
    try:
        from app.database import get_database
        from app.config import settings
        
        # Test connection with timeout
        print(f"📡 Connecting to: {settings.database_url}")
        print(f"🗄️  Database: {settings.database_name}")
        
        database = await get_database()
        health_result = await database.health_check()
        
        elapsed = time.time() - start_time
        
        if health_result.get("status") == "healthy":
            print(f"✅ Connection successful ({elapsed:.2f}s)")
            print(f"📊 Containers: {list(health_result.get('containers', {}).keys())}")
            return 0
        else:
            print(f"❌ Connection unhealthy: {health_result.get('error', 'Unknown error')}")
            return 1
            
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ Connection failed ({elapsed:.2f}s): {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)