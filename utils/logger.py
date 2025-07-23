"""
Enhanced logging configuration for Pinfairy Bot
Provides structured logging with different levels, file rotation, and performance tracking
"""

import logging
import logging.handlers
import os
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional
from constants import LOG_FORMAT, LOG_DATE_FORMAT, LOG_MAX_BYTES, LOG_BACKUP_COUNT, LOGS_DIR

class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured logs in JSON format"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'user_id'):
            log_entry["user_id"] = record.user_id
        if hasattr(record, 'url'):
            log_entry["url"] = record.url
        if hasattr(record, 'duration'):
            log_entry["duration"] = record.duration
        if hasattr(record, 'error_code'):
            log_entry["error_code"] = record.error_code
            
        return json.dumps(log_entry, ensure_ascii=False)

class PinfairyLogger:
    """Enhanced logger for Pinfairy Bot with structured logging and performance tracking"""
    
    def __init__(self, name: str = "pinfairy"):
        self.name = name
        self.logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self):
        """Setup logger with file rotation and structured formatting"""
        # Create logs directory if it doesn't exist
        os.makedirs(LOGS_DIR, exist_ok=True)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Set log level from environment or default to INFO
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.logger.setLevel(getattr(logging, log_level, logging.INFO))
        
        # Console handler with simple format
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)
        
        # File handler with rotation and structured format
        file_handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join(LOGS_DIR, f"{self.name}.log"),
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setFormatter(StructuredFormatter())
        file_handler.setLevel(logging.DEBUG)
        
        # Error file handler for errors only
        error_handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join(LOGS_DIR, f"{self.name}_errors.log"),
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        error_handler.setFormatter(StructuredFormatter())
        error_handler.setLevel(logging.ERROR)
        
        # Add handlers
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(error_handler)
        
        # Prevent propagation to root logger
        self.logger.propagate = False
    
    def debug(self, message: str, **kwargs):
        """Log debug message with optional extra fields"""
        self.logger.debug(message, extra=kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message with optional extra fields"""
        self.logger.info(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with optional extra fields"""
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message: str, exc_info: bool = False, **kwargs):
        """Log error message with optional exception info and extra fields"""
        self.logger.error(message, exc_info=exc_info, extra=kwargs)
    
    def critical(self, message: str, exc_info: bool = False, **kwargs):
        """Log critical message with optional exception info and extra fields"""
        self.logger.critical(message, exc_info=exc_info, extra=kwargs)
    
    def log_user_action(self, user_id: int, action: str, url: Optional[str] = None, 
                       duration: Optional[float] = None, success: bool = True, **kwargs):
        """Log user action with structured data"""
        extra = {
            "user_id": user_id,
            "action": action,
            "success": success,
            **kwargs
        }
        
        if url:
            extra["url"] = url
        if duration:
            extra["duration"] = duration
            
        level = logging.INFO if success else logging.WARNING
        message = f"User {user_id} {action}"
        if not success:
            message += " (failed)"
            
        self.logger.log(level, message, extra=extra)
    
    def log_performance(self, operation: str, duration: float, **kwargs):
        """Log performance metrics"""
        extra = {
            "operation": operation,
            "duration": duration,
            "performance": True,
            **kwargs
        }
        
        self.logger.info(f"Performance: {operation} took {duration:.2f}s", extra=extra)
    
    def log_error_with_code(self, message: str, error_code: str, **kwargs):
        """Log error with specific error code"""
        extra = {"error_code": error_code, **kwargs}
        self.logger.error(f"[{error_code}] {message}", extra=extra)

# Global logger instance
logger = PinfairyLogger()

# Convenience functions for backward compatibility
def get_logger(name: str = "pinfairy") -> PinfairyLogger:
    """Get a logger instance"""
    return PinfairyLogger(name)

def log_user_action(user_id: int, action: str, **kwargs):
    """Log user action using global logger"""
    logger.log_user_action(user_id, action, **kwargs)

def log_performance(operation: str, duration: float, **kwargs):
    """Log performance using global logger"""
    logger.log_performance(operation, duration, **kwargs)