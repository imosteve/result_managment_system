# config.py
from dotenv import load_dotenv
import os

# Load variables from .env into environment
load_dotenv()

# Application Configuration
APP_CONFIG = {
    "school_name": "scripture union international schools".upper(),
    "app_name": "Result Management System".upper(),
    "version": "1.0.0",
    "page_title": "Student Result System",
    "cookie_prefix": "student_results_app",
    "session_timeout": 30,  # 1 hour in seconds
    "max_login_attempts": 5,
    "lockout_duration": 300,  # 5 minutes in seconds
}

# Environment Configuration
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
COOKIE_PASSWORD = os.getenv('COOKIE_PASSWORD', 'fallback-secure-password-change-in-production')

# Database Configuration
DB_CONFIG = {
    "path": os.path.join("data", "school.db"),
    "backup_dir": os.path.join("data", "backups"),
    "enable_foreign_keys": True
}

# Logging Configuration
LOG_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "dir": "logs",
    "file": "logs/app.log",
    "max_size": 10 * 1024 * 1024,  # 10MB
    "backup_count": 5
}

# Security Configuration
SECURITY_CONFIG = {
    "disable_right_click": True,
    "disable_dev_tools": True,
    "session_timeout_enabled": True,
    "force_https": ENVIRONMENT == 'production'
}
