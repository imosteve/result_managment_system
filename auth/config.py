# auth/config.py
"""Authentication configuration and constants"""

try:
    from config import APP_CONFIG  # ✅ Import from main config
    
    # Use values from main config
    MAX_LOGIN_ATTEMPTS = APP_CONFIG["max_login_attempts"]
    LOCKOUT_DURATION = APP_CONFIG["lockout_duration"]
    SESSION_TIMEOUT = APP_CONFIG["session_timeout"]
    COOKIE_PREFIX = APP_CONFIG["cookie_prefix"]
except ImportError:
    # Fallback values if import fails
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION = 900
    SESSION_TIMEOUT = 3600
    COOKIE_PREFIX = "student_results_app"

# UI Messages - KEEP EXACTLY AS IS
MESSAGES = {
    "loading_auth": "Loading authentication...",
    "login_success": "✅ Login successful! Redirecting...",
    "assignment_selected": "✅ Assignment selected! Redirecting...",
    "logout_success": "🔓 You have been logged out.",
    "invalid_credentials": "❌ Invalid credentials. Please try again.",
    "fill_all_fields": "⚠️ Please fill in both fields.",
    "no_assignments": "⚠️ No class or subject assignments found. Contact the admin.",
    "cookies_error": "⚠️ Cookies error: {}. Please try again.",
    "logout_failed": "⚠️ Logout failed: {}. Please try again.",
    "cookie_not_initialized": "Cookie manager not initialized."
}

# CSS Classes - KEEP EXACTLY AS IS
CSS_CLASSES = {
    "login_container": "block-container",
    "login_title": "login-title",
    "assignment_title": "assignment-title"
}