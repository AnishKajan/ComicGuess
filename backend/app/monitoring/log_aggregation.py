"""
Log aggregation and searchable log management for ComicGuess application.
Provides centralized log collection, indexing, and search capabilities.
"""

import json
import time
import asyncio
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import re
from collections import defaultdict, deque

from .logging_config import get_logger

class LogLevel(Enum):
    """Log levels for filtering."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

@dataclass
class LogEntry:
    """Structured log entry."""
    timestamp: float
    level: LogLevel
    logger: str
    message: str
    correlation_id: str
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    module: Optional[str] = None
    function: Optional[str] = None
    line: Optional[int] = None
    extra_fields: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.extra_fields is None:
            self.extra_fields = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'timestamp': self.timestamp,
            'datetime': datetime.fromtimestamp(self.timestamp).isoformat(),
            'level': self.level.value,
            'logger': self.logger,
            'message': self.message,
            'correlation_id': self.correlation_id,
            'trace_id': self.trace_id,
            'span_id': self.span_id,
            'module': self.module,
            'function': self.function,
            'line': self.line,
            **self.extra_fields
        }

class LogFilter:
    """Filter for log entries."""
    
    def __init__(self):
        self.level: Optional[LogLevel] = None
        self.logger_pattern: Optional[str] = None
        self.message_pattern: Optional[str] = None
        self.correlation_id: Optional[str] = None
        self.trace_id: Optional[str] = None
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.extra_filters: Dict[str, Any] = {}
    
    def matches(self, entry: LogEntry) -> bool:
        """Check if log entry matches filter criteria."""
        # Level filter
        if self.level and entry.level != self.level:
            return False
        
        # Logger pattern filter
        if self.logger_pattern and not re.search(self.logger_pattern, entry.logger, re.IGNORECASE):
            return False
        
        # Message pattern filter
        if self.message_pattern and not re.search(self.message_pattern, entry.message, re.IGNORECASE):
            return False
        
        # Correlation ID filter
        if self.correlation_id and entry.correlation_id != self.correlation_id:
            return False
        
        # Trace ID filter
        if self.trace_id and entry.trace_id != self.trace_id:
            return False
        
        # Time range filter
        if self.start_time and entry.timestamp < self.start_time:
            return False
        if self.end_time and entry.timestamp > self.end_time:
            return False
        
        # Extra field filters
        for key, value in self.extra_filters.items():
            if key not in entry.extra_fields or entry.extra_fields[key] != value:
                return False
        
        return True

class LogAggregator:
    """Centralized log aggregation and management."""
    
    def __init__(self, max_entries: int = 100000, retention_hours: int = 168):  # 7 days
        self.max_entries = max_entries
        self.retention_hours = retention_hours
        self.entries: deque = deque(maxlen=max_entries)
        self.indices: Dict[str, Dict[str, List[LogEntry]]] = {
            'level': defaultdict(list),
            'logger': defaultdict(list),
            'correlation_id': defaultdict(list),
            'trace_id': defaultdict(list)
        }
        self.logger = get_logger("log_aggregator")
        self._cleanup_task = None
        
        # Start cleanup task if event loop is running
        try:
            loop = asyncio.get_running_loop()
            self._cleanup_task = loop.create_task(self._cleanup_task_impl())
        except RuntimeError:
            # No event loop running, cleanup task will be started later
            pass
    
    def add_entry(self, entry: LogEntry):
        """Add a log entry to the aggregator."""
        self.entries.append(entry)
        
        # Update indices
        self.indices['level'][entry.level.value].append(entry)
        self.indices['logger'][entry.logger].append(entry)
        self.indices['correlation_id'][entry.correlation_id].append(entry)
        if entry.trace_id:
            self.indices['trace_id'][entry.trace_id].append(entry)
        
        # Limit index sizes
        for index_type, index in self.indices.items():
            for key, entries in index.items():
                if len(entries) > 1000:  # Keep only recent 1000 entries per index key
                    entries[:] = entries[-1000:]
    
    def search(self, filter_obj: LogFilter, limit: int = 1000, offset: int = 0) -> List[LogEntry]:
        """Search log entries with filtering."""
        matching_entries = []
        
        # Use indices for efficient filtering when possible
        candidate_entries = None
        
        if filter_obj.level:
            candidate_entries = self.indices['level'][filter_obj.level.value]
        elif filter_obj.correlation_id:
            candidate_entries = self.indices['correlation_id'][filter_obj.correlation_id]
        elif filter_obj.trace_id:
            candidate_entries = self.indices['trace_id'][filter_obj.trace_id]
        else:
            candidate_entries = list(self.entries)
        
        # Apply all filters
        for entry in candidate_entries:
            if filter_obj.matches(entry):
                matching_entries.append(entry)
        
        # Sort by timestamp (newest first)
        matching_entries.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Apply pagination
        return matching_entries[offset:offset + limit]
    
    def get_stats(self, time_window_hours: int = 1) -> Dict[str, Any]:
        """Get log statistics for the specified time window."""
        cutoff_time = time.time() - (time_window_hours * 3600)
        
        stats = {
            'total_entries': 0,
            'by_level': defaultdict(int),
            'by_logger': defaultdict(int),
            'error_rate': 0,
            'top_errors': [],
            'time_window_hours': time_window_hours
        }
        
        recent_entries = [e for e in self.entries if e.timestamp > cutoff_time]
        stats['total_entries'] = len(recent_entries)
        
        error_messages = defaultdict(int)
        
        for entry in recent_entries:
            stats['by_level'][entry.level.value] += 1
            stats['by_logger'][entry.logger] += 1
            
            if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]:
                # Group similar error messages
                error_key = entry.message[:100]  # Truncate for grouping
                error_messages[error_key] += 1
        
        # Calculate error rate (errors per minute)
        error_count = stats['by_level']['ERROR'] + stats['by_level']['CRITICAL']
        stats['error_rate'] = error_count / (time_window_hours * 60) if time_window_hours > 0 else 0
        
        # Top errors
        stats['top_errors'] = [
            {'message': msg, 'count': count}
            for msg, count in sorted(error_messages.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
        return stats
    
    def get_trace_logs(self, trace_id: str) -> List[LogEntry]:
        """Get all log entries for a specific trace."""
        return self.indices['trace_id'].get(trace_id, [])
    
    def get_correlation_logs(self, correlation_id: str) -> List[LogEntry]:
        """Get all log entries for a specific correlation ID."""
        return self.indices['correlation_id'].get(correlation_id, [])
    
    def export_logs(self, filter_obj: LogFilter, format: str = 'json') -> Union[str, List[Dict]]:
        """Export filtered logs in specified format."""
        entries = self.search(filter_obj, limit=10000)  # Large limit for export
        
        if format == 'json':
            return json.dumps([entry.to_dict() for entry in entries], indent=2)
        elif format == 'dict':
            return [entry.to_dict() for entry in entries]
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def start_cleanup_task(self):
        """Start the cleanup task if not already running."""
        if self._cleanup_task is None or self._cleanup_task.done():
            try:
                loop = asyncio.get_running_loop()
                self._cleanup_task = loop.create_task(self._cleanup_task_impl())
            except RuntimeError:
                # No event loop running
                pass
    
    async def _cleanup_task_impl(self):
        """Background task to clean up old log entries."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await self._cleanup_old_entries()
            except Exception as e:
                self.logger.error(f"Error in log cleanup task: {e}")
    
    async def _cleanup_old_entries(self):
        """Remove old log entries beyond retention period."""
        cutoff_time = time.time() - (self.retention_hours * 3600)
        
        # Clean main entries
        original_count = len(self.entries)
        self.entries = deque(
            (entry for entry in self.entries if entry.timestamp > cutoff_time),
            maxlen=self.max_entries
        )
        
        # Clean indices
        for index_type, index in self.indices.items():
            for key, entries in index.items():
                entries[:] = [e for e in entries if e.timestamp > cutoff_time]
        
        cleaned_count = original_count - len(self.entries)
        if cleaned_count > 0:
            self.logger.info(f"Cleaned up {cleaned_count} old log entries")

# Global log aggregator instance
log_aggregator = LogAggregator()

class AggregatingLogHandler:
    """Log handler that sends logs to the aggregator."""
    
    def __init__(self, aggregator: LogAggregator):
        self.aggregator = aggregator
        self.logger = get_logger("aggregating_handler")
    
    def handle_log(self, record: Dict[str, Any]):
        """Handle a log record and add it to the aggregator."""
        try:
            # Parse log level
            level_str = record.get('level', 'INFO').upper()
            try:
                level = LogLevel(level_str)
            except ValueError:
                level = LogLevel.INFO
            
            # Create log entry
            entry = LogEntry(
                timestamp=record.get('timestamp', time.time()),
                level=level,
                logger=record.get('logger', 'unknown'),
                message=record.get('message', ''),
                correlation_id=record.get('correlation_id', 'no-correlation-id'),
                trace_id=record.get('trace_id'),
                span_id=record.get('span_id'),
                module=record.get('module'),
                function=record.get('function'),
                line=record.get('line'),
                extra_fields={k: v for k, v in record.items() 
                            if k not in ['timestamp', 'level', 'logger', 'message', 
                                       'correlation_id', 'trace_id', 'span_id', 
                                       'module', 'function', 'line']}
            )
            
            self.aggregator.add_entry(entry)
            
        except Exception as e:
            self.logger.error(f"Error handling log record: {e}")

# Global log handler
log_handler = AggregatingLogHandler(log_aggregator)

def search_logs(
    level: Optional[str] = None,
    logger_pattern: Optional[str] = None,
    message_pattern: Optional[str] = None,
    correlation_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    hours_back: Optional[int] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Convenience function to search logs."""
    filter_obj = LogFilter()
    
    if level:
        try:
            filter_obj.level = LogLevel(level.upper())
        except ValueError:
            pass
    
    if logger_pattern:
        filter_obj.logger_pattern = logger_pattern
    
    if message_pattern:
        filter_obj.message_pattern = message_pattern
    
    if correlation_id:
        filter_obj.correlation_id = correlation_id
    
    if trace_id:
        filter_obj.trace_id = trace_id
    
    if hours_back:
        filter_obj.start_time = time.time() - (hours_back * 3600)
    
    entries = log_aggregator.search(filter_obj, limit, offset)
    return [entry.to_dict() for entry in entries]

def get_log_stats(hours_back: int = 1) -> Dict[str, Any]:
    """Get log statistics."""
    return log_aggregator.get_stats(hours_back)

def get_trace_logs(trace_id: str) -> List[Dict[str, Any]]:
    """Get all logs for a trace."""
    entries = log_aggregator.get_trace_logs(trace_id)
    return [entry.to_dict() for entry in entries]