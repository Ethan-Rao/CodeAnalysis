"""Logging configuration for CMS Explorer."""
import logging
from pathlib import Path

def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Set up logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("cms_explorer")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

# Create module-level logger
logger = setup_logging()


