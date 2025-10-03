"""
Tests for puzzle validation and error handling
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from puzzle_validation import (
    PuzzleValidator, PuzzleErrorHandler, PuzzleMonitor,
    ValidationSeverity, ValidationIssue
)


class TestPuzzleValidator:
    """Test cases for PuzzleValidator"""
    
    @pytest.fixture
    def validator(self):
        return PuzzleValidator()
    
    def test_validate_character_data_valid(self, validator):
        """Test validation of valid character data"""
        character_data = {
            "character": "Spider-Man",
            "aliases": ["Spidey", "Peter Parker"],
            "image_key": "marvel/spider-man.jpg"
        }
        
        issues = validator.validate_character_data(character_data, "marvel")
        assert len(issues) == 0
    
    def test_validate_character_data_missing_fields(self, validator):
        """Test validation with missing required fields"""
        character_data = {
            "character": "Spider-Man"
            # Missing aliases and image_key
        }
        
        issues = validator.validate_character_data(character_data, "marvel")
        assert len(issues) == 2  # Missing aliases and image_key
        assert all(issue.severity == ValidationSeverity.ERROR for issue in issues)
    
    def test_validate_character_data_empty_name(self, validator):
        """Test validation with empty character name"""
        character_data = {
            "character": "",
            "aliases": [],
            "image_key": "marvel/test.jpg"
        }
        
        issues = validator.validate_character_data(character_data, "marvel")
        error_issues = [issue for issue in issues if issue.severity == ValidationSeverity.ERROR]
        assert len(error_issues) >= 1
        assert any("empty" in issue.message.lower() for issue in error_issues)
    
    def test_validate_character_data_long_name(self, validator):
        """Test validation with very long character name"""
        character_data = {
            "character": "A" * 150,  # Very long name
            "aliases": [],
            "image_key": "marvel/test.jpg"
        }
        
        issues = validator.validate_character_data(character_data, "marvel")
        warning_issues = [issue for issue in issues if issue.severity == ValidationSeverity.WARNING]
        assert len(warning_issues) >= 1
        assert any("long" in issue.message.lower() for issue in warning_issues)
    
    def test_validate_image_key_valid(self, validator):
        """Test validation of valid image keys"""
        valid_keys = [
            "marvel/spider-man.jpg",
            "dc/batman.png",
            "image/spawn.jpeg"
        ]
        
        for key in valid_keys:
            universe = key.split('/')[0]
            issues = validator.validate_image_key(key, universe)
            assert len(issues) == 0
    
    def test_validate_image_key_wrong_prefix(self, validator):
        """Test validation with wrong universe prefix"""
        issues = validator.validate_image_key("dc/batman.jpg", "marvel")
        error_issues = [issue for issue in issues if issue.severity == ValidationSeverity.ERROR]
        assert len(error_issues) >= 1
        assert any("must start with" in issue.message.lower() for issue in error_issues)
    
    def test_validate_image_key_invalid_extension(self, validator):
        """Test validation with invalid file extension"""
        issues = validator.validate_image_key("marvel/spider-man.txt", "marvel")
        warning_issues = [issue for issue in issues if issue.severity == ValidationSeverity.WARNING]
        assert len(warning_issues) >= 1
        assert any("extension" in issue.message.lower() for issue in warning_issues)
    
    def test_validate_date_format_valid(self, validator):
        """Test validation of valid date formats"""
        # Use dates that are close to today to avoid past/future warnings
        today = datetime.utcnow()
        valid_dates = [
            today.strftime('%Y-%m-%d'),
            (today + timedelta(days=1)).strftime('%Y-%m-%d'),
            (today - timedelta(days=1)).strftime('%Y-%m-%d')
        ]
        
        for date in valid_dates:
            issues = validator.validate_date_format(date)
            # Should have no ERROR issues, warnings about past/future are acceptable
            error_issues = [issue for issue in issues if issue.severity == ValidationSeverity.ERROR]
            assert len(error_issues) == 0
    
    def test_validate_date_format_invalid(self, validator):
        """Test validation of invalid date formats"""
        invalid_dates = ["2024-13-01", "2024/01/15", "invalid-date", ""]
        
        for date in invalid_dates:
            issues = validator.validate_date_format(date)
            error_issues = [issue for issue in issues if issue.severity == ValidationSeverity.ERROR]
            assert len(error_issues) >= 1
    
    def test_validate_date_format_far_future(self, validator):
        """Test validation of dates far in the future"""
        far_future = (datetime.utcnow() + timedelta(days=400)).strftime('%Y-%m-%d')
        
        issues = validator.validate_date_format(far_future)
        warning_issues = [issue for issue in issues if issue.severity == ValidationSeverity.WARNING]
        assert len(warning_issues) >= 1
        assert any("future" in issue.message.lower() for issue in warning_issues)
    
    def test_validate_universe_valid(self, validator):
        """Test validation of valid universes"""
        for universe in ["marvel", "dc", "image"]:
            issues = validator.validate_universe(universe)
            assert len(issues) == 0
    
    def test_validate_universe_invalid(self, validator):
        """Test validation of invalid universes"""
        invalid_universes = ["invalid", "", "Marvel", "DC"]
        
        for universe in invalid_universes:
            issues = validator.validate_universe(universe)
            error_issues = [issue for issue in issues if issue.severity == ValidationSeverity.ERROR]
            assert len(error_issues) >= 1
    
    def test_validate_character_pool_empty(self, validator):
        """Test validation of empty character pool"""
        issues = validator.validate_character_pool([], "marvel")
        critical_issues = [issue for issue in issues if issue.severity == ValidationSeverity.CRITICAL]
        assert len(critical_issues) >= 1
        assert any("no characters" in issue.message.lower() for issue in critical_issues)
    
    def test_validate_character_pool_duplicates(self, validator):
        """Test validation of character pool with duplicates"""
        character_pool = [
            {
                "character": "Spider-Man",
                "aliases": ["Spidey"],
                "image_key": "marvel/spider-man.jpg"
            },
            {
                "character": "spider-man",  # Duplicate (case insensitive)
                "aliases": ["Peter Parker"],
                "image_key": "marvel/spider-man-2.jpg"
            }
        ]
        
        issues = validator.validate_character_pool(character_pool, "marvel")
        error_issues = [issue for issue in issues if issue.severity == ValidationSeverity.ERROR]
        assert any("duplicate" in issue.message.lower() for issue in error_issues)
    
    def test_get_validation_summary(self, validator):
        """Test validation summary generation"""
        issues = [
            ValidationIssue(ValidationSeverity.ERROR, "Test error"),
            ValidationIssue(ValidationSeverity.WARNING, "Test warning"),
            ValidationIssue(ValidationSeverity.CRITICAL, "Test critical")
        ]
        
        summary = validator.get_validation_summary(issues)
        
        assert summary["total_issues"] == 3
        assert summary["by_severity"]["error"] == 1
        assert summary["by_severity"]["warning"] == 1
        assert summary["by_severity"]["critical"] == 1
        assert summary["has_errors"] is True
        assert summary["has_critical"] is True


class TestPuzzleErrorHandler:
    """Test cases for PuzzleErrorHandler"""
    
    @pytest.fixture
    def error_handler(self):
        return PuzzleErrorHandler()
    
    @pytest.mark.asyncio
    async def test_handle_character_selection_error_with_fallback(self, error_handler):
        """Test character selection error handling with fallback"""
        result = await error_handler.handle_character_selection_error(
            "marvel", "2024-01-15", Exception("Test error")
        )
        
        assert result["success"] is True
        assert result["fallback_used"] is True
        assert "character_data" in result
        assert result["character_data"]["character"] == "Spider-Man"
    
    @pytest.mark.asyncio
    async def test_handle_character_selection_error_no_fallback(self, error_handler):
        """Test character selection error handling without fallback"""
        result = await error_handler.handle_character_selection_error(
            "invalid_universe", "2024-01-15", Exception("Test error")
        )
        
        assert result["success"] is False
        assert "No fallback character" in result["error"]
    
    @pytest.mark.asyncio
    async def test_handle_database_error_retryable(self, error_handler):
        """Test database error handling for retryable errors"""
        result = await error_handler.handle_database_error(
            "test_operation", Exception("Connection timeout")
        )
        
        assert result["success"] is False
        assert result["retryable"] is True
        assert result["suggested_action"] == "retry"
    
    @pytest.mark.asyncio
    async def test_handle_database_error_non_retryable(self, error_handler):
        """Test database error handling for non-retryable errors"""
        result = await error_handler.handle_database_error(
            "test_operation", Exception("Invalid credentials")
        )
        
        assert result["success"] is False
        assert result["retryable"] is False
        assert result["suggested_action"] == "investigate"
    
    @pytest.mark.asyncio
    async def test_handle_validation_errors_critical(self, error_handler):
        """Test validation error handling for critical errors"""
        validation_summary = {
            "has_critical": True,
            "has_errors": False,
            "by_severity": {"critical": 1, "error": 0, "warning": 0}
        }
        
        result = await error_handler.handle_validation_errors(validation_summary)
        
        assert result["success"] is False
        assert result["action_required"] == "fix_configuration"
    
    @pytest.mark.asyncio
    async def test_handle_validation_errors_warnings_only(self, error_handler):
        """Test validation error handling for warnings only"""
        validation_summary = {
            "has_critical": False,
            "has_errors": False,
            "by_severity": {"critical": 0, "error": 0, "warning": 2}
        }
        
        result = await error_handler.handle_validation_errors(validation_summary)
        
        assert result["success"] is True
        assert result["action_required"] == "monitor"
    
    def test_create_error_notification(self, error_handler):
        """Test error notification creation"""
        notification = error_handler.create_error_notification(
            "database_connection_failed",
            {"error": "Connection timeout", "attempts": 3}
        )
        
        assert notification["error_type"] == "database_connection_failed"
        assert notification["severity"] == "critical"
        assert "timestamp" in notification
        assert notification["notification_sent"] is False


class TestPuzzleMonitor:
    """Test cases for PuzzleMonitor"""
    
    @pytest.fixture
    def monitor(self):
        return PuzzleMonitor()
    
    def test_record_generation_attempt_success(self, monitor):
        """Test recording successful generation attempt"""
        monitor.record_generation_attempt("marvel", "2024-01-15", True)
        
        assert monitor.metrics["total_generations"] == 1
        assert monitor.metrics["successful_generations"] == 1
        assert monitor.metrics["failed_generations"] == 0
        assert monitor.consecutive_failures == 0
        assert monitor.last_successful_generation is not None
    
    def test_record_generation_attempt_failure(self, monitor):
        """Test recording failed generation attempt"""
        monitor.record_generation_attempt("marvel", "2024-01-15", False, {
            "error_type": "database_error"
        })
        
        assert monitor.metrics["total_generations"] == 1
        assert monitor.metrics["successful_generations"] == 0
        assert monitor.metrics["failed_generations"] == 1
        assert monitor.metrics["database_errors"] == 1
        assert monitor.consecutive_failures == 1
    
    def test_get_health_status_healthy(self, monitor):
        """Test health status when system is healthy"""
        # Record some successful attempts
        for i in range(5):
            monitor.record_generation_attempt("marvel", f"2024-01-{15+i}", True)
        
        status = monitor.get_health_status()
        
        assert status["health"] == "healthy"
        assert status["success_rate"] == 100.0
        assert status["consecutive_failures"] == 0
    
    def test_get_health_status_degraded(self, monitor):
        """Test health status when system is degraded"""
        # Record some failures
        for i in range(3):
            monitor.record_generation_attempt("marvel", f"2024-01-{15+i}", False)
        
        status = monitor.get_health_status()
        
        assert status["health"] == "degraded"
        assert status["consecutive_failures"] == 3
    
    def test_get_health_status_critical(self, monitor):
        """Test health status when system is critical"""
        # Record many failures
        for i in range(6):
            monitor.record_generation_attempt("marvel", f"2024-01-{15+i}", False)
        
        status = monitor.get_health_status()
        
        assert status["health"] == "critical"
        assert status["consecutive_failures"] == 6
    
    def test_should_alert_critical_threshold(self, monitor):
        """Test alert triggering at critical failure threshold"""
        # Record failures to reach critical threshold
        for i in range(5):
            monitor.record_generation_attempt("marvel", f"2024-01-{15+i}", False)
        
        should_alert, reason = monitor.should_alert()
        
        assert should_alert is True
        assert reason == "critical_failure_threshold"
    
    def test_should_alert_degraded_performance(self, monitor):
        """Test alert triggering for degraded performance"""
        # Record failures to reach degraded threshold
        for i in range(3):
            monitor.record_generation_attempt("marvel", f"2024-01-{15+i}", False)
        
        should_alert, reason = monitor.should_alert()
        
        assert should_alert is True
        assert reason == "degraded_performance"
    
    def test_should_alert_extended_outage(self, monitor):
        """Test alert triggering for extended outage"""
        # Set last successful generation to more than 25 hours ago
        monitor.last_successful_generation = datetime.utcnow() - timedelta(hours=26)
        
        should_alert, reason = monitor.should_alert()
        
        assert should_alert is True
        assert reason == "extended_outage"


class TestValidationIssue:
    """Test cases for ValidationIssue"""
    
    def test_validation_issue_creation(self):
        """Test ValidationIssue creation and serialization"""
        issue = ValidationIssue(
            ValidationSeverity.ERROR,
            "Test error message",
            {"context_key": "context_value"}
        )
        
        assert issue.severity == ValidationSeverity.ERROR
        assert issue.message == "Test error message"
        assert issue.context["context_key"] == "context_value"
        assert issue.timestamp is not None
    
    def test_validation_issue_to_dict(self):
        """Test ValidationIssue serialization to dictionary"""
        issue = ValidationIssue(
            ValidationSeverity.WARNING,
            "Test warning",
            {"universe": "marvel"}
        )
        
        issue_dict = issue.to_dict()
        
        assert issue_dict["severity"] == "warning"
        assert issue_dict["message"] == "Test warning"
        assert issue_dict["context"]["universe"] == "marvel"
        assert "timestamp" in issue_dict


if __name__ == "__main__":
    pytest.main([__file__])