import streamlit as st
import os
from streamlit_cookies_manager import EncryptedCookieManager
import time
from database import mark_session_as_logged_out  # Hypothetical function to track logout
from utils import inject_login_css

# Check authentication using cookies passed from main.py
def login(cookies):
    # Wait for cookies to be ready
    if not cookies.ready():
        st.spinner("Loading authentication...")
        time.sleep(0.5)
        st.rerun()

    # Check authentication status
    try:
        if cookies.get("authenticated") == "true":
            st.session_state.authenticated = True
            st.session_state.role = cookies.get("role")
            reset_main_app_styles()
            return
    except Exception as e:  # Catch generic exception instead of CookiesNotReady
        st.spinner("Loading authentication... (Error: {e})")
        time.sleep(0.5)
        st.rerun()

    inject_login_css("templates/login_styles.css")

    # Add some spacing at top
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # Create centered login form
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown('<h1 class="login-title"> Login </h1>', unsafe_allow_html=True)
    
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        login_button = st.form_submit_button("Sign in")

        if login_button:
            if username and password:
                user = USER_CREDENTIALS.get(username)
                if user and user["password"] == password:
                    # Update session state
                    st.session_state.authenticated = True
                    st.session_state.role = user["role"]

                    # Set cookies (persist for 7 days)
                    try:
                        cookies["authenticated"] = "true"
                        cookies["role"] = user["role"]
                        cookies.save()
                        st.success("✅ Login successful! Redirecting...")
                        st.rerun()
                    except Exception as e:  # Catch generic exception
                        st.error(f"⚠️ Cookies not ready or error occurred: {e}. Please try again.")
                else:
                    st.error("❌ Invalid credentials. Please try again.")
            else:
                st.warning("⚠️ Please fill in both fields.")

    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

def logout():
    cookies = st.session_state.get("cookies")
    if cookies:
        try:
            # Attempt to clear cookie values
            cookies["authenticated"] = ""
            cookies["role"] = ""
            cookies.save()

            # Inject JavaScript to delete cookies with configurable prefix and path
            prefix = "student_results_app"  # Match with main.py prefix
            st.markdown(
                f"""
                <script>
                document.cookie = "{prefix}/authenticated=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
                document.cookie = "{prefix}/role=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
                </script>
                """,
                unsafe_allow_html=True
            )

            # Clear the current page from URL query params
            st.query_params.clear()

            # Brief delay to allow JavaScript to execute
            time.sleep(0.2)  # Reduced to minimize delay

            # Server-side logout tracking (e.g., invalidate session)
            if "session_id" in st.session_state:  # Assume session_id is set during login
                mark_session_as_logged_out(st.session_state["session_id"])

            # Update session state
            st.session_state.authenticated = False
            st.session_state.role = None

            # Clear only relevant session state keys
            for key in ["authenticated", "role", "session_id"]:
                if key in st.session_state:
                    del st.session_state[key]

            st.success("🔓 You have been logged out.")
            st.rerun()
        except Exception as e:
            # Log error in production (replace with logging library)
            st.error(f"⚠️ Logout failed: {e}. Please try again or contact support.")
            # Fallback to clear session state
            st.session_state.authenticated = False
            st.session_state.role = None
            for key in ["authenticated", "role", "session_id"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    else:
        st.error("Cookie manager not initialized.")
        st.session_state.authenticated = False
        st.session_state.role = None
        st.rerun()

def reset_main_app_styles():
    """Reset styles for main app after login"""
    st.markdown("""
    <style>
    /* Reset to normal app styling */
    .stApp {
        # background: #5b5c5b;
        min-height: auto;
    }
    
    .block-container {
        padding-top: 3rem !important;
        padding-bottom: 2rem !important;
        max-width: 1000px !important;
    }
    
    /* Main content styling */
    # .main-content {
    #     background: blue;
    #     border-radius: 10px;
    #     padding: 1rem;
    #     box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    #     margin-bottom: 2rem;
    # }
    </style>
    """, unsafe_allow_html=True)

# User credentials (in-memory for now)
USER_CREDENTIALS = {
    "admin": {"password": "admin", "role": "admin"},
    "cteacher": {"password": "class", "role": "class_teacher"},
    "steacher": {"password": "subject", "role": "subject_teacher"},
}

if __name__ == "__main__":
    # For standalone testing, reinitialize cookie manager
    cookies = EncryptedCookieManager(
        prefix="student_results_app/",  # Match with main.py
        password="your-secure-password"  # Match with main.py
    )
    login(cookies)