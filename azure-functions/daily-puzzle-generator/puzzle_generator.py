"""
Puzzle Generator Service for Azure Function
Handles daily puzzle generation logic and character selection
"""

import logging
import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import os
import asyncio

# Import backend modules (these need to be available in the function environment)
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from app.models.puzzle import PuzzleCreate
from app.repositories.puzzle_repository import PuzzleRepository
from app.services.puzzle_service import PuzzleService
from app.database.connection import get_cosmos_db
from app.config import Settings

# Import validation and error handling
from puzzle_validation import PuzzleValidator, PuzzleErrorHandler, PuzzleMonitor, ValidationSeverity
from logging_config import get_logger

logger = get_logger()

class PuzzleGeneratorService:
    """Service for generating daily puzzles with character rotation logic"""
    
    def __init__(self):
        # Initialize settings from environment variables
        self.settings = Settings()
        self.puzzle_service = PuzzleService()
        self.universes = ["marvel", "dc", "image"]
        
        # Initialize validation and error handling
        self.validator = PuzzleValidator()
        self.error_handler = PuzzleErrorHandler()
        self.monitor = PuzzleMonitor()
        
        # Character pools for each universe (this would typically come from a database or config)
        self.character_pools = self._load_character_pools()
        
        # Validate character pools on initialization
        self._validate_character_pools()
    
    def _load_character_pools(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load character pools for each universe
        In production, this would load from a database or configuration service
        """
        # Default character pools - in production these should be loaded from external source
        return {
            "marvel": [
                {
                    "character": "Spider-Man",
                    "aliases": ["Spidey", "Peter Parker", "Web-Slinger"],
                    "image_key": "marvel/spider-man.jpg"
                },
                {
                    "character": "Iron Man", 
                    "aliases": ["Tony Stark", "Shellhead"],
                    "image_key": "marvel/iron-man.jpg"
                },
                {
                    "character": "Captain America",
                    "aliases": ["Steve Rogers", "Cap", "First Avenger"],
                    "image_key": "marvel/captain-america.jpg"
                },
                {
                    "character": "Thor",
                    "aliases": ["God of Thunder", "Odinson"],
                    "image_key": "marvel/thor.jpg"
                },
                {
                    "character": "Hulk",
                    "aliases": ["Bruce Banner", "Green Goliath"],
                    "image_key": "marvel/hulk.jpg"
                }
            ],
            "dc": [
                {
                    "character": "Batman",
                    "aliases": ["Bruce Wayne", "Dark Knight", "Caped Crusader"],
                    "image_key": "dc/batman.jpg"
                },
                {
                    "character": "Superman",
                    "aliases": ["Clark Kent", "Man of Steel", "Kal-El"],
                    "image_key": "dc/superman.jpg"
                },
                {
                    "character": "Wonder Woman",
                    "aliases": ["Diana Prince", "Amazon Princess"],
                    "image_key": "dc/wonder-woman.jpg"
                },
                {
                    "character": "The Flash",
                    "aliases": ["Barry Allen", "Scarlet Speedster"],
                    "image_key": "dc/flash.jpg"
                },
                {
                    "character": "Green Lantern",
                    "aliases": ["Hal Jordan", "Emerald Knight"],
                    "image_key": "dc/green-lantern.jpg"
                }
            ],
            "image": [
                {
                    "character": "Spawn",
                    "aliases": ["Al Simmons", "Hellspawn"],
                    "image_key": "image/spawn.jpg"
                },
                {
                    "character": "Invincible",
                    "aliases": ["Mark Grayson"],
                    "image_key": "image/invincible.jpg"
                },
                {
                    "character": "The Walking Dead Rick",
                    "aliases": ["Rick Grimes"],
                    "image_key": "image/rick-grimes.jpg"
                },
                {
                    "character": "Savage Dragon",
                    "aliases": ["Dragon"],
                    "image_key": "image/savage-dragon.jpg"
                },
                {
                    "character": "Witchblade",
                    "aliases": ["Sara Pezzini"],
                    "image_key": "image/witchblade.jpg"
                }
            ]
        }
    
    def _validate_character_pools(self) -> None:
        """Validate character pools during initialization"""
        logger.info("Validating character pools...")
        
        all_issues = []
        for universe, character_pool in self.character_pools.items():
            issues = self.validator.validate_character_pool(character_pool, universe)
            all_issues.extend(issues)
            
            if issues:
                logger.warning(f"Validation issues found for {universe} universe: {len(issues)} issues")
        
        # Log summary
        validation_summary = self.validator.get_validation_summary(all_issues)
        
        if validation_summary["has_critical"]:
            logger.critical(f"Critical validation errors in character pools: {validation_summary}")
            raise ValueError("Critical validation errors prevent service initialization")
        elif validation_summary["has_errors"]:
            logger.error(f"Validation errors in character pools: {validation_summary}")
        elif validation_summary["total_issues"] > 0:
            logger.warning(f"Validation warnings in character pools: {validation_summary['by_severity']['warning']} warnings")
        else:
            logger.info("Character pools validation passed successfully")
    
    async def generate_daily_puzzles_for_date(self, date: str) -> Dict[str, Any]:
        """
        Generate daily puzzles for all universes for a specific date
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            Dictionary with generation results
        """
        logger.info(f"Starting puzzle generation for date: {date}")
        
        results = {
            "date": date,
            "puzzles_created": 0,
            "universes_processed": [],
            "errors": [],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        for universe in self.universes:
            try:
                puzzle_result = await self.generate_puzzle_for_universe(universe, date)
                
                if puzzle_result["success"]:
                    results["puzzles_created"] += 1
                    results["universes_processed"].append(universe)
                    logger.info(f"Successfully generated puzzle for {universe}: {puzzle_result['puzzle_id']}")
                else:
                    results["errors"].append({
                        "universe": universe,
                        "error": puzzle_result["error"]
                    })
                    logger.error(f"Failed to generate puzzle for {universe}: {puzzle_result['error']}")
                    
            except Exception as e:
                error_msg = f"Exception generating puzzle for {universe}: {str(e)}"
                results["errors"].append({
                    "universe": universe,
                    "error": error_msg
                })
                logger.error(error_msg)
        
        logger.info(f"Puzzle generation completed. Created {results['puzzles_created']} puzzles")
        return results
    
    async def generate_puzzle_for_universe(self, universe: str, date: str) -> Dict[str, Any]:
        """
        Generate a puzzle for a specific universe and date with comprehensive validation
        
        Args:
            universe: Universe name (marvel, dc, image)
            date: Date in YYYY-MM-DD format
            
        Returns:
            Dictionary with generation result
        """
        generation_start = datetime.utcnow()
        
        try:
            # Validate input parameters
            validation_issues = []
            validation_issues.extend(self.validator.validate_universe(universe))
            validation_issues.extend(self.validator.validate_date_format(date))
            
            if validation_issues:
                validation_summary = self.validator.get_validation_summary(validation_issues)
                error_result = await self.error_handler.handle_validation_errors(validation_summary)
                
                self.monitor.record_generation_attempt(universe, date, False, {
                    "error_type": "validation_error",
                    "validation_summary": validation_summary
                })
                
                return error_result
            
            # Check if puzzle already exists
            try:
                existing_puzzle = await self.puzzle_service.get_daily_puzzle(universe, date)
                if existing_puzzle:
                    self.monitor.record_generation_attempt(universe, date, True, {
                        "already_existed": True
                    })
                    
                    return {
                        "success": True,
                        "puzzle_id": existing_puzzle.id,
                        "message": "Puzzle already exists",
                        "character": existing_puzzle.character,
                        "universe": existing_puzzle.universe,
                        "active_date": existing_puzzle.active_date
                    }
            except Exception as db_error:
                # Handle database error for checking existing puzzle
                error_result = await self.error_handler.handle_database_error(
                    "check_existing_puzzle", db_error
                )
                
                if not error_result.get("retryable", False):
                    self.monitor.record_generation_attempt(universe, date, False, {
                        "error_type": "database_error",
                        "operation": "check_existing_puzzle"
                    })
                    return error_result
                
                # Continue with generation if error is not critical
                logger.warning(f"Non-critical database error checking existing puzzle: {str(db_error)}")
            
            # Select character for this date and universe
            try:
                character_data = await self.select_character_for_date(universe, date)
            except Exception as char_error:
                # Handle character selection error with fallback
                fallback_result = await self.error_handler.handle_character_selection_error(
                    universe, date, char_error
                )
                
                if not fallback_result["success"]:
                    self.monitor.record_generation_attempt(universe, date, False, {
                        "error_type": "character_selection_error",
                        "original_error": str(char_error)
                    })
                    return fallback_result
                
                character_data = fallback_result["character_data"]
                logger.warning(f"Using fallback character for {universe}: {character_data['character']}")
            
            # Validate selected character data
            char_validation_issues = self.validator.validate_character_data(character_data, universe)
            if char_validation_issues:
                char_validation_summary = self.validator.get_validation_summary(char_validation_issues)
                
                if char_validation_summary["has_errors"]:
                    self.monitor.record_generation_attempt(universe, date, False, {
                        "error_type": "character_validation_error",
                        "validation_summary": char_validation_summary
                    })
                    
                    return {
                        "success": False,
                        "error": "Selected character data failed validation",
                        "validation_summary": char_validation_summary
                    }
            
            # Create the puzzle
            try:
                puzzle = await self.puzzle_service.create_daily_puzzle(
                    universe=universe,
                    character=character_data["character"],
                    character_aliases=character_data["aliases"],
                    image_key=character_data["image_key"],
                    active_date=date
                )
                
                # Record successful generation
                generation_time = (datetime.utcnow() - generation_start).total_seconds()
                self.monitor.record_generation_attempt(universe, date, True, {
                    "generation_time_seconds": generation_time,
                    "character": puzzle.character,
                    "fallback_used": "fallback_used" in locals()
                })
                
                logger.log_puzzle_generation(
                    universe, date, True, generation_time,
                    puzzle_id=puzzle.id, character=puzzle.character
                )
                
                return {
                    "success": True,
                    "puzzle_id": puzzle.id,
                    "character": puzzle.character,
                    "universe": puzzle.universe,
                    "active_date": puzzle.active_date,
                    "generation_time_seconds": generation_time
                }
                
            except Exception as create_error:
                # Handle puzzle creation error
                error_result = await self.error_handler.handle_database_error(
                    "create_puzzle", create_error
                )
                
                self.monitor.record_generation_attempt(universe, date, False, {
                    "error_type": "puzzle_creation_error",
                    "original_error": str(create_error)
                })
                
                return error_result
            
        except Exception as e:
            # Handle unexpected errors
            logger.error(f"Unexpected error generating puzzle for {universe} on {date}: {str(e)}")
            
            self.monitor.record_generation_attempt(universe, date, False, {
                "error_type": "unexpected_error",
                "original_error": str(e)
            })
            
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "error_type": "unexpected_error"
            }
    
    async def select_character_for_date(self, universe: str, date: str) -> Dict[str, Any]:
        """
        Select a character for a specific universe and date using deterministic rotation
        
        Args:
            universe: Universe name
            date: Date in YYYY-MM-DD format
            
        Returns:
            Character data dictionary
        """
        # Get character pool for universe
        character_pool = self.character_pools.get(universe, [])
        
        if not character_pool:
            raise ValueError(f"No characters available for universe: {universe}")
        
        # Use date as seed for deterministic selection
        # This ensures the same character is selected for the same date across function runs
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        
        # Create a deterministic seed based on date and universe
        seed_string = f"{date}-{universe}"
        seed_value = hash(seed_string) % (2**32)  # Ensure positive 32-bit integer
        
        # Use seeded random to select character
        random.seed(seed_value)
        selected_character = random.choice(character_pool)
        
        logger.info(f"Selected character '{selected_character['character']}' for {universe} on {date}")
        
        return selected_character
    
    async def validate_puzzle_generation(self, date: str) -> Dict[str, Any]:
        """
        Validate that puzzles exist for all universes on a given date
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            Validation results
        """
        validation_results = {
            "date": date,
            "all_puzzles_exist": True,
            "missing_puzzles": [],
            "existing_puzzles": [],
            "validation_timestamp": datetime.utcnow().isoformat()
        }
        
        for universe in self.universes:
            try:
                puzzle = await self.puzzle_service.get_daily_puzzle(universe, date)
                
                if puzzle:
                    validation_results["existing_puzzles"].append({
                        "universe": universe,
                        "puzzle_id": puzzle.id,
                        "character": puzzle.character
                    })
                else:
                    validation_results["missing_puzzles"].append(universe)
                    validation_results["all_puzzles_exist"] = False
                    
            except Exception as e:
                logger.error(f"Error validating puzzle for {universe} on {date}: {str(e)}")
                validation_results["missing_puzzles"].append(universe)
                validation_results["all_puzzles_exist"] = False
        
        return validation_results
    
    async def perform_health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check on the puzzle generation system
        
        Returns:
            Health check results with monitoring data
        """
        health_check_start = datetime.utcnow()
        
        health_status = {
            "healthy": True,
            "checks": {},
            "monitoring": {},
            "timestamp": health_check_start.isoformat()
        }
        
        # Get monitoring status
        monitor_status = self.monitor.get_health_status()
        health_status["monitoring"] = monitor_status
        
        # Overall health is affected by monitoring status
        if monitor_status["health"] in ["critical", "degraded"]:
            health_status["healthy"] = False
        
        # Check database connectivity with retry logic
        database_healthy = False
        database_attempts = 0
        max_db_attempts = 3
        
        while not database_healthy and database_attempts < max_db_attempts:
            database_attempts += 1
            try:
                # Test database connection by getting stats for one universe
                stats = await self.puzzle_service.get_universe_statistics("marvel")
                health_status["checks"]["database"] = {
                    "status": "healthy",
                    "message": "Database connection successful",
                    "attempts": database_attempts,
                    "stats_sample": stats
                }
                database_healthy = True
                
            except Exception as e:
                if database_attempts >= max_db_attempts:
                    health_status["healthy"] = False
                    health_status["checks"]["database"] = {
                        "status": "unhealthy",
                        "error": str(e),
                        "attempts": database_attempts,
                        "max_attempts": max_db_attempts
                    }
                else:
                    # Wait before retry
                    await asyncio.sleep(1.0)
        
        # Check character pools with validation
        try:
            total_characters = sum(len(pool) for pool in self.character_pools.values())
            if total_characters == 0:
                raise ValueError("No characters available in any universe")
            
            # Validate character pools
            all_validation_issues = []
            pool_validation = {}
            
            for universe, pool in self.character_pools.items():
                issues = self.validator.validate_character_pool(pool, universe)
                all_validation_issues.extend(issues)
                
                validation_summary = self.validator.get_validation_summary(issues)
                pool_validation[universe] = {
                    "character_count": len(pool),
                    "validation_issues": validation_summary["total_issues"],
                    "has_errors": validation_summary["has_errors"]
                }
            
            overall_validation = self.validator.get_validation_summary(all_validation_issues)
            
            health_status["checks"]["character_pools"] = {
                "status": "unhealthy" if overall_validation["has_critical"] else 
                         "warning" if overall_validation["has_errors"] else "healthy",
                "total_characters": total_characters,
                "universes": pool_validation,
                "validation_summary": overall_validation
            }
            
            if overall_validation["has_critical"]:
                health_status["healthy"] = False
                
        except Exception as e:
            health_status["healthy"] = False
            health_status["checks"]["character_pools"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Check today's puzzles with detailed validation
        try:
            today = datetime.utcnow().strftime('%Y-%m-%d')
            validation = await self.validate_puzzle_generation(today)
            
            puzzle_status = "healthy"
            if not validation["all_puzzles_exist"]:
                missing_count = len(validation["missing_puzzles"])
                if missing_count == len(self.universes):
                    puzzle_status = "critical"
                    health_status["healthy"] = False
                elif missing_count > 0:
                    puzzle_status = "warning"
            
            health_status["checks"]["todays_puzzles"] = {
                "status": puzzle_status,
                "date": today,
                "all_exist": validation["all_puzzles_exist"],
                "missing": validation["missing_puzzles"],
                "existing": validation["existing_puzzles"],
                "missing_count": len(validation["missing_puzzles"]),
                "existing_count": len(validation["existing_puzzles"])
            }
                
        except Exception as e:
            health_status["healthy"] = False
            health_status["checks"]["todays_puzzles"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Check system resources and performance
        try:
            health_check_duration = (datetime.utcnow() - health_check_start).total_seconds()
            
            health_status["checks"]["system_performance"] = {
                "status": "healthy" if health_check_duration < 10.0 else "warning",
                "health_check_duration_seconds": health_check_duration,
                "message": "Health check completed within acceptable time" if health_check_duration < 10.0 
                          else "Health check took longer than expected"
            }
            
        except Exception as e:
            health_status["checks"]["system_performance"] = {
                "status": "warning",
                "error": str(e)
            }
        
        # Check if alerts should be sent
        should_alert, alert_reason = self.monitor.should_alert()
        if should_alert:
            health_status["alert_required"] = {
                "should_alert": True,
                "reason": alert_reason,
                "monitoring_data": monitor_status
            }
        
        # Add recommendations based on health status
        recommendations = []
        if not health_status["healthy"]:
            if health_status["checks"].get("database", {}).get("status") == "unhealthy":
                recommendations.append("Check database connectivity and credentials")
            if health_status["checks"].get("character_pools", {}).get("status") == "unhealthy":
                recommendations.append("Review character pool configuration and validation")
            if health_status["checks"].get("todays_puzzles", {}).get("status") in ["critical", "unhealthy"]:
                recommendations.append("Generate missing daily puzzles immediately")
        
        health_status["recommendations"] = recommendations
        
        return health_status
    
    async def validate_data_integrity(self) -> Dict[str, Any]:
        """
        Perform comprehensive data integrity validation
        
        Returns:
            Detailed validation report
        """
        logger.info("Starting comprehensive data integrity validation...")
        
        validation_report = {
            "validation_timestamp": datetime.utcnow().isoformat(),
            "overall_status": "healthy",
            "character_pools": {},
            "recent_puzzles": {},
            "database_integrity": {},
            "recommendations": [],
            "critical_issues": [],
            "warnings": []
        }
        
        # Validate character pools
        try:
            for universe in self.universes:
                pool = self.character_pools.get(universe, [])
                issues = self.validator.validate_character_pool(pool, universe)
                validation_summary = self.validator.get_validation_summary(issues)
                
                validation_report["character_pools"][universe] = {
                    "character_count": len(pool),
                    "validation_summary": validation_summary,
                    "status": "critical" if validation_summary["has_critical"] else
                             "error" if validation_summary["has_errors"] else
                             "warning" if validation_summary["total_issues"] > 0 else "healthy"
                }
                
                # Collect critical issues and warnings
                for issue in issues:
                    if issue.severity.value in ["critical", "error"]:
                        validation_report["critical_issues"].append({
                            "universe": universe,
                            "severity": issue.severity.value,
                            "message": issue.message,
                            "context": issue.context
                        })
                    elif issue.severity.value == "warning":
                        validation_report["warnings"].append({
                            "universe": universe,
                            "message": issue.message,
                            "context": issue.context
                        })
        
        except Exception as e:
            validation_report["character_pools"]["error"] = str(e)
            validation_report["critical_issues"].append({
                "component": "character_pools",
                "severity": "critical",
                "message": f"Failed to validate character pools: {str(e)}"
            })
        
        # Validate recent puzzles (last 7 days)
        try:
            end_date = datetime.utcnow().strftime('%Y-%m-%d')
            start_date = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
            
            for universe in self.universes:
                try:
                    recent_puzzles = await self.puzzle_service.puzzle_repository.get_puzzles_by_date_range(
                        universe, start_date, end_date
                    )
                    
                    puzzle_issues = []
                    for puzzle in recent_puzzles:
                        # Validate puzzle data
                        puzzle_dict = puzzle.model_dump()
                        char_data = {
                            "character": puzzle_dict["character"],
                            "aliases": puzzle_dict["character_aliases"],
                            "image_key": puzzle_dict["image_key"]
                        }
                        
                        issues = self.validator.validate_character_data(char_data, universe)
                        puzzle_issues.extend(issues)
                    
                    puzzle_validation_summary = self.validator.get_validation_summary(puzzle_issues)
                    
                    validation_report["recent_puzzles"][universe] = {
                        "puzzle_count": len(recent_puzzles),
                        "date_range": f"{start_date} to {end_date}",
                        "validation_summary": puzzle_validation_summary,
                        "status": "error" if puzzle_validation_summary["has_errors"] else
                                 "warning" if puzzle_validation_summary["total_issues"] > 0 else "healthy"
                    }
                    
                except Exception as universe_error:
                    validation_report["recent_puzzles"][universe] = {
                        "status": "error",
                        "error": str(universe_error)
                    }
                    validation_report["critical_issues"].append({
                        "universe": universe,
                        "component": "recent_puzzles",
                        "severity": "error",
                        "message": f"Failed to validate recent puzzles: {str(universe_error)}"
                    })
        
        except Exception as e:
            validation_report["recent_puzzles"]["error"] = str(e)
            validation_report["critical_issues"].append({
                "component": "recent_puzzles",
                "severity": "critical",
                "message": f"Failed to validate recent puzzles: {str(e)}"
            })
        
        # Check database integrity
        try:
            db_stats = {}
            for universe in self.universes:
                try:
                    stats = await self.puzzle_service.get_universe_statistics(universe)
                    db_stats[universe] = stats
                except Exception as stats_error:
                    db_stats[universe] = {"error": str(stats_error)}
                    validation_report["critical_issues"].append({
                        "universe": universe,
                        "component": "database_stats",
                        "severity": "error",
                        "message": f"Failed to get database statistics: {str(stats_error)}"
                    })
            
            validation_report["database_integrity"] = {
                "status": "healthy" if all("error" not in stats for stats in db_stats.values()) else "error",
                "universe_stats": db_stats
            }
            
        except Exception as e:
            validation_report["database_integrity"] = {
                "status": "critical",
                "error": str(e)
            }
            validation_report["critical_issues"].append({
                "component": "database_integrity",
                "severity": "critical",
                "message": f"Failed to check database integrity: {str(e)}"
            })
        
        # Determine overall status
        if validation_report["critical_issues"]:
            critical_count = sum(1 for issue in validation_report["critical_issues"] 
                               if issue.get("severity") == "critical")
            error_count = sum(1 for issue in validation_report["critical_issues"] 
                            if issue.get("severity") == "error")
            
            if critical_count > 0:
                validation_report["overall_status"] = "critical"
            elif error_count > 0:
                validation_report["overall_status"] = "error"
            else:
                validation_report["overall_status"] = "warning"
        elif validation_report["warnings"]:
            validation_report["overall_status"] = "warning"
        
        # Generate recommendations
        if validation_report["overall_status"] != "healthy":
            if any("character_pools" in str(issue) for issue in validation_report["critical_issues"]):
                validation_report["recommendations"].append(
                    "Review and fix character pool configuration issues"
                )
            if any("database" in str(issue) for issue in validation_report["critical_issues"]):
                validation_report["recommendations"].append(
                    "Check database connectivity and data integrity"
                )
            if validation_report["warnings"]:
                validation_report["recommendations"].append(
                    "Address validation warnings to improve data quality"
                )
        
        logger.info(f"Data integrity validation completed. Status: {validation_report['overall_status']}")
        
        return validation_report
    
    async def generate_future_puzzles(self, days_ahead: int = 7) -> Dict[str, Any]:
        """
        Generate puzzles for future dates
        
        Args:
            days_ahead: Number of days ahead to generate puzzles for
            
        Returns:
            Generation results
        """
        results = {
            "days_ahead": days_ahead,
            "total_puzzles_created": 0,
            "dates_processed": [],
            "errors": [],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        for day_offset in range(1, days_ahead + 1):
            target_date = (datetime.utcnow() + timedelta(days=day_offset)).strftime('%Y-%m-%d')
            
            try:
                date_result = await self.generate_daily_puzzles_for_date(target_date)
                results["total_puzzles_created"] += date_result["puzzles_created"]
                results["dates_processed"].append({
                    "date": target_date,
                    "puzzles_created": date_result["puzzles_created"],
                    "universes_processed": date_result["universes_processed"]
                })
                
                if date_result["errors"]:
                    results["errors"].extend(date_result["errors"])
                    
            except Exception as e:
                error_msg = f"Error generating puzzles for {target_date}: {str(e)}"
                results["errors"].append({
                    "date": target_date,
                    "error": error_msg
                })
                logger.error(error_msg)
        
        return results
    
    async def cleanup_old_puzzles(self, days_to_keep: int = 365) -> Dict[str, Any]:
        """
        Clean up old puzzles beyond retention period
        
        Args:
            days_to_keep: Number of days of puzzles to keep
            
        Returns:
            Cleanup results
        """
        try:
            deleted_count = await self.puzzle_service.cleanup_old_puzzles(days_to_keep)
            
            return {
                "success": True,
                "deleted_count": deleted_count,
                "days_to_keep": days_to_keep,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error during puzzle cleanup: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }