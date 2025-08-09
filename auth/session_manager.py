# auth/session_manager.py
"""Session management for authentication"""

import streamlit as st
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from .config import COOKIE_PREFIX

logger = logging.getLogger(__name__)

class SessionManager:
    """Handles user session management"""
    
    @staticmethod
    def create_session(user: Dict[str, Any], cookies) -> bool:
        """
        Create a new user session
        
        Args:
            user: User data from database
            cookies: Cookie manager instance
            
        Returns:
            True if session created successfully, False otherwise
        """
        try:
            # Set session state
            st.session_state.authenticated = True
            st.session_state.user_id = user["id"]
            st.session_state.role = user["role"]
            st.session_state.username = user["username"]
            st.session_state.login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state.last_activity = datetime.now()
            
            # Set cookies using your existing structure
            cookies["authenticated"] = "true"
            cookies["user_id"] = str(user["id"])
            cookies["role"] = user["role"]
            cookies["username"] = user["username"]
            cookies["login_time"] = st.session_state.login_time
            cookies.save()
            
            logger.info(f"Session created for user: {user['username']} (ID: {user['id']})")
            return True
            
        except Exception as e:
            logger.error(f"Error creating session for user {user.get('username', 'unknown')}: {str(e)}")
            return False
    
    @staticmethod
    def save_assignment(assignment_data: Dict[str, Any], cookies) -> bool:
        """
        Save user assignment to session and cookies
        
        Args:
            assignment_data: Assignment data
            cookies: Cookie manager instance
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            st.session_state.assignment = {
                "class_name": assignment_data["class_name"],
                "term": assignment_data["term"],
                "session": assignment_data["session"],
                "subject_name": assignment_data.get("subject_name")
            }
            
            cookies["assignment_class"] = assignment_data["class_name"]
            cookies["assignment_term"] = assignment_data["term"]
            cookies["assignment_session"] = assignment_data["session"]
            cookies["assignment_subject"] = assignment_data.get("subject_name", "")
            cookies.save()
            
            logger.info(f"Assignment saved for user {st.session_state.get('username')}: {assignment_data['class_name']}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving assignment: {str(e)}")
            return False
    
    @staticmethod
    def clear_session(cookies) -> bool:
        """
        Clear user session and cookies
        
        Args:
            cookies: Cookie manager instance
            
        Returns:
            True if cleared successfully, False otherwise
        """
        try:
            # Clear cookies
            if cookies:
                cookie_keys = [
                    "authenticated", "user_id", "role", "username", "login_time",
                    "assignment_class", "assignment_term", "assignment_session", "assignment_subject"
                ]
                
                for key in cookie_keys:
                    cookies[key] = ""
                cookies.save()
                
                # Clear browser cookies with JavaScript
                SessionManager._clear_browser_cookies()
            
            # Clear session state
            session_keys = [
                "authenticated", "user_id", "role", "username", "login_time",
                "assignment", "last_activity", "session_id"
            ]
            
            for key in session_keys:
                if key in st.session_state:
                    del st.session_state[key]
            
            # Clear query parameters
            st.query_params.clear()
            
            logger.info("Session cleared successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing session: {str(e)}")
            return False
    
    @staticmethod
    def _clear_browser_cookies():
        """Clear browser cookies using JavaScript"""
        cookie_names = [
            "authenticated", "user_id", "role", "username", "login_time",
            "assignment_class", "assignment_term", "assignment_session", "assignment_subject"
        ]
        
        script_parts = []
        for name in cookie_names:
            # ✅ FIXED: Use consistent cookie naming
            script_parts.append(
                f'document.cookie = "{name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";'
            )
        
        script = f"<script>{''.join(script_parts)}</script>"
        st.markdown(script, unsafe_allow_html=True)
    
    # ✅ ALL OTHER METHODS STAY EXACTLY THE SAME
    @staticmethod
    def is_authenticated() -> bool:
        """Check if user is authenticated"""
        return st.session_state.get("authenticated", False)
    
    @staticmethod
    def get_current_user() -> Optional[Dict[str, Any]]:
        """Get current user information"""
        if not SessionManager.is_authenticated():
            return None
            
        return {
            "user_id": st.session_state.get("user_id"),
            "username": st.session_state.get("username"),
            "role": st.session_state.get("role"),
            "login_time": st.session_state.get("login_time"),
            "assignment": st.session_state.get("assignment")
        }
    
    @staticmethod
    def update_activity():
        """Update user's last activity timestamp"""
        if SessionManager.is_authenticated():
            st.session_state.last_activity = datetime.now()