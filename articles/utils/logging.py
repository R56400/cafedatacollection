import logging
import sys

from ..config import LOG_LEVEL


def setup_logger(name: str, level: int | None = None) -> logging.Logger:
    """Set up a logger with console output for the article generation pipeline.

    Args:
        name: Name of the logger (typically __name__ of the module)
        level: Optional logging level (defaults to LOG_LEVEL from config)

    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)

    # Use configured level or default to INFO
    if level is None:
        level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

    logger.setLevel(level)

    # Remove any existing handlers to avoid duplicate logs
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Create formatter with timestamp, module name, and message
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Add formatter to handler
    console_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(console_handler)

    return logger
