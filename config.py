# config.py  — FINAL VERSION
"""
Changes from single-tenant version:
  - school_name, sch_abrv, school_address removed from APP_CONFIG
    → these now live per-school in master.db, loaded into session state at login
  - platform_name added — shown in header when no school session is active
  - DB_CONFIG updated to reference master.db and schools directory
"""

from dotenv import load_dotenv
import os

load_dotenv()

APP_CONFIG = {
    "platform_name":      "School Result Management System",
    "app_name":           "Result Management System".upper(),
    "version":            "2.0.0",
    "page_title":         "Student Result System",
    "cookie_prefix":      "student_results_app",
    "session_timeout":    7200,   # 2 hours
    "max_login_attempts": 5,
    "lockout_duration":   300,    # 5 minutes
}

ENVIRONMENT     = os.getenv("ENVIRONMENT", "development")
DEBUG           = os.getenv("DEBUG", "True").lower() == "true"
COOKIE_PASSWORD = os.getenv("COOKIE_PASSWORD", "fallback-secure-password-change-in-production")

DB_CONFIG = {
    "master_path": os.path.join("data", "master.db"),
    "schools_dir": os.path.join("data", "schools"),
    "backup_dir":  os.path.join("data", "backups"),
    "enable_foreign_keys": True,
}

LOG_CONFIG = {
    "level":        "INFO",
    "format":       "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "dir":          "logs",
    "file":         "logs/app.log",
    "max_size":     10 * 1024 * 1024,
    "backup_count": 5,
}

SECURITY_CONFIG = {
    "disable_right_click":     True,
    "disable_dev_tools":       True,
    "session_timeout_enabled": True,
    "force_https":             ENVIRONMENT == "production",
}