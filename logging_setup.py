# logging_setup.py
import logging
import logging.handlers
import os
import sys
from config import LOG_CONFIG

def setup_logging():
    """Setup logging configuration with proper error handling and UTF-8 encoding"""
    try:
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        # Create formatter
        formatter = logging.Formatter(LOG_CONFIG['format'])
        
        # Create file handler with rotation and UTF-8 encoding
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_CONFIG['file'],
            maxBytes=LOG_CONFIG['max_size'],
            backupCount=LOG_CONFIG['backup_count'],
            mode='a',
            encoding='utf-8'  # Explicitly set UTF-8 encoding for file
        )
        file_handler.setFormatter(formatter)
        
        # Create console handler with UTF-8 encoding
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setEncoding('utf-8')  # Explicitly set UTF-8 encoding for console
        
        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, LOG_CONFIG['level']),
            handlers=[file_handler, console_handler],
            force=True  # Force reconfiguration if already configured
        )
        
        # Create error log handler with UTF-8 encoding
        error_handler = logging.handlers.RotatingFileHandler(
            'logs/error.log',
            maxBytes=LOG_CONFIG['max_size'],
            backupCount=LOG_CONFIG['backup_count'],
            encoding='utf-8'  # Explicitly set UTF-8 encoding for error log
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        
        # Add error handler to root logger
        logging.getLogger().addHandler(error_handler)
        
        return True
    except Exception as e:
        # Fallback to console logging only with UTF-8 encoding
        logging.basicConfig(
            level=getattr(logging, LOG_CONFIG['level']),
            format=LOG_CONFIG['format'],
            handlers=[logging.StreamHandler(sys.stdout)],
            encoding='utf-8',  # Explicitly set UTF-8 encoding for fallback
            force=True
        )
        print(f"Warning: Could not setup file logging: {e}")
        return False