# app_manager.py
import streamlit as st
import logging
import os
from typing import Dict, Callable, Optional
from streamlit_cookies_manager import EncryptedCookieManager

from app_sections import admin_panel
from config import APP_CONFIG, COOKIE_PASSWORD
from database import create_tables, get_database_stats
from utils import inject_login_css, render_page_header

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
        MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        # header {visibility: hidden;}

        .stApp {
            background-color: #e5ece4;
        }
        
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

    def render_user_info(self, role: str, username: str):
        """Render user information in sidebar"""
        with st.sidebar:
            st.markdown(f"""
            <div class="user-info-card">
                <h4>👤 User Information</h4>
                <p><strong>Username:</strong> {username.title()}</p>
                <p><strong>Role:</strong> {role.replace('_', ' ').title()}</p>
                <p><strong>Login Time:</strong> {st.session_state.get('login_time', 'Unknown')}</p>
            </div>
            """, unsafe_allow_html=True)

            if st.button("🔄 Refresh", key="refresh_data", width="stretch"):
                    st.rerun()

    def get_navigation_options(self, role: str) -> Dict[str, Callable]:
        """Get navigation options based on user role"""
        try:
            # Import functions with error handling
            from app_sections import (
                manage_comments,
                manage_classes, register_students, manage_subjects, 
                enter_scores, view_broadsheet, generate_reports
            )
            from auth.assignment_selection import select_assignment
            
            base_options = {}
            
            if role == "superadmin":
                base_options = {
                    "🏠 Dashboard": self.render_dashboard,
                    "👥 Admin Panel": admin_panel.admin_panel,
                    "🏫 Manage Classes": manage_classes.create_class_section,
                    "👥 Register Students": register_students.register_students,
                    "📚 Manage Subjects": manage_subjects.add_subjects,
                    "📝 Enter Scores": enter_scores.enter_scores,
                    "📋 View Broadsheet": view_broadsheet.generate_broadsheet,
                    "📝 Manage Comments": manage_comments.manage_comments,
                    "📄 Generate Reports": generate_reports.report_card_section
                }
            elif role == "admin":
                base_options = {
                    "👥 Admin Panel": admin_panel.admin_panel,
                    "🏫 Manage Classes": manage_classes.create_class_section,
                    "👥 Register Students": register_students.register_students,
                    "📚 Manage Subjects": manage_subjects.add_subjects,
                    "📝 Enter Scores": enter_scores.enter_scores,
                    "📋 View Broadsheet": view_broadsheet.generate_broadsheet,
                    "📝 Manage Comments": manage_comments.manage_comments,
                    "📄 Generate Reports": generate_reports.report_card_section
                }
            elif role == "class_teacher":
                base_options = {
                    "👥 Register Students": register_students.register_students,
                    "📚 Manage Subjects": manage_subjects.add_subjects,
                    "📝 Enter Scores": enter_scores.enter_scores,
                    "📋 View Broadsheet": view_broadsheet.generate_broadsheet,
                    "📝 Manage Comments": manage_comments.manage_comments,
                    "📄 Generate Reports": generate_reports.report_card_section
                }
            elif role == "subject_teacher":
                base_options = {
                    "📝 Enter Scores": enter_scores.enter_scores,
                    "📋 View Broadsheet": view_broadsheet.generate_broadsheet,
                }
            
            # # Add assignment selection for teachers
            # if role in ["class_teacher", "subject_teacher"]:
            #     base_options["🔄 Change Assignment"] = select_assignment
            
            return base_options
            
        except ImportError as e:
            logger.error(f"Error importing navigation modules: {e}")
            # Return minimal navigation if imports fail
            return {
                "🏠 Dashboard": self.render_dashboard
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

    def render_dashboard(self):
        """Render dashboard with system statistics"""
        render_page_header("📊 System Dashboard")
        try:
            # Get database statistics
            stats = get_database_stats()
            
            # Create columns for metrics
            col1, col2, col3, col4 = st.columns(4)
            
            inject_login_css("templates/metrics_styles.css")
            # Display metrics with custom style
            with col1:
                st.markdown(f"<div class='custom-metric'><div class='label'>🏫 Classes</div><div class='value'>{stats.get('classes', 0)}</div></div>", unsafe_allow_html=True)
            with col2:
                st.markdown(f"<div class='custom-metric'><div class='label'>👥 Students</div><div class='value'>{stats.get('students', 0)}</div></div>", unsafe_allow_html=True)
            with col3:
                st.markdown(f"<div class='custom-metric'><div class='label'>📚 Subjects</div><div class='value'>{stats.get('subjects', 0)}</div></div>", unsafe_allow_html=True)
            with col4:
                st.markdown(f"<div class='custom-metric'><div class='label'>📝 Scores</div><div class='value'>{stats.get('scores', 0)}</div></div>", unsafe_allow_html=True)


            # Role-specific dashboard content
            role = st.session_state.get('role')
            self.render_role_specific_dashboard(role)
            
        except Exception as e:
            logger.error(f"Error rendering dashboard: {str(e)}")
            st.error("❌ Error loading dashboard data.")
            
            # Show basic info even if stats fail
            st.info("📊 Dashboard data temporarily unavailable.")

    def render_role_specific_dashboard(self, role: str):
        """Render role-specific dashboard content"""
        st.markdown("---")
        
        if role in "superadmin":
            st.subheader("🔧 Admin Tools")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("📊 System Health Check", type="secondary"):
                    self.perform_health_check()
            
            with col2:
                if st.button("🗄️ Database Backup", type="secondary"):
                    st.info("💡 Database backup functionality would be implemented here.")
            
            with col3:
                if st.button("📋 Activity Logs", type="secondary"):
                    st.info("💡 Activity log viewer would be implemented here.")
        
        elif role in ["class_teacher", "subject_teacher"]:
            st.subheader("📋 Quick Actions")
            assignment = st.session_state.get('assignment')
            
            if assignment:
                st.info(f"📌 Current Assignment: {assignment.get('class_name', 'N/A')} - {assignment.get('subject_name', 'All Subjects')}")
            else:
                st.warning("⚠️ No assignment selected. Logout and login again to select an assignment to continue.")

    def perform_health_check(self):
        """Perform system health check"""
        with st.spinner("🔍 Performing health check..."):
            import time
            time.sleep(1)  # Simulate health check
            
            checks = {
                "Database Connection": self.check_database_connection(),
                "Session Management": self.check_session_management(),
                "File System": self.check_file_system(),
                "Memory Usage": self.check_memory_usage()
            }
            
            st.subheader("🏥 System Health Report")
            for check_name, status in checks.items():
                if status:
                    st.success(f"✅ {check_name}: OK")
                else:
                    st.error(f"❌ {check_name}: Issues detected")

    def check_database_connection(self) -> bool:
        """Check database connection health"""
        try:
            get_database_stats()
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    def check_session_management(self) -> bool:
        """Check session management health"""
        return 'cookies' in st.session_state and st.session_state.cookies is not None

    def check_file_system(self) -> bool:
        """Check file system health"""
        try:
            required_dirs = ['logs', 'data', 'templates']
            for directory in required_dirs:
                if not os.path.exists(directory):
                    try:
                        os.makedirs(directory, exist_ok=True)
                        logger.info(f"Created directory: {directory}")
                    except Exception as e:
                        logger.warning(f"Could not create directory {directory}: {e}")
                        return False
            
            # Check if directories are writable
            for directory in required_dirs:
                if os.path.exists(directory):
                    test_file = os.path.join(directory, '.test_write')
                    try:
                        with open(test_file, 'w') as f:
                            f.write('test')
                        os.remove(test_file)
                    except Exception as e:
                        logger.warning(f"Directory {directory} is not writable: {e}")
                        return False
            
            return True
        except Exception as e:
            logger.error(f"File system check failed: {e}")
            return False

    def check_memory_usage(self) -> bool:
        """Check memory usage (simplified)"""
        try:
            import psutil
            memory_percent = psutil.virtual_memory().percent
            return memory_percent < 80  # Consider healthy if less than 80%
        except ImportError:
            logger.info("psutil not available, skipping memory check")
            return True  # If psutil not available, assume OK
        except Exception as e:
            logger.error(f"Memory check failed: {e}")
            return False