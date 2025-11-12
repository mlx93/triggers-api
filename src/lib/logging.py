"""
Structured JSON logging configuration for Zapier Triggers API.

Configures python-json-logger for CloudWatch Logs compatibility with structured
context fields: event_id, tenant_id, event_type, payload_size, storage_type.
"""
import os
import logging
from pythonjsonlogger import json


def setup_logger(name: str = None) -> logging.Logger:
    """
    Set up a logger with structured JSON formatting.
    
    Configures JSON formatter compatible with CloudWatch Logs Insights.
    Includes context fields: event_id, tenant_id, event_type, payload_size, storage_type.
    
    Args:
        name: Logger name (defaults to root logger)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers if logger already configured
    if logger.handlers:
        return logger
    
    # Set log level from environment variable
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # Create JSON formatter
    # Format: timestamp, level, message, and custom fields
    formatter = json.JsonFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s',
        timestamp=True
    )
    
    # Create console handler (Lambda sends stdout/stderr to CloudWatch)
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Prevent propagation to root logger (avoid duplicate logs)
    logger.propagate = False
    
    return logger


def get_logger(name: str = None) -> logging.Logger:
    """
    Get or create a logger with structured JSON formatting.
    
    Convenience function that calls setup_logger if needed.
    
    Args:
        name: Logger name (defaults to root logger)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Set up if not already configured
    if not logger.handlers:
        setup_logger(name)
    
    return logger


def add_logging_context(logger: logging.Logger, **kwargs) -> logging.Logger:
    """
    Add context fields to logger for structured logging.
    
    Adds context fields as extra parameters that will be included in JSON logs.
    Common fields: event_id, tenant_id, event_type, payload_size, storage_type.
    
    Args:
        logger: Logger instance
        **kwargs: Context fields to add (event_id, tenant_id, etc.)
        
    Returns:
        Logger adapter with context
    """
    return logging.LoggerAdapter(logger, kwargs)

