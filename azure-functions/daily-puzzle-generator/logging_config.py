"""
Logging configuration for Azure Function
"""

import logging
import sys
from datetime import datetime
import json
from typing import Dict, Any


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "function_name": getattr(record, 'funcName', ''),
            "line_number": getattr(record, 'lineno', ''),
            "module": getattr(record, 'module', '')
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        return json.dumps(log_entry)


class PuzzleGeneratorLogger:
    """Logger wrapper for puzzle generator with structured logging"""
    
    def __init__(self, name: str = "puzzle_generator"):
        self.logger = logging.getLogger(name)
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup structured logging configuration"""
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Create console handler with structured formatter
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(StructuredFormatter())
        
        # Set log level based on environment
        log_level = logging.INFO  # Default to INFO for production
        
        self.logger.setLevel(log_level)
        self.logger.addHandler(console_handler)
        
        # Prevent duplicate logs
        self.logger.propagate = False
    
    def info(self, message: str, **kwargs):
        """Log info message with optional extra fields"""
        extra = {"extra_fields": kwargs} if kwargs else {}
        self.logger.info(message, extra=extra)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with optional extra fields"""
        extra = {"extra_fields": kwargs} if kwargs else {}
        self.logger.warning(message, extra=extra)
    
    def error(self, message: str, **kwargs):
        """Log error message with optional extra fields"""
        extra = {"extra_fields": kwargs} if kwargs else {}
        self.logger.error(message, extra=extra)
    
    def critical(self, message: str, **kwargs):
        """Log critical message with optional extra fields"""
        extra = {"extra_fields": kwargs} if kwargs else {}
        self.logger.critical(message, extra=extra)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with optional extra fields"""
        extra = {"extra_fields": kwargs} if kwargs else {}
        self.logger.debug(message, extra=extra)
    
    def log_puzzle_generation(self, universe: str, date: str, success: bool, 
                            duration_seconds: float = None, **kwargs):
        """Log puzzle generation event with structured data"""
        log_data = {
            "event_type": "puzzle_generation",
            "universe": universe,
            "date": date,
            "success": success,
            "duration_seconds": duration_seconds
        }
        log_data.update(kwargs)
        
        if success:
            self.info(f"Puzzle generated successfully for {universe} on {date}", **log_data)
        else:
            self.error(f"Puzzle generation failed for {universe} on {date}", **log_data)
    
    def log_validation_result(self, component: str, validation_summary: Dict[str, Any]):
        """Log validation results with structured data"""
        log_data = {
            "event_type": "validation",
            "component": component,
            "validation_summary": validation_summary
        }
        
        if validation_summary.get("has_critical"):
            self.critical(f"Critical validation issues in {component}", **log_data)
        elif validation_summary.get("has_errors"):
            self.error(f"Validation errors in {component}", **log_data)
        elif validation_summary.get("total_issues", 0) > 0:
            self.warning(f"Validation warnings in {component}", **log_data)
        else:
            self.info(f"Validation passed for {component}", **log_data)
    
    def log_health_check(self, health_status: Dict[str, Any]):
        """Log health check results"""
        log_data = {
            "event_type": "health_check",
            "health_status": health_status
        }
        
        if not health_status.get("healthy", True):
            self.error("Health check failed", **log_data)
        else:
            self.info("Health check passed", **log_data)
    
    def log_error_handling(self, error_type: str, error_details: Dict[str, Any]):
        """Log error handling events"""
        log_data = {
            "event_type": "error_handling",
            "error_type": error_type,
            "error_details": error_details
        }
        
        self.warning(f"Error handled: {error_type}", **log_data)
    
    def log_performance_metric(self, operation: str, duration_seconds: float, 
                             success: bool = True, **kwargs):
        """Log performance metrics"""
        log_data = {
            "event_type": "performance_metric",
            "operation": operation,
            "duration_seconds": duration_seconds,
            "success": success
        }
        log_data.update(kwargs)
        
        self.info(f"Performance metric: {operation}", **log_data)


# Global logger instance
puzzle_logger = PuzzleGeneratorLogger()


def get_logger() -> PuzzleGeneratorLogger:
    """Get the global puzzle generator logger"""
    return puzzle_logger


def setup_azure_logging():
    """Setup logging for Azure Functions environment"""
    # Configure root logger for Azure Functions
    root_logger = logging.getLogger()
    
    # Set appropriate log level
    root_logger.setLevel(logging.INFO)
    
    # Azure Functions automatically handles log output,
    # but we can configure additional structured logging here
    
    # Suppress noisy loggers
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    
    return puzzle_logger