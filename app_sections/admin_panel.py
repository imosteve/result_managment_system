# app_sections/admin_panel.py

import streamlit as st
import time
from database import (
    get_all_classes, get_subjects_by_class,
    create_user, get_all_users, delete_user, assign_teacher, get_user_assignments,
    delete_assignment, get_database_stats
)
from utils import inject_login_css, render_page_header

def admin_panel():
    """Admin panel for user management and assignments"""
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    if st.session_state.role not in ["superadmin", "admin"]:
        st.error("⚠️ Access denied. Admins only.")
        st.switch_page("main.py")
        return

    user_id = st.session_state.get('user_id', None)
    role = st.session_state.get('role', None)

    if user_id is None or role is None:
        st.error("⚠️ Session state missing user_id or role. Please log out and log in again.")
        return

    st.set_page_config(page_title="Admin Panel", layout="wide")
    
    # Subheader
    render_page_header("Admin Dashboard")

    
    # Custom CSS for better table styling
    inject_login_css("templates/metrics_styles.css")

    # Dashboard Metrics
    stats = get_database_stats()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"<div class='custom-metric'><div class='label'>Total Users</div><div class='value'>{stats['users']}</div></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='custom-metric'><div class='label'>Total Classes</div><div class='value'>{stats['classes']}</div></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='custom-metric'><div class='label'>Total Assignments</div><div class='value'>{stats['assignments']}</div></div>", unsafe_allow_html=True)
    with col4:
        st.markdown(f"<div class='custom-metric'><div class='label'>Total Comments</div><div class='value'>{stats['comments']}</div></div>", unsafe_allow_html=True)

    st.markdown("---")

    # Inject CSS to increase tab font size
    inject_login_css("templates/tabs_styles.css")
    # Tabs
    tabs = st.tabs([
        "View/Delete User",
        "Add New User",
        "View/Edit Assignment",
        "Assign Class Teacher",
        "Assign Subject Teacher"
    ])

    # Get fresh data each time - no caching for admin
    def get_fresh_classes():
        return get_all_classes(user_id, role)
    
    def get_fresh_subjects(class_name, term, session):
        return get_subjects_by_class(class_name, term, session, user_id, role)

    # View/Delete User Tab
    with tabs[0]:
        st.subheader("Current Users")
        users = get_all_users()
        if users:
            if role == "superadmin":
                user_data = [{"Username": u[1], "Role": u[2].replace("_", " ").title(), "Password": u[3]} for u in users]
            else:
                user_data = [{"Username": u[1], "Role": u[2].replace("_", " ").title(), "Password": u[3]} for u in users if u[2] not in ["superadmin", "admin"]]
            st.dataframe(user_data, width="stretch")
            
            # Initialize session state for delete confirmation
            if 'show_delete_user_confirm' not in st.session_state:
                st.session_state.show_delete_user_confirm = False
            if 'user_to_delete_info' not in st.session_state:
                st.session_state.user_to_delete_info = None
            
            # Delete user section with expander
            with st.expander("🗑️ Delete User", expanded=False):
                st.warning("⚠️ **Warning:** This action cannot be undone. Deleting a user will remove all their data and assignments.")
                
                # Get user IDs and add a placeholder option
                if role == "superadmin":
                    user_ids = [""] + [u[0] for u in users]  # Add empty string as first option
                else:
                    user_ids = [""] + [u[0] for u in users if u[2] not in ["superadmin", "admin"]]  # Add empty string as first option
                user_id_to_delete = st.selectbox(
                    "Select User to Delete",
                    user_ids,
                    format_func=lambda x: "Select a user" if x == "" else next(u[1] for u in users if u[0] == x),
                    key="delete_user_select"
                )
                
                if user_id_to_delete and user_id_to_delete != "":
                    selected_user = next(u for u in users if u[0] == user_id_to_delete)
                    st.info(f"Selected user: **{selected_user[1]}** (Role: {selected_user[2].replace('_', ' ').title()})")
                
                if st.button("❌ Delete Selected User", key="delete_user_button", type="primary"):
                    if user_id_to_delete == "":
                        st.error("⚠️ Please select a user to delete.")
                    elif user_id_to_delete == user_id:
                        st.error("⚠️ Cannot delete your own account.")
                    else:
                        # Store user info and show confirmation dialog
                        selected_user = next(u for u in users if u[0] == user_id_to_delete)
                        st.session_state.user_to_delete_info = {
                            'id': user_id_to_delete,
                            'name': selected_user[1],
                            'role': selected_user[2]
                        }
                        st.session_state.show_delete_user_confirm = True
                        st.rerun()
                        
                # Confirmation dialog
                if st.session_state.show_delete_user_confirm and st.session_state.user_to_delete_info:
                    @st.dialog("Confirm User Deletion")
                    def confirm_delete_user():
                        user_info = st.session_state.user_to_delete_info
                        st.markdown(f"### Are you sure you want to delete this user?")
                        st.error(f"**Username:** {user_info['name']}")
                        st.error(f"**Role:** {user_info['role'].replace('_', ' ').title()}")
                        st.markdown("---")
                        st.warning("⚠️ **This action cannot be undone!**")
                        st.warning("• All user data will be permanently deleted")
                        st.warning("• All assignments will be removed")
                        st.warning("• User will lose access immediately")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("🚫 Cancel", key="cancel_delete_user", type="secondary", use_container_width=True):
                                st.session_state.show_delete_user_confirm = False
                                st.session_state.user_to_delete_info = None
                                st.rerun()
                        with col2:
                            if st.button("❌ Delete User", key="confirm_delete_user", type="primary", use_container_width=True):
                                delete_user(user_info['id'])
                                st.session_state.show_delete_user_confirm = False
                                st.session_state.user_to_delete_info = None
                                st.success(f"✅ User {user_info['name']} deleted successfully.")
                                time.sleep(1)
                                st.rerun()
                    
                    confirm_delete_user()
        else:
            st.info("No users found.")

    # Add New User Tab
    with tabs[1]:
        with st.form("add_user_form"):
            st.subheader("Add New User")
            # Column layout for add user form
            col1, col2, col3 = st.columns(3)
            form_key = f"add_user_form_{st.session_state.get('form_submit_count', 0)}"
            with col1:
                username = st.text_input("Username", key=f"username_{form_key}")
            with col2:
                password = st.text_input("Password", type="password", key=f"password_{form_key}")
            with col3:
                # role = st.selectbox("Role", ["admin", "class_teacher", "subject_teacher"], key=f"role_{form_key}")
                if st.session_state.role == "superadmin":
                    role = st.selectbox("Role", ["", "superadmin", "admin", "class_teacher", "subject_teacher"], key=f"role_{form_key}")
                else:
                    role = st.selectbox("Role", ["", "admin", "class_teacher", "subject_teacher"], key=f"role_{form_key}")
            print(role)
            submitted = st.form_submit_button("Add User")
            if submitted:
                if username and password and role:
                    if create_user(username, password, role):
                        st.session_state.success_message = f"✅ User {username} added successfully."
                        st.session_state.form_submit_count = st.session_state.get('form_submit_count', 0) + 1
                        st.rerun()
                    else:
                        st.error(f"❌ Failed to add user. Username may already exist.")
                else:
                    st.error("⚠️ Please fill in all fields.")

    # View/Delete Teachers Assignment Tab
    with tabs[2]:
        st.subheader("Current Assignments")
        users = get_all_users()
        assignments = []
        sn_counter = 1
        for user in users:
            user_assignments = get_user_assignments(user[0])
            for a in user_assignments:
                assignments.append({
                    "S/N": str(sn_counter),
                    "Teacher": user[1].title(),
                    "Role": user[2].replace("_", " ").title(),
                    "Class": f"{a['class_name']} - {a['term']} - {a['session']}",
                    "Subject": a['subject_name'] or "-"
                })
                sn_counter += 1
                
        if assignments:
            st.dataframe(assignments, width="stretch")
            
            # Initialize session state for delete assignment confirmation
            if 'show_delete_assignment_confirm' not in st.session_state:
                st.session_state.show_delete_assignment_confirm = False
            if 'assignment_to_delete_info' not in st.session_state:
                st.session_state.assignment_to_delete_info = None
            
            # Delete assignment section with expander
            with st.expander("🗑️ Delete Assignment", expanded=False):
                st.warning("⚠️ **Warning:** This action cannot be undone. Deleting an assignment will remove the teacher's access to the assigned class/subject.")
                
                assignment_s_n_to_delete = st.selectbox(
                    "Select Assignment to Delete",
                    [a["S/N"] for a in assignments],
                    format_func=lambda x: next(f"{a['Teacher']} - {a['Class']} - {a['Subject']}" for a in assignments if a["S/N"] == x),
                    key="delete_assignment_select"
                )
                
                if assignment_s_n_to_delete:
                    selected_assignment = next((a for a in assignments if a["S/N"] == assignment_s_n_to_delete), None)
                    if selected_assignment:
                        st.info(f"Selected assignment: **{selected_assignment['Teacher']}** - {selected_assignment['Class']} - {selected_assignment['Subject']}")
                
                if st.button("❌ Delete Assignment", key="delete_assignment_button", type="primary"):
                    selected_assignment = next((a for a in assignments if a["S/N"] == assignment_s_n_to_delete), None)
                    if selected_assignment:
                        # Store assignment info and show confirmation dialog
                        st.session_state.assignment_to_delete_info = selected_assignment
                        st.session_state.show_delete_assignment_confirm = True
                        st.rerun()
                        
                # Confirmation dialog
                if st.session_state.show_delete_assignment_confirm and st.session_state.assignment_to_delete_info:
                    @st.dialog("Confirm Assignment Deletion", width="small")
                    def confirm_delete_assignment():
                        assignment_info = st.session_state.assignment_to_delete_info
                        st.markdown(f"### Are you sure you want to delete this assignment?")
                        st.error(f"**Teacher:** {assignment_info['Teacher']}")
                        st.error(f"**Class:** {assignment_info['Class']}")
                        st.error(f"**Subject:** {assignment_info['Subject']}")
                        st.markdown("---")
                        st.warning("⚠️ **This action cannot be undone!**")
                        st.warning("• Teacher will lose access to this class/subject")
                        st.warning("• All related data may be affected")
                        st.warning("• Assignment will be permanently removed")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("🚫 Cancel", key="cancel_delete_assignment", type="secondary", use_container_width=True):
                                st.session_state.show_delete_assignment_confirm = False
                                st.session_state.assignment_to_delete_info = None
                                st.rerun()
                        with col2:
                            if st.button("❌ Delete Assignment", key="confirm_delete_assignment", type="primary", use_container_width=True):
                                delete_assignment(assignment_info["id"])
                                st.session_state.show_delete_assignment_confirm = False
                                st.session_state.assignment_to_delete_info = None
                                st.success(f"✅ Assignment deleted successfully.")
                                time.sleep(1)
                                st.rerun()
                    
                    confirm_delete_assignment()
        else:
            st.info("No assignments found.")
    
    # Assign Class Teacher Tab
    with tabs[3]:
        with st.form("assign_class_teacher_form"):
            users = get_all_users()
            user_options = [(u[0], u[1], u[2]) for u in users if u[2] == "class_teacher"]
            if not user_options:
                st.warning("⚠️ No class teachers available. Add teachers in the Add New User tab.")
                submitted = st.form_submit_button("Assign", disabled=True)
            else:
                # Column layout for class teacher assignment
                col1, col2 = st.columns(2)
                with col1:
                    selected_user_id = st.selectbox(
                        "Select Class Teacher",
                        [u[0] for u in user_options],
                        format_func=lambda x: next(u[1] for u in user_options if u[0] == x),
                        key="class_teacher_select"
                    )
                classes = get_fresh_classes()
                if not classes:
                    st.warning("⚠️ No classes available. Add a class in the Manage Classes section.")
                    submitted = st.form_submit_button("Assign", disabled=True)
                else:
                    with col2:
                        class_options = [f"{cls['class_name']} - {cls['term']} - {cls['session']}" for cls in classes]
                        selected_class = st.selectbox(
                            "Select Class",
                            class_options,
                            key="class_teacher_class_select"
                        )
                    selected_index = class_options.index(selected_class)
                    class_data = classes[selected_index]
                    class_name, term, session = class_data['class_name'], class_data['term'], class_data['session']
                    submitted = st.form_submit_button("Assign")
                    if submitted:
                        if assign_teacher(selected_user_id, class_name, term, session, None):
                            st.success(f"✅ Class teacher assigned: {next(u[1] for u in user_options if u[0] == selected_user_id)}.")
                            st.rerun()
                        else:
                            st.error("❌ Failed to assign class teacher. Assignment may already exist.")
        
    # Assign Subject Teacher Tab
    with tabs[4]:
        # Initialize session state for dynamic updates
        if 'selected_class_for_subject' not in st.session_state:
            st.session_state.selected_class_for_subject = None
        
        users = get_all_users()
        user_options = [(u[0], u[1], u[2]) for u in users if u[2] == "subject_teacher"]
        
        if not user_options:
            st.warning("⚠️ No subject teachers available. Add teachers in the Add New User tab.")
        else:
            # Column layout for subject teacher assignment
            col1, col2, col3 = st.columns(3)
            with col1:
                selected_user_id = st.selectbox(
                    "Select Subject Teacher",
                    [u[0] for u in user_options],
                    format_func=lambda x: next(u[1] for u in user_options if u[0] == x),
                    key="subject_teacher_select"
                )
            
            classes = get_fresh_classes()
            if not classes:
                st.warning("⚠️ No classes available. Add a class in the Manage Classes section.")
            else:
                with col2:
                    class_options = [f"{cls['class_name']} - {cls['term']} - {cls['session']}" for cls in classes]
                    selected_class = st.selectbox(
                        "Select Class",
                        class_options,
                        key="subject_teacher_class_select"
                    )
                
                # Update session state when class changes
                if st.session_state.selected_class_for_subject != selected_class:
                    st.session_state.selected_class_for_subject = selected_class
                
                selected_index = class_options.index(selected_class)
                class_data = classes[selected_index]
                class_name, term, session = class_data['class_name'], class_data['term'], class_data['session']
                
                # Get subjects for selected class
                subjects = get_fresh_subjects(class_name, term, session)
                
                if not subjects:
                    st.warning("⚠️ No subjects available for this class. Add subjects in the Manage Subjects section.")
                    subject_name = None
                else:
                    with col3:
                        subject_options = [s[1] for s in subjects]
                        subject_name = st.selectbox(
                            "Select Subject",
                            [""] + subject_options,
                            key=f"subject_select_{selected_class}"
                        )
                
                # Assignment form
                with st.form("assign_subject_teacher_form"):
                    submitted = st.form_submit_button(
                        "Assign Subject Teacher",
                        disabled=not subject_name
                    )
                    if submitted and subject_name:
                        if assign_teacher(selected_user_id, class_name, term, session, subject_name):
                            st.success(f"✅ Subject teacher assigned: {next(u[1] for u in user_options if u[0] == selected_user_id)} to {subject_name}.")
                            st.rerun()
                        else:
                            st.error("❌ Failed to assign subject teacher. Assignment may already exist.")
        

if __name__ == "__main__":
    admin_panel()