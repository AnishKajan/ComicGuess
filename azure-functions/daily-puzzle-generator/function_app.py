"""
Azure Function for daily puzzle generation
Triggered daily at UTC midnight to generate new puzzles for all universes
"""

import azure.functions as func
import logging
import json
import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Import enhanced logging
from logging_config import setup_azure_logging, get_logger

# Setup logging
logger = setup_azure_logging()

app = func.FunctionApp()

@app.timer_trigger(schedule="0 0 0 * * *", arg_name="mytimer", run_on_startup=False,
                  use_monitor=False) 
def daily_puzzle_generator(mytimer: func.TimerRequest) -> None:
    """
    Timer trigger function that runs daily at UTC midnight (0 0 0 * * *)
    Generates new puzzles for all three universes: Marvel, DC, and Image
    """
    utc_timestamp = datetime.utcnow().replace(
        tzinfo=None
    ).isoformat()
    
    if mytimer.past_due:
        logger.warning('The timer is past due!')
    
    logger.info(f'Daily puzzle generator executed at: {utc_timestamp}')
    
    try:
        # Run the async puzzle generation
        result = asyncio.run(generate_daily_puzzles())
        
        if result["success"]:
            logger.info(f"Successfully generated {result['puzzles_created']} puzzles")
            logger.info(f"Universes processed: {', '.join(result['universes_processed'])}")
        else:
            logger.error(f"Puzzle generation failed: {result['error']}")
            
    except Exception as e:
        logger.error(f"Critical error in daily puzzle generator: {str(e)}")
        raise


async def generate_daily_puzzles() -> Dict[str, Any]:
    """
    Generate daily puzzles for all universes
    Returns a result dictionary with success status and details
    """
    try:
        # Import here to avoid circular imports and ensure proper initialization
        from puzzle_generator import PuzzleGeneratorService
        
        generator = PuzzleGeneratorService()
        
        # Get today's date
        today = datetime.utcnow().strftime('%Y-%m-%d')
        
        # Generate puzzles for all universes
        result = await generator.generate_daily_puzzles_for_date(today)
        
        # Trigger cache invalidation after successful puzzle generation
        if result["puzzles_created"] > 0:
            try:
                await trigger_cache_invalidation()
                logger.info("Cache invalidation triggered successfully")
            except Exception as cache_error:
                logger.warning(f"Cache invalidation failed (non-critical): {cache_error}")
                # Don't fail the entire operation if cache invalidation fails
        
        return {
            "success": True,
            "puzzles_created": result["puzzles_created"],
            "universes_processed": result["universes_processed"],
            "date": today,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating daily puzzles: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "date": datetime.utcnow().strftime('%Y-%m-%d'),
            "timestamp": datetime.utcnow().isoformat()
        }


async def trigger_cache_invalidation() -> None:
    """
    Trigger Cloudflare cache invalidation for puzzle-related paths
    Called after successful daily puzzle generation
    """
    try:
        import aiohttp
        import os
        
        # Get Cloudflare configuration from environment
        zone_id = os.getenv("CLOUDFLARE_ZONE_ID")
        api_token = os.getenv("CLOUDFLARE_API_TOKEN")
        
        if not zone_id or not api_token:
            logger.warning("Cloudflare configuration not found, skipping cache invalidation")
            return
        
        # Define paths to purge at puzzle rollover
        paths_to_purge = [
            "https://comicguess.app/api/puzzle/today*",
            "https://comicguess.app/api/daily-progress*",
            "https://comicguess.app/api/streak-status*",
            "https://comicguess.app/marvel/*",
            "https://comicguess.app/dc/*",
            "https://comicguess.app/image/*"
        ]
        
        # Cache tags to purge
        cache_tags = [
            "puzzle-metadata",
            "daily-puzzle",
            f"puzzle-{datetime.utcnow().strftime('%Y%m%d')}"
        ]
        
        url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache"
        
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "files": paths_to_purge,
            "tags": cache_tags
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                response_data = await response.json()
                
                if response.status == 200 and response_data.get("success"):
                    logger.info(f"Cache invalidation successful: purged {len(paths_to_purge)} paths")
                else:
                    error_msg = response_data.get("errors", [{"message": f"HTTP {response.status}"}])
                    logger.error(f"Cache invalidation failed: {error_msg}")
                    raise Exception(f"Cloudflare API error: {error_msg}")
        
    except Exception as e:
        logger.error(f"Cache invalidation error: {str(e)}")
        raise


@app.function_name(name="ManualPuzzleGeneration")
@app.route(route="generate-puzzles", auth_level=func.AuthLevel.FUNCTION)
async def manual_puzzle_generation(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP trigger for manual puzzle generation (for testing and admin use)
    Supports generating puzzles for specific dates or universes
    """
    logger.info('Manual puzzle generation HTTP trigger function processed a request.')
    
    try:
        # Parse request parameters
        date = req.params.get('date')
        universe = req.params.get('universe')
        
        # If no date specified, use today
        if not date:
            date = datetime.utcnow().strftime('%Y-%m-%d')
        
        # Validate date format
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            return func.HttpResponse(
                json.dumps({"error": "Invalid date format. Use YYYY-MM-DD"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Import and initialize generator
        from puzzle_generator import PuzzleGeneratorService
        generator = PuzzleGeneratorService()
        
        # Generate puzzles
        if universe:
            # Generate for specific universe
            result = await generator.generate_puzzle_for_universe(universe, date)
        else:
            # Generate for all universes
            result = await generator.generate_daily_puzzles_for_date(date)
        
        return func.HttpResponse(
            json.dumps(result, indent=2),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logger.error(f"Error in manual puzzle generation: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


@app.function_name(name="PuzzleHealthCheck")
@app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS)
async def puzzle_health_check(req: func.HttpRequest) -> func.HttpResponse:
    """
    Health check endpoint for monitoring puzzle generation system
    """
    try:
        from puzzle_generator import PuzzleGeneratorService
        generator = PuzzleGeneratorService()
        
        # Perform health checks
        health_status = await generator.perform_health_check()
        
        status_code = 200 if health_status["healthy"] else 503
        
        return func.HttpResponse(
            json.dumps(health_status, indent=2),
            status_code=status_code,
            mimetype="application/json"
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return func.HttpResponse(
            json.dumps({
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }),
            status_code=503,
            mimetype="application/json"
        )