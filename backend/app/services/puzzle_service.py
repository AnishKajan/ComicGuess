"""Puzzle generation and management service"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import random
import asyncio

from app.models.puzzle import Puzzle, PuzzleCreate, PuzzleResponse
from app.repositories.puzzle_repository import PuzzleRepository
from app.database.exceptions import ItemNotFoundError, DuplicateItemError

logger = logging.getLogger(__name__)

class PuzzleService:
    """Service for puzzle generation and management operations"""
    
    def __init__(self):
        self.puzzle_repository = PuzzleRepository()
        self.universes = ["marvel", "DC", "image"]
    
    def generate_puzzle_id(self, date: str, universe: str) -> str:
        """Generate puzzle ID in format YYYYMMDD-universe"""
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        date_str = date_obj.strftime('%Y%m%d')
        return f"{date_str}-{universe}"
    
    def get_today_date(self) -> str:
        """Get today's date in YYYY-MM-DD format"""
        return datetime.utcnow().strftime('%Y-%m-%d')
    
    def get_date_for_offset(self, days_offset: int = 0) -> str:
        """Get date with offset in YYYY-MM-DD format"""
        target_date = datetime.utcnow() + timedelta(days=days_offset)
        return target_date.strftime('%Y-%m-%d')
    
    async def create_daily_puzzle(self, universe: str, character: str, 
                                character_aliases: List[str], image_key: str, 
                                active_date: Optional[str] = None) -> Puzzle:
        """Create a daily puzzle for a specific universe"""
        if active_date is None:
            active_date = self.get_today_date()
        
        puzzle_data = PuzzleCreate(
            universe=universe,
            character=character,
            character_aliases=character_aliases,
            image_key=image_key,
            active_date=active_date
        )
        
        return await self.puzzle_repository.create_puzzle(puzzle_data)
    
    async def get_daily_puzzle(self, universe: str, date: Optional[str] = None) -> Optional[Puzzle]:
        """Get the daily puzzle for a universe"""
        if date is None:
            date = self.get_today_date()
        
        return await self.puzzle_repository.get_daily_puzzle(universe, date)
    
    async def get_daily_puzzle_response(self, universe: str, date: Optional[str] = None) -> Optional[PuzzleResponse]:
        """Get daily puzzle response (without revealing answer)"""
        if date is None:
            date = self.get_today_date()
        
        return await self.puzzle_repository.get_puzzle_response(universe, date)
    
    async def validate_puzzle_guess(self, puzzle_id: str, guess: str) -> tuple[bool, Optional[str], Optional[str]]:
        """Validate a guess against a puzzle and return result with image key"""
        puzzle = await self.puzzle_repository.get_puzzle_by_id(puzzle_id)
        if not puzzle:
            raise ItemNotFoundError(f"Puzzle with id {puzzle_id} not found")
        
        is_correct = puzzle.is_correct_guess(guess)
        character_name = puzzle.character if is_correct else None
        image_key = puzzle.image_key if is_correct else None
        
        return is_correct, character_name, image_key
    
    async def generate_daily_puzzles_for_all_universes(self, 
                                                     character_data: Dict[str, Dict[str, Any]], 
                                                     active_date: Optional[str] = None) -> List[Puzzle]:
        """Generate daily puzzles for all universes
        
        Args:
            character_data: Dict with universe as key and character info as value
                          Format: {
                              "marvel": {"character": "Spider-Man", "aliases": ["Spidey"], "image_key": "marvel/spiderman.jpg"},
                              "DC": {"character": "Batman", "aliases": ["Dark Knight"], "image_key": "DC/batman.jpg"},
                              "image": {"character": "Spawn", "aliases": [], "image_key": "image/spawn.jpg"}
                          }
            active_date: Date for puzzles (defaults to today)
        """
        if active_date is None:
            active_date = self.get_today_date()
        
        created_puzzles = []
        
        for universe in self.universes:
            if universe not in character_data:
                logger.warning(f"No character data provided for {universe} universe")
                continue
            
            char_info = character_data[universe]
            
            try:
                puzzle = await self.create_daily_puzzle(
                    universe=universe,
                    character=char_info["character"],
                    character_aliases=char_info.get("aliases", []),
                    image_key=char_info["image_key"],
                    active_date=active_date
                )
                created_puzzles.append(puzzle)
                logger.info(f"Created puzzle for {universe}: {puzzle.id}")
                
            except DuplicateItemError:
                logger.warning(f"Puzzle already exists for {universe} on {active_date}")
                # Get existing puzzle
                existing_puzzle = await self.get_daily_puzzle(universe, active_date)
                if existing_puzzle:
                    created_puzzles.append(existing_puzzle)
            except Exception as e:
                logger.error(f"Failed to create puzzle for {universe} on {active_date}: {e}")
        
        return created_puzzles
    
    async def schedule_future_puzzles(self, 
                                    puzzle_schedule: Dict[str, Dict[str, Dict[str, Any]]], 
                                    days_ahead: int = 7) -> List[Puzzle]:
        """Schedule puzzles for future dates
        
        Args:
            puzzle_schedule: Nested dict with date -> universe -> character info
                           Format: {
                               "2024-01-16": {
                                   "marvel": {"character": "Iron Man", "aliases": ["Tony Stark"], "image_key": "marvel/ironman.jpg"}
                               }
                           }
            days_ahead: Number of days to schedule ahead
        """
        created_puzzles = []
        
        for day_offset in range(1, days_ahead + 1):
            target_date = self.get_date_for_offset(day_offset)
            
            if target_date in puzzle_schedule:
                date_puzzles = await self.generate_daily_puzzles_for_all_universes(
                    puzzle_schedule[target_date], 
                    target_date
                )
                created_puzzles.extend(date_puzzles)
        
        return created_puzzles
    
    async def get_puzzle_metadata(self, puzzle_id: str) -> Dict[str, Any]:
        """Get puzzle metadata without revealing the answer"""
        puzzle = await self.puzzle_repository.get_puzzle_by_id(puzzle_id)
        if not puzzle:
            raise ItemNotFoundError(f"Puzzle with id {puzzle_id} not found")
        
        return {
            "id": puzzle.id,
            "universe": puzzle.universe,
            "active_date": puzzle.active_date,
            "created_at": puzzle.created_at.isoformat(),
            "has_aliases": len(puzzle.character_aliases) > 0,
            "alias_count": len(puzzle.character_aliases)
        }
    
    async def get_universe_statistics(self, universe: str) -> Dict[str, Any]:
        """Get statistics for a specific universe"""
        return await self.puzzle_repository.get_puzzle_statistics(universe)
    
    async def get_all_universe_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all universes"""
        stats = {}
        
        for universe in self.universes:
            stats[universe] = await self.get_universe_statistics(universe)
        
        return stats
    
    async def check_puzzle_availability(self, universe: str, date: str) -> bool:
        """Check if a puzzle exists for a specific universe and date"""
        puzzle = await self.puzzle_repository.get_daily_puzzle(universe, date)
        return puzzle is not None
    
    async def get_missing_puzzles(self, start_date: str, end_date: str) -> Dict[str, List[str]]:
        """Get list of missing puzzles for each universe in a date range"""
        missing_puzzles = {universe: [] for universe in self.universes}
        
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        current_date = start_dt
        while current_date <= end_dt:
            date_str = current_date.strftime('%Y-%m-%d')
            
            for universe in self.universes:
                if not await self.check_puzzle_availability(universe, date_str):
                    missing_puzzles[universe].append(date_str)
            
            current_date += timedelta(days=1)
        
        return missing_puzzles
    
    async def bulk_create_puzzles(self, puzzles_data: List[Dict[str, Any]]) -> List[Puzzle]:
        """Bulk create puzzles from a list of puzzle data
        
        Args:
            puzzles_data: List of dicts with keys: universe, character, aliases, image_key, active_date
        """
        puzzle_creates = []
        
        for data in puzzles_data:
            puzzle_create = PuzzleCreate(
                universe=data["universe"],
                character=data["character"],
                character_aliases=data.get("aliases", []),
                image_key=data["image_key"],
                active_date=data["active_date"]
            )
            puzzle_creates.append(puzzle_create)
        
        return await self.puzzle_repository.bulk_create_puzzles(puzzle_creates)
    
    async def update_puzzle_metadata(self, puzzle_id: str, updates: Dict[str, Any]) -> Puzzle:
        """Update puzzle metadata (excluding character and aliases for security)"""
        # Only allow safe updates
        allowed_updates = {}
        safe_fields = ["image_key", "active_date"]
        
        for field in safe_fields:
            if field in updates:
                allowed_updates[field] = updates[field]
        
        if not allowed_updates:
            raise ValueError("No valid fields to update")
        
        return await self.puzzle_repository.update_puzzle(puzzle_id, allowed_updates)
    
    async def delete_puzzle(self, puzzle_id: str) -> bool:
        """Delete a puzzle"""
        return await self.puzzle_repository.delete_puzzle(puzzle_id)
    
    async def cleanup_old_puzzles(self, days_to_keep: int = 365) -> int:
        """Clean up old puzzles"""
        return await self.puzzle_repository.cleanup_old_puzzles(days_to_keep)
    
    async def get_recent_puzzles(self, universe: str, limit: int = 10) -> List[PuzzleResponse]:
        """Get recent puzzles for a universe (without answers)"""
        puzzles = await self.puzzle_repository.get_puzzles_by_universe(universe, limit)
        
        return [
            PuzzleResponse(
                id=puzzle.id,
                universe=puzzle.universe,
                active_date=puzzle.active_date
            )
            for puzzle in puzzles
        ]
    
    async def validate_puzzle_data_integrity(self) -> Dict[str, Any]:
        """Validate puzzle data integrity across all universes"""
        integrity_report = {
            "total_puzzles": 0,
            "universes": {},
            "issues": []
        }
        
        for universe in self.universes:
            universe_stats = await self.get_universe_statistics(universe)
            integrity_report["universes"][universe] = universe_stats
            integrity_report["total_puzzles"] += universe_stats.get("total_puzzles", 0)
            
            # Check for missing recent puzzles
            today = self.get_today_date()
            recent_puzzle = await self.get_daily_puzzle(universe, today)
            if not recent_puzzle:
                integrity_report["issues"].append(f"Missing today's puzzle for {universe}")
        
        return integrity_report
    
    async def hotfix_puzzle(self, puzzle_id: str, replacement_character: str, 
                          replacement_aliases: Optional[List[str]] = None) -> Puzzle:
        """Apply emergency hotfix to a puzzle by replacing the character"""
        puzzle = await self.puzzle_repository.get_puzzle_by_id(puzzle_id)
        if not puzzle:
            raise ItemNotFoundError(f"Puzzle with id {puzzle_id} not found")
        
        # Prepare update data
        updates = {
            "character": replacement_character,
            "character_aliases": replacement_aliases or []
        }
        
        # Update the puzzle
        updated_puzzle = await self.puzzle_repository.update_puzzle(puzzle_id, updates)
        
        logger.warning(f"HOTFIX APPLIED: Puzzle {puzzle_id} character changed from '{puzzle.character}' to '{replacement_character}'")
        
        return updated_puzzle