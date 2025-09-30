"""
Logging configuration for SatoApp
"""

import logging
import sys
from typing import Dict, Any
from .settings import get_settings

settings = get_settings()


def setup_logging() -> None:
    """Setup application logging configuration"""
    
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Setup console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    
    # Setup specific loggers
    loggers_config = {
        "app": log_level,
        "app.agents": log_level,
        "app.services": log_level,
        "app.api": log_level,
        "uvicorn": logging.WARNING,
        "fastapi": logging.WARNING,
    }
    
    for logger_name, level in loggers_config.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Get logger instance"""
    return logging.getLogger(f"app.{name}")
