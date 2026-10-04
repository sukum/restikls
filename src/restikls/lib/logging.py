# File: src/restikls/lib/logging.py
"""
logging configuration module.
Provides functions to set up rotating file logging with configurable parameters.
Handles log directory creation, handler configuration, and log level settings.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask
from flask.logging import default_handler

def setup_logging(app: Flask) -> None:
    """
    Orchestrates the logging setup for the Flask application.
    Args:
        app (Flask): The Flask application instance.
    """
    # Get configuration with defaults
    log_dir: str = app.config["LOG_DIRECTORY"]
    log_file: str = app.config["LOG_FILENAME"]
    max_bytes: int = app.config["LOG_MAX_BYTES"]
    backup_count: int = app.config["LOG_BACKUP_COUNT"]

    try:
        # Create log path
        log_path = os.path.join(log_dir, log_file)

        # Try to create log directory
        if not create_log_directory(log_dir):
            # Fallback to current directory if creation fails
            log_path = log_file

        # Configure handler
        handler = configure_log_handler(log_path, max_bytes, backup_count)
        if not handler:
            app.logger.error("Failed to configure log handler")
            return
        app.logger.removeHandler(default_handler)
        app.logger.addHandler(handler)
    except Exception as e:
        print("Error setting up logging", str(e))

    # Set log level
    try:
        log_level_name = app.config["LOG_LEVEL"].upper()
        log_level = getattr(logging, log_level_name, logging.WARNING)
        app.logger.setLevel(log_level)
    except AttributeError:
        app.logger.setLevel(logging.NOTSET)

def create_log_directory(log_dir: str) -> bool:
    """
    Creates the log directory if it doesn't exist.
    Args:
        log_dir (str): Path to the log directory.
    Returns:
        bool: True if directory exists or was created, False otherwise.
    """
    try:
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        return True
    except OSError as e:
        logging.error(f"Error creating log directory '{log_dir}': {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error creating log directory: {e}")
        return False


def configure_log_handler(
    log_path: str, max_bytes: int, backup_count: int
) -> logging.Handler | None:
    """
    Configures and returns a rotating file handler.
    Args:
        log_path (str): Full path to the log file.
        max_bytes (int): Maximum size in bytes before rotation.
        backup_count (int): Number of backup logs to keep.
    Returns:
        RotatingFileHandler: Configured handler or None if configuration fails.
    """
    try:
        handler = RotatingFileHandler(
            log_path, maxBytes=max_bytes, backupCount=backup_count
        )
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        return handler
    except Exception as e:
        logging.error(f"Error configuring log handler: {e}")
        return None
