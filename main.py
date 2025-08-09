import streamlit as st
import logging
import os
import sys
from typing import Dict, Callable, Optional
from datetime import datetime, timedelta
import traceback
from streamlit_cookies_manager import EncryptedCookieManager

# Ensure logs directory exists BEFORE configuring logging
os.makedirs('logs', exist_ok=True)

# Import database and authentication modules
from database import create_tables, get_database_stats
from admin_interface import admin_interface
from manage_comments import manage_comments
from app_sections import (
    manage_classes, register_students, manage_subjects, 
    enter_scores, view_broadsheet, generate_reports
)
from auth import login, logout, select_assignment
from utils import inject_login_css

# Configure logging AFTER creating directories
def setup_logging():
    """Setup logging configuration with proper error handling"""
    try:
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/app.log', mode='a'),
                logging.StreamHandler(sys.stdout)
            ],
            force=True  # Force reconfiguration if already configured
        )
        return True
    except Exception as e:
        # Fallback to console logging only
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)],
            force=True
        )
        print(f"Warning: Could not setup file logging: {e}")
        return False

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Application Configuration
APP_CONFIG = {
    "app_name": "Student Result Management System",
    "version": "1.0.0",
    "page_title": "Student Result System",
    "cookie_prefix": "student_results_app/",
    "session_timeout": 3600,  # 1 hour in seconds
    "max_login_attempts": 5,
    "lockout_duration": 900,  # 15 minutes in seconds
}

class SecurityManager:
    """Handle security-related operations"""
    
    @staticmethod
    def initialize_security_headers():
        """Initialize security headers"""
        st.markdown("""
        <script>
        // Disable right-click context menu
        document.addEventListener('contextmenu', function(e) {
            e.preventDefault();
        });
        
        // Disable certain keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            // Disable F12, Ctrl+Shift+I, Ctrl+U
            if (e.keyCode === 123 || 
                (e.ctrlKey && e.shiftKey && e.keyCode === 73) || 
                (e.ctrlKey && e.keyCode === 85)) {
                e.preventDefault();
            }
        });
        </script>
        """, unsafe_allow_html=True)

    @staticmethod
    def check_session_timeout():
        """Check if user session has timed out"""
        if 'last_activity' in st.session_state:
            time_diff = datetime.now() - st.session_state.last_activity
            if time_diff.total_seconds() > APP_CONFIG['session_timeout']:
                logger.warning(f"Session timeout for user {st.session_state.get('username')}")
                SecurityManager.force_logout("Session expired due to inactivity")
                return False
        
        st.session_state.last_activity = datetime.now()
        return True

    @staticmethod
    def force_logout(reason: str = "Security logout"):
        """Force user logout for security reasons"""
        logger.info(f"Force logout: {reason}")
        if 'cookies' in st.session_state:
            cookies = st.session_state.cookies
            cookies['authenticated'] = 'false'
            cookies.save()
        
        # Clear session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        
        st.error(f"🔒 {reason}. Please log in again.")
        st.rerun()

class ApplicationManager:
    """Main application management class"""
    
    def __init__(self):
        self.setup_page_config()
        self.setup_custom_css()
        
    def setup_page_config(self):
        """Setup Streamlit page configuration"""
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

    def setup_custom_css(self):
        """Setup custom CSS styling"""
        inject_login_css("templates/main_styles.css")
        
        # Additional custom CSS for production
        st.markdown("""
        <style>
        .main-header {
            background: linear-gradient(135deg, #2E8B57, #228B22);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        .main-header h2 {
            color: white;
            font-size: 28px;
            font-weight: bold;
            text-align: center;
            margin: 0;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
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
        </style>
        """, unsafe_allow_html=True)

    def initialize_database(self):
        """Initialize database with error handling"""
        try:
            create_tables()
            logger.info("Database tables initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Database initialization failed: {str(e)}")
            st.error("❌ Database initialization failed. Please contact system administrator.")
            return False

    def initialize_cookies(self) -> Optional[EncryptedCookieManager]:
        """Initialize encrypted cookie manager with error handling"""
        try:
            # Use environment variable for password in production
            cookie_password = os.getenv('COOKIE_PASSWORD', 'fallback-secure-password-change-in-production')
            
            cookies = EncryptedCookieManager(
                prefix=APP_CONFIG["cookie_prefix"],
                password=cookie_password
            )
            
            if not cookies.ready():
                with st.spinner("🔄 Initializing secure session..."):
                    import time
                    time.sleep(1)
                st.rerun()
            
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
            <h2>{APP_CONFIG['app_name']}</h2>
        </div>
        """, unsafe_allow_html=True)

    def render_user_info(self, role: str, username: str):
        """Render user information in sidebar"""
        with st.sidebar:
            st.markdown(f"""
            <div class="user-info-card">
                <h4>👤 User Information</h4>
                <p><strong>Username:</strong> {username}</p>
                <p><strong>Role:</strong> {role.replace('_', ' ').title()}</p>
                <p><strong>Login Time:</strong> {st.session_state.get('login_time', 'Unknown')}</p>
            </div>
            """, unsafe_allow_html=True)

    def get_navigation_options(self, role: str) -> Dict[str, Callable]:
        """Get navigation options based on user role"""
        base_options = {}
        
        if role == "admin":
            base_options = {
                "🏠 Dashboard": self.render_dashboard,
                "👥 Admin Panel": admin_interface,
                "🏫 Manage Classes": manage_classes.create_class_section,
                "👥 Register Students": register_students.register_students,
                "📚 Manage Subjects": manage_subjects.add_subjects,
                "📝 Enter Scores": enter_scores.enter_scores,
                "📋 View Broadsheet": view_broadsheet.generate_broadsheet,
                "📝 Manage Comments": manage_comments,
                "📄 Generate Reports": generate_reports.report_card_section
            }
        elif role == "class_teacher":
            base_options = {
                "🏠 Dashboard": self.render_dashboard,
                "👥 Register Students": register_students.register_students,
                "📚 Manage Subjects": manage_subjects.add_subjects,
                "📝 Enter Scores": enter_scores.enter_scores,
                "📋 View Broadsheet": view_broadsheet.generate_broadsheet,
                "📝 Manage Comments": manage_comments,
                "📄 Generate Reports": generate_reports.report_card_section
            }
        elif role == "subject_teacher":
            base_options = {
                "🏠 Dashboard": self.render_dashboard,
                "📝 Enter Scores": enter_scores.enter_scores
            }
        
        # Add assignment selection for teachers
        if role in ["class_teacher", "subject_teacher"]:
            base_options["🔄 Change Assignment"] = select_assignment
        
        return base_options

    def render_dashboard(self):
        """Render dashboard with system statistics"""
        st.subheader("📊 System Dashboard")
        
        try:
            # Get database statistics
            stats = get_database_stats()
            
            # Create columns for metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("🏫 Classes", stats.get('classes', 0))
            
            with col2:
                st.metric("👥 Students", stats.get('students', 0))
            
            with col3:
                st.metric("📚 Subjects", stats.get('subjects', 0))
            
            with col4:
                st.metric("📝 Scores", stats.get('scores', 0))
            
            # Role-specific dashboard content
            role = st.session_state.get('role')
            self.render_role_specific_dashboard(role)
            
        except Exception as e:
            logger.error(f"Error rendering dashboard: {str(e)}")
            st.error("❌ Error loading dashboard data.")

    def render_role_specific_dashboard(self, role: str):
        """Render role-specific dashboard content"""
        st.markdown("---")
        
        if role == "admin":
            st.subheader("🔧 Admin Tools")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("📊 System Health Check", type="secondary"):
                    self.perform_health_check()
            
            with col2:
                if st.button("🗄️ Database Backup", type="secondary"):
                    st.info("Database backup functionality would be implemented here.")
            
            with col3:
                if st.button("📋 Activity Logs", type="secondary"):
                    st.info("Activity log viewer would be implemented here.")
        
        elif role in ["class_teacher", "subject_teacher"]:
            st.subheader("📋 Quick Actions")
            assignment = st.session_state.get('assignment')
            
            if assignment:
                st.info(f"📌 Current Assignment: {assignment.get('class_name', 'N/A')} - {assignment.get('subject_name', 'All Subjects')}")
            else:
                st.warning("⚠️ No assignment selected. Please select an assignment to continue.")

    def perform_health_check(self):
        """Perform system health check"""
        with st.spinner("🔍 Performing health check..."):
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
        except Exception:
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
                    os.makedirs(directory, exist_ok=True)
                    logger.info(f"Created directory: {directory}")
            
            # Check if directories are writable
            for directory in required_dirs:
                test_file = os.path.join(directory, '.test_write')
                try:
                    with open(test_file, 'w') as f:
                        f.write('test')
                    os.remove(test_file)
                except Exception:
                    logger.warning(f"Directory {directory} is not writable")
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
            return True  # If psutil not available, assume OK

    def handle_navigation(self, options: Dict[str, Callable]):
        """Handle navigation logic"""
        option_keys = list(options.keys())
        if not option_keys:
            st.error("❌ No navigation options available for your role.")
            return

        # Handle URL parameters
        param_page = st.query_params.get("page", None)
        if param_page in option_keys:
            current_page = param_page
        else:
            current_page = option_keys[0]

        # Navigation selectbox
        choice = st.sidebar.selectbox(
            "🧭 Navigate to:",
            option_keys,
            index=option_keys.index(current_page)
        )

        # Update URL parameters if choice changed
        if choice != st.query_params.get("page"):
            st.query_params["page"] = choice
            st.rerun()

        # Execute selected function
        try:
            logger.info(f"User {st.session_state.get('username')} accessed {choice}")
            options[choice]()
        except Exception as e:
            logger.error(f"Error in {choice}: {str(e)}\n{traceback.format_exc()}")
            st.error(f"❌ Error loading {choice}. Please try again or contact support.")
            
            # Show error details to admins
            if st.session_state.get('role') == 'admin':
                with st.expander("🔧 Error Details (Admin Only)"):
                    st.code(str(e))

    def render_logout_button(self):
        """Render logout button with confirmation"""
        with st.sidebar:
            st.markdown("---")
            if st.button("🚪 Logout", type="secondary", use_container_width=True):
                # Clear query parameters
                st.query_params.clear()
                logout()
                st.rerun()

def main():
    """Main application entry point"""
    try:
        # Initialize application manager
        app = ApplicationManager()
        
        # Initialize security
        SecurityManager.initialize_security_headers()
        
        # Initialize database
        if not app.initialize_database():
            st.stop()
        
        # Initialize cookies
        cookies = app.initialize_cookies()
        if not cookies:
            st.stop()
        
        # Handle authentication
        login(cookies)
        
        # Check if user is authenticated
        if not st.session_state.get("authenticated"):
            st.stop()
        
        # Security checks
        if not SecurityManager.check_session_timeout():
            st.stop()
        
        # Get user information
        role = st.session_state.get('role', 'unknown')
        username = st.session_state.get('username', 'Unknown User')
        user_id = st.session_state.get('user_id')
        
        # Validate user data
        if not all([role, username, user_id]):
            logger.error(f"Invalid session data: role={role}, username={username}, user_id={user_id}")
            SecurityManager.force_logout("Invalid session data")
            st.stop()
        
        # Render main application
        st.markdown('<div class="main-content">', unsafe_allow_html=True)
        
        # Render header
        app.render_header()
        
        # Render user info
        app.render_user_info(role, username)
        
        # Render logout button
        app.render_logout_button()
        
        # Get navigation options based on role
        options = app.get_navigation_options(role)
        
        # Handle navigation
        app.handle_navigation(options)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Update user activity timestamp
        st.session_state.last_activity = datetime.now()
        
    except Exception as e:
        logger.critical(f"Critical error in main application: {str(e)}\n{traceback.format_exc()}")
        st.error("❌ A critical error occurred. Please refresh the page or contact support.")
        
        # Show error details to admins
        if st.session_state.get('role') == 'admin':
            with st.expander("🔧 Critical Error Details (Admin Only)"):
                st.code(f"{str(e)}\n\n{traceback.format_exc()}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Final fallback error handling
        st.error("❌ Application failed to start. Please contact system administrator.")
        logger.critical(f"Application startup failed: {str(e)}")