"""Streak repository for managing user streak data in Cosmos DB"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, date

from app.repositories.base import BaseRepository
from app.config import settings
from app.database.exceptions import ItemNotFoundError

logger = logging.getLogger(__name__)

class StreakDocument:
    """Streak document structure"""
    def __init__(self, user_id: str, publisher: str, current_streak: int = 0, 
                 longest_streak: int = 0, last_played_utc: Optional[str] = None):
        self.id = f"{user_id}:{publisher}"
        self.userId = user_id
        self.publisher = publisher
        self.currentStreak = current_streak
        self.longestStreak = longest_streak
        self.lastPlayedUTC = last_played_utc
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "userId": self.userId,
            "publisher": self.publisher,
            "currentStreak": self.currentStreak,
            "longestStreak": self.longestStreak,
            "lastPlayedUTC": self.lastPlayedUTC
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StreakDocument':
        return cls(
            user_id=data["userId"],
            publisher=data["publisher"],
            current_streak=data.get("currentStreak", 0),
            longest_streak=data.get("longestStreak", 0),
            last_played_utc=data.get("lastPlayedUTC")
        )

class StreakRepository(BaseRepository):
    """Repository for streak data operations"""
    
    def __init__(self):
        super().__init__(settings.cosmos_container_streaks)
    
    def _has_partition_key(self, item: Dict[str, Any], partition_key: str) -> bool:
        """Check if item has the required partition key (userId for streaks)"""
        return 'userId' in item and item['userId'] == partition_key
    
    def _add_partition_key(self, item: Dict[str, Any], partition_key: str) -> Dict[str, Any]:
        """Add partition key to item (userId for streaks)"""
        item['userId'] = partition_key
        return item
    
    async def get_streak(self, user_id: str, publisher: str) -> Optional[StreakDocument]:
        """Get streak for a specific user and publisher"""
        streak_id = f"{user_id}:{publisher}"
        
        try:
            result = await self.get_by_id(streak_id, user_id)
            if result:
                return StreakDocument.from_dict(result)
            return None
        except ItemNotFoundError:
            return None
    
    async def create_or_update_streak(self, user_id: str, publisher: str, 
                                    result: str, played_date_utc: str) -> StreakDocument:
        """
        Create or update streak based on game result
        
        Args:
            user_id: User's unique identifier
            publisher: Publisher name (marvel, dc, image)
            result: Game result ("success" or "fail")
            played_date_utc: Date played in YYYY-MM-DD format
        
        Returns:
            Updated streak document
        """
        existing_streak = await self.get_streak(user_id, publisher)
        
        if existing_streak is None:
            # Create new streak
            current_streak = 1 if result == "success" else 0
            longest_streak = current_streak
            
            streak = StreakDocument(
                user_id=user_id,
                publisher=publisher,
                current_streak=current_streak,
                longest_streak=longest_streak,
                last_played_utc=played_date_utc
            )
        else:
            # Update existing streak
            streak = existing_streak
            
            if result == "success":
                # Check if this is consecutive
                if (streak.lastPlayedUTC and 
                    self._is_consecutive_day(streak.lastPlayedUTC, played_date_utc)):
                    streak.currentStreak += 1
                else:
                    streak.currentStreak = 1
                
                # Update longest streak if needed
                streak.longestStreak = max(streak.longestStreak, streak.currentStreak)
            else:
                # Failed - reset current streak
                streak.currentStreak = 0
            
            streak.lastPlayedUTC = played_date_utc
        
        # Save to database
        streak_dict = streak.to_dict()
        await self.create_or_update(streak_dict, user_id)
        
        return streak
    
    async def get_user_streaks(self, user_id: str) -> Dict[str, Dict[str, int]]:
        """Get all streaks for a user"""
        publishers = ["marvel", "dc", "image"]
        streaks = {}
        
        for publisher in publishers:
            streak = await self.get_streak(user_id, publisher)
            if streak:
                streaks[publisher] = {
                    "current": streak.currentStreak,
                    "longest": streak.longestStreak
                }
            else:
                streaks[publisher] = {
                    "current": 0,
                    "longest": 0
                }
        
        return streaks
    
    def _is_consecutive_day(self, last_played: str, current_played: str) -> bool:
        """Check if current_played is exactly one day after last_played"""
        try:
            last_date = datetime.strptime(last_played, '%Y-%m-%d').date()
            current_date = datetime.strptime(current_played, '%Y-%m-%d').date()
            
            # Check if current date is exactly one day after last date
            delta = current_date - last_date
            return delta.days == 1
        except ValueError:
            # If date parsing fails, assume not consecutive
            return False
    
    async def create_or_update(self, item: Dict[str, Any], partition_key: str) -> Dict[str, Any]:
        """Create or update an item"""
        try:
            # Try to get existing item first
            existing = await self.get_by_id(item["id"], partition_key)
            if existing:
                # Update existing
                return await self.update(item, partition_key)
            else:
                # Create new
                return await self.create(item, partition_key)
        except ItemNotFoundError:
            # Create new
            return await self.create(item, partition_key)