# auth/session_manager.py
"""Session management for authentication with mobile persistence"""

import streamlit as st
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class SessionManager:
    """Handles user session management with mobile support"""
    
    @staticmethod
    def create_session(user: Dict[str, Any], cookies) -> bool:
        """
        Create a new user session with enhanced mobile persistence
        
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
            
            # Enhanced cookie settings for mobile persistence
            cookie_options = {
                'expires_at': datetime.now().timestamp() + (7 * 24 * 3600),  # 7 days
                'same_site': 'lax',  # Better for mobile
                'secure': False,  # Set to True in production with HTTPS
                'path': '/'
            }
            
            # Set cookies with enhanced options
            cookies["authenticated"] = "true"
            cookies["user_id"] = str(user["id"])
            cookies["role"] = user["role"]
            cookies["username"] = user["username"]
            cookies["login_time"] = st.session_state.login_time
            
            # Save with options if supported
            try:
                cookies.save()
            except Exception as cookie_error:
                logger.warning(f"Cookie save with options failed: {cookie_error}")
                # Fallback to basic save
                cookies.save()
            
            # Store session backup in session_state instead of localStorage
            SessionManager._save_to_session_backup(user)
            
            logger.info(f"Session created for user: {user['username']} (ID: {user['id']})")
            return True
            
        except Exception as e:
            logger.error(f"Error creating session for user {user.get('username', 'unknown')}: {str(e)}")
            return False
    
    @staticmethod
    def _save_to_session_backup(user: Dict[str, Any]):
        """Save session data to session_state as backup for mobile (replaces localStorage)"""
        try:
            st.session_state.session_backup = {
                'authenticated': 'true',
                'user_id': user["id"],
                'role': user["role"],
                'username': user["username"],
                'timestamp': datetime.now().isoformat()
            }
            logger.debug("Session backup saved to session_state")
        except Exception as e:
            logger.warning(f"Failed to save session backup: {e}")
    
    @staticmethod
    def restore_session_from_backup():
        """Attempt to restore session from session_state backup"""
        try:
            backup = st.session_state.get('session_backup')
            if backup:
                timestamp = datetime.fromisoformat(backup['timestamp'])
                now = datetime.now()
                diff_hours = (now - timestamp).total_seconds() / 3600
                
                if diff_hours < 168:  # 7 days
                    st.session_state.authenticated = True
                    st.session_state.user_id = backup['user_id']
                    st.session_state.role = backup['role']
                    st.session_state.username = backup['username']
                    st.session_state.login_time = backup.get('login_time', '')
                    st.session_state.last_activity = datetime.now()
                    logger.info("Session restored from backup")
                    return True
                else:
                    # Clear expired backup
                    if 'session_backup' in st.session_state:
                        del st.session_state['session_backup']
            return False
        except Exception as e:
            logger.warning(f"Failed to restore from backup: {e}")
            return False
    
    @staticmethod
    def save_assignment(assignment_data: Dict[str, Any], cookies) -> bool:
        """
        Save user assignment to session and cookies with mobile persistence
        
        Args:
            assignment_data: Assignment data
            cookies: Cookie manager instance
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Handle None values properly
            subject_name = assignment_data.get("subject_name") or ""
            
            st.session_state.assignment = {
                "class_name": assignment_data["class_name"],
                "term": assignment_data["term"],
                "session": assignment_data["session"],
                "subject_name": subject_name
            }
            
            # Ensure all cookie values are strings, not None
            cookies["assignment_class"] = str(assignment_data["class_name"])
            cookies["assignment_term"] = str(assignment_data["term"])
            cookies["assignment_session"] = str(assignment_data["session"])
            cookies["assignment_subject"] = subject_name
            cookies.save()
            
            # Save assignment to session_state backup instead of localStorage
            SessionManager._save_assignment_to_session_backup(st.session_state.assignment)
            
            logger.info(f"Assignment saved for user {st.session_state.get('username')}: {assignment_data['class_name']}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving assignment: {str(e)}")
            return False
    
    @staticmethod
    def _save_assignment_to_session_backup(assignment_data: Dict[str, Any]):
        """Save assignment data to session_state backup"""
        try:
            st.session_state.assignment_backup = {
                'class_name': assignment_data["class_name"],
                'term': assignment_data["term"],
                'session': assignment_data["session"],
                'subject_name': assignment_data["subject_name"],
                'timestamp': datetime.now().isoformat()
            }
            logger.debug("Assignment backup saved to session_state")
        except Exception as e:
            logger.warning(f"Failed to save assignment backup: {e}")
    
    @staticmethod
    def clear_session(cookies) -> bool:
        """
        Clear user session and cookies with mobile cleanup
        
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
                
                # Clear browser cookies (without localStorage)
                SessionManager._clear_browser_cookies()
            
            # Clear session state
            session_keys = [
                "authenticated", "user_id", "role", "username", "login_time",
                "assignment", "last_activity", "session_id", "session_backup", "assignment_backup"
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
        """Clear browser cookies only (removed localStorage clearing)"""
        cookie_names = [
            "authenticated", "user_id", "role", "username", "login_time",
            "assignment_class", "assignment_term", "assignment_session", "assignment_subject"
        ]
        
        script_parts = []
        for name in cookie_names:
            script_parts.append(
                f'document.cookie = "{name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax";'
            )
        
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
    def validate_mobile_session(cookies) -> bool:
        """Validate session specifically for mobile devices"""
        try:
            # Check cookies first
            if (cookies.get("authenticated") == "true" and 
                cookies.get("user_id") and 
                cookies.get("role")):
                
                # Restore session state from cookies
                st.session_state.authenticated = True
                st.session_state.user_id = int(cookies["user_id"])
                st.session_state.role = cookies["role"]
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
                        "subject_name": cookies.get("assignment_subject", "")
                    }
                
                logger.info(f"Mobile session validated for user: {st.session_state.username}")
                return True
            
            # If cookies fail, try session_state backup
            return SessionManager.restore_session_from_backup()
            
        except Exception as e:
            logger.error(f"Error validating mobile session: {e}")
            return False