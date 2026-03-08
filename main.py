# main.py  — FINAL VERSION
import streamlit as st
import logging
import traceback
from datetime import datetime

from config import APP_CONFIG
from logging_setup import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

from app_manager import ApplicationManager
from security_manager import SecurityManager
from auth.login import login
from auth.logout import logout


def get_first_app_section(options: dict, role: str) -> str:
    skip_keys = [
        "👤 My Profile", "🏠 Dashboard", "🔧 System Dashboard",
        "👥 Admin Panel", "🌐 Platform Admin", "🔄 Change Assignment",
    ]
    option_keys = list(options.keys())
    for key in option_keys:
        if key not in skip_keys:
            return key
    for key in option_keys:
        if key != "👤 My Profile":
            return key
    return option_keys[0] if option_keys else None


def handle_post_assignment_navigation(app, role, options):
    if st.session_state.get("assignment_just_selected"):
        del st.session_state["assignment_just_selected"]
        first_section = get_first_app_section(options, role)
        if first_section:
            logger.info(f"Post-assignment navigation → {first_section}")
            st.query_params["page"] = first_section
            return first_section
    return None


def handle_navigation(app, options: dict, role: str):
    option_keys = list(options.keys())
    if not option_keys:
        st.error("❌ No navigation options available for your role.")
        return

    post_assignment_page = handle_post_assignment_navigation(app, role, options)
    if post_assignment_page:
        current_page = post_assignment_page
    else:
        param_page = st.query_params.get("page", None)
        current_page = param_page if param_page in option_keys else option_keys[0]

    school_code = st.session_state.get("school_code", "platform")
    if not school_code:
        school_code = "platform"
    logo_path = f"static/logos/{school_code}_logo.png"
    st.logo(logo_path, size="large")

    for page in option_keys:
        if st.sidebar.button(
            page,
            key=f"nav_{page}",
            type="secondary" if page == current_page else "tertiary",
        ):
            st.query_params["page"] = page
            st.rerun()

    try:
        logger.info(
            f"User '{st.session_state.get('username')}' "
            f"@ school '{st.session_state.get('school_code', 'platform')}' "
            f"accessed '{current_page}'"
        )
        options[current_page]()
    except Exception as e:
        logger.error(f"Error in '{current_page}': {e}\n{traceback.format_exc()}")
        st.error(f"❌ Error loading {current_page}. Please try again or contact support.")
        if st.session_state.get("role") in ("superadmin", "admin", "platform_superadmin"):
            with st.expander("🔧 Error Details (Admin Only)"):
                st.code(str(e))


def render_logout_button():
    with st.sidebar:
        if st.button("🚪 Logout", type="primary", width="stretch"):
            st.query_params.clear()
            logout()


def validate_session_data(role: str, username: str, user_id: int) -> bool:
    if not username or not user_id:
        logger.error(f"Invalid session — role={role}, username={username}, user_id={user_id}")
        SecurityManager.force_logout("Invalid session data")
        return False
    return True


def render_authenticated_app(app: ApplicationManager, cookies):
    try:
        if not SecurityManager.check_session_timeout():
            return

        role     = st.session_state.get("role", "unknown")
        username = st.session_state.get("username", "Unknown User")
        user_id  = st.session_state.get("user_id")

        if not validate_session_data(role, username, user_id):
            return

        st.markdown('<div class="main-content">', unsafe_allow_html=True)
        app.render_header()
        options = app.get_navigation_options(role, username)
        handle_navigation(app, options, role)
        render_logout_button()
        st.markdown("</div>", unsafe_allow_html=True)

        st.session_state.last_activity = datetime.now()

    except Exception as e:
        logger.error(f"Error in authenticated app: {e}\n{traceback.format_exc()}")
        st.error("❌ An error occurred. Please refresh the page or contact support.")
        if st.session_state.get("role") in ("superadmin", "admin", "platform_superadmin"):
            with st.expander("🔧 Error Details (Admin Only)"):
                st.code(f"{e}\n\n{traceback.format_exc()}")


def main():
    try:
        app = ApplicationManager()
        SecurityManager.initialize_security_headers()

        # Only initialises master.db — school DBs are never touched at startup
        if not app.initialize_master_database():
            st.stop()

        app.initialize_mobile_support()

        cookies = app.initialize_cookies()
        if cookies is None:
            st.stop()

        login(cookies)

        if st.session_state.get("authenticated"):
            render_authenticated_app(app, cookies)
        else:
            logger.warning("User reached main without authentication")
            st.stop()

    except Exception as e:
        logger.critical(f"Critical error in main: {e}\n{traceback.format_exc()}")
        st.error("❌ A critical error occurred. Please refresh the page or contact support.")
        if st.session_state.get("role") in ("superadmin", "admin", "platform_superadmin"):
            with st.expander("🔧 Critical Error Details (Admin Only)"):
                st.code(f"{e}\n\n{traceback.format_exc()}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error("❌ Application failed to start. Please contact system administrator.")
        if logger:
            logger.critical(f"Application startup failed: {e}")
        else:
            print(f"CRITICAL: Application startup failed: {e}")