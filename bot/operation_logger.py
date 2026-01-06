"""
Operation Logger

Provides file-based logging with automatic rotation at 10MB maximum size.
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional


def setup_logger(log_file: Optional[str] = None) -> logging.Logger:
    """
    Setup and configure the operation logger.
    
    Args:
        log_file: Optional path to log file. Defaults to 'logs/operations.log'
    
    Returns:
        Configured logger instance
    """
    if log_file is None:
        log_file = "logs/operations.log"
    
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger('bot_operations')
    logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create rotating file handler with 10MB max size
    max_bytes = 10 * 1024 * 1024  # 10MB
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=1,  # Keep one backup file
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(file_handler)
    
    return logger


def get_logger() -> logging.Logger:
    """
    Get the operation logger instance.
    Creates it if it doesn't exist.
    
    Returns:
        Logger instance
    """
    logger = logging.getLogger('bot_operations')
    if not logger.handlers:
        # Logger not set up yet, set it up
        return setup_logger()
    return logger

