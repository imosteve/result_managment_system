import streamlit as st
import os
import time
from streamlit_cookies_manager import EncryptedCookieManager
from database import get_user_by_username, get_user_assignments, get_all_classes, get_subjects_by_class
import bcrypt
from utils import inject_login_css

def login(cookies):
    # Wait for cookies to be ready
    if not cookies.ready():
        st.spinner("Loading authentication...")
        time.sleep(0.5)
        st.rerun()

    # Check authentication status
    try:
        if cookies.get("authenticated") == "true" and cookies.get("user_id"):
            st.session_state.authenticated = True
            st.session_state.user_id = int(cookies.get("user_id"))
            st.session_state.role = cookies.get("role")
            if st.session_state.role in ["class_teacher", "subject_teacher"] and "assignment" not in st.session_state:
                select_assignment()
            else:
                reset_main_app_styles()
            return
    except Exception:
        st.spinner("Loading authentication...")
        time.sleep(0.5)
        st.rerun()

    inject_login_css("templates/login_styles.css")

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown('<h1 class="login-title"> Login </h1>', unsafe_allow_html=True)
    
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        login_button = st.form_submit_button("Sign in")

        if login_button:
            if username and password:
                user = get_user_by_username(username)
                if user and bcrypt.checkpw(password.encode('utf-8'), user["password"].encode('utf-8')):
                    st.session_state.authenticated = True
                    st.session_state.user_id = user["id"]
                    st.session_state.role = user["role"]

                    try:
                        cookies["authenticated"] = "true"
                        cookies["user_id"] = str(user["id"])
                        cookies["role"] = user["role"]
                        cookies.save()
                        st.rerun()
                        if user["role"] in ["class_teacher", "subject_teacher"]:
                            st.rerun()
                            select_assignment()
                        else:
                            st.success("✅ Login successful! Redirecting...")
                            st.rerun()
                    except Exception as e:
                        st.error(f"⚠️ Cookies error: {e}. Please try again.")
                else:
                    st.error("❌ Invalid credentials. Please try again.")
            else:
                st.warning("⚠️ Please fill in both fields.")

    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

def select_assignment():
    """Display assignment selection for class/subject teachers"""
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown('<h1 class="login-title">Select Assignment</h1>', unsafe_allow_html=True)
    
    assignments = get_user_assignments(st.session_state.user_id)
    if not assignments:
        st.warning("⚠️ No class or subject assignments found. Contact the admin.")
        time.sleep(2)  # Brief delay to show warning
        logout()  # Automatically log out
        return

    assignment_options = []
    for assignment in assignments:
        class_display = f"{assignment['class_name']} - {assignment['term']} - {assignment['session']}"
        if assignment['subject_name']:
            class_display += f" - {assignment['subject_name']}"
        assignment_options.append(class_display)

    selected_assignment = st.selectbox("Select Your Assignment", assignment_options)
    selected_index = assignment_options.index(selected_assignment)
    selected_assignment_data = assignments[selected_index]

    if st.button("Confirm Selection"):
        st.session_state.assignment = {
            "class_name": selected_assignment_data["class_name"],
            "term": selected_assignment_data["term"],
            "session": selected_assignment_data["session"],
            "subject_name": selected_assignment_data["subject_name"]
        }
        st.session_state.cookies["assignment_class"] = selected_assignment_data["class_name"]
        st.session_state.cookies["assignment_term"] = selected_assignment_data["term"]
        st.session_state.cookies["assignment_session"] = selected_assignment_data["session"]
        st.session_state.cookies["assignment_subject"] = selected_assignment_data["subject_name"] or ""
        st.session_state.cookies.save()
        st.success("✅ Assignment selected! Redirecting...")
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

def logout():
    cookies = st.session_state.get("cookies")
    if cookies:
        try:
            cookies["authenticated"] = ""
            cookies["user_id"] = ""
            cookies["role"] = ""
            cookies["assignment_class"] = ""
            cookies["assignment_term"] = ""
            cookies["assignment_session"] = ""
            cookies["assignment_subject"] = ""
            cookies.save()

            prefix = "student_results_app"
            st.markdown(
                f"""
                <script>
                document.cookie = "{prefix}/authenticated=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
                document.cookie = "{prefix}/user_id=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
                document.cookie = "{prefix}/role=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
                document.cookie = "{prefix}/assignment_class=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
                document.cookie = "{prefix}/assignment_term=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
                document.cookie = "{prefix}/assignment_session=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
                document.cookie = "{prefix}/assignment_subject=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
                </script>
                """,
                unsafe_allow_html=True
            )

            st.query_params.clear()
            time.sleep(0.2)

            st.session_state.authenticated = False
            st.session_state.user_id = None
            st.session_state.role = None
            st.session_state.assignment = None
            for key in ["authenticated", "user_id", "role", "assignment", "session_id"]:
                if key in st.session_state:
                    del st.session_state[key]

            st.success("🔓 You have been logged out.")
            st.rerun()
        except Exception as e:
            st.error(f"⚠️ Logout failed: {e}. Please try again.")
            st.session_state.authenticated = False
            st.session_state.user_id = None
            st.session_state.role = None
            st.session_state.assignment = None
            st.rerun()
    else:
        st.error("Cookie manager not initialized.")
        st.session_state.authenticated = False
        st.session_state.user_id = None
        st.session_state.role = None
        st.session_state.assignment = None
        st.rerun()

def reset_main_app_styles():
    """Reset styles for main app after login"""
    st.markdown("""
    <style>
    .stApp {
        min-height: auto;
    }
    .block-container {
        padding-top: 3rem !important;
        padding-bottom: 2rem !important;
        max-width: 1000px !important;
    }
    </style>
    """, unsafe_allow_html=True)