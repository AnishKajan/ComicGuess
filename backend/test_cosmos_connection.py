#!/usr/bin/env python3
"""
Fast smoke test to verify Cosmos DB connection.
"""
import asyncio
import sys
import os
import time

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def main():
    """Fast smoke test for Cosmos DB connection."""
    start_time = time.time()
    print("🔍 Running Cosmos DB smoke test...")
    
    try:
        from app.database import get_cosmos_db
        from app.config import settings
        
        # Test connection with timeout
        print(f"📡 Connecting to: {settings.effective_cosmos_endpoint}")
        print(f"🗄️  Database: {settings.effective_cosmos_database_name}")
        
        cosmos_db = await get_cosmos_db()
        health_result = await cosmos_db.health_check()
        
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