# auth/validators.py
"""Authentication validation functions - SIMPLIFIED"""

import streamlit as st
import logging
from typing import Optional, Dict, Any
from database import get_user_by_username

logger = logging.getLogger(__name__)

def validate_credentials(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Validate user credentials against database
    
    Args:
        username: Username to validate
        password: Password to validate
        
    Returns:
        User data if valid, None if invalid
    """
    if not username or not password:
        return None
        
    try:
        user = get_user_by_username(username)
        if user and user["password"] == password:
            logger.info(f"Successful login for user: {username}")
            return user
        else:
            logger.warning(f"Failed login attempt for user: {username}")
            return None
    except Exception as e:
        logger.error(f"Error validating credentials for {username}: {str(e)}")
        return None

def validate_session_cookies(cookies) -> bool:
    """
    Validate session cookies - SIMPLIFIED VERSION
    
    Args:
        cookies: Cookie manager instance
        
    Returns:
        True if valid session exists, False otherwise
    """
    if not cookies:
        return False

    try:
        from auth.session_manager import SessionManager
        
        # Try to restore session from cookies
        return SessionManager.restore_from_cookies(cookies)
        
    except Exception as e:
        logger.error(f"Error validating session cookies: {str(e)}")
        return False
    
def validate_user_input(username: str, password: str) -> tuple[bool, str]:
    """
    Validate user input for login form
    
    Args:
        username: Username input
        password: Password input
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not username or not password:
        return False, "Please fill in both fields."
    
    if len(username.strip()) == 0:
        return False, "Username cannot be empty."
    
    if len(password) < 4:
        return False, "Password too short."
    
    return True, ""