"""
Logging utilities for the application.
"""

import os
import logging
import functools
import time
from datetime import datetime
from typing import Callable, Any

# Configure logging
def setup_logging():
    """Set up logging for the application."""
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("logs/app.log"),
            logging.StreamHandler(),
        ],
    )
    
    # Set specific loggers to different levels
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    
    # Return the root logger
    return logging.getLogger()

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

def log_function_call(func: Callable) -> Callable:
    """
    Decorator to log function calls.
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        func_name = func.__qualname__
        
        # Log function call
        logger.debug(f"Calling {func_name}")
        
        # Measure execution time
        start_time = time.time()
        
        try:
            # Call the function
            result = func(*args, **kwargs)
            
            # Log successful execution
            elapsed_time = time.time() - start_time
            logger.debug(f"{func_name} completed in {elapsed_time:.3f}s")
            
            return result
        except Exception as e:
            # Log exception
            elapsed_time = time.time() - start_time
            logger.error(f"{func_name} failed after {elapsed_time:.3f}s: {str(e)}")
            
            # Re-raise the exception
            raise
    
    return wrapper

def log_execution_time(func: Callable) -> Callable:
    """
    Decorator to log function execution time.
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Measure execution time
        start_time = time.time()
        
        # Call the function
        result = func(*args, **kwargs)
        
        # Log execution time
        elapsed_time = time.time() - start_time
        logger = get_logger(func.__module__)
        logger.debug(f"{func.__qualname__} executed in {elapsed_time:.3f}s")
        
        return result
    
    return wrapper
