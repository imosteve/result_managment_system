# app_manager.py
import streamlit as st
import logging
import os
from typing import Dict, Callable, Optional
from streamlit_cookies_manager import EncryptedCookieManager

from config import APP_CONFIG, COOKIE_PASSWORD
from database import create_tables, get_all_classes
from main_utils import inject_login_css, render_page_header

logger = logging.getLogger(__name__)

class ApplicationManager:
    """Main application management class"""
    
    def __init__(self):
        self.setup_page_config()
        self.setup_custom_css()
        
    def setup_page_config(self):
        """Setup Streamlit page configuration"""
        try:
            st.set_page_config(
                page_title=APP_CONFIG["page_title"],
                page_icon="🎓",
                layout="wide",
                initial_sidebar_state="expanded",
                menu_items={
                    'Get Help': None,
                    'Report a bug': None,
                    'About': f"{APP_CONFIG['app_name']} v{APP_CONFIG['version']}"
                }
            )
        except st.errors.StreamlitAPIException:
            # Page config already set, ignore
            pass
   
    def setup_custom_css(self):
        """Setup custom CSS styling with mobile responsiveness"""
        try:
            inject_login_css("templates/main_styles.css")
        except Exception as e:
            logger.warning(f"Could not load main styles: {e}")

        # st.markdown("""
        # <style>
        # 
        # </style>
        # """, unsafe_allow_html=True)

    def initialize_mobile_support(self):
            """Initialize mobile-specific features without localStorage usage"""
            
            # Add mobile detection and responsive JavaScript
            st.markdown("""
            <script>
            // Mobile detection
            function isMobile() {
                return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
            }
            
            // Handle mobile viewport
            if (isMobile()) {
                const viewport = document.querySelector('meta[name="viewport"]');
                if (viewport) {
                    viewport.setAttribute('content', 
                        'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0');
                } else {
                    const newViewport = document.createElement('meta');
                    newViewport.name = 'viewport';
                    newViewport.content = 'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0';
                    document.head.appendChild(newViewport);
                }
                
                // Add mobile-specific body class
                document.body.classList.add('mobile-device');
                
                // Set mobile flag in session storage (not localStorage)
                sessionStorage.setItem('is_mobile', 'true');
            }
            
            // Prevent zoom on input focus (iOS Safari)
            if (/iPad|iPhone|iPod/.test(navigator.userAgent)) {
                const inputs = document.querySelectorAll('input[type="text"], input[type="password"], select, textarea');
                inputs.forEach(input => {
                    input.style.fontSize = '16px';
                });
            }
            
            // Enhanced cookie settings for mobile persistence
            function setCookieWithMobileSupport(name, value, days = 7) {
                const expires = new Date();
                expires.setTime(expires.getTime() + (days * 24 * 60 * 60 * 1000));
                document.cookie = `${name}=${value}; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;
            }
            
            // Make cookie function available globally
            window.setCookieWithMobileSupport = setCookieWithMobileSupport;
            </script>
            """, unsafe_allow_html=True)
            
            # Set mobile flag in session state if detected
            if 'is_mobile' not in st.session_state:
                st.session_state.is_mobile = False  # Will be updated by client-side detection
    
    def initialize_database(self) -> bool:
        """Initialize database with error handling"""
        try:
            create_tables()

            logger.info("Database tables initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Database initialization failed: {str(e)}")
            st.error("❌ Database initialization failed. Please contact system administrator.")
            return False

    def initialize_mobile_support(self):
        """Initialize mobile-specific features and session restoration"""
        
        # Set mobile-friendly page config
        st.set_page_config(
            page_title="Student Results",
            page_icon="📊",
            layout="centered",  # Better for mobile
            initial_sidebar_state="collapsed",  # Start with sidebar collapsed on mobile
            menu_items={
                'Get Help': None,
                'Report a bug': None,
                'About': None
            }
        )
        
        # Add mobile detection and session restoration
        st.markdown("""
        <script>
        // Mobile detection
        function isMobile() {
            return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
        }
        
        // Enhanced session restoration for mobile
        function restoreSessionOnMobile() {
            if (typeof(Storage) !== "undefined" && isMobile()) {
                const authBackup = localStorage.getItem('auth_backup');
                const assignmentBackup = localStorage.getItem('assignment_backup');
                
                if (authBackup) {
                    try {
                        const authData = JSON.parse(authBackup);
                        const timestamp = new Date(authData.timestamp);
                        const now = new Date();
                        const diffHours = (now - timestamp) / (1000 * 60 * 60);
                        
                        // Session valid for 7 days
                        if (diffHours < 168) {
                            // Set cookies from localStorage backup
                            document.cookie = `authenticated=${authData.authenticated}; path=/; SameSite=Lax; max-age=604800`;
                            document.cookie = `user_id=${authData.user_id}; path=/; SameSite=Lax; max-age=604800`;
                            document.cookie = `role=${authData.role}; path=/; SameSite=Lax; max-age=604800`;
                            document.cookie = `username=${authData.username}; path=/; SameSite=Lax; max-age=604800`;
                            document.cookie = `login_time=${authData.login_time || ''}; path=/; SameSite=Lax; max-age=604800`;
                            
                            console.log('Session restored from localStorage for mobile');
                        } else {
                            localStorage.removeItem('auth_backup');
                        }
                    } catch (e) {
                        console.error('Error restoring auth session:', e);
                        localStorage.removeItem('auth_backup');
                    }
                }
                
                if (assignmentBackup) {
                    try {
                        const assignmentData = JSON.parse(assignmentBackup);
                        const timestamp = new Date(assignmentData.timestamp);
                        const now = new Date();
                        const diffHours = (now - timestamp) / (1000 * 60 * 60);
                        
                        if (diffHours < 168) {
                            document.cookie = `assignment_class=${assignmentData.class_name}; path=/; SameSite=Lax; max-age=604800`;
                            document.cookie = `assignment_term=${assignmentData.term}; path=/; SameSite=Lax; max-age=604800`;
                            document.cookie = `assignment_session=${assignmentData.session}; path=/; SameSite=Lax; max-age=604800`;
                            document.cookie = `assignment_subject=${assignmentData.subject_name}; path=/; SameSite=Lax; max-age=604800`;
                            
                            console.log('Assignment restored from localStorage for mobile');
                        } else {
                            localStorage.removeItem('assignment_backup');
                        }
                    } catch (e) {
                        console.error('Error restoring assignment:', e);
                        localStorage.removeItem('assignment_backup');
                    }
                }
            }
        }
        
        // Run on page load
        document.addEventListener('DOMContentLoaded', restoreSessionOnMobile);
        
        // Also run immediately in case DOMContentLoaded already fired
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', restoreSessionOnMobile);
        } else {
            restoreSessionOnMobile();
        }
        
        // Handle mobile viewport
        if (isMobile()) {
            const viewport = document.querySelector('meta[name="viewport"]');
            if (viewport) {
                viewport.setAttribute('content', 
                    'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0');
            } else {
                const newViewport = document.createElement('meta');
                newViewport.name = 'viewport';
                newViewport.content = 'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0';
                document.head.appendChild(newViewport);
            }
            
            // Add mobile-specific body class
            document.body.classList.add('mobile-device');
        }
        
        // Prevent zoom on input focus (iOS Safari)
        if (/iPad|iPhone|iPod/.test(navigator.userAgent)) {
            const inputs = document.querySelectorAll('input[type="text"], input[type="password"], select, textarea');
            inputs.forEach(input => {
                input.style.fontSize = '16px';
            });
        }
        </script>
        """, unsafe_allow_html=True)

    def initialize_cookies(self) -> Optional[EncryptedCookieManager]:
        """Initialize encrypted cookie manager with robust error handling"""
        try:
            cookies = EncryptedCookieManager(
                prefix=APP_CONFIG["cookie_prefix"],
                password=COOKIE_PASSWORD
            )
            
            # Store cookies in session state for access
            st.session_state["cookies"] = cookies
            logger.info("Cookie manager initialized successfully")
            return cookies
            
        except Exception as e:
            logger.error(f"Cookie manager initialization failed: {str(e)}")
            st.error("❌ Session management initialization failed. Please refresh the page.")
            return None

    def render_header(self):
        """Render application header"""
        st.markdown(f"""
        <div class="main-header">
            <h2>{APP_CONFIG['school_name']}</h2>
        </div>
        """, unsafe_allow_html=True)

    # app_manager.py - UPDATE the get_navigation_options method
    def get_navigation_options(self, role: str, username: str) -> Dict[str, Callable]:
        """Get navigation options based on user role with profile included"""
        try:
            # Import functions with error handling
            from app_sections import (
                manage_comments,
                manage_classes, register_students, manage_subjects, 
                enter_scores, view_broadsheet, generate_reports,
                system_dashboard, admin_panel, manage_comment_templates,
                next_term_info, user_profile
            )
            from auth.assignment_selection import select_assignment
            
            # Create user profile function
            profile_function = user_profile.create_user_info_page(role, username)
            
            base_options = {}
            
            if role == "superadmin":
                base_options = {
                    "👤 My Profile": profile_function,
                    "🔧 System Dashboard": system_dashboard.system_dashboard,
                    "👥 Admin Panel": admin_panel.admin_panel,
                    "🗓️ Next Term Info": next_term_info.next_term_info,
                    "📝 Comments Template": manage_comment_templates.manage_comment_templates,
                    "🏫 Manage Classes": manage_classes.create_class_section,
                    "👥 Register Students": register_students.register_students,
                    "📚 Manage Subjects": manage_subjects.add_subjects,
                    "📝 Enter Scores": enter_scores.enter_scores,
                    "📝 Manage Comments": manage_comments.manage_comments,
                    "📋 View Broadsheet": view_broadsheet.generate_broadsheet,
                    "📄 Generate Reports": generate_reports.report_card_section
                }
            elif role == "admin":
                base_options = {
                    "👤 My Profile": profile_function,
                    "👥 Admin Panel": admin_panel.admin_panel,
                    "🗓️ Next Term Info": next_term_info.next_term_info,
                    "📝 Comments Template": manage_comment_templates.manage_comment_templates,
                    "🏫 Manage Classes": manage_classes.create_class_section,
                    "👥 Register Students": register_students.register_students,
                    "📚 Manage Subjects": manage_subjects.add_subjects,
                    "📝 Enter Scores": enter_scores.enter_scores,
                    "📝 Manage Comments": manage_comments.manage_comments,
                    "📋 View Broadsheet": view_broadsheet.generate_broadsheet,
                    "📄 Generate Reports": generate_reports.report_card_section
                }
            elif role == "class_teacher":
                base_options = {
                    "👤 My Profile": profile_function,
                    "👥 Register Students": register_students.register_students,
                    "📚 Manage Subjects": manage_subjects.add_subjects,
                    "📝 Manage Comments": manage_comments.manage_comments,
                    "📋 View Broadsheet": view_broadsheet.generate_broadsheet,
                    "📄 Generate Reports": generate_reports.report_card_section,
                    "🔄 Change Assignment": select_assignment
                }
                
            elif role == "subject_teacher":
                base_options = {
                    "👤 My Profile": profile_function,
                    "📝 Enter Scores": enter_scores.enter_scores,
                    "📋 View Broadsheet": view_broadsheet.generate_broadsheet,
                    "🔄 Change Assignment": select_assignment
                }
            
            return base_options
            
        except ImportError as e:
            logger.error(f"Error importing navigation modules: {e}")
            # Return minimal navigation if imports fail
            return {
                "👤 My Profile": profile_function,
                "🔧 System Dashboard": system_dashboard.system_dashboard
            }
       
    # Add this method to ApplicationManager class in app_manager.py
    def handle_post_assignment_navigation(self, role: str):
        """
        Handle navigation after assignment selection
        Should be called in your main app flow
        """
        # Check if assignment was just selected
        if st.session_state.get('assignment_just_selected'):
            # Clear the flag
            del st.session_state['assignment_just_selected']
            
            # Get the first available section for the role
            nav_options = self.get_navigation_options(role)
            
            if nav_options:
                # Get the first menu item (skip dashboard/admin panel if exists)
                first_section = None
                for key in nav_options.keys():
                    if "Dashboard" not in key and "Admin Panel" not in key and "Change Assignment" not in key:
                        first_section = key
                        break
                
                if not first_section:
                    # If no other option, use the first one
                    first_section = list(nav_options.keys())[0]
                
                # Set this as the selected page
                st.session_state.selected_page = first_section
                logger.info(f"Navigating to first section after assignment: {first_section}")
