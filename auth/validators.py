# auth/validators.py
"""Authentication validators - UPDATED VERSION"""

import streamlit as st
import logging
from typing import Optional, Dict, Any, Tuple
from database import get_user_by_username, get_user_role
from .session_manager import SessionManager

logger = logging.getLogger(__name__)

def validate_user_input(username: str, password: str) -> Tuple[bool, str]:
    """
    Validate user input for login
    
    Args:
        username: Username string
        password: Password string
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not username or not username.strip():
        return False, "Username is required"
    
    if not password or not password.strip():
        return False, "Password is required"
    
    if len(password) < 4:
        return False, "Password must be at least 4 characters"
    
    return True, ""

def validate_credentials(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Validate user credentials against database
    
    Args:
        username: Username to validate
        password: Password to validate
        
    Returns:
        User dictionary if valid, None otherwise
    """
    try:
        user_record = get_user_by_username(username)
        
        if not user_record:
            logger.warning(f"Login attempt for non-existent user: {username}")
            return None
        
        # Check password (plain text comparison for now)
        if user_record[2] != password:
            logger.warning(f"Invalid password attempt for user: {username}")
            return None
        
        # Get admin role if exists
        admin_role = user_record[3] if user_record[3] else None
        
        # Return user data
        user_data = {
            "id": user_record[0],
            "username": user_record[1],
            "role": admin_role  # Will be None for teachers (set during assignment selection)
        }
        
        logger.info(f"Successful login validation for user: {username}")
        return user_data
        
    except Exception as e:
        logger.error(f"Error validating credentials for {username}: {str(e)}")
        return None

def validate_session_cookies(cookies) -> bool:
    """
    Validate and restore session from cookies
    
    Args:
        cookies: Cookie manager instance
        
    Returns:
        True if session restored successfully, False otherwise
    """
    try:
        # Check if cookies indicate authenticated session
        if not cookies.get("authenticated") == "true":
            return False
        
        # Try to restore session from cookies
        if SessionManager.restore_from_cookies(cookies):
            # Check if user is admin or has assignment
            role = st.session_state.get('role')
            
            if role in ['admin', 'superadmin']:
                # Admin users can proceed directly
                logger.info(f"Admin session restored for: {st.session_state.get('username')}")
                return True
            elif 'assignment' in st.session_state and st.session_state.assignment:
                # Teacher with assignment can proceed
                logger.info(f"Teacher session with assignment restored for: {st.session_state.get('username')}")
                return True
            else:
                # Teacher without assignment needs to select one
                # This is valid - they'll be redirected to assignment selection
                logger.info(f"Teacher session without assignment for: {st.session_state.get('username')}")
                return True  # Changed from False to True - let login.py handle it
        
        return False
        
    except Exception as e:
        logger.error(f"Error validating session cookies: {str(e)}")
        return False