"""
Puzzle validation and error handling utilities
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import re

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation issues"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationIssue:
    """Represents a validation issue"""
    
    def __init__(self, severity: ValidationSeverity, message: str, 
                 context: Optional[Dict[str, Any]] = None):
        self.severity = severity
        self.message = message
        self.context = context or {}
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity.value,
            "message": self.message,
            "context": self.context,
            "timestamp": self.timestamp.isoformat()
        }


class PuzzleValidator:
    """Validates puzzle data integrity and business rules"""
    
    def __init__(self):
        self.universes = ["marvel", "dc", "image"]
        self.required_character_fields = ["character", "aliases", "image_key"]
        self.image_extensions = [".jpg", ".jpeg", ".png", ".webp"]
    
    def validate_character_data(self, character_data: Dict[str, Any], 
                              universe: str) -> List[ValidationIssue]:
        """Validate character data structure and content"""
        issues = []
        
        # Check required fields
        for field in self.required_character_fields:
            if field not in character_data:
                issues.append(ValidationIssue(
                    ValidationSeverity.ERROR,
                    f"Missing required field: {field}",
                    {"universe": universe, "character_data": character_data}
                ))
        
        if not issues:  # Only continue if basic structure is valid
            # Validate character name
            character_name = character_data.get("character", "")
            if not character_name or not character_name.strip():
                issues.append(ValidationIssue(
                    ValidationSeverity.ERROR,
                    "Character name cannot be empty",
                    {"universe": universe}
                ))
            elif len(character_name.strip()) > 100:
                issues.append(ValidationIssue(
                    ValidationSeverity.WARNING,
                    f"Character name is very long ({len(character_name)} chars)",
                    {"universe": universe, "character": character_name}
                ))
            
            # Validate aliases
            aliases = character_data.get("aliases", [])
            if not isinstance(aliases, list):
                issues.append(ValidationIssue(
                    ValidationSeverity.ERROR,
                    "Aliases must be a list",
                    {"universe": universe, "aliases_type": type(aliases).__name__}
                ))
            else:
                for i, alias in enumerate(aliases):
                    if not isinstance(alias, str) or not alias.strip():
                        issues.append(ValidationIssue(
                            ValidationSeverity.WARNING,
                            f"Invalid alias at index {i}: '{alias}'",
                            {"universe": universe, "character": character_name}
                        ))
            
            # Validate image key
            image_key = character_data.get("image_key", "")
            image_issues = self.validate_image_key(image_key, universe)
            issues.extend(image_issues)
        
        return issues
    
    def validate_image_key(self, image_key: str, universe: str) -> List[ValidationIssue]:
        """Validate image key format and structure"""
        issues = []
        
        if not image_key:
            issues.append(ValidationIssue(
                ValidationSeverity.ERROR,
                "Image key cannot be empty",
                {"universe": universe}
            ))
            return issues
        
        # Check universe prefix
        expected_prefix = f"{universe}/"
        if not image_key.startswith(expected_prefix):
            issues.append(ValidationIssue(
                ValidationSeverity.ERROR,
                f"Image key must start with '{expected_prefix}'",
                {"universe": universe, "image_key": image_key}
            ))
        
        # Check file extension
        has_valid_extension = any(image_key.lower().endswith(ext) 
                                for ext in self.image_extensions)
        if not has_valid_extension:
            issues.append(ValidationIssue(
                ValidationSeverity.WARNING,
                f"Image key should have valid extension: {self.image_extensions}",
                {"universe": universe, "image_key": image_key}
            ))
        
        # Check for invalid characters
        if re.search(r'[<>:"|?*]', image_key):
            issues.append(ValidationIssue(
                ValidationSeverity.ERROR,
                "Image key contains invalid characters",
                {"universe": universe, "image_key": image_key}
            ))
        
        return issues
    
    def validate_date_format(self, date_str: str) -> List[ValidationIssue]:
        """Validate date format and reasonableness"""
        issues = []
        
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            
            # Check if date is too far in the past or future
            today = datetime.utcnow()
            days_diff = (date_obj - today).days
            
            if days_diff < -365:  # More than a year in the past
                issues.append(ValidationIssue(
                    ValidationSeverity.WARNING,
                    f"Date is {abs(days_diff)} days in the past",
                    {"date": date_str, "days_diff": days_diff}
                ))
            elif days_diff > 365:  # More than a year in the future
                issues.append(ValidationIssue(
                    ValidationSeverity.WARNING,
                    f"Date is {days_diff} days in the future",
                    {"date": date_str, "days_diff": days_diff}
                ))
            
        except ValueError as e:
            issues.append(ValidationIssue(
                ValidationSeverity.ERROR,
                f"Invalid date format: {str(e)}",
                {"date": date_str}
            ))
        
        return issues
    
    def validate_universe(self, universe: str) -> List[ValidationIssue]:
        """Validate universe name"""
        issues = []
        
        if not universe:
            issues.append(ValidationIssue(
                ValidationSeverity.ERROR,
                "Universe cannot be empty",
                {}
            ))
        elif universe not in self.universes:
            issues.append(ValidationIssue(
                ValidationSeverity.ERROR,
                f"Invalid universe '{universe}'. Must be one of: {self.universes}",
                {"universe": universe}
            ))
        
        return issues
    
    def validate_character_pool(self, character_pool: List[Dict[str, Any]], 
                              universe: str) -> List[ValidationIssue]:
        """Validate entire character pool for a universe"""
        issues = []
        
        if not character_pool:
            issues.append(ValidationIssue(
                ValidationSeverity.CRITICAL,
                f"No characters available for {universe} universe",
                {"universe": universe}
            ))
            return issues
        
        character_names = set()
        image_keys = set()
        
        for i, character_data in enumerate(character_pool):
            # Validate individual character
            char_issues = self.validate_character_data(character_data, universe)
            issues.extend(char_issues)
            
            # Check for duplicates
            character_name = character_data.get("character", "").lower().strip()
            if character_name in character_names:
                issues.append(ValidationIssue(
                    ValidationSeverity.ERROR,
                    f"Duplicate character name: '{character_name}'",
                    {"universe": universe, "index": i}
                ))
            else:
                character_names.add(character_name)
            
            image_key = character_data.get("image_key", "")
            if image_key in image_keys:
                issues.append(ValidationIssue(
                    ValidationSeverity.WARNING,
                    f"Duplicate image key: '{image_key}'",
                    {"universe": universe, "index": i}
                ))
            else:
                image_keys.add(image_key)
        
        # Check pool size
        if len(character_pool) < 5:
            issues.append(ValidationIssue(
                ValidationSeverity.WARNING,
                f"Small character pool for {universe}: only {len(character_pool)} characters",
                {"universe": universe, "pool_size": len(character_pool)}
            ))
        
        return issues
    
    def validate_puzzle_generation_request(self, universe: str, date: str, 
                                         character_data: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate a complete puzzle generation request"""
        issues = []
        
        # Validate universe
        issues.extend(self.validate_universe(universe))
        
        # Validate date
        issues.extend(self.validate_date_format(date))
        
        # Validate character data
        issues.extend(self.validate_character_data(character_data, universe))
        
        return issues
    
    def get_validation_summary(self, issues: List[ValidationIssue]) -> Dict[str, Any]:
        """Get summary of validation issues"""
        summary = {
            "total_issues": len(issues),
            "by_severity": {severity.value: 0 for severity in ValidationSeverity},
            "has_errors": False,
            "has_critical": False,
            "issues": [issue.to_dict() for issue in issues]
        }
        
        for issue in issues:
            summary["by_severity"][issue.severity.value] += 1
            if issue.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]:
                summary["has_errors"] = True
            if issue.severity == ValidationSeverity.CRITICAL:
                summary["has_critical"] = True
        
        return summary


class PuzzleErrorHandler:
    """Handles errors during puzzle generation with recovery strategies"""
    
    def __init__(self):
        self.retry_attempts = 3
        self.retry_delay = 1.0  # seconds
        self.fallback_characters = {
            "marvel": {
                "character": "Spider-Man",
                "aliases": ["Spidey", "Peter Parker"],
                "image_key": "marvel/spider-man.jpg"
            },
            "dc": {
                "character": "Batman", 
                "aliases": ["Bruce Wayne", "Dark Knight"],
                "image_key": "dc/batman.jpg"
            },
            "image": {
                "character": "Spawn",
                "aliases": ["Al Simmons"],
                "image_key": "image/spawn.jpg"
            }
        }
    
    async def handle_character_selection_error(self, universe: str, date: str, 
                                             error: Exception) -> Dict[str, Any]:
        """Handle errors in character selection with fallback"""
        logger.error(f"Character selection failed for {universe} on {date}: {str(error)}")
        
        # Try fallback character
        if universe in self.fallback_characters:
            fallback_char = self.fallback_characters[universe]
            logger.warning(f"Using fallback character for {universe}: {fallback_char['character']}")
            
            return {
                "success": True,
                "character_data": fallback_char,
                "fallback_used": True,
                "original_error": str(error)
            }
        else:
            return {
                "success": False,
                "error": f"No fallback character available for {universe}",
                "original_error": str(error)
            }
    
    async def handle_database_error(self, operation: str, error: Exception) -> Dict[str, Any]:
        """Handle database operation errors"""
        logger.error(f"Database error during {operation}: {str(error)}")
        
        # Determine if error is retryable
        retryable_errors = [
            "timeout", "connection", "throttle", "rate limit", "busy"
        ]
        
        error_str = str(error).lower()
        is_retryable = any(keyword in error_str for keyword in retryable_errors)
        
        return {
            "success": False,
            "error": str(error),
            "operation": operation,
            "retryable": is_retryable,
            "suggested_action": "retry" if is_retryable else "investigate"
        }
    
    async def handle_validation_errors(self, validation_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Handle validation errors with appropriate responses"""
        if validation_summary["has_critical"]:
            return {
                "success": False,
                "error": "Critical validation errors prevent puzzle generation",
                "validation_summary": validation_summary,
                "action_required": "fix_configuration"
            }
        elif validation_summary["has_errors"]:
            return {
                "success": False,
                "error": "Validation errors prevent puzzle generation",
                "validation_summary": validation_summary,
                "action_required": "fix_data"
            }
        else:
            # Only warnings, can proceed with caution
            return {
                "success": True,
                "warnings": validation_summary["by_severity"]["warning"],
                "validation_summary": validation_summary,
                "action_required": "monitor"
            }
    
    def create_error_notification(self, error_type: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """Create standardized error notification"""
        return {
            "error_type": error_type,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details,
            "severity": self._determine_severity(error_type, details),
            "notification_sent": False  # Would be set to True after sending notification
        }
    
    def _determine_severity(self, error_type: str, details: Dict[str, Any]) -> str:
        """Determine error severity for notifications"""
        critical_errors = [
            "database_connection_failed",
            "all_universes_failed",
            "character_pool_empty"
        ]
        
        if error_type in critical_errors:
            return "critical"
        elif "failed" in error_type or "error" in error_type:
            return "error"
        else:
            return "warning"


class PuzzleMonitor:
    """Monitors puzzle generation health and performance"""
    
    def __init__(self):
        self.metrics = {
            "total_generations": 0,
            "successful_generations": 0,
            "failed_generations": 0,
            "validation_failures": 0,
            "database_errors": 0,
            "fallback_uses": 0
        }
        self.last_successful_generation = None
        self.consecutive_failures = 0
    
    def record_generation_attempt(self, universe: str, date: str, success: bool, 
                                details: Optional[Dict[str, Any]] = None):
        """Record a puzzle generation attempt"""
        self.metrics["total_generations"] += 1
        
        if success:
            self.metrics["successful_generations"] += 1
            self.last_successful_generation = datetime.utcnow()
            self.consecutive_failures = 0
        else:
            self.metrics["failed_generations"] += 1
            self.consecutive_failures += 1
            
            # Track specific failure types
            if details:
                if "validation" in details.get("error_type", ""):
                    self.metrics["validation_failures"] += 1
                elif "database" in details.get("error_type", ""):
                    self.metrics["database_errors"] += 1
                elif details.get("fallback_used", False):
                    self.metrics["fallback_uses"] += 1
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status"""
        total = self.metrics["total_generations"]
        success_rate = (self.metrics["successful_generations"] / total * 100) if total > 0 else 0
        
        # Determine health status
        if self.consecutive_failures >= 5:
            health = "critical"
        elif self.consecutive_failures >= 3:
            health = "degraded"
        elif success_rate < 90:
            health = "warning"
        else:
            health = "healthy"
        
        return {
            "health": health,
            "success_rate": round(success_rate, 2),
            "consecutive_failures": self.consecutive_failures,
            "last_successful_generation": self.last_successful_generation.isoformat() if self.last_successful_generation else None,
            "metrics": self.metrics.copy(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def should_alert(self) -> Tuple[bool, str]:
        """Determine if an alert should be sent"""
        if self.consecutive_failures >= 5:
            return True, "critical_failure_threshold"
        elif self.consecutive_failures >= 3:
            return True, "degraded_performance"
        elif self.last_successful_generation:
            hours_since_success = (datetime.utcnow() - self.last_successful_generation).total_seconds() / 3600
            if hours_since_success > 25:  # More than 25 hours without success
                return True, "extended_outage"
        
        return False, ""