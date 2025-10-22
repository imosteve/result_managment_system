# auth/session_manager.py
"""Session management - UPDATED VERSION for new user model"""

import streamlit as st
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class SessionManager:
    """Handles user session management - UPDATED"""
    
    @staticmethod
    def create_session(user: Dict[str, Any], cookies) -> bool:
        """
        Create a new user session with proper cookie expiry
        
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
            st.session_state.role = user["role"]  # Will be None for teachers
            st.session_state.username = user["username"]
            st.session_state.login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state.last_activity = datetime.now()
            
            # Set cookies (they will auto-expire based on cookie manager settings)
            cookies["authenticated"] = "true"
            cookies["user_id"] = str(user["id"])
            cookies["role"] = str(user["role"]) if user["role"] else ""  # Handle None role
            cookies["username"] = user["username"]
            cookies["login_time"] = st.session_state.login_time
            cookies.save()
            
            logger.info(f"Session created for user: {user['username']} (ID: {user['id']}, Role: {user['role'] or 'Teacher'})")
            return True
            
        except Exception as e:
            logger.error(f"Error creating session for user {user.get('username', 'unknown')}: {str(e)}")
            return False
    
    @staticmethod
    def save_assignment(assignment_data: Dict[str, Any], cookies) -> bool:
        """
        Save user assignment to session and cookies
        Also updates the role based on assignment type
        
        Args:
            assignment_data: Assignment data
            cookies: Cookie manager instance
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            subject_name = assignment_data.get("subject_name") or ""
            assignment_type = assignment_data.get("assignment_type", "class_teacher")
            
            st.session_state.assignment = {
                "class_name": assignment_data["class_name"],
                "term": assignment_data["term"],
                "session": assignment_data["session"],
                "subject_name": subject_name,
                "assignment_type": assignment_type
            }
            
            # Update role based on assignment type
            st.session_state.role = assignment_type
            
            # Save to cookies - DON'T call save() as it will be saved on rerun
            cookies["assignment_class"] = str(assignment_data["class_name"])
            cookies["assignment_term"] = str(assignment_data["term"])
            cookies["assignment_session"] = str(assignment_data["session"])
            cookies["assignment_subject"] = subject_name
            cookies["assignment_type"] = assignment_type
            cookies["role"] = assignment_type  # Update role in cookies
            # cookies.save()  # REMOVED - causes duplicate key error
            
            logger.info(f"Assignment saved for user {st.session_state.get('username')}: {assignment_data['class_name']} ({assignment_type})")
            return True
            
        except Exception as e:
            logger.error(f"Error saving assignment: {str(e)}")
            return False
    
    @staticmethod
    def clear_session(cookies) -> bool:
        """
        Clear user session and cookies with proper browser cleanup
        
        Args:
            cookies: Cookie manager instance
            
        Returns:
            True if cleared successfully, False otherwise
        """
        try:
            # Clear cookies by setting them to empty and saving
            if cookies:
                cookie_keys = [
                    "authenticated", "user_id", "role", "username", "login_time",
                    "assignment_class", "assignment_term", "assignment_session", 
                    "assignment_subject", "assignment_type"
                ]
                
                for key in cookie_keys:
                    cookies[key] = ""
                
                cookies.save()
                
                # Force browser to delete cookies
                SessionManager._clear_browser_cookies()
            
            # Clear session state
            session_keys = [
                "authenticated", "user_id", "role", "username", "login_time",
                "assignment", "last_activity", "session_id", "assignment_just_selected"
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
        """Force browser to delete cookies by setting expiry to past date"""
        cookie_names = [
            "authenticated", "user_id", "role", "username", "login_time",
            "assignment_class", "assignment_term", "assignment_session", 
            "assignment_subject", "assignment_type"
        ]
        
        # Set cookies to expire immediately
        script_parts = []
        for name in cookie_names:
            script_parts.append(
                f'document.cookie = "{name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax";'
            )
        
        # Also clear from local storage (if any scripts added data there)
        script_parts.append('localStorage.clear();')
        script_parts.append('sessionStorage.clear();')
        
        script = f"<script>{''.join(script_parts)}</script>"
        st.markdown(script, unsafe_allow_html=True)
    
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
    
    @staticmethod
    def restore_from_cookies(cookies) -> bool:
        """
        Restore session from cookies if valid
        
        Args:
            cookies: Cookie manager instance
            
        Returns:
            True if session restored, False otherwise
        """
        try:
            if cookies.get("authenticated") == "true" and cookies.get("user_id"):
                # Restore session state from cookies
                st.session_state.authenticated = True
                st.session_state.user_id = int(cookies["user_id"])
                
                # Handle role - can be empty string for teachers without assignment
                role = cookies.get("role", "")
                st.session_state.role = role if role else None
                
                st.session_state.username = cookies.get("username", "")
                st.session_state.login_time = cookies.get("login_time", "")
                st.session_state.last_activity = datetime.now()
                
                # Restore assignment if exists
                if (cookies.get("assignment_class") and 
                    cookies.get("assignment_term") and 
                    cookies.get("assignment_session")):
                    st.session_state.assignment = {
                        "class_name": cookies["assignment_class"],
                        "term": cookies["assignment_term"],
                        "session": cookies["assignment_session"],
                        "subject_name": cookies.get("assignment_subject", ""),
                        "assignment_type": cookies.get("assignment_type", "class_teacher")
                    }
                    
                    # Update role from assignment if not admin
                    if not st.session_state.role or st.session_state.role not in ["admin", "superadmin"]:
                        st.session_state.role = cookies.get("assignment_type", "class_teacher")
                
                logger.info(f"Session restored for user: {st.session_state.username} (Role: {st.session_state.role or 'Teacher'})")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error restoring session from cookies: {e}")
            return False