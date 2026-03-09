# app_sections/manage_classes.py

import streamlit as st
from database_school import get_all_classes, create_class, delete_class, update_class
from main_utils import inject_login_css, render_page_header
from auth.activity_tracker import ActivityTracker

def create_class_section():
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    if st.session_state.role not in ["superadmin", "admin"]:
        st.error("⚠️ Access denied. Admins only.")
        return

    ActivityTracker.init()

    st.set_page_config(page_title="Manage Classes", layout="wide")
    inject_login_css("templates/tabs_styles.css")
    render_page_header("Manage Class")

    # New schema: get_all_classes() → [{id, class_name, description, created_at}]
    classes = get_all_classes()

    tab1, tab2 = st.tabs(["View/Edit Classes", "Add Class"])

    active_tab = st.session_state.get("manage_classes_active_tab", 0)
    ActivityTracker.watch_tab("manage_classes", active_tab)

    # ── TAB 1: VIEW / EDIT ─────────────────────────────────────────────────────
    with tab1:
        st.session_state.manage_classes_active_tab = 0
        st.subheader("View/Edit Classes")

        with st.container(border=True):
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                filter_type = st.selectbox(
                    "Filter by Class",
                    ["All", "Kindergarten", "Nursery", "Primary", "JSS", "SSS"],
                    key="filter_class_view"
                )
                ActivityTracker.watch_value("filter_class_view", filter_type)
            with col3:
                search_query = st.text_input(
                    "🔍 Search",
                    placeholder="Search class...",
                    key="search_class_view"
                )
                if search_query:
                    ActivityTracker.watch_value("search_class_view", search_query)

        filtered_classes = classes

        if filter_type != "All":
            filtered_classes = [
                cls for cls in filtered_classes
                if cls['class_name'].upper().startswith(filter_type.upper())
            ]

        if search_query:
            filtered_classes = [
                cls for cls in filtered_classes
                if search_query.lower() in cls['class_name'].lower()
            ]

        if filtered_classes:
            header_cols = st.columns([3, 4, 1.2, 1.2])
            header_cols[0].markdown("**Class Name**")
            header_cols[1].markdown("**Description**")
            header_cols[2].markdown("**Update**")
            header_cols[3].markdown("**Delete**")

            for i, cls in enumerate(filtered_classes):
                col1, col2, col3, col4 = st.columns([3, 4, 1.2, 1.2], gap="small", vertical_alignment="bottom")

                new_class = col1.text_input(
                    "Class",
                    value=cls['class_name'],
                    key=f"class_name_{i}",
                    label_visibility="collapsed"
                ).strip().upper()

                new_desc = col2.text_input(
                    "Description",
                    value=cls.get('description') or "",
                    key=f"desc_{i}",
                    label_visibility="collapsed"
                ).strip()

                if col3.button("💾", key=f"update_{i}"):
                    ActivityTracker.update()
                    new_class_upper = new_class.strip().upper()
                    # Duplicate check (exclude self)
                    if any(
                        c["class_name"].strip().upper() == new_class_upper
                        and c["class_name"] != cls["class_name"]
                        for c in classes
                    ):
                        st.markdown(
                            f'<div class="error-container">⚠️ A class named "{new_class_upper}" already exists.</div>',
                            unsafe_allow_html=True
                        )
                    else:
                        update_class(
                            class_name=cls['class_name'],
                            new_name=new_class_upper,
                            description=new_desc or None
                        )
                        st.markdown(
                            f'<div class="success-container">✅ Updated to {new_class_upper}</div>',
                            unsafe_allow_html=True
                        )
                        st.rerun()

                if col4.button("❌", key=f"delete_{i}"):
                    ActivityTracker.update()
                    st.session_state["delete_pending"] = {
                        "class_name": cls["class_name"],
                        "index": i
                    }

                if "delete_pending" in st.session_state:
                    @st.dialog("Confirm Class Deletion", width="small")
                    def confirm_delete_class():
                        pending = st.session_state["delete_pending"]
                        if pending["index"] == i:
                            st.warning(f"⚠️ Are you sure you want to delete '{pending['class_name']}'?")
                            st.error("This will also delete all associated students, subjects, and scores.")
                            confirm_col1, confirm_col2 = st.columns(2)
                            if confirm_col1.button("✅ Delete", key=f"confirm_delete_{i}"):
                                ActivityTracker.update()
                                success, msg = delete_class(pending["class_name"])
                                if success:
                                    st.markdown(
                                        f'<div class="success-container">❌ Deleted {pending["class_name"]}</div>',
                                        unsafe_allow_html=True
                                    )
                                else:
                                    st.error(f"❌ {msg}")
                                del st.session_state["delete_pending"]
                                st.rerun()
                            elif confirm_col2.button("❌ Cancel", key=f"cancel_delete_{i}"):
                                del st.session_state["delete_pending"]
                                st.info("Deletion cancelled.")
                                st.rerun()
                    confirm_delete_class()
                    break
        else:
            st.info("No classes found matching your filters.")

    # ── TAB 2: ADD CLASS ───────────────────────────────────────────────────────
    with tab2:
        st.session_state.manage_classes_active_tab = 1
        st.subheader("Add Class")

        if st.session_state.get("reset_add_class", False):
            st.session_state["class_input"] = ""
            st.session_state["arm_input"] = ""
            st.session_state["reset_add_class"] = False

        for key, default in [("class_input", ""), ("arm_input", "")]:
            if key not in st.session_state:
                st.session_state[key] = default

        with st.form("add_class_form"):
            col1, col2 = st.columns([2, 2])
            class_name = col1.selectbox(
                "Class",
                ["", "Kindergarten", "Nursery", "Primary", "JSS", "SSS"],
                key="class_input"
            )
            class_arm = col2.text_input(
                "Arm (e.g. 4, 4A, 4B)",
                key="arm_input"
            ).strip().upper()

            new_class = f'{class_name.upper()} {class_arm}'.strip()

            description = st.text_input(
                "Description (optional)",
                placeholder="e.g. Morning class"
            ).strip()

            submitted = st.form_submit_button("➕ Add Class")
            ActivityTracker.watch_form(submitted)

            if submitted:
                if not class_name or not class_arm:
                    st.markdown(
                        '<div class="error-container">⚠️ Please fill all required fields.</div>',
                        unsafe_allow_html=True
                    )
                elif any(
                    cls["class_name"].strip().upper() == new_class.upper()
                    for cls in classes
                ):
                    st.markdown(
                        f'<div class="error-container">⚠️ Class "{new_class}" already exists.</div>',
                        unsafe_allow_html=True
                    )
                else:
                    success = create_class(new_class, description or None)
                    if success:
                        st.markdown(
                            f'<div class="success-container">✅ Class "{new_class}" added.</div>',
                            unsafe_allow_html=True
                        )
                        st.session_state["reset_add_class"] = True
                        st.rerun()
                    else:
                        st.markdown(
                            f'<div class="error-container">❌ Failed to add class "{new_class}". It may already exist.</div>',
                            unsafe_allow_html=True
                        )
                        st.rerun()
