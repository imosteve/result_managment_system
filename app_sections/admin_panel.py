# app_sections/admin_panel.py

import streamlit as st
import math
import time
import pandas as pd
from database import (
    get_all_classes, get_subjects_by_class,
    create_user, get_all_users, delete_user, assign_teacher, get_user_assignments,
    delete_assignment, get_database_stats, update_user, update_assignment, get_user_role,
    batch_assign_subject_teacher, get_classes_summary
)
from .system_dashboard import get_activity_statistics
from utils import inject_login_css, render_page_header, inject_metric_css
from util.paginators import streamlit_paginator

def admin_panel():
    """Admin panel for user management and assignments"""
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    # Get user's admin role
    user_id = st.session_state.get('user_id', None)
    admin_role = get_user_role(user_id)
    
    if admin_role not in ["superadmin", "admin"]:
        st.error("⚠️ Access denied. Admins only.")
        st.switch_page("main.py")
        return

    if user_id is None:
        st.error("⚠️ Session state missing user_id. Please log out and log in again.")
        return

    st.set_page_config(page_title="Admin Panel", layout="wide")
    
    render_page_header("Admin Dashboard")
    
    
    # Dashboard Metrics
    stats = get_database_stats()
    
    inject_login_css("templates/metrics_styles.css")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.markdown(f"<div class='custom-metric'><div class='label'>Total Users</div><div class='value'>{stats['teachers']}</div></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='custom-metric'><div class='label'>Total Classes</div><div class='value'>{stats['classes']}</div></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='custom-metric'><div class='label'>Total Assignments</div><div class='value'>{stats['assignments']}</div></div>", unsafe_allow_html=True)
    with col4:
        st.markdown(f"<div class='custom-metric'><div class='label'>Total Students</div><div class='value'>{stats['students']}</div></div>", unsafe_allow_html=True)
    with col5:
        st.markdown(f"<div class='custom-metric'><div class='label'>Total Subjects</div><div class='value'>{stats.get('subjects', 0)}</div></div>", unsafe_allow_html=True)
    with col6:
        st.markdown(f"<div class='custom-metric'><div class='label'>Total Scores</div><div class='value'>{stats.get('scores', 0)}</div></div>", unsafe_allow_html=True)

    inject_login_css("templates/tabs_styles.css")
    
    tabs = st.tabs([
        "View/Delete User",
        "Add New User",
        "View/Edit Assignment",
        "Assign Class Teacher",
        "Assign Subject Teacher",
        "Analytics & Reports",
    ])

    def get_fresh_classes():
        return get_all_classes(user_id, admin_role)
    
    def get_fresh_subjects(class_name, term, session):
        return get_subjects_by_class(class_name, term, session, user_id, admin_role)

    # View/Delete User Tab
    with tabs[0]:
        st.subheader("Current Users")
        users = get_all_users()
        if users:
            # Format user data with roles
            user_data = []
            for u in users:
                username = u[1]
                password = u[2]
                role = u[3] if u[3] else "Teacher"  # If no admin role, they're a teacher
                
                # Filter based on admin level
                if admin_role == "admin" and role in ["superadmin", "admin"]:
                    continue
                    
                user_data.append({
                    "Username": username,
                    "Role": role.replace("_", " ").title() if role else "Teacher",
                    "Password": password
                })
            
            streamlit_paginator(user_data, table_name="users")

            if 'show_delete_user_confirm' not in st.session_state:
                st.session_state.show_delete_user_confirm = False
            if 'user_to_delete_info' not in st.session_state:
                st.session_state.user_to_delete_info = None
            if 'show_edit_user' not in st.session_state:
                st.session_state.show_edit_user = False
            if 'user_to_edit_info' not in st.session_state:
                st.session_state.user_to_edit_info = None
            
            # Edit User Section
            with st.expander("✏️ Edit User", expanded=False):
                st.info("Update username and password for existing users")
                
                # Filter users for editing
                editable_users = [u for u in users if admin_role == "superadmin" or (u[3] not in ["superadmin", "admin"])]
                user_ids = [""] + [u[0] for u in editable_users]
                
                user_id_to_edit = st.selectbox(
                    "Select User to Edit",
                    user_ids,
                    format_func=lambda x: "Select a user" if x == "" else next(u[1] for u in editable_users if u[0] == x),
                    key="edit_user_select"
                )
                
                if user_id_to_edit and user_id_to_edit != "":
                    selected_user = next(u for u in editable_users if u[0] == user_id_to_edit)
                    role_display = selected_user[3].replace('_', ' ').title() if selected_user[3] else "Teacher"
                    st.info(f"Editing: **{selected_user[1]}** (Role: {role_display})")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        new_username = st.text_input("New Username", value=selected_user[1], key="new_username")
                    with col2:
                        new_password = st.text_input("New Password", type="password", placeholder="Leave blank to keep current", key="new_password")
                    
                    if st.button("💾 Update User", key="update_user_button", type="primary"):
                        if not new_username.strip():
                            st.error("Username cannot be empty")
                        else:
                            update_success = update_user(
                                user_id_to_edit, 
                                new_username.strip(), 
                                new_password if new_password else None
                            )
                            if update_success:
                                st.success(f"✅ User updated successfully")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("❌ Failed to update user. Username may already exist.")
            
            # Delete user section
            with st.expander("🗑️ Delete User", expanded=False):
                st.warning("⚠️ **Warning:** This action cannot be undone. Deleting a user will remove all their data and assignments.")
                
                deletable_users = [u for u in users if admin_role == "superadmin" or (u[3] not in ["superadmin", "admin"])]
                user_ids = [""] + [u[0] for u in deletable_users]
                
                user_id_to_delete = st.selectbox(
                    "Select User to Delete",
                    user_ids,
                    format_func=lambda x: "Select a user" if x == "" else next(u[1] for u in deletable_users if u[0] == x),
                    key="delete_user_select"
                )
                
                if user_id_to_delete and user_id_to_delete != "":
                    selected_user = next(u for u in deletable_users if u[0] == user_id_to_delete)
                    role_display = selected_user[3].replace('_', ' ').title() if selected_user[3] else "Teacher"
                    st.info(f"Selected user: **{selected_user[1]}** (Role: {role_display})")
                
                if st.button("❌ Delete Selected User", key="delete_user_button", type="primary"):
                    if user_id_to_delete == "":
                        st.error("⚠️ Please select a user to delete.")
                    elif user_id_to_delete == user_id:
                        st.error("⚠️ Cannot delete your own account.")
                    else:
                        selected_user = next(u for u in deletable_users if u[0] == user_id_to_delete)
                        role_display = selected_user[3].replace('_', ' ').title() if selected_user[3] else "Teacher"
                        st.session_state.user_to_delete_info = {
                            'id': user_id_to_delete,
                            'name': selected_user[1],
                            'role': role_display
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
                        st.error(f"**Role:** {user_info['role']}")
                        st.markdown("---")
                        st.warning("⚠️ **This action cannot be undone!**")
                        st.warning("• All user data will be permanently deleted")
                        st.warning("• All assignments will be removed")
                        st.warning("• User will lose access immediately")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("🚫 Cancel", key="cancel_delete_user", type="secondary", width='stretch'):
                                st.session_state.show_delete_user_confirm = False
                                st.session_state.user_to_delete_info = None
                                st.rerun()
                        with col2:
                            if st.button("❌ Delete User", key="confirm_delete_user", type="primary", width='stretch'):
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
            form_key = f"add_user_form_{st.session_state.get('form_submit_count', 0)}"
            
            col1, col2, col3 = st.columns(3)
            with col1:
                username = st.text_input("Username", key=f"username_{form_key}")
            with col2:
                password = st.text_input("Password", type="password", key=f"password_{form_key}")
            with col3:
                # Only superadmin can create admin users
                if admin_role == "superadmin":
                    user_type = st.selectbox("User Type", ["", "Teacher", "Admin", "Superadmin"], key=f"role_{form_key}")
                else:
                    user_type = st.selectbox("User Type", ["", "Teacher", "Admin"], key=f"role_{form_key}")

            submitted = st.form_submit_button("Add User")
            if submitted:
                if username and password and user_type:
                    # Map user type to role
                    role_map = {
                        "Teacher": None,
                        "Admin": "admin",
                        "Superadmin": "superadmin"
                    }
                    role = role_map.get(user_type)
                    
                    if create_user(username, password, role):
                        st.session_state.success_message = f"✅ User {username} added successfully as {user_type}."
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
        
        for u in users:
            # Skip admin users in assignment list if not superadmin
            if admin_role == "admin" and u[3] in ["superadmin", "admin"]:
                continue
                
            user_assignments = get_user_assignments(u[0])
            for a in user_assignments:
                assignment_type = a['assignment_type']
                role_display = "Class Teacher" if assignment_type == "class_teacher" else "Subject Teacher"
                
                assignments.append({
                    "id": a['id'],
                    "S/N": str(sn_counter),
                    "user_id": u[0],
                    "Username": u[1],
                    "Role": role_display,
                    "Class": f"{a['class_name']} - {a['term']} - {a['session']}",
                    "class_name": a['class_name'],
                    "term": a['term'],
                    "session": a['session'],
                    "Subject": a['subject_name'] or "-",
                    "subject_name": a['subject_name'],
                    "assignment_type": assignment_type
                })
                sn_counter += 1
                
        if assignments:
            display_assignments = [{k: v for k, v in a.items() if k in ["S/N", "Username", "Role", "Class", "Subject"]} for a in assignments]
            streamlit_paginator(display_assignments, table_name="teacher_assignments")
            
            if 'show_delete_assignment_confirm' not in st.session_state:
                st.session_state.show_delete_assignment_confirm = False
            if 'assignment_to_delete_info' not in st.session_state:
                st.session_state.assignment_to_delete_info = None
            
            # Edit Assignment Section
            with st.expander("✏️ Edit Assignment", expanded=False):
                st.info("Update class and subject assignments for teachers")
                
                assignment_s_n_to_edit = st.selectbox(
                    "Select Assignment to Edit",
                    [""] + [a["S/N"] for a in assignments],
                    format_func=lambda x: "Select an assignment" if x == "" else next(f"{a['Username']} - {a['Class']} - {a['Subject']}" for a in assignments if a["S/N"] == x),
                    key="edit_assignment_select"
                )
                
                if assignment_s_n_to_edit and assignment_s_n_to_edit != "":
                    selected_assignment = next((a for a in assignments if a["S/N"] == assignment_s_n_to_edit), None)
                    if selected_assignment:
                        st.info(f"Editing: **{selected_assignment['Username']}** - {selected_assignment['Class']} - {selected_assignment['Subject']}")
                        
                        classes = get_fresh_classes()
                        
                        col1, col2 = st.columns(2, vertical_alignment='bottom')
                        with col1:
                            class_options = [f"{cls['class_name']} - {cls['term']} - {cls['session']}" for cls in classes]
                            current_class = f"{selected_assignment['class_name']} - {selected_assignment['term']} - {selected_assignment['session']}"
                            current_index = class_options.index(current_class) if current_class in class_options else 0
                            
                            new_class = st.selectbox(
                                "New Class",
                                class_options,
                                index=current_index,
                                key="edit_assignment_class"
                            )
                            
                            selected_class_index = class_options.index(new_class)
                            class_data = classes[selected_class_index]
                            new_class_name, new_term, new_session = class_data['class_name'], class_data['term'], class_data['session']
                        
                        with col2:
                            if selected_assignment['subject_name']:  # Subject teacher
                                subjects = get_fresh_subjects(new_class_name, new_term, new_session)
                                subject_options = [s[1] for s in subjects]
                                current_subject_index = subject_options.index(selected_assignment['subject_name']) if selected_assignment['subject_name'] in subject_options else 0
                                
                                new_subject = st.selectbox(
                                    "New Subject",
                                    subject_options,
                                    index=current_subject_index,
                                    key="edit_assignment_subject"
                                )
                            else:  # Class teacher
                                new_subject = None
                                st.info("Class teacher (no subject)")
                        
                        if st.button("💾 Update Assignment", key="update_assignment_button", type="primary"):
                            update_success = update_assignment(
                                selected_assignment['id'],
                                new_class_name,
                                new_term,
                                new_session,
                                new_subject
                            )
                            if update_success:
                                st.success("✅ Assignment updated successfully")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("❌ Failed to update assignment. Assignment may already exist.")
            
            # Delete assignment section
            with st.expander("🗑️ Delete Assignment", expanded=False):
                st.warning("⚠️ **Warning:** This action cannot be undone. Deleting an assignment will remove the teacher's access to the assigned class/subject.")
                
                assignment_s_n_to_delete = st.selectbox(
                    "Select Assignment to Delete",
                    [""] + [a["S/N"] for a in assignments],
                    format_func=lambda x: "Select an assignment" if x == "" else next(f"{a['Username']} - {a['Class']} - {a['Subject']}" for a in assignments if a["S/N"] == x),
                    key="delete_assignment_select"
                )
                if assignment_s_n_to_delete:
                    selected_assignment = next((a for a in assignments if a["S/N"] == assignment_s_n_to_delete), None)
                    if selected_assignment:
                        st.info(f"Selected assignment: **{selected_assignment['Username']}** - {selected_assignment['Class']} - {selected_assignment['Subject']}")
                
                if st.button("❌ Delete Assignment", key="delete_assignment_button", type="primary"):
                    selected_assignment = next((a for a in assignments if a["S/N"] == assignment_s_n_to_delete), None)
                    if selected_assignment:
                        st.session_state.assignment_to_delete_info = selected_assignment
                        st.session_state.show_delete_assignment_confirm = True
                        st.rerun()
                        
                # Confirmation dialog
                if st.session_state.show_delete_assignment_confirm and st.session_state.assignment_to_delete_info:
                    @st.dialog("Confirm Assignment Deletion", width="small")
                    def confirm_delete_assignment():
                        assignment_info = st.session_state.assignment_to_delete_info
                        st.markdown(f"### Are you sure you want to delete this assignment?")
                        st.error(f"**Teacher:** {assignment_info['Username']}")
                        st.error(f"**Class:** {assignment_info['Class']}")
                        st.error(f"**Subject:** {assignment_info['Subject']}")
                        st.markdown("---")
                        st.warning("⚠️ **This action cannot be undone!**")
                        st.warning("• Teacher will lose access to this class/subject")
                        st.warning("• All related data may be affected")
                        st.warning("• Assignment will be permanently removed")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("🚫 Cancel", key="cancel_delete_assignment", type="secondary", width='stretch'):
                                st.session_state.show_delete_assignment_confirm = False
                                st.session_state.assignment_to_delete_info = None
                                st.rerun()
                        with col2:
                            if st.button("❌ Delete Assignment", key="confirm_delete_assignment", type="primary", width='stretch'):
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
            st.subheader("Assign Class Teacher")
            users = get_all_users()
            
            # Filter out admin users
            teacher_users = [u for u in users if not u[3] or u[3] not in ["superadmin", "admin"]]
            
            if not teacher_users:
                st.warning("⚠️ No teachers available. Add teachers in the Add New User tab.")
                submitted = st.form_submit_button("Assign", disabled=True)
            else:
                col1, col2 = st.columns(2)
                with col1:
                    selected_user_id = st.selectbox(
                        "Select Teacher",
                        [u[0] for u in teacher_users],
                        format_func=lambda x: next(u[1] for u in teacher_users if u[0] == x),
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
                    submitted = st.form_submit_button("Assign Class Teacher")
                    if submitted:
                        if assign_teacher(selected_user_id, class_name, term, session, None, 'class_teacher'):
                            st.success(f"✅ Class teacher assigned: {next(u[1] for u in teacher_users if u[0] == selected_user_id)}.")
                            st.rerun()
                        else:
                            st.error("❌ Failed to assign class teacher. Assignment may already exist.")

    # Assign Subject Teacher Tab
    with tabs[4]:
        st.subheader("Assign Subject Teacher")
        
        if 'selected_class_for_subject' not in st.session_state:
            st.session_state.selected_class_for_subject = None
        
        users = get_all_users()
        teacher_users = [u for u in users if not u[3] or u[3] not in ["superadmin", "admin"]]
        
        if not teacher_users:
            st.warning("⚠️ No teachers available. Add teachers in the Add New User tab.")
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                selected_user_id = st.selectbox(
                    "Select Teacher",
                    [u[0] for u in teacher_users],
                    format_func=lambda x: next(u[1] for u in teacher_users if u[0] == x),
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
                
                if st.session_state.selected_class_for_subject != selected_class:
                    st.session_state.selected_class_for_subject = selected_class
                
                selected_index = class_options.index(selected_class)
                class_data = classes[selected_index]
                class_name, term, session = class_data['class_name'], class_data['term'], class_data['session']
                
                subjects = get_fresh_subjects(class_name, term, session)
                
                if not subjects:
                    st.warning("⚠️ No subjects available for this class. Add subjects in the Manage Subjects section.")
                else:
                    # Check if this is Kindergarten or Nursery for batch assignment
                    is_kindergarten_nursery = class_name.upper().startswith("KINDERGARTEN") or class_name.upper().startswith("NURSERY")
                    
                    if is_kindergarten_nursery:
                        # Show batch assignment button for Kindergarten/Nursery
                        st.info(f"💡 **Tip:** For {class_name.split()[0]} classes, you can assign all subjects at once using the button below.")
                        
                        with col3:
                            subject_options = [s[1] for s in subjects]
                            subject_name = st.selectbox(
                                "Select Subject",
                                [""] + subject_options,
                                key=f"subject_select_{selected_class}"
                            )
                        
                        with st.form("assign_subject_teacher_form"):
                            col_single, col_batch = st.columns([1, 1])
                            
                            with col_single:
                                st.markdown("**Assign Single Subject**")
                                submitted_single = st.form_submit_button(
                                    "Assign Subject Teacher",
                                    disabled=not subject_name,
                                    width=200
                                )
                            
                            with col_batch:
                                st.markdown("**Assign All Subjects**")
                                st.caption(f"This will assign **{len(subjects)} subjects** to the selected teacher.")
                                submitted_all = st.form_submit_button(
                                    "Assign All Subjects", 
                                    type="primary",
                                    width=200
                                )
                            
                            # Handle single subject assignment
                            if submitted_single and subject_name:
                                if assign_teacher(selected_user_id, class_name, term, session, subject_name, 'subject_teacher'):
                                    st.success(f"✅ Subject teacher assigned: {next(u[1] for u in teacher_users if u[0] == selected_user_id)} to {subject_name}.")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to assign subject teacher. Assignment may already exist.")
                            
                            # Handle batch assignment
                            if submitted_all:
                                subject_names = [s[1] for s in subjects]
                                success_count, failed_subjects = batch_assign_subject_teacher(
                                    selected_user_id, class_name, term, session, subject_names
                                )
                                
                                if success_count == len(subjects):
                                    st.success(f"✅ All {success_count} subjects assigned successfully to {next(u[1] for u in teacher_users if u[0] == selected_user_id)}!")
                                elif success_count > 0:
                                    st.warning(f"⚠️ {success_count} subjects assigned. {len(failed_subjects)} subjects already existed or failed.")
                                    if failed_subjects:
                                        st.info(f"Skipped subjects: {', '.join(failed_subjects)}")
                                else:
                                    st.error("❌ No subjects were assigned. They may already exist.")
                                
                                time.sleep(1)
                                st.rerun()
                    else:
                        # Regular single subject assignment for other classes
                        with col3:
                            subject_options = [s[1] for s in subjects]
                            subject_name = st.selectbox(
                                "Select Subject",
                                [""] + subject_options,
                                key=f"subject_select_{selected_class}"
                            )
                        
                        with st.form("assign_subject_teacher_form_regular"):
                            submitted = st.form_submit_button(
                                "Assign Subject Teacher",
                                disabled=not subject_name
                            )
                            if submitted and subject_name:
                                if assign_teacher(selected_user_id, class_name, term, session, subject_name, 'subject_teacher'):
                                    st.success(f"✅ Subject teacher assigned: {next(u[1] for u in teacher_users if u[0] == selected_user_id)} to {subject_name}.")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to assign subject teacher. Assignment may already exist.")

    # Analytics & Reports
    with tabs[5]:
        render_analytics_tab(stats)
    

def render_analytics_tab(stats):
    """Render analytics and reports tab"""
    
    # Inject custom CSS for metric styling
    inject_metric_css()

    # Class distribution
    st.markdown("#### Class Overview")
    
    class_summary = get_classes_summary()
    
    if class_summary:
        class_data = [
            {
                "Class": row[0],
                "Term": row[1],
                "Session": row[2],
                "Students": row[3],
                "Subjects": row[4],
                "Scores": row[5]
            }
            for row in class_summary
        ]

        streamlit_paginator(class_data, table_name="class_summary_analytics")
    else:
        st.info("No classes found in the system.")

    # Activity statistics
    st.markdown("---")
    st.markdown("#### 📈 Activity Statistics")
    
    activity_stats = get_activity_statistics()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Active Classes", activity_stats['active_classes'])
    with col2:
        st.metric("Active Students", activity_stats['active_students'])
    with col3:
        st.metric("Score Completion", f"{activity_stats['score_completion']}%")
    with col4:
        st.metric("Assignments", stats['assignments'])


if __name__ == "__main__":
    admin_panel()