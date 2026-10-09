"""
Structured Logging Configuration.
"""

import sys
import logging
from app.core.config import LOGS_DIR

LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s:%(lineno)d | %(message)s"
LOG_FILE = LOGS_DIR / "app.log"


def configure_logging(level: int = logging.INFO):
    """Configures handlers for console and file logging."""
    logger = logging.getLogger()
    logger.setLevel(level)

    # Avoid duplicate handlers if already configured
    if logger.handlers:
        return logger

    # Console Handler (utf-8 compatible)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_formatter = logging.Formatter(LOG_FORMAT)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File Handler
    try:
        file_handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    except Exception as exc:
        print(f"Warning: Could not initialize file logger at {LOG_FILE}: {exc}")

    return logger


def get_logger(name: str) -> logging.Logger:
    """Returns a named logger."""
    return logging.getLogger(name)
