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
        # try:
        #     inject_login_css("templates/main_styles.css")
        # except Exception as e:
        #     logger.warning(f"Could not load main styles: {e}")

        st.markdown("""
        <style>
        #MainMenu {visibility: visible;}
        footer {visibility: hidden;}
        # header {visibility: hidden;}

        # .stApp {
        #     background-color: #e5ece4;
        # }
        
        /* Responsive container */
        .block-container {
            padding-top: 1rem;
            padding-left: 1rem;
            padding-right: 1rem;
            max-width: 100% !important;
        }
        
        /* Desktop styles */
        @media (min-width: 768px) {
            .block-container {
                max-width: 500px !important;
                # margin: auto;
                padding-top: 2rem;
            }
        }
        
        /* Mobile specific styles */
        @media (max-width: 767px) {
            .block-container {
                padding-top: 0.5rem !important;
                padding-left: 0.5rem !important;
                padding-right: 0.5rem !important;
            }
            
            .main-header h2 {
                font-size: 20px !important;
                padding: 10px !important;
            }
            
            /* Make buttons full width on mobile */
            .stButton > button {
                width: 100% !important;
                margin-bottom: 0.5rem;
            }
            
            /* Responsive selectbox */
            .stSelectbox > div > div {
                font-size: 14px;
            }
            
            /* Responsive text inputs */
            .stTextInput > div > div > input {
                font-size: 16px; /* Prevents zoom on iOS */
            }
            
            /* Responsive metrics */
            .custom-metric {
                margin-bottom: 1rem !important;
            }
            
            /* Responsive dataframes */
            .stDataFrame {
                font-size: 12px !important;
            }
            
            /* Fix sidebar on mobile */
            .css-1d391kg {
                padding-top: 1rem;
            }
        }
        
        .main-header {
            background: linear-gradient(135deg, #2E8B57, #228B22);
            # padding: 15px;
            border-radius: 5px;
            margin-bottom: 5px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        .main-header h2 {
            color: white;
            font-size: 35px;
            font-weight: bold;
            text-align: center;
            margin: 0;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
            line-height: 1.2;
        }
        
        .user-info-card {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
        }
        
        .error-container {
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
            padding: 12px;
            border-radius: 5px;
            margin: 10px 0;
        }
        
        .success-container {
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
            padding: 12px;
            border-radius: 5px;
            margin: 10px 0;
        }
        
        .warning-container {
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            color: #856404;
            padding: 12px;
            border-radius: 5px;
            margin: 10px 0;
        }
        
        /* Ensure touch targets are large enough on mobile */
        @media (max-width: 767px) {
            button, .stSelectbox, .stTextInput {
                min-height: 44px;
            }
        }
        
        /* Responsive tables */
        @media (max-width: 767px) {
            .stDataFrame table {
                font-size: 11px !important;
            }
            
            .stDataFrame th, .stDataFrame td {
                padding: 4px !important;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                max-width: 80px;
            }
        }
        
        /* Mobile navigation improvements */
        @media (max-width: 767px) {
            .css-1v0mbdj {
                padding: 0.5rem;
            }
            
            .css-1y4p8pa {
                padding: 0.5rem;
            }
        }
        </style>
        """, unsafe_allow_html=True)

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

    # def render_user_info(self, role: str, username: str):
    #     """Render user information in sidebar - UPDATED to handle None role"""
    #     with st.sidebar:
    #         # Format role display - handle None for teachers
    #         if role is None:
    #             role_display = "Teacher (No Assignment)"
    #         elif role in ["admin", "superadmin"]:
    #             role_display = role.replace('_', ' ').title()
    #         else:
    #             role_display = role.replace('_', ' ').title()

    #         with st.expander("👤 User Information"):
    #             st.write(f"**Username**: {username.title()}")
    #             st.write(f"**Role**: {role_display}")
    #             st.write(f"**Login Time**: {st.session_state.get('login_time', 'Unknown')}")

    #         if st.button("🔄 Refresh", key="refresh_data", width="stretch", type="secondary"):
    #             st.rerun()

    # # app_manager.py - UPDATE the get_navigation_options method
    # def get_navigation_options(self, role: str) -> Dict[str, Callable]:
    #     """Get navigation options based on user role"""
    #     try:
    #         # Import functions with error handling
    #         from app_sections import (
    #             manage_comments,
    #             manage_classes, register_students, manage_subjects, 
    #             enter_scores, view_broadsheet, generate_reports,
    #             system_dashboard, admin_panel, manage_comment_templates,
    #             next_term_info
    #         )
    #         from auth.assignment_selection import select_assignment
    #         base_options = {}
            
    #         if role == "superadmin":
    #             base_options = {
    #                 "🔧 System Dashboard": system_dashboard.system_dashboard,
    #                 "👥 Admin Panel": admin_panel.admin_panel,
    #                 "🗓️ Next Term Info": next_term_info.next_term_info,
    #                 "📝 Comments Template": manage_comment_templates.manage_comment_templates,
    #                 "🏫 Manage Classes": manage_classes.create_class_section,
    #                 "👥 Register Students": register_students.register_students,
    #                 "📚 Manage Subjects": manage_subjects.add_subjects,
    #                 "📝 Enter Scores": enter_scores.enter_scores,
    #                 "📝 Manage Comments": manage_comments.manage_comments,
    #                 "📋 View Broadsheet": view_broadsheet.generate_broadsheet,
    #                 "📄 Generate Reports": generate_reports.report_card_section
    #             }
    #         elif role == "admin":
    #             base_options = {
    #                 "👥 Admin Panel": admin_panel.admin_panel,
    #                 "🗓️ Next Term Info": next_term_info.next_term_info,
    #                 "📝 Comments Template": manage_comment_templates.manage_comment_templates,
    #                 "🏫 Manage Classes": manage_classes.create_class_section,
    #                 "👥 Register Students": register_students.register_students,
    #                 "📚 Manage Subjects": manage_subjects.add_subjects,
    #                 "📝 Enter Scores": enter_scores.enter_scores,
    #                 "📝 Manage Comments": manage_comments.manage_comments,
    #                 "📋 View Broadsheet": view_broadsheet.generate_broadsheet,
    #                 "📄 Generate Reports": generate_reports.report_card_section
    #             }
    #         elif role == "class_teacher":
    #             base_options = {
    #                 "👥 Register Students": register_students.register_students,
    #                 "📚 Manage Subjects": manage_subjects.add_subjects,
    #                 "📝 Manage Comments": manage_comments.manage_comments,
    #                 "📋 View Broadsheet": view_broadsheet.generate_broadsheet,
    #                 "📄 Generate Reports": generate_reports.report_card_section,
    #                 "🔄 Change Assignment": select_assignment
    #             }
                
    #         elif role == "subject_teacher":
    #             base_options = {
    #                 "📝 Enter Scores": enter_scores.enter_scores,
    #                 "📋 View Broadsheet": view_broadsheet.generate_broadsheet,
    #                 "🔄 Change Assignment": select_assignment
    #             }
            
    #         return base_options
            
    #     except ImportError as e:
    #         logger.error(f"Error importing navigation modules: {e}")
    #         # Return minimal navigation if imports fail
    #         return {
    #             "🔧 System Dashboard": system_dashboard.system_dashboard
    #         }
    
    # app_manager.py - UPDATED METHODS
    def get_navigation_options(self, role: str) -> dict:
        """
        Get navigation options organized by sections based on user role
        
        Returns:
            Dict with section names as keys and list of page configs as values
            Each page config is a dict with 'title', 'icon', 'function', and optional 'default'
        """
        try:
            # Import functions with error handling
            from app_sections import (
                manage_comments,
                manage_classes, register_students, manage_subjects, 
                enter_scores, view_broadsheet, generate_reports,
                system_dashboard, admin_panel, manage_comment_templates,
                next_term_info
            )
            from auth.assignment_selection import select_assignment
            
            navigation_structure = {}
            
            if role == "superadmin":
                navigation_structure = {
                    "System Management": [
                        {
                            "title": "System Dashboard",
                            "icon": ":material/dashboard:",
                            "function": system_dashboard.system_dashboard,
                            "default": True
                        },
                        {
                            "title": "Admin Panel",
                            "icon": ":material/admin_panel_settings:",
                            "function": admin_panel.admin_panel
                        },
                        {
                            "title": "Next Term Info",
                            "icon": ":material/event:",
                            "function": next_term_info.next_term_info
                        },
                        {
                            "title": "Comments Template",
                            "icon": ":material/comment:",
                            "function": manage_comment_templates.manage_comment_templates
                        }
                    ],
                    "Academic Management": [
                        {
                            "title": "Manage Classes",
                            "icon": ":material/school:",
                            "function": manage_classes.create_class_section
                        },
                        {
                            "title": "Register Students",
                            "icon": ":material/group_add:",
                            "function": register_students.register_students
                        },
                        {
                            "title": "Manage Subjects",
                            "icon": ":material/book:",
                            "function": manage_subjects.add_subjects
                        }
                    ],
                    "Assessment & Reports": [
                        {
                            "title": "Enter Scores",
                            "icon": ":material/edit_note:",
                            "function": enter_scores.enter_scores
                        },
                        {
                            "title": "Manage Comments",
                            "icon": ":material/rate_review:",
                            "function": manage_comments.manage_comments
                        },
                        {
                            "title": "View Broadsheet",
                            "icon": ":material/table_chart:",
                            "function": view_broadsheet.generate_broadsheet
                        },
                        {
                            "title": "Generate Reports",
                            "icon": ":material/description:",
                            "function": generate_reports.report_card_section
                        }
                    ]
                }
                
            elif role == "admin":
                navigation_structure = {
                    "Administration": [
                        {
                            "title": "Admin Panel",
                            "icon": ":material/admin_panel_settings:",
                            "function": admin_panel.admin_panel,
                            "default": True
                        },
                        {
                            "title": "Next Term Info",
                            "icon": ":material/event:",
                            "function": next_term_info.next_term_info
                        },
                        {
                            "title": "Comments Template",
                            "icon": ":material/comment:",
                            "function": manage_comment_templates.manage_comment_templates
                        }
                    ],
                    "Academic Management": [
                        {
                            "title": "Manage Classes",
                            "icon": ":material/school:",
                            "function": manage_classes.create_class_section
                        },
                        {
                            "title": "Register Students",
                            "icon": ":material/group_add:",
                            "function": register_students.register_students
                        },
                        {
                            "title": "Manage Subjects",
                            "icon": ":material/book:",
                            "function": manage_subjects.add_subjects
                        }
                    ],
                    "Assessment & Reports": [
                        {
                            "title": "Enter Scores",
                            "icon": ":material/edit_note:",
                            "function": enter_scores.enter_scores
                        },
                        {
                            "title": "Manage Comments",
                            "icon": ":material/rate_review:",
                            "function": manage_comments.manage_comments
                        },
                        {
                            "title": "View Broadsheet",
                            "icon": ":material/table_chart:",
                            "function": view_broadsheet.generate_broadsheet
                        },
                        {
                            "title": "Generate Reports",
                            "icon": ":material/description:",
                            "function": generate_reports.report_card_section
                        }
                    ]
                }
                
            elif role == "class_teacher":
                navigation_structure = {
                    "Class Management": [
                        {
                            "title": "Register Students",
                            "icon": ":material/group_add:",
                            "function": register_students.register_students,
                            "default": True
                        },
                        {
                            "title": "Manage Subjects",
                            "icon": ":material/book:",
                            "function": manage_subjects.add_subjects
                        }
                    ],
                    "Assessment & Reports": [
                        {
                            "title": "Manage Comments",
                            "icon": ":material/rate_review:",
                            "function": manage_comments.manage_comments
                        },
                        {
                            "title": "View Broadsheet",
                            "icon": ":material/table_chart:",
                            "function": view_broadsheet.generate_broadsheet
                        },
                        {
                            "title": "Generate Reports",
                            "icon": ":material/description:",
                            "function": generate_reports.report_card_section
                        }
                    ],
                    "Settings": [
                        {
                            "title": "Change Assignment",
                            "icon": ":material/swap_horiz:",
                            "function": select_assignment
                        }
                    ]
                }
                    
            elif role == "subject_teacher":
                navigation_structure = {
                    "Teaching": [
                        {
                            "title": "Enter Scores",
                            "icon": ":material/edit_note:",
                            "function": enter_scores.enter_scores,
                            "default": True
                        },
                        {
                            "title": "View Broadsheet",
                            "icon": ":material/table_chart:",
                            "function": view_broadsheet.generate_broadsheet
                        }
                    ],
                    "Settings": [
                        {
                            "title": "Change Assignment",
                            "icon": ":material/swap_horiz:",
                            "function": select_assignment
                        }
                    ]
                }
            
            return navigation_structure
            
        except ImportError as e:
            logger.error(f"Error importing navigation modules: {e}")
            # Return minimal navigation if imports fail
            return {
                "System": [
                    {
                        "title": "Dashboard",
                        "icon": ":material/dashboard:",
                        "function": lambda: st.error("Navigation modules not available"),
                        "default": True
                    }
                ]
            }

    def render_user_info(self, role: str, username: str):
        """Render user information in sidebar with improved styling"""
        with st.sidebar:
            # User info card with better formatting
            st.markdown("""
            <style>
                .user-info-container {
                    background: linear-gradient(135deg, #2E8B57 0%, #228B22 100%);
                    padding: 15px;
                    border-radius: 10px;
                    margin-bottom: 20px;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                }
                .user-info-title {
                    color: white;
                    font-size: 14px;
                    font-weight: 600;
                    margin-bottom: 8px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }
                .user-info-detail {
                    color: white;
                    font-size: 13px;
                    margin: 5px 0;
                    padding: 5px 0;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.2);
                }
                .user-info-detail:last-child {
                    border-bottom: none;
                }
                .user-info-label {
                    font-weight: 600;
                    opacity: 0.9;
                }
                .user-info-value {
                    opacity: 1;
                    font-weight: 400;
                }
            </style>
            """, unsafe_allow_html=True)
            
            # Format role display - handle None for teachers
            if role is None:
                role_display = "Teacher (No Assignment)"
            elif role in ["admin", "superadmin"]:
                role_display = role.replace('_', ' ').title()
            else:
                role_display = role.replace('_', ' ').title()
            
            # Get login time
            login_time = st.session_state.get('login_time', 'Unknown')
            
            # Render user info card
            st.markdown(f"""
            <div class="user-info-container">
                <div class="user-info-title">👤 User Information</div>
                <div class="user-info-detail">
                    <span class="user-info-label">Username:</span> 
                    <span class="user-info-value">{username.title()}</span>
                </div>
                <div class="user-info-detail">
                    <span class="user-info-label">Role:</span> 
                    <span class="user-info-value">{role_display}</span>
                </div>
                <div class="user-info-detail">
                    <span class="user-info-label">Login:</span> 
                    <span class="user-info-value">{login_time}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Refresh button with better styling
            if st.button("🔄 Refresh", key="refresh_data", use_container_width=True, type="secondary"):
                st.rerun()

    def handle_navigation(self, role: str):
        """
        Handle navigation with sections similar to the sample code
        
        Args:
            role: User role
        """
        # Get navigation structure
        navigation_structure = self.get_navigation_options(role)
        
        if not navigation_structure:
            st.error("❌ No navigation options available for your role.")
            return
        
        # Convert navigation structure to st.navigation format
        pages_dict = {}
        default_page = None
        
        for section_name, pages_list in navigation_structure.items():
            section_pages = []
            
            for page_config in pages_list:
                # Create st.Page object
                page = st.Page(
                    page_config["function"],
                    title=page_config["title"],
                    icon=page_config["icon"],
                    default=page_config.get("default", False)
                )
                
                section_pages.append(page)
                
                # Track default page
                if page_config.get("default", False):
                    default_page = page
            
            pages_dict[section_name] = section_pages
        
        # Add custom styling for navigation
        st.markdown("""
            <style>
                /* Sidebar styling */
                [data-testid="stSidebarContent"] {
                    background-color: #f8f9fa;
                }
                
                /* Navigation section headers */
                [data-testid="stSidebarNav"] > div > div:first-child {
                    font-weight: 600;
                    color: #2E8B57;
                    font-size: 14px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    padding: 10px 12px 5px 12px;
                    margin-top: 10px;
                }
                
                /* Navigation links styling */
                [data-testid="stSidebarNav"] a {
                    background-color: white;
                    border-radius: 8px;
                    padding: 4px 12px;
                    margin: 2px 4px;
                    transition: all 0.2s ease;
                    border: 1px solid #e0e0e0;
                    font-size: 14px;
                }
                
                /* Navigation link hover effect */
                [data-testid="stSidebarNav"] a:hover {
                    background-color: #e8f5e9;
                    border-color: #2E8B57;
                    transform: translateX(3px);
                    box-shadow: 0 2px 4px rgba(46, 139, 87, 0.15);
                }
                
                /* Active/selected navigation link */
                [data-testid="stSidebarNav"] a[aria-current="page"] {
                    background: linear-gradient(135deg, #2E8B57, #228B22);
                    color: white !important;
                    border-color: #228B22;
                    font-weight: 600;
                    box-shadow: 0 3px 6px rgba(46, 139, 87, 0.3);
                }
                
                /* Active link icon and text color */
                [data-testid="stSidebarNav"] a[aria-current="page"] span,
                [data-testid="stSidebarNav"] a[aria-current="page"] div {
                    color: white !important;
                }
            </style>
        """, unsafe_allow_html=True)
        
        # Create navigation with sections
        pg = st.navigation(pages_dict)
        
        # Log navigation
        try:
            logger.info(f"User {st.session_state.get('username')} accessed {pg.title}")
        except:
            pass
        
        # Run the selected page
        try:
            pg.run()
        except Exception as e:
            logger.error(f"Error in navigation: {str(e)}")
            st.error(f"❌ Error loading page. Please try again or contact support.")
            
            # Show error details to admins
            if st.session_state.get('role') in ['superadmin', 'admin']:
                with st.expander("🔧 Error Details (Admin Only)"):
                    st.code(str(e))
        
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
