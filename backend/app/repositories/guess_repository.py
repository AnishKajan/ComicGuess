"""Guess repository for managing user guess data in Cosmos DB"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from app.repositories.base import BaseRepository
from app.models.guess import Guess, GuessCreate, GuessHistory
from app.config import settings
from app.database.exceptions import ItemNotFoundError, DuplicateItemError

logger = logging.getLogger(__name__)

class GuessRepository(BaseRepository[Guess]):
    """Repository for guess data operations"""
    
    def __init__(self):
        super().__init__(settings.cosmos_container_guesses)
    
    def _has_partition_key(self, item: Dict[str, Any], partition_key: str) -> bool:
        """Check if item has the required partition key (user_id for guesses)"""
        return 'user_id' in item and item['user_id'] == partition_key
    
    def _add_partition_key(self, item: Dict[str, Any], partition_key: str) -> Dict[str, Any]:
        """Add partition key to item (user_id for guesses)"""
        item['user_id'] = partition_key
        return item
    
    async def create_guess(self, guess_data: GuessCreate, is_correct: bool, attempt_number: int) -> Guess:
        """Create a new guess"""
        # Create guess model
        guess = Guess(
            user_id=guess_data.user_id,
            puzzle_id=guess_data.puzzle_id,
            guess=guess_data.guess,
            is_correct=is_correct,
            attempt_number=attempt_number
        )
        
        # Convert to dict for storage
        guess_dict = guess.model_dump()
        
        # Create in database
        result = await self.create(guess_dict, guess.user_id)
        
        # Return Guess model
        return Guess(**result)
    
    async def get_guess_by_id(self, guess_id: str, user_id: str) -> Optional[Guess]:
        """Get a guess by ID"""
        result = await self.get_by_id(guess_id, user_id)
        if result:
            return Guess(**result)
        return None
    
    async def get_user_guesses_for_puzzle(self, user_id: str, puzzle_id: str) -> List[Guess]:
        """Get all guesses by a user for a specific puzzle"""
        query = """
        SELECT * FROM c 
        WHERE c.user_id = @user_id 
        AND c.puzzle_id = @puzzle_id 
        ORDER BY c.attempt_number ASC
        """
        parameters = [
            {"name": "@user_id", "value": user_id},
            {"name": "@puzzle_id", "value": puzzle_id}
        ]
        
        results = await self.query(query, parameters, partition_key=user_id)
        return [Guess(**result) for result in results]
    
    async def get_user_guess_history(self, user_id: str, puzzle_id: str) -> GuessHistory:
        """Get guess history for a user and puzzle"""
        guesses = await self.get_user_guesses_for_puzzle(user_id, puzzle_id)
        
        guess_list = [guess.guess for guess in guesses]
        is_solved = any(guess.is_correct for guess in guesses)
        attempts_used = len(guesses)
        
        return GuessHistory(
            puzzle_id=puzzle_id,
            guesses=guess_list,
            is_solved=is_solved,
            attempts_used=attempts_used
        )
    
    async def get_next_attempt_number(self, user_id: str, puzzle_id: str) -> int:
        """Get the next attempt number for a user's puzzle"""
        guesses = await self.get_user_guesses_for_puzzle(user_id, puzzle_id)
        return len(guesses) + 1
    
    async def has_user_solved_puzzle(self, user_id: str, puzzle_id: str) -> bool:
        """Check if user has already solved a puzzle"""
        query = """
        SELECT VALUE COUNT(1) FROM c 
        WHERE c.user_id = @user_id 
        AND c.puzzle_id = @puzzle_id 
        AND c.is_correct = true
        """
        parameters = [
            {"name": "@user_id", "value": user_id},
            {"name": "@puzzle_id", "value": puzzle_id}
        ]
        
        results = await self.query(query, parameters, partition_key=user_id)
        return (results[0] if results else 0) > 0
    
    async def get_user_attempts_count(self, user_id: str, puzzle_id: str) -> int:
        """Get the number of attempts a user has made for a puzzle"""
        query = """
        SELECT VALUE COUNT(1) FROM c 
        WHERE c.user_id = @user_id 
        AND c.puzzle_id = @puzzle_id
        """
        parameters = [
            {"name": "@user_id", "value": user_id},
            {"name": "@puzzle_id", "value": puzzle_id}
        ]
        
        results = await self.query(query, parameters, partition_key=user_id)
        return results[0] if results else 0
    
    async def can_user_make_guess(self, user_id: str, puzzle_id: str, max_attempts: int = 6) -> bool:
        """Check if user can make another guess (hasn't solved and under max attempts)"""
        if await self.has_user_solved_puzzle(user_id, puzzle_id):
            return False
        
        attempts_count = await self.get_user_attempts_count(user_id, puzzle_id)
        return attempts_count < max_attempts
    
    async def get_user_guesses_by_date(self, user_id: str, date: str) -> List[Guess]:
        """Get all guesses by a user for a specific date"""
        # Convert date to start and end of day for timestamp comparison
        start_datetime = datetime.strptime(date, '%Y-%m-%d')
        end_datetime = start_datetime + timedelta(days=1)
        
        query = """
        SELECT * FROM c 
        WHERE c.user_id = @user_id 
        AND c.timestamp >= @start_time 
        AND c.timestamp < @end_time 
        ORDER BY c.timestamp ASC
        """
        parameters = [
            {"name": "@user_id", "value": user_id},
            {"name": "@start_time", "value": start_datetime.isoformat()},
            {"name": "@end_time", "value": end_datetime.isoformat()}
        ]
        
        results = await self.query(query, parameters, partition_key=user_id)
        return [Guess(**result) for result in results]
    
    async def get_user_recent_guesses(self, user_id: str, limit: int = 50) -> List[Guess]:
        """Get recent guesses by a user"""
        query = """
        SELECT * FROM c 
        WHERE c.user_id = @user_id 
        ORDER BY c.timestamp DESC 
        OFFSET 0 LIMIT @limit
        """
        parameters = [
            {"name": "@user_id", "value": user_id},
            {"name": "@limit", "value": limit}
        ]
        
        results = await self.query(query, parameters, partition_key=user_id)
        return [Guess(**result) for result in results]
    
    async def get_puzzle_guess_statistics(self, puzzle_id: str) -> Dict[str, Any]:
        """Get statistics for guesses on a specific puzzle"""
        # Total attempts
        query = "SELECT VALUE COUNT(1) FROM c WHERE c.puzzle_id = @puzzle_id"
        parameters = [{"name": "@puzzle_id", "value": puzzle_id}]
        
        total_attempts = await self.query(query, parameters)
        total_attempts = total_attempts[0] if total_attempts else 0
        
        # Successful solves
        query = "SELECT VALUE COUNT(1) FROM c WHERE c.puzzle_id = @puzzle_id AND c.is_correct = true"
        
        successful_solves = await self.query(query, parameters)
        successful_solves = successful_solves[0] if successful_solves else 0
        
        # Unique users who attempted
        query = "SELECT VALUE COUNT(DISTINCT c.user_id) FROM c WHERE c.puzzle_id = @puzzle_id"
        
        unique_users = await self.query(query, parameters)
        unique_users = unique_users[0] if unique_users else 0
        
        # Average attempts per solve
        if successful_solves > 0:
            query = """
            SELECT AVG(c.attempt_number) as avg_attempts 
            FROM c 
            WHERE c.puzzle_id = @puzzle_id 
            AND c.is_correct = true
            """
            
            avg_results = await self.query(query, parameters)
            avg_attempts = avg_results[0].get('avg_attempts', 0) if avg_results else 0
        else:
            avg_attempts = 0
        
        return {
            "puzzle_id": puzzle_id,
            "total_attempts": total_attempts,
            "successful_solves": successful_solves,
            "unique_users": unique_users,
            "success_rate": successful_solves / unique_users if unique_users > 0 else 0,
            "average_attempts_to_solve": avg_attempts
        }
    
    async def get_user_guess_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get guess statistics for a specific user"""
        # Total guesses
        query = "SELECT VALUE COUNT(1) FROM c WHERE c.user_id = @user_id"
        parameters = [{"name": "@user_id", "value": user_id}]
        
        total_guesses = await self.query(query, parameters, partition_key=user_id)
        total_guesses = total_guesses[0] if total_guesses else 0
        
        # Correct guesses
        query = "SELECT VALUE COUNT(1) FROM c WHERE c.user_id = @user_id AND c.is_correct = true"
        
        correct_guesses = await self.query(query, parameters, partition_key=user_id)
        correct_guesses = correct_guesses[0] if correct_guesses else 0
        
        # Unique puzzles attempted
        query = "SELECT VALUE COUNT(DISTINCT c.puzzle_id) FROM c WHERE c.user_id = @user_id"
        
        unique_puzzles = await self.query(query, parameters, partition_key=user_id)
        unique_puzzles = unique_puzzles[0] if unique_puzzles else 0
        
        return {
            "user_id": user_id,
            "total_guesses": total_guesses,
            "correct_guesses": correct_guesses,
            "unique_puzzles_attempted": unique_puzzles,
            "accuracy_rate": correct_guesses / total_guesses if total_guesses > 0 else 0
        }
    
    async def delete_user_guesses(self, user_id: str) -> int:
        """Delete all guesses for a user (for user deletion/cleanup)"""
        guesses = await self.get_user_recent_guesses(user_id, limit=1000)  # Get all guesses
        
        deleted_count = 0
        for guess in guesses:
            if await self.delete(guess.id, user_id):
                deleted_count += 1
        
        logger.info(f"Deleted {deleted_count} guesses for user {user_id}")
        return deleted_count
    
    async def cleanup_old_guesses(self, days_to_keep: int = 365) -> int:
        """Clean up guesses older than specified days"""
        cutoff_datetime = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # Get old guesses across all users
        query = "SELECT c.id, c.user_id FROM c WHERE c.timestamp < @cutoff_time"
        parameters = [{"name": "@cutoff_time", "value": cutoff_datetime.isoformat()}]
        
        old_guesses = await self.query(query, parameters)
        
        deleted_count = 0
        for guess_data in old_guesses:
            if await self.delete(guess_data['id'], guess_data['user_id']):
                deleted_count += 1
        
        logger.info(f"Cleaned up {deleted_count} old guesses")
        return deleted_count
    
    async def get_daily_guess_counts(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Get daily guess counts for analytics"""
        query = """
        SELECT 
            LEFT(c.timestamp, 10) as date,
            COUNT(1) as guess_count,
            COUNT(DISTINCT c.user_id) as unique_users
        FROM c 
        WHERE c.timestamp >= @start_date 
        AND c.timestamp < @end_date
        GROUP BY LEFT(c.timestamp, 10)
        ORDER BY LEFT(c.timestamp, 10)
        """
        parameters = [
            {"name": "@start_date", "value": f"{start_date}T00:00:00"},
            {"name": "@end_date", "value": f"{end_date}T23:59:59"}
        ]
        
        results = await self.query(query, parameters)
        return results