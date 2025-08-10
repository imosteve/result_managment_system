# app_manager.py
import streamlit as st
import logging
import os
from typing import Dict, Callable, Optional
from streamlit_cookies_manager import EncryptedCookieManager

from config import APP_CONFIG, COOKIE_PASSWORD
from database import create_tables, get_database_stats
from utils import inject_login_css

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
        """Setup custom CSS styling"""
        try:
            inject_login_css("templates/main_styles.css")
        except Exception as e:
            logger.warning(f"Could not load main styles: {e}")
        
        # Core CSS that always loads
        st.markdown("""
        <style>
        .main-header {
            background: linear-gradient(135deg, #2E8B57, #228B22);
            # padding: 20px;
            # border-radius: 10px;
            margin-bottom: 10px;
            height: auto;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        .main-header h4 {
            color: white;
            font-size: 24px;
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
            <h2>{APP_CONFIG['app_name']}</h2>
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
                admin_interface, manage_comments,
                manage_classes, register_students, manage_subjects, 
                enter_scores, view_broadsheet, generate_reports
            )
            from auth.assignment_selection import select_assignment
            
            base_options = {}
            
            if role == "superadmin":
                base_options = {
                    "🏠 Dashboard": self.render_dashboard,
                    "👥 Admin Panel": admin_interface.admin_interface,
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
                    "👥 Admin Panel": admin_interface.admin_interface,
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
            
            # Add assignment selection for teachers
            if role in ["class_teacher", "subject_teacher"]:
                base_options["🔄 Change Assignment"] = select_assignment
            
            return base_options
            
        except ImportError as e:
            logger.error(f"Error importing navigation modules: {e}")
            # Return minimal navigation if imports fail
            return {
                "🏠 Dashboard": self.render_dashboard
            }

    def render_dashboard(self):
        """Render dashboard with system statistics"""
        st.markdown(
            """
            <div style='width: auto; margin: auto; text-align: center; background-color: #c6b7b1;'>
                <h3 style='color:#000; font-size:25px; margin-top:30px; margin-bottom:10px;'>
                    📊 System Dashboard
                </h3>
            </div>
            """,
            unsafe_allow_html=True
        )
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