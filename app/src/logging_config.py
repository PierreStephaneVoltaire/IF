"""Centralized logging configuration for IF Prototype A1.

This module provides a unified logging setup that writes all application logs
to a single file with proper formatting and log levels.
"""
import logging
import sys
import time
from pathlib import Path
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from config import LOG_LEVEL, LOG_FILE


# Custom log format
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    """Configure the root logger with file and console handlers.
    
    This should be called once at application startup.
    Creates the log directory if it doesn't exist.
    """
    # Create log directory if needed
    log_path = Path(LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Get log level from string
    level = getattr(logging, LOG_LEVEL, logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove any existing handlers
    root_logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    
    # File handler - always write to file
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler - also output to stdout
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    # Log that logging is configured
    logging.getLogger(__name__).info(f"Logging configured: level={LOG_LEVEL}, file={LOG_FILE}")


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.
    
    Args:
        name: Logger name, typically __name__ of the calling module
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for logging HTTP requests.
    
    Logs all incoming HTTP requests with method, path, status code, and duration.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log details.
        
        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler
            
        Returns:
            The HTTP response
        """
        logger = get_logger("http")
        
        # Skip logging for health check endpoint to reduce noise
        if request.url.path == "/health":
            return await call_next(request)
        
        # Record start time
        start_time = time.perf_counter()
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.perf_counter() - start_time
        
        # Log the request
        logger.info(
            f"{request.method} {request.url.path} {response.status_code} {duration:.3f}s"
        )
        
        return response
