# app_manager.py  — FINAL VERSION
"""
Changes from single-tenant version:
  - initialize_master_database() replaces initialize_database()
    → only ensures master.db tables exist at startup
  - render_header() reads school name from session state
    (platform superadmins see the live metrics header instead)
  - get_navigation_options() handles platform_superadmin role
    → shows 3 sidebar sections mirroring the school-section pattern:
        🏫 Schools & Admins
        💾 Database
        📋 Audit Log
  - setup_default_users() removed entirely
"""

import streamlit as st
import logging
from typing import Dict, Callable, Optional
from streamlit_cookies_manager import EncryptedCookieManager

from config import APP_CONFIG, COOKIE_PASSWORD
from main_utils import inject_login_css

logger = logging.getLogger(__name__)


class ApplicationManager:
    """Main application management class"""

    def __init__(self):
        self.setup_page_config()
        self.setup_custom_css()

    def setup_page_config(self):
        try:
            st.set_page_config(
                page_title=APP_CONFIG["page_title"],
                page_icon="🎓",
                layout="wide",
                initial_sidebar_state="expanded",
                menu_items={
                    "Get Help": None,
                    "Report a bug": None,
                    "About": f"{APP_CONFIG['app_name']} v{APP_CONFIG['version']}",
                },
            )
        except st.errors.StreamlitAPIException:
            pass

    def setup_custom_css(self):
        try:
            inject_login_css("templates/main_styles.css")
        except Exception as e:
            logger.warning(f"Could not load main styles: {e}")

    def initialize_mobile_support(self):
        st.markdown("""
        <script>
        function isMobile() {
            return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i
                   .test(navigator.userAgent);
        }
        if (isMobile()) {
            const vp = document.querySelector('meta[name="viewport"]');
            if (vp) {
                vp.setAttribute('content',
                    'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0');
            } else {
                const m = document.createElement('meta');
                m.name = 'viewport';
                m.content = 'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0';
                document.head.appendChild(m);
            }
            document.body.classList.add('mobile-device');
            sessionStorage.setItem('is_mobile', 'true');
        }
        if (/iPad|iPhone|iPod/.test(navigator.userAgent)) {
            document.querySelectorAll(
                'input[type="text"], input[type="password"], select, textarea'
            ).forEach(el => { el.style.fontSize = '16px'; });
        }
        </script>
        """, unsafe_allow_html=True)
        if "is_mobile" not in st.session_state:
            st.session_state.is_mobile = False

    def initialize_master_database(self) -> bool:
        """
        Ensure master.db tables exist and default platform superadmin is seeded.
        Called once at every app startup — safe to repeat.
        Individual school databases are NOT touched here.
        """
        try:
            from database_master import create_master_tables
            create_master_tables()
            logger.info("Master database initialised")
            return True
        except Exception as e:
            logger.error(f"Master database initialisation failed: {e}")
            st.error(
                "❌ Platform database initialisation failed. "
                "Please contact the system administrator."
            )
            return False

    def initialize_cookies(self) -> Optional[EncryptedCookieManager]:
        try:
            cookies = EncryptedCookieManager(
                prefix=APP_CONFIG["cookie_prefix"],
                password=COOKIE_PASSWORD,
            )
            st.session_state["cookies"] = cookies
            logger.info("Cookie manager initialised")
            return cookies
        except Exception as e:
            logger.error(f"Cookie manager initialisation failed: {e}")
            st.error(
                "❌ Session management initialisation failed. "
                "Please refresh the page."
            )
            return None

    def render_header(self):
        """
        Injects the school name into Streamlit's native top toolbar header.
        platform_superadmin → renders the live metrics header via render_platform_header().
        School users        → school name floated into the top bar via CSS pseudo-content.
        """
        role = st.session_state.get("role")

        if role == "platform_superadmin":
            from app_sections_master import render_platform_header
            render_platform_header()
        else:
            display_name = (
                st.session_state.get("school_name")
                or APP_CONFIG.get("platform_name", "School Result Management System")
            )
            st.markdown(f"""
                <style>
                /* Show school name inside Streamlit's top toolbar */
                [data-testid="stHeader"]::before {{
                    content: "{display_name.upper()}";
                    display: block;
                    position: absolute;
                    left: 50%;
                    top: 50%;
                    transform: translate(-50%, -50%);
                    font-size: 28px;
                    font-weight: bold;
                    color: white;
                    white-space: nowrap;
                    pointer-events: none;
                    z-index: 999;
                    text-shadow: 1px 1px 3px rgba(0,0,0,0.3);
                    letter-spacing: 0.5px;
                }}

                /* Style the header bar to match your green theme */
                [data-testid="stHeader"] {{
                    background: linear-gradient(135deg, #198046, #228B22) !important;
                    position: relative;
                }}

                /* Keep the sidebar toggle button visible */
                [data-testid="stHeader"] button {{
                    color: white !important;
                }}

                /* Remove the old in-page header div since it's now in the toolbar */
                .main-header {{
                    display: none !important;
                }}
                </style>
            """, unsafe_allow_html=True)

    def get_navigation_options(self, role: str, username: str) -> Dict[str, Callable]:
        """
        Return sidebar navigation for the current role.
        """
        try:
            # ── Platform superadmin — no school DB, platform sections only ──
            if role == "platform_superadmin":
                from app_sections_master import (
                    platform_schools_section,
                    platform_db_section,
                    platform_audit_section,
                )
                return {
                    "🏫 Schools & Admins": platform_schools_section,
                    "💾 Database":         platform_db_section,
                    "📋 Audit Log":        platform_audit_section,
                }

            # ── School roles ──────────────────────────────────────────────
            from app_sections_school import (
                manage_comments, manage_classes, register_students,
                manage_subjects, enter_scores, view_broadsheet,
                generate_reports, system_dashboard, admin_panel,
                manage_comment_templates, next_term_info, user_profile,
            )
            from auth.assignment_selection import select_assignment

            profile_function = user_profile.create_user_info_page(role, username)

            if role == "superadmin":
                return {
                    "🔧 System Dashboard":  system_dashboard.system_dashboard,
                    "👥 Admin Panel":       admin_panel.admin_panel,
                    "🗓️ Next Term Info":    next_term_info.next_term_info,
                    "📝 Comments Template": manage_comment_templates.manage_comment_templates,
                    "🏫 Manage Classes":    manage_classes.create_class_section,
                    "👥 Register Students": register_students.register_students,
                    "📚 Manage Subjects":   manage_subjects.add_subjects,
                    "📝 Enter Scores":      enter_scores.enter_scores,
                    "📝 Manage Comments":   manage_comments.manage_comments,
                    "📋 View Broadsheet":   view_broadsheet.generate_broadsheet,
                    "📄 Generate Reports":  generate_reports.report_card_section,
                    "👤 My Profile":        profile_function,
                }

            if role == "admin":
                return {
                    "👥 Admin Panel":       admin_panel.admin_panel,
                    "🗓️ Next Term Info":    next_term_info.next_term_info,
                    "📝 Comments Template": manage_comment_templates.manage_comment_templates,
                    "🏫 Manage Classes":    manage_classes.create_class_section,
                    "👥 Register Students": register_students.register_students,
                    "📚 Manage Subjects":   manage_subjects.add_subjects,
                    "📝 Enter Scores":      enter_scores.enter_scores,
                    "📝 Manage Comments":   manage_comments.manage_comments,
                    "📋 View Broadsheet":   view_broadsheet.generate_broadsheet,
                    "📄 Generate Reports":  generate_reports.report_card_section,
                    "👤 My Profile":        profile_function,
                }

            if role == "class_teacher":
                return {
                    "👥 Register Students": register_students.register_students,
                    "📚 Manage Subjects":   manage_subjects.add_subjects,
                    "📝 Enter Scores":      enter_scores.enter_scores,
                    "📝 Manage Comments":   manage_comments.manage_comments,
                    "📋 View Broadsheet":   view_broadsheet.generate_broadsheet,
                    "📄 Generate Reports":  generate_reports.report_card_section,
                    "🔄 Change Assignment": select_assignment,
                    "👤 My Profile":        profile_function,
                }

            if role == "subject_teacher":
                return {
                    "📝 Enter Scores":      enter_scores.enter_scores,
                    "📋 View Broadsheet":   view_broadsheet.generate_broadsheet,
                    "🔄 Change Assignment": select_assignment,
                    "👤 My Profile":        profile_function,
                }

            logger.warning(f"Unknown role '{role}' — returning empty navigation")
            return {}

        except ImportError as e:
            logger.error(f"Error importing navigation modules: {e}")
            return {}