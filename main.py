# main.py

import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager
from database import create_tables
from app_sections import manage_classes, register_students, manage_subjects, enter_scores, view_broadsheet, generate_reports
from auth import login, logout
import time

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

st.set_page_config(page_title="Student Result System", layout="wide")

# ---------------------- App Navigation ---------------------- #
def main():
    # Initialize database
    create_tables()

    # Initialize cookie manager globally
    cookies = EncryptedCookieManager(
        prefix="student_results_app/",  # Unique prefix to namespace cookies
        password="your-secure-password"  # Replace with a strong, secure password
    )
    st.session_state["cookies"] = cookies  # Store in session state for global access

    # Wait for cookies to be ready
    if not cookies.ready():
        st.spinner("Loading cookies... Please wait.")
        time.sleep(0.5)  # Brief delay to allow JavaScript to load
        st.rerun()

    # Handle login with the initialized cookies
    login(cookies)  # Pass cookies to login function

    st.markdown('<div class="main-content">', unsafe_allow_html=True)
    
    # Main title
    st.markdown(
        """
        <div style='text-align: center; background-color: green;'>
            <h2 style='color:white; font-size:30px; font-weight:bold;'>
                Student Result Management System 
            </h2>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Sidebar navigation
    role = st.session_state.role
    
    # Logout button in sidebar
    if st.session_state.get("authenticated"):
        if st.sidebar.button("🚪 Logout"):
            logout()
            # Clear query params so page resets after logout
            st.query_params.clear()
            st.rerun()

    # Display current user
    st.sidebar.markdown(f"**👤 Logged in as:** {role.replace('_', ' ').title()}")

    # Define navigation options based on role
    if role == "admin":
        options = {
            "🏫 Manage Classes": manage_classes.create_class_section,
            "👥 Register Students": register_students.register_students,
            "📚 Manage Subjects": manage_subjects.add_subjects,
            "📝 Enter Scores": enter_scores.enter_scores,
            "📋 View Broadsheet": view_broadsheet.generate_broadsheet,
            "📄 Generate Reports": generate_reports.report_card_section
        }
    elif role == "class_teacher":
        options = {
            "👥 Register Students": register_students.register_students,
            "📚 Manage Subjects": manage_subjects.add_subjects,
            "📝 Enter Scores": enter_scores.enter_scores,
            "📋 View Broadsheet": view_broadsheet.generate_broadsheet,
            "📄 Generate Reports": generate_reports.report_card_section
        }
    elif role == "subject_teacher":
        options = {
            "📝 Enter Scores": enter_scores.enter_scores
        }

    option_keys = list(options.keys())

    # Restore from URL param if available
    param_page = st.query_params.get("page", None)
    if param_page in option_keys:
        st.session_state.current_page = param_page

    # Sidebar navigation selectbox
    choice = st.sidebar.selectbox(
        "Navigate to:",
        option_keys,
        index=option_keys.index(st.session_state.get("current_page", option_keys[0]))
    )

    # If the user selects a new page, update and rerun immediately
    if choice != st.session_state.get("current_page"):
        st.session_state.current_page = choice
        st.query_params["page"] = choice
        st.rerun()  # <-- Forces immediate reload on first click

    # Display the selected section
    if choice in options:
        try:
            options[choice]()
        except Exception as e:
            st.error(f"Error loading {choice}: {str(e)}")

    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()