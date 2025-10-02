"""Partition key handling utilities for Cosmos DB"""

from typing import Any, Dict, Optional
from datetime import datetime

from app.models import User, Puzzle, Guess


class PartitionKeyManager:
    """Manages partition key operations for different document types"""
    
    @staticmethod
    def get_user_partition_key(user_id: str) -> str:
        """Get partition key for user documents"""
        # Users are partitioned by their ID for even distribution
        return user_id
    
    @staticmethod
    def get_puzzle_partition_key(universe: str) -> str:
        """Get partition key for puzzle documents"""
        # Puzzles are partitioned by universe (marvel, dc, image)
        return universe.lower()
    
    @staticmethod
    def get_guess_partition_key(user_id: str) -> str:
        """Get partition key for guess documents"""
        # Guesses are partitioned by user_id to keep user's guesses together
        return user_id
    
    @staticmethod
    def extract_partition_key_from_document(document: Dict[str, Any], document_type: str) -> str:
        """Extract partition key from a document based on its type"""
        
        if document_type == "user":
            return document.get("id", "")
        elif document_type == "puzzle":
            return document.get("universe", "").lower()
        elif document_type == "guess":
            return document.get("user_id", "")
        else:
            raise ValueError(f"Unknown document type: {document_type}")
    
    @staticmethod
    def validate_partition_key(partition_key: str, document_type: str) -> bool:
        """Validate that a partition key is valid for the given document type"""
        
        if not partition_key or not isinstance(partition_key, str):
            return False
        
        if document_type == "user":
            # User partition keys should be valid UUIDs or user IDs
            return len(partition_key.strip()) > 0
        
        elif document_type == "puzzle":
            # Puzzle partition keys should be valid universes
            valid_universes = {"marvel", "dc", "image"}
            return partition_key.lower() in valid_universes
        
        elif document_type == "guess":
            # Guess partition keys should be valid user IDs
            return len(partition_key.strip()) > 0
        
        return False
    
    @staticmethod
    def get_cross_partition_query_options() -> Dict[str, Any]:
        """Get options for cross-partition queries"""
        return {
            "enable_cross_partition_query": True,
            "max_item_count": 100  # Limit results for performance
        }
    
    @staticmethod
    def get_single_partition_query_options(partition_key: str) -> Dict[str, Any]:
        """Get options for single-partition queries"""
        return {
            "partition_key": partition_key,
            "max_item_count": 1000  # Higher limit for single partition
        }


class DocumentRouter:
    """Routes documents to appropriate containers and partition keys"""
    
    def __init__(self):
        self.partition_manager = PartitionKeyManager()
    
    def route_user_document(self, user: User) -> Dict[str, Any]:
        """Route user document to appropriate container and partition"""
        return {
            "container_name": "users",
            "partition_key": self.partition_manager.get_user_partition_key(user.id),
            "document": user.model_dump()
        }
    
    def route_puzzle_document(self, puzzle: Puzzle) -> Dict[str, Any]:
        """Route puzzle document to appropriate container and partition"""
        return {
            "container_name": "puzzles",
            "partition_key": self.partition_manager.get_puzzle_partition_key(puzzle.universe),
            "document": puzzle.model_dump()
        }
    
    def route_guess_document(self, guess: Guess) -> Dict[str, Any]:
        """Route guess document to appropriate container and partition"""
        return {
            "container_name": "guesses",
            "partition_key": self.partition_manager.get_guess_partition_key(guess.user_id),
            "document": guess.model_dump()
        }
    
    def get_user_query_info(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get query information for user documents"""
        if user_id:
            return {
                "container_name": "users",
                "query_options": self.partition_manager.get_single_partition_query_options(user_id)
            }
        else:
            return {
                "container_name": "users",
                "query_options": self.partition_manager.get_cross_partition_query_options()
            }
    
    def get_puzzle_query_info(self, universe: Optional[str] = None) -> Dict[str, Any]:
        """Get query information for puzzle documents"""
        if universe:
            partition_key = self.partition_manager.get_puzzle_partition_key(universe)
            return {
                "container_name": "puzzles",
                "query_options": self.partition_manager.get_single_partition_query_options(partition_key)
            }
        else:
            return {
                "container_name": "puzzles",
                "query_options": self.partition_manager.get_cross_partition_query_options()
            }
    
    def get_guess_query_info(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get query information for guess documents"""
        if user_id:
            partition_key = self.partition_manager.get_guess_partition_key(user_id)
            return {
                "container_name": "guesses",
                "query_options": self.partition_manager.get_single_partition_query_options(partition_key)
            }
        else:
            return {
                "container_name": "guesses",
                "query_options": self.partition_manager.get_cross_partition_query_options()
            }


# Utility functions for common partition operations
def get_daily_puzzle_partition_key(universe: str) -> str:
    """Get partition key for daily puzzle queries"""
    return PartitionKeyManager.get_puzzle_partition_key(universe)


def get_user_guesses_partition_key(user_id: str) -> str:
    """Get partition key for user's guess queries"""
    return PartitionKeyManager.get_guess_partition_key(user_id)


def validate_universe_partition_key(universe: str) -> bool:
    """Validate that a universe is a valid partition key"""
    return PartitionKeyManager.validate_partition_key(universe, "puzzle")


def create_puzzle_id_from_date_and_universe(date: datetime, universe: str) -> str:
    """Create a puzzle ID from date and universe"""
    if not validate_universe_partition_key(universe):
        raise ValueError(f"Invalid universe for partition key: {universe}")
    
    date_str = date.strftime("%Y%m%d")
    return f"{date_str}-{universe.lower()}"


# Global document router instance
document_router = DocumentRouter()