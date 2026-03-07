# auth/__init__.py
"""Authentication module initialization"""

from .login import login
from .logout import logout
from .assignment_selection import select_assignment
from .session_manager import SessionManager
from .validators import validate_platform_admin_credentials, validate_school_user_credentials, validate_session_cookies

__all__ = [
    'login',
    'logout', 
    'select_assignment',
    'SessionManager',
    'validate_platform_admin_credentials',
    'validate_school_user_credentials',
    'validate_session_cookies'
]