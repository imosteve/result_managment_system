# app_sections/manage classes.py

import streamlit as st
from database import get_all_classes, create_class, delete_class, update_class, clear_all_classes
from utils import inject_login_css, render_page_header

def create_class_section():
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    if st.session_state.role not in ["superadmin", "admin"]:
        st.error("⚠️ Access denied. Admins only.")
        return

    st.set_page_config(page_title="Manage Classes", layout="wide")

    # Custom CSS for better table styling
    inject_login_css("templates/tabs_styles.css")

    # Subheader
    render_page_header("Manage Class")

    # FIX: Pass user_id and role to get_all_classes
    classes = get_all_classes(user_id=st.session_state.user_id, role=st.session_state.role)

    tab1, tab2, tab3 = st.tabs(["View/Edit Classes", "Add Class", "Clear All Classes"])

    with tab1:
        st.subheader("View/Edit Classes")
        if classes:
            header_cols = st.columns([3, 3, 3, 1.2, 1.2])
            header_cols[0].markdown("**Class Name**")
            header_cols[1].markdown("**Term**")
            header_cols[2].markdown("**Session**")
            header_cols[3].markdown("**Update**")
            header_cols[4].markdown("**Delete**")

            for i, cls in enumerate(classes):
                col1, col2, col3, col4, col5 = st.columns([3, 3, 3, 1.2, 1.2], gap="small", vertical_alignment="bottom")
                new_class = col1.text_input("Class", 
                                            value=cls['class_name'], 
                                            key=f"class_name_{i}", 
                                            label_visibility="collapsed"
                                            ).strip().upper()
                new_term = col2.selectbox("Term", 
                                          options=["1st Term", "2nd Term", "3rd Term"], 
                                          index=["1st Term", "2nd Term", "3rd Term"].index(cls['term']), 
                                          key=f"term_{i}", 
                                          label_visibility="collapsed"
                                          )
                new_session = col3.text_input("Session", 
                                              value=cls['session'], 
                                              key=f"session_{i}", 
                                              label_visibility="collapsed"
                                              )

                if col4.button("💾", key=f"update_{i}"):
                    new_class_upper = new_class.strip().upper()
                    if any(
                        cls_other["class_name"].strip().upper() == new_class_upper and
                        cls_other["term"] == new_term and
                        cls_other["session"].strip() == new_session.strip() and
                        not (
                            cls_other["class_name"] == cls["class_name"] and
                            cls_other["term"] == cls["term"] and
                            cls_other["session"] == cls["session"]
                        )
                        for cls_other in classes
                    ):
                        st.markdown(f'<div class="error-container">⚠️ A class with name "{new_class_upper}", term "{new_term}", and session "{new_session}" already exists.</div>', unsafe_allow_html=True)
                    else:
                        update_class(
                            original_class_name=cls['class_name'],
                            original_term=cls['term'], 
                            original_session=cls['session'],
                            new_class_name=new_class_upper,
                            new_term=new_term,
                            new_session=new_session.strip()
                        )
                        st.markdown(f'<div class="success-container">✅ Updated to {new_class_upper} - {new_term} - {new_session}</div>', unsafe_allow_html=True)
                        st.rerun()

                if col5.button("❌", key=f"delete_{i}"):
                    st.session_state["delete_pending"] = {
                        "class_name": cls["class_name"],
                        "term": cls["term"],
                        "session": cls["session"],
                        "index": i
                    }

                if "delete_pending" in st.session_state:
                    @st.dialog("Confirm Class Deletion", width="small")
                    def confirm_delete_class():
                        pending = st.session_state["delete_pending"]
                        if pending["index"] == i:
                            st.warning(f"⚠️ Are you sure you want to delete '{pending['class_name']}' for {pending['term']}, {pending['session']}?")
                            confirm_col1, confirm_col2 = st.columns(2)
                            if confirm_col1.button("✅ Delete", key=f"confirm_delete_{i}"):
                                delete_class(pending["class_name"], pending["term"], pending["session"])
                                st.markdown(f'<div class="success-container">❌ Deleted {pending["class_name"]} - {pending["term"]} - {pending["session"]}</div>', unsafe_allow_html=True)
                                del st.session_state["delete_pending"]
                                st.rerun()
                            elif confirm_col2.button("❌ Cancel", key=f"cancel_delete_{i}"):
                                del st.session_state["delete_pending"]
                                st.info("Deletion cancelled.")
                                st.rerun()
                    confirm_delete_class()
                    break
        else:
            st.info("No classes found. Add one in the 'Add Class' tab.")

    with tab2:
        st.subheader("Add Class")

        # ✅ Initialize default values before widgets
        if "new_class_input" not in st.session_state:
            st.session_state["class_input"] = ""
        if "new_class_input" not in st.session_state:
            st.session_state["arm_input"] = ""
        if "term_input" not in st.session_state:
            st.session_state["term_input"] = "1st Term"
        if "session_input" not in st.session_state:
            st.session_state["session_input"] = ""

        with st.form("add_class_form"):
            col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
            class_name = col1.selectbox(
                "Class",
                ["", "Primary", "SSS"],
                key="class_input"
            )

            class_arm = col2.text_input(
                "Arm (e.g. 4, 4A, 4B)",
                key="arm_input"
            ).strip().upper()

            new_class = f'{class_name.upper()} {class_arm}'

            term = col3.selectbox(
                "Term",
                ["1st Term", "2nd Term", "3rd Term"],
                key="term_input"
            )

            session = col4.text_input(
                "Session (e.g. 2024/2025)",
                key="session_input"
            ).strip()

            submitted = st.form_submit_button("➕ Add Class")

            if submitted:
                if not class_name or not class_arm or not session or not term:
                    st.markdown('<div class="error-container">⚠️ Please fill all fields.</div>', unsafe_allow_html=True)
                else:
                    session_parts = session.split('/')
                    if len(session_parts) != 2 or not (session_parts[0].isdigit() and session_parts[1].isdigit() and len(session_parts[0]) == 4 and len(session_parts[1]) == 4):
                        st.markdown('<div class="error-container">⚠️ Session must be in format YYYY/YYYY (e.g., 2024/2025).</div>', unsafe_allow_html=True)
                    elif any(
                        cls["class_name"].strip().upper() == new_class and
                        cls["term"] == term and
                        cls["session"].strip() == session
                        for cls in classes
                    ):
                        st.markdown(f'<div class="error-container">⚠️ Class with name "{new_class}", term "{term}", and session "{session}" already exists.</div>', unsafe_allow_html=True)
                    else:
                        success = create_class(new_class, term, session)
                        if success:
                            st.markdown(f'<div class="success-container">✅ Class "{new_class}" added for {term}, {session}.</div>', unsafe_allow_html=True)
                            st.rerun()
                            reset_add_class_fields()  # ✅ Reset via function
                            st.rerun()
                        else:
                            st.markdown(f'<div class="error-container">❌ Failed to add class "{new_class}". A class with this name, term, and session may already exist in the database.</div>', unsafe_allow_html=True)
                            st.rerun()

    with tab3:
        st.subheader("Clear All Classes")
        st.warning("⚠️ This action will permanently delete all classes and their associated students, subjects, and scores. This cannot be undone.")
        if classes:
            confirm_clear = st.checkbox("I confirm I want to clear all classes")
            clear_all_button = st.button("🗑️ Clear All Classes", key="clear_all_classes", disabled=not confirm_clear)
            
            if 'clear_all_class' not in st.session_state:
                    st.session_state.clear_all_class = None
            
            # Confirmation dialog
            if clear_all_button and confirm_clear:
                @st.dialog("Confirm All Classes Deletion", width="small")
                def confirm_delete_all_classes():
                    st.warning(f"⚠️ Are you sure you want to delete delete all classes and their associated students, subjects, and scores.?")
                    
                    confirm_col1, confirm_col2 = st.columns(2)
                    if confirm_col1.button("✅ Delete", key=f"confirm_delete_{i}"):
                        st.session_state.clear_all_class = clear_all_classes()
                        if st.session_state.clear_all_class:
                            st.markdown('<div class="success-container">✅ All classes cleared successfully!</div>', unsafe_allow_html=True)
                            st.session_state.clear_all_class = None
                            st.rerun()
                        else:
                            st.markdown('<div class="error-container">❌ Failed to clear classes. Please try again.</div>', unsafe_allow_html=True)
                    elif confirm_col2.button("❌ Cancel", key=f"cancel_delete_{i}"):
                        st.session_state.clear_all_class = None
                        st.info("Deletion cancelled.")
                        st.rerun()
                
                confirm_delete_all_classes()

        else:
            st.info("No classes available to clear.")

def reset_add_class_fields():
    st.session_state["class_input"] = ""
    st.session_state["arm_input"] = ""
    st.session_state["term_input"] = "1st Term"
    st.session_state["session_input"] = ""

