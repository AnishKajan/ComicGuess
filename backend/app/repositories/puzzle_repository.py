"""Puzzle repository for managing puzzle data in Cosmos DB"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from app.repositories.base import BaseRepository
from app.models.puzzle import Puzzle, PuzzleCreate, PuzzleResponse
from app.config import settings
from app.database.exceptions import ItemNotFoundError, DuplicateItemError

logger = logging.getLogger(__name__)

class PuzzleRepository(BaseRepository[Puzzle]):
    """Repository for puzzle data operations"""
    
    def __init__(self):
        super().__init__(settings.cosmos_container_puzzles)
    
    def _has_partition_key(self, item: Dict[str, Any], partition_key: str) -> bool:
        """Check if item has the required partition key (universe for puzzles)"""
        return 'universe' in item and item['universe'] == partition_key
    
    def _add_partition_key(self, item: Dict[str, Any], partition_key: str) -> Dict[str, Any]:
        """Add partition key to item (universe for puzzles)"""
        item['universe'] = partition_key
        return item
    
    def _generate_puzzle_id(self, active_date: str, universe: str) -> str:
        """Generate puzzle ID in format YYYYMMDD-universe"""
        date_obj = datetime.strptime(active_date, '%Y-%m-%d')
        date_str = date_obj.strftime('%Y%m%d')
        return f"{date_str}-{universe}"
    
    async def create_puzzle(self, puzzle_data: PuzzleCreate) -> Puzzle:
        """Create a new puzzle"""
        # Generate puzzle ID
        puzzle_id = self._generate_puzzle_id(puzzle_data.active_date, puzzle_data.universe)
        
        # Check if puzzle already exists for this date and universe
        existing_puzzle = await self.get_puzzle_by_id(puzzle_id)
        if existing_puzzle:
            raise DuplicateItemError(f"Puzzle already exists for {puzzle_data.active_date} in {puzzle_data.universe} universe")
        
        # Create puzzle model
        puzzle = Puzzle(
            id=puzzle_id,
            universe=puzzle_data.universe,
            character=puzzle_data.character,
            character_aliases=puzzle_data.character_aliases,
            image_key=puzzle_data.image_key,
            active_date=puzzle_data.active_date
        )
        
        # Convert to dict for storage
        puzzle_dict = puzzle.model_dump()
        
        # Create in database
        result = await self.create(puzzle_dict, puzzle.universe)
        
        # Return Puzzle model
        return Puzzle(**result)
    
    async def get_puzzle_by_id(self, puzzle_id: str) -> Optional[Puzzle]:
        """Get a puzzle by ID"""
        # Extract universe from puzzle ID for partition key
        if '-' not in puzzle_id:
            return None
        
        universe = puzzle_id.split('-')[1]
        result = await self.get_by_id(puzzle_id, universe)
        if result:
            return Puzzle(**result)
        return None
    
    async def get_daily_puzzle(self, universe: str, date: Optional[str] = None) -> Optional[Puzzle]:
        """Get the daily puzzle for a specific universe and date"""
        if date is None:
            date = datetime.utcnow().strftime('%Y-%m-%d')
        
        puzzle_id = self._generate_puzzle_id(date, universe)
        return await self.get_puzzle_by_id(puzzle_id)
    
    async def get_puzzles_by_universe(self, universe: str, limit: int = 50) -> List[Puzzle]:
        """Get puzzles for a specific universe"""
        query = "SELECT * FROM c WHERE c.universe = @universe ORDER BY c.active_date DESC OFFSET 0 LIMIT @limit"
        parameters = [
            {"name": "@universe", "value": universe},
            {"name": "@limit", "value": limit}
        ]
        
        results = await self.query(query, parameters, partition_key=universe)
        return [Puzzle(**result) for result in results]
    
    async def get_puzzles_by_date_range(self, universe: str, start_date: str, end_date: str) -> List[Puzzle]:
        """Get puzzles for a universe within a date range"""
        query = """
        SELECT * FROM c 
        WHERE c.universe = @universe 
        AND c.active_date >= @start_date 
        AND c.active_date <= @end_date 
        ORDER BY c.active_date ASC
        """
        parameters = [
            {"name": "@universe", "value": universe},
            {"name": "@start_date", "value": start_date},
            {"name": "@end_date", "value": end_date}
        ]
        
        results = await self.query(query, parameters, partition_key=universe)
        return [Puzzle(**result) for result in results]
    
    async def update_puzzle(self, puzzle_id: str, puzzle_data: Dict[str, Any]) -> Puzzle:
        """Update puzzle information"""
        # Get existing puzzle
        existing_puzzle = await self.get_puzzle_by_id(puzzle_id)
        if not existing_puzzle:
            raise ItemNotFoundError(f"Puzzle with id {puzzle_id} not found")
        
        # Update fields
        puzzle_dict = existing_puzzle.model_dump()
        puzzle_dict.update(puzzle_data)
        
        # Validate updated puzzle
        updated_puzzle = Puzzle(**puzzle_dict)
        
        # Update in database
        result = await self.update(updated_puzzle.model_dump(), updated_puzzle.universe)
        
        return Puzzle(**result)
    
    async def delete_puzzle(self, puzzle_id: str) -> bool:
        """Delete a puzzle"""
        # Extract universe from puzzle ID for partition key
        if '-' not in puzzle_id:
            return False
        
        universe = puzzle_id.split('-')[1]
        return await self.delete(puzzle_id, universe)
    
    async def get_puzzle_response(self, universe: str, date: Optional[str] = None) -> Optional[PuzzleResponse]:
        """Get puzzle response (without revealing the answer)"""
        puzzle = await self.get_daily_puzzle(universe, date)
        if puzzle:
            return PuzzleResponse(
                id=puzzle.id,
                universe=puzzle.universe,
                active_date=puzzle.active_date
            )
        return None
    
    async def validate_guess(self, puzzle_id: str, guess: str) -> tuple[bool, Optional[str]]:
        """Validate a guess against a puzzle"""
        puzzle = await self.get_puzzle_by_id(puzzle_id)
        if not puzzle:
            raise ItemNotFoundError(f"Puzzle with id {puzzle_id} not found")
        
        is_correct = puzzle.is_correct_guess(guess)
        character_name = puzzle.character if is_correct else None
        
        return is_correct, character_name
    
    async def get_puzzles_by_character(self, character_name: str, limit: int = 10) -> List[Puzzle]:
        """Get puzzles featuring a specific character"""
        query = """
        SELECT * FROM c 
        WHERE LOWER(c.character) = @character 
        OR ARRAY_CONTAINS(c.character_aliases, @character, true)
        ORDER BY c.active_date DESC 
        OFFSET 0 LIMIT @limit
        """
        parameters = [
            {"name": "@character", "value": character_name.lower()},
            {"name": "@limit", "value": limit}
        ]
        
        results = await self.query(query, parameters)
        return [Puzzle(**result) for result in results]
    
    async def get_upcoming_puzzles(self, universe: str, days_ahead: int = 7) -> List[Puzzle]:
        """Get upcoming puzzles for a universe"""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        future_date = (datetime.utcnow() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
        
        return await self.get_puzzles_by_date_range(universe, today, future_date)
    
    async def get_past_puzzles(self, universe: str, days_back: int = 30) -> List[Puzzle]:
        """Get past puzzles for a universe"""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        past_date = (datetime.utcnow() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        return await self.get_puzzles_by_date_range(universe, past_date, today)
    
    async def get_puzzle_statistics(self, universe: str) -> Dict[str, Any]:
        """Get statistics for puzzles in a universe"""
        query = "SELECT VALUE COUNT(1) FROM c WHERE c.universe = @universe"
        parameters = [{"name": "@universe", "value": universe}]
        
        count_results = await self.query(query, parameters, partition_key=universe)
        total_puzzles = count_results[0] if count_results else 0
        
        # Get date range
        query = """
        SELECT 
            MIN(c.active_date) as earliest_date,
            MAX(c.active_date) as latest_date
        FROM c 
        WHERE c.universe = @universe
        """
        
        date_results = await self.query(query, parameters, partition_key=universe)
        date_info = date_results[0] if date_results else {}
        
        return {
            "universe": universe,
            "total_puzzles": total_puzzles,
            "earliest_date": date_info.get("earliest_date"),
            "latest_date": date_info.get("latest_date")
        }
    
    async def bulk_create_puzzles(self, puzzles_data: List[PuzzleCreate]) -> List[Puzzle]:
        """Create multiple puzzles in batch"""
        created_puzzles = []
        
        for puzzle_data in puzzles_data:
            try:
                puzzle = await self.create_puzzle(puzzle_data)
                created_puzzles.append(puzzle)
            except DuplicateItemError as e:
                logger.warning(f"Skipping duplicate puzzle: {e}")
                continue
            except Exception as e:
                logger.error(f"Error creating puzzle for {puzzle_data.active_date}-{puzzle_data.universe}: {e}")
                continue
        
        logger.info(f"Successfully created {len(created_puzzles)} puzzles")
        return created_puzzles
    
    async def cleanup_old_puzzles(self, days_to_keep: int = 365) -> int:
        """Clean up puzzles older than specified days"""
        cutoff_date = (datetime.utcnow() - timedelta(days=days_to_keep)).strftime('%Y-%m-%d')
        
        # Get old puzzles across all universes
        query = "SELECT c.id, c.universe FROM c WHERE c.active_date < @cutoff_date"
        parameters = [{"name": "@cutoff_date", "value": cutoff_date}]
        
        old_puzzles = await self.query(query, parameters)
        
        deleted_count = 0
        for puzzle_data in old_puzzles:
            if await self.delete_puzzle(puzzle_data['id']):
                deleted_count += 1
        
        logger.info(f"Cleaned up {deleted_count} old puzzles")
        return deleted_count
    
    async def get_puzzle_count(self) -> int:
        """Get total number of puzzles across all universes"""
        query = "SELECT VALUE COUNT(1) FROM c"
        results = await self.query(query)
        return results[0] if results else 0
    
    async def get_puzzle_count_by_universe(self, universe: str) -> int:
        """Get total number of puzzles for a specific universe"""
        query = "SELECT VALUE COUNT(1) FROM c WHERE c.universe = @universe"
        parameters = [{"name": "@universe", "value": universe}]
        results = await self.query(query, parameters, partition_key=universe)
        return results[0] if results else 0
    
    async def get_puzzles_paginated(self, universe: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Puzzle]:
        """Get puzzles with pagination, optionally filtered by universe"""
        if universe:
            query = "SELECT * FROM c WHERE c.universe = @universe ORDER BY c.active_date DESC OFFSET @offset LIMIT @limit"
            parameters = [
                {"name": "@universe", "value": universe},
                {"name": "@offset", "value": offset},
                {"name": "@limit", "value": limit}
            ]
            results = await self.query(query, parameters, partition_key=universe)
        else:
            query = "SELECT * FROM c ORDER BY c.active_date DESC OFFSET @offset LIMIT @limit"
            parameters = [
                {"name": "@offset", "value": offset},
                {"name": "@limit", "value": limit}
            ]
            results = await self.query(query, parameters)
        
        return [Puzzle(**result) for result in results]