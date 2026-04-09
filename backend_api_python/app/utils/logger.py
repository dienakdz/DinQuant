"""
Logging utilities (local-only friendly).
"""

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logger():
    """Configure global logs"""
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(level=getattr(logging, log_level.upper()), format=log_format)

    # Filter werkzeug's INFO level logs (reduce noise)
    # Only keep WARNING and above levels
    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.setLevel(logging.WARNING)

    # Filter INFO level logs for kline routes (reduce noise)
    # Only keep WARNING and above levels
    kline_logger = logging.getLogger("app.routes.kline")
    kline_logger.setLevel(logging.WARNING)

    # Create log directory
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Add file handler
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "app.log"),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(log_format))
    logging.getLogger().addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get the logger with the specified name

    Args:
        name: logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
