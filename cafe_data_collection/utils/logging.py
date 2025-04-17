import logging
import sys
from typing import Optional


def setup_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """Set up a logger with console output.
    
    Args:
        name: Name of the logger
        level: Optional logging level (defaults to INFO if not specified)
    
    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)
    
    if level is None:
        level = logging.INFO
    
    logger.setLevel(level)
    
    # Remove any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Add formatter to handler
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    return logger 