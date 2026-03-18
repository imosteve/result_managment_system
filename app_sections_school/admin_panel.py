# app_sections/admin_panel.py

import streamlit as st
import math
import time
import pandas as pd
from database_school import (
    get_all_classes, get_subjects_by_class, get_classes_for_session,
    get_active_session, get_active_term_name,
    get_all_sessions, create_session, delete_session, update_session, set_active_term,
    open_class_for_session, get_classes_for_session,
    create_user, get_all_users, delete_user, assign_teacher, get_user_assignments,
    delete_assignment, get_database_stats, update_user, update_assignment, get_user_role,
    batch_assign_subject_teacher, get_classes_summary,
    get_scores_for_class, get_connection,
)
from .system_dashboard import get_activity_statistics
from database_master import get_school_by_code
from main_utils import inject_login_css, render_page_header, inject_metric_css
from utils.paginators import streamlit_paginator
from auth.activity_tracker import ActivityTracker
from security_manager import SecurityManager

_active_session = get_active_session()

def admin_panel():
    """Admin panel for user management and assignments"""
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    if not SecurityManager.check_session_timeout():
        return  # Security manager will handle logout

    # Get user's admin role
    user_id = st.session_state.get('user_id', None)
    admin_role = get_user_role(user_id)
    
    # ── CHANGE: 'teacher' replaces 'class_teacher' as the non-admin role ──
    if admin_role not in ("superadmin", "admin"):
        st.error("⚠️ Access denied. Admins only.")
        st.switch_page("main.py")
        return

    if user_id is None:
        st.error("⚠️ Session state missing user_id. Please log out and log in again.")
        return

    # Initialize activity tracker
    ActivityTracker.init()

    st.set_page_config(page_title="Admin Panel", layout="wide")
    
    # Tab-based interface for different operations
    inject_login_css("templates/tabs_styles.css")

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
        st.markdown(f"<div class='custom-metric'><div class='label'>Total Assigned</div><div class='value'>{stats['assignments']}</div></div>", unsafe_allow_html=True)
    with col4:
        st.markdown(f"<div class='custom-metric'><div class='label'>Total Students</div><div class='value'>{stats['students']}</div></div>", unsafe_allow_html=True)
    with col5:
        st.markdown(f"<div class='custom-metric'><div class='label'>Total Subjects</div><div class='value'>{stats.get('subjects', 0)}</div></div>", unsafe_allow_html=True)
    with col6:
        st.markdown(f"<div class='custom-metric'><div class='label'>Total Scores</div><div class='value'>{stats.get('scores', 0)}</div></div>", unsafe_allow_html=True)

    st.markdown("---")
    
    tabs = st.tabs([
        "View/Delete User",
        "Add New User",
        "View/Edit Assignment",
        "Assign Teacher",
        "Academic Settings",
        "Analytics & Reports",
    ])

    # Track active tab
    active_tab = st.session_state.get("admin_panel_active_tab", 0)
    ActivityTracker.watch_tab("admin_panel", active_tab)

    # Active session for classes (no term needed — subjects are per-class)
    _active_session = get_active_session()

    def get_fresh_classes():
        if _active_session:
            return get_classes_for_session(_active_session)
        return get_all_classes()

    def get_fresh_subjects(class_name, term=None, session=None):
        # New schema: subjects are per-class only, no term/session
        return get_subjects_by_class(class_name)

    # View/Delete User Tab
    with tabs[0]:
        st.session_state.admin_panel_active_tab = 0
        render_view_delete_user_tab(user_id, admin_role)

    # Add New User Tab
    with tabs[1]:
        st.session_state.admin_panel_active_tab = 1
        render_add_user_tab(admin_role)

    # View/Edit Assignment Tab
    with tabs[2]:
        st.session_state.admin_panel_active_tab = 2
        render_assignments_tab(user_id, admin_role, get_fresh_classes, get_fresh_subjects)

    # Assign Teacher Tab (class teacher + subject teacher combined)
    with tabs[3]:
        st.session_state.admin_panel_active_tab = 3
        render_assign_teacher_tab(get_fresh_classes, get_fresh_subjects, _active_session)

    # Academic Settings Tab
    with tabs[4]:
        st.session_state.admin_panel_active_tab = 4
        render_academic_settings_tab()

    # Analytics & Reports
    with tabs[5]:
        st.session_state.admin_panel_active_tab = 5
        render_analytics_tab(stats)


def render_view_delete_user_tab(user_id, admin_role):
    """Render View/Delete User tab"""
    st.subheader("Current Users")
    users = get_all_users()
    
    if users:
        # Format user data with roles
        user_data = []
        for u in users:
            username = u["username"]
            password = u["password"]
            role = u["role"] if u["role"] else "teacher"
            
            # admins cannot see superadmin/admin rows
            if admin_role == "admin" and role in ("superadmin", "admin"):
                continue
                
            user_data.append({
                "Username": username,
                "Email": u["email"] or "-",
                "Role": role.title(),
                "Password": password
            })
        
        if len(user_data) == 0:
            st.info("No users found.")
        else:
            streamlit_paginator(user_data, table_name="users")

        if 'show_delete_user_confirm' not in st.session_state:
            st.session_state.show_delete_user_confirm = False
        if 'user_to_delete_info' not in st.session_state:
            st.session_state.user_to_delete_info = None
        
        if len(user_data) > 0:
            
            st.divider()
            # Edit User Section
            with st.expander("✏️ Edit User", expanded=False):
                st.info("Update username and password for existing users")
                
                editable_users = [
                    u for u in users
                    if admin_role == "superadmin" or u["role"] not in ("superadmin", "admin")
                ]
                user_ids = [""] + [u["id"] for u in editable_users]
                
                user_id_to_edit = st.selectbox(
                    "Select User to Edit",
                    user_ids,
                    format_func=lambda x: "Select a user" if x == "" else next(u["username"] for u in editable_users if u["id"] == x),
                    key="edit_user_select"
                )
                ActivityTracker.watch_value("edit_user_select", user_id_to_edit)
                
                if user_id_to_edit and user_id_to_edit != "":
                    selected_user = next(u for u in editable_users if u["id"] == user_id_to_edit)
                    role_display = selected_user["role"].title() if selected_user["role"] else "Teacher"
                    st.info(f"Editing: **{selected_user["username"]}** (Role: {role_display})")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        new_username = st.text_input("New Username", value=selected_user["username"], key="new_username")
                    with col2:
                        new_email = st.text_input("New Email", value=selected_user["email"] or "", placeholder="user@example.com", key="new_email")
                    with col3:
                        new_password = st.text_input("New Password", type="password", placeholder="Leave blank to keep current", key="new_password")
                    
                    if st.button("💾 Update User", key="update_user_button", type="primary"):
                        ActivityTracker.update()
                        
                        if not new_username.strip():
                            st.error("Username cannot be empty")
                        else:
                            update_success = update_user(
                                user_id_to_edit,
                                new_username.strip(),
                                new_password if new_password else None,
                                new_email.strip() if new_email.strip() else None
                            )
                            if update_success:
                                st.success(f"✅ User updated successfully")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("❌ Failed to update user. Username or email may already exist.")
            
            st.divider()
            
            # Delete user section
            with st.expander("🗑️ Delete User", expanded=False):
                st.warning("⚠️ **Warning:** This action cannot be undone. Deleting a user will remove all their data and assignments.")
                
                deletable_users = [
                    u for u in users
                    if admin_role == "superadmin" or u["role"] not in ("superadmin", "admin")
                ]
                user_ids = [""] + [u["id"] for u in deletable_users]
                
                user_id_to_delete = st.selectbox(
                    "Select User to Delete",
                    user_ids,
                    format_func=lambda x: "Select a user" if x == "" else next(u["username"] for u in deletable_users if u["id"] == x),
                    key="delete_user_select"
                )
                ActivityTracker.watch_value("delete_user_select", user_id_to_delete)
                
                if user_id_to_delete and user_id_to_delete != "":
                    selected_user = next(u for u in deletable_users if u["id"] == user_id_to_delete)
                    role_display = selected_user["role"].title() if selected_user["role"] else "Teacher"
                    st.info(f"Selected user: **{selected_user["username"]}** (Role: {role_display})")
                
                if st.button("❌ Delete Selected User", key="delete_user_button", type="primary"):
                    ActivityTracker.update()
                    
                    if user_id_to_delete == "":
                        st.error("⚠️ Please select a user to delete.")
                    elif user_id_to_delete == user_id:
                        st.error("⚠️ Cannot delete your own account.")
                    else:
                        selected_user = next(u for u in deletable_users if u["id"] == user_id_to_delete)
                        role_display = selected_user["role"].title() if selected_user["role"] else "Teacher"
                        st.session_state.user_to_delete_info = {
                            'id': user_id_to_delete,
                            'name': selected_user["username"],
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
                            ActivityTracker.update()
                            delete_user(user_info['id'])
                            st.session_state.show_delete_user_confirm = False
                            st.session_state.user_to_delete_info = None
                            st.success(f"✅ User {user_info['name']} deleted successfully.")
                            time.sleep(1)
                            st.rerun()
                
                confirm_delete_user()
    else:
        st.info("No users found.")


def render_add_user_tab(admin_role):
    """Render Add New User tab"""
    # ── Resolve school email domain from master DB ────────────────────────────
    school_code = st.session_state.get("school_code", "")
    school_info = get_school_by_code(school_code) if school_code else None
    email_domain = school_info.get("email_domain", "").strip() if school_info else ""

    with st.form("add_user_form"):
        st.subheader("Add New User")
        form_key = f"add_user_form_{st.session_state.get('form_submit_count', 0)}"

        col1, col2 = st.columns(2, vertical_alignment='bottom')
        with col1:
            username = st.text_input("Username", key=f"username_{form_key}")
        with col2:
            # ── Email input: autofill domain if known ─────────────────────────
            if email_domain:
                st.markdown(f"**Email** &nbsp; *(`username@{email_domain}`)*")
                email_local = st.text_input(
                    "Email local part",
                    placeholder=f"e.g. john.doe",
                    key=f"email_local_{form_key}",
                    label_visibility="collapsed",
                    help=f"Enter the part before @. The domain @{email_domain} will be added automatically."
                )
                email = f"{email_local.strip()}@{email_domain}" if email_local.strip() else ""
                # st.caption(f"📧 Full email: `{email}`" if email else "📧 Enter the part before @")
            else:
                email = st.text_input(
                    "Email",
                    placeholder="e.g. john.doe@school.edu",
                    key=f"email_{form_key}"
                )

        col3, col4 = st.columns(2)
        with col3:
            password = st.text_input("Password", type="password", key=f"password_{form_key}")
        with col4:
            if admin_role == "superadmin":
                user_type = st.selectbox("User Type", ["", "Teacher", "Admin", "Superadmin"], key=f"role_{form_key}")
            else:
                user_type = st.selectbox("User Type", ["", "Teacher", "Admin"], key=f"role_{form_key}")

        submitted = st.form_submit_button("Add User")
        ActivityTracker.watch_form(submitted)

        if submitted:
            # ── Validation ────────────────────────────────────────────────────
            errors = []

            if not username.strip():
                errors.append("Username is required.")
            if not password:
                errors.append("Password is required.")
            if not user_type:
                errors.append("User Type is required.")

            # Email format check
            email_clean = email.strip()
            if not email_clean:
                errors.append("Email is required.")
            elif "@" not in email_clean or email_clean.startswith("@") or email_clean.endswith("@"):
                errors.append("Enter a valid email address.")
            else:
                local, _, domain_part = email_clean.partition("@")
                if not local or not domain_part or "." not in domain_part:
                    errors.append("Enter a valid email address (e.g. name@school.edu).")
                elif email_domain and domain_part.lower() != email_domain.lower():
                    errors.append(f"Email domain must be @{email_domain} (got @{domain_part}).")

            if errors:
                for e in errors:
                    st.error(f"⚠️ {e}")
            else:
                role_map = {
                    "Teacher":    "teacher",
                    "Admin":      "admin",
                    "Superadmin": "superadmin",
                }
                role = role_map.get(user_type)

                if create_user(username.strip(), password, email_clean, role):
                    st.session_state.success_message = f"✅ User {username} added successfully as {user_type}."
                    st.session_state.form_submit_count = st.session_state.get('form_submit_count', 0) + 1
                    st.rerun()
                else:
                    st.error("❌ Failed to add user. Username or email may already exist.")


def render_assignments_tab(user_id, admin_role, get_fresh_classes, get_fresh_subjects):
    """Render View/Edit Assignment tab"""
    st.subheader("Current Assignments")
    users = get_all_users()
    assignments = []
    sn_counter = 1
    
    for u in users:
        if admin_role == "admin" and u["role"] in ("superadmin", "admin"):
            continue
            
        user_assignments = get_user_assignments(u["id"])
        for a in user_assignments:
            assignment_type = a['assignment_type']
            role_display = "Class Teacher" if assignment_type == "class_teacher" else "Subject Teacher"
            
            assignments.append({
                "id": a['id'],
                "S/N": str(sn_counter),
                "user_id": u["id"],
                "Username": u["username"].title(),
                "Role": role_display,
                "Class": a['class_name'],
                "class_name": a['class_name'],
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
            ActivityTracker.watch_value("edit_assignment_select", assignment_s_n_to_edit)
            
            if assignment_s_n_to_edit and assignment_s_n_to_edit != "":
                selected_assignment = next((a for a in assignments if a["S/N"] == assignment_s_n_to_edit), None)
                if selected_assignment:
                    st.info(f"Editing: **{selected_assignment['Username']}** - {selected_assignment['Class']} - {selected_assignment['Subject']}")
                    
                    classes = get_fresh_classes()
                    
                    col1, col2 = st.columns(2, vertical_alignment='bottom')
                    with col1:
                        class_options = [cls['class_name'] for cls in classes]
                        current_class = selected_assignment['class_name']
                        current_index = class_options.index(current_class) if current_class in class_options else 0
                        
                        new_class = st.selectbox("New Class", class_options, index=current_index, key="edit_assignment_class")
                        
                        selected_class_index = class_options.index(new_class)
                        class_data = classes[selected_class_index]
                        new_class_name = class_data['class_name']
                    
                    with col2:
                        if selected_assignment['subject_name']:
                            subjects = get_fresh_subjects(new_class_name)
                            subject_options = [s["subject_name"] if isinstance(s, dict) else s[1] for s in subjects]
                            current_subject_index = subject_options.index(selected_assignment['subject_name']) if selected_assignment['subject_name'] in subject_options else 0
                            new_subject = st.selectbox("New Subject", subject_options, index=current_subject_index, key="edit_assignment_subject")
                        else:
                            new_subject = None
                            st.info("Class teacher (no subject)")
                    
                    if st.button("💾 Update Assignment", key="update_assignment_button", type="primary"):
                        ActivityTracker.update()
                        
                        update_success = update_assignment(selected_assignment['id'], new_class_name, new_subject)
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
            ActivityTracker.watch_value("delete_assignment_select", assignment_s_n_to_delete)
            
            if assignment_s_n_to_delete:
                selected_assignment = next((a for a in assignments if a["S/N"] == assignment_s_n_to_delete), None)
                if selected_assignment:
                    st.info(f"Selected assignment: **{selected_assignment['Username']}** - {selected_assignment['Class']} - {selected_assignment['Subject']}")
            
            if st.button("❌ Delete Assignment", key="delete_assignment_button", type="primary"):
                ActivityTracker.update()
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
                            ActivityTracker.update()
                            delete_assignment(assignment_info["id"])
                            st.session_state.show_delete_assignment_confirm = False
                            st.session_state.assignment_to_delete_info = None
                            st.success(f"✅ Assignment deleted successfully.")
                            time.sleep(1)
                            st.rerun()
                
                confirm_delete_assignment()
    else:
        st.info("No assignments found.")


def render_assign_teacher_tab(get_fresh_classes, get_fresh_subjects, active_session):
    """Render Assign Teacher tab — class teacher and subject teacher combined."""
    users = get_all_users()
    teacher_users = [u for u in users if u["role"] == "teacher"]

    if not teacher_users:
        st.warning("⚠️ No teachers available. Add teachers in the Add New User tab.")
        return

    classes = get_fresh_classes()
    if not classes:
        st.warning("⚠️ No classes available. Add a class in the Manage Classes section.")
        return

    class_options = [cls['class_name'] for cls in classes]

    # ── Assign Class Teacher ──────────────────────────────────────────────────
    with st.form("assign_class_teacher_form"):
        st.subheader("Assign Class Teacher")
        col1, col2 = st.columns(2)
        with col1:
            ct_user_id = st.selectbox(
                "Select Teacher",
                [u["id"] for u in teacher_users],
                format_func=lambda x: next(u["username"] for u in teacher_users if u["id"] == x),
                key="class_teacher_select"
            )
        with col2:
            ct_class = st.selectbox("Select Class", class_options, key="class_teacher_class_select")

        submitted_ct = st.form_submit_button("Assign Class Teacher")
        ActivityTracker.watch_form(submitted_ct)
        if submitted_ct:
            ct_class_name = classes[class_options.index(ct_class)]['class_name']
            if assign_teacher(ct_user_id, ct_class_name, active_session or '', None, 'class_teacher'):
                st.success(f"✅ Class teacher assigned: {next(u['username'] for u in teacher_users if u['id'] == ct_user_id)}.")
                st.rerun()
            else:
                st.error("❌ Failed to assign class teacher. Assignment may already exist.")

    st.markdown("---")

    # ── Assign Subject Teacher ────────────────────────────────────────────────
    st.subheader("Assign Subject Teacher")

    if 'selected_class_for_subject' not in st.session_state:
        st.session_state.selected_class_for_subject = None

    col1, col2, col3 = st.columns(3)
    with col1:
        st_user_id = st.selectbox(
            "Select Teacher",
            [u["id"] for u in teacher_users],
            format_func=lambda x: next(u["username"] for u in teacher_users if u["id"] == x),
            key="subject_teacher_select"
        )
        ActivityTracker.watch_value("subject_teacher_select", st_user_id)
    with col2:
        selected_class = st.selectbox("Select Class", class_options, key="subject_teacher_class_select")
        ActivityTracker.watch_value("subject_teacher_class_select", selected_class)

    if st.session_state.selected_class_for_subject != selected_class:
        st.session_state.selected_class_for_subject = selected_class

    class_name = classes[class_options.index(selected_class)]['class_name']
    subjects = get_fresh_subjects(class_name)

    if not subjects:
        st.warning("⚠️ No subjects available for this class. Add subjects in the Manage Subjects section.")
        return

    is_kindergarten_nursery = (
        class_name.upper().startswith("KINDERGARTEN") or class_name.upper().startswith("NURSERY")
    )

    if is_kindergarten_nursery:
        st.info(f"💡 **Tip:** For {class_name.split()[0]} classes, you can assign all subjects at once using the button below.")

    with col3:
        subject_options = [s["subject_name"] if isinstance(s, dict) else s[1] for s in subjects]
        subject_name = st.selectbox("Select Subject", [""] + subject_options, key=f"subject_select_{selected_class}")
        ActivityTracker.watch_value("subject_select", subject_name)

    if is_kindergarten_nursery:
        with st.form("assign_subject_teacher_form"):
            col_single, col_batch = st.columns([1, 1])
            with col_single:
                st.markdown("**Assign Single Subject**")
                submitted_single = st.form_submit_button("Assign Subject Teacher", disabled=not subject_name, width='stretch')
            with col_batch:
                st.markdown("**Assign All Subjects**")
                st.caption(f"This will assign **{len(subjects)} subjects** to the selected teacher.")
                submitted_all = st.form_submit_button("Assign All Subjects", type="primary", width='stretch')

            if submitted_single:
                ActivityTracker.update()
            if submitted_all:
                ActivityTracker.update()

            if submitted_single and subject_name:
                if assign_teacher(st_user_id, class_name, active_session or '', subject_name, 'subject_teacher'):
                    st.success(f"✅ Subject teacher assigned: {next(u['username'] for u in teacher_users if u['id'] == st_user_id)} to {subject_name}.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Failed to assign subject teacher. Assignment may already exist.")

            if submitted_all:
                subject_names = [s['subject_name'] if isinstance(s, dict) else s[1] for s in subjects]
                success_count, failed_subjects = batch_assign_subject_teacher(st_user_id, class_name, active_session or '', subject_names)
                if success_count == len(subjects):
                    st.success(f"✅ All {success_count} subjects assigned successfully to {next(u['username'] for u in teacher_users if u['id'] == st_user_id)}!")
                elif success_count > 0:
                    st.warning(f"⚠️ {success_count} subjects assigned. {len(failed_subjects)} subjects already existed or failed.")
                    if failed_subjects:
                        st.info(f"Skipped subjects: {', '.join(failed_subjects)}")
                else:
                    st.error("❌ No subjects were assigned. They may already exist.")
                time.sleep(1)
                st.rerun()
    else:
        with st.form("assign_subject_teacher_form_regular"):
            submitted = st.form_submit_button("Assign Subject Teacher", disabled=not subject_name)
            ActivityTracker.watch_form(submitted)
            if submitted and subject_name:
                if assign_teacher(st_user_id, class_name, active_session or '', subject_name, 'subject_teacher'):
                    st.success(f"✅ Subject teacher assigned: {next(u['username'] for u in teacher_users if u['id'] == st_user_id)} to {subject_name}.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Failed to assign subject teacher. Assignment may already exist.")


def render_analytics_tab(stats):
    """Render analytics and reports tab"""
    inject_metric_css()

    # ── Filter row: Session + Term ────────────────────────────────────────────
    all_sessions = get_all_sessions()
    session_names = [s["session"] if isinstance(s, dict) else s[0] for s in all_sessions]

    TERM_LABELS = {
        "First":  "1st Term",
        "Second": "2nd Term",
        "Third":  "3rd Term",
    }

    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        if session_names:
            active_session = get_active_session()
            default_idx = session_names.index(active_session) if active_session in session_names else 0
            selected_session = st.selectbox(
                "Session",
                session_names,
                index=default_idx,
                key="analytics_session_filter",
            )
        else:
            selected_session = None
            st.info("No sessions configured yet.")

    with filter_col2:
        selected_term = st.selectbox(
            "Term",
            ["First", "Second", "Third"],
            format_func=lambda t: TERM_LABELS[t],
            key="analytics_term_filter",
        )

    st.markdown("---")

    # ── Class Overview ────────────────────────────────────────────────────────
    st.markdown("#### Class Overview")

    class_summary = get_classes_summary()

    if class_summary:
        filtered_summary = [
            r for r in class_summary
            if selected_session is None or r["session"] == selected_session
        ]

        if filtered_summary:
            conn = get_connection()
            cursor = conn.cursor()
            class_data = []
            for row in filtered_summary:
                scores = get_scores_for_class(
                    row["class_name"], row["session"], selected_term
                )
                # Count unique students enrolled for this specific class + session + term
                cursor.execute("""
                    SELECT COUNT(DISTINCT css.student_name)
                    FROM   class_session_students css
                    JOIN   class_sessions cs ON cs.id = css.class_session_id
                    WHERE  cs.class_name = ? AND cs.session = ? AND css.term = ?
                """, (row["class_name"], row["session"], selected_term))
                student_count = cursor.fetchone()[0]

                class_data.append({
                    "Class":    row["class_name"],
                    "Session":  row["session"] or "-",
                    "Term":     TERM_LABELS[selected_term],
                    "Students": student_count,
                    "Subjects": row["subject_count"],
                    "Scores":   len(scores),
                })
            conn.close()
            streamlit_paginator(class_data, table_name="class_summary_analytics")
        else:
            st.info(f"No classes found for session **{selected_session}**.")
    else:
        st.info("No classes found in the system.")

    st.markdown("---")

    # ── Activity Statistics (per selected session + term) ─────────────────────
    st.markdown("#### 📈 Activity Statistics")

    if selected_session:
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Active classes: class_sessions in the selected session with ≥1 enrolled student
            cursor.execute("""
                SELECT COUNT(DISTINCT cs.id)
                FROM   class_sessions cs
                JOIN   class_session_students css ON css.class_session_id = cs.id
                WHERE  cs.session = ?
            """, (selected_session,))
            active_classes = cursor.fetchone()[0]

            # Total students: unique students enrolled for the selected session + term
            cursor.execute("""
                SELECT COUNT(DISTINCT css.student_name)
                FROM   class_session_students css
                JOIN   class_sessions cs ON cs.id = css.class_session_id
                WHERE  cs.session = ? AND css.term = ?
            """, (selected_session, selected_term))
            total_students = cursor.fetchone()[0]

            # Active students: distinct enrollments that have at least one score
            # in the selected session + term
            cursor.execute("""
                SELECT COUNT(DISTINCT sc.enrollment_id)
                FROM   scores sc
                JOIN   class_session_students css ON css.id = sc.enrollment_id
                JOIN   class_sessions         cs  ON cs.id  = css.class_session_id
                WHERE  cs.session = ? AND sc.term = ?
            """, (selected_session, selected_term))
            active_students = cursor.fetchone()[0]

            # Expected scores: enrolled students × subjects for the selected session + term
            cursor.execute("""
                SELECT COUNT(*)
                FROM   class_session_students css
                JOIN   class_sessions cs  ON cs.id  = css.class_session_id
                JOIN   subjects       sub ON sub.class_name = cs.class_name
                WHERE  cs.session = ? AND css.term = ?
            """, (selected_session, selected_term))
            expected = cursor.fetchone()[0]

            # Actual scores recorded for the selected session + term
            cursor.execute("""
                SELECT COUNT(*)
                FROM   scores sc
                JOIN   class_session_students css ON css.id = sc.enrollment_id
                JOIN   class_sessions         cs  ON cs.id  = css.class_session_id
                WHERE  cs.session = ? AND sc.term = ?
            """, (selected_session, selected_term))
            actual = cursor.fetchone()[0]

            conn.close()
            score_completion = int((actual / expected * 100) if expected > 0 else 0)

        except Exception as e:
            active_classes   = 0
            total_students   = 0
            active_students  = 0
            score_completion = 0
    else:
        # Fallback to global stats when no session is available
        activity_stats   = get_activity_statistics()
        active_classes   = activity_stats["active_classes"]
        total_students   = 0
        active_students  = activity_stats["active_students"]
        score_completion = activity_stats["score_completion"]

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Active Classes", active_classes)
    with col2:
        st.metric("Total Students", total_students)
    with col3:
        st.metric("Active Students", active_students)
    with col4:
        st.metric("Score Completion", f"{score_completion}%")
    with col5:
        st.metric("Assignments", stats["assignments"])




def render_academic_settings_tab():
    """Render Academic Settings tab — manage sessions and active term"""
    st.subheader("Academic Settings")
    st.info(
        "Configure the active session and term. All teachers will automatically see the "
        "active term when entering scores, comments, and reports."
    )

    performed_by = st.session_state.get('user_id')

    if 'show_delete_session_confirm' not in st.session_state:
        st.session_state.show_delete_session_confirm = False
    if 'session_to_delete_name' not in st.session_state:
        st.session_state.session_to_delete_name = None

    # ── Current active settings ───────────────────────────────────────────────
    active_session = get_active_session()
    active_term = get_active_term_name()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Active Session", active_session or "Not set")
    with col2:
        st.metric("Active Term", active_term or "Not set")

    st.markdown("---")

    # ── Set active term ───────────────────────────────────────────────────────
    st.markdown("#### Set Active Session & Term")

    all_sessions = get_all_sessions()
    session_names = [s['session'] if isinstance(s, dict) else s[0] for s in all_sessions]

    if not session_names:
        st.warning("⚠️ No sessions available. Create a session below first.")
    else:
        with st.form("set_active_term_form"):
            col1, col2 = st.columns(2)
            with col1:
                sel_session = st.selectbox("Session", session_names, key="set_term_session")
            with col2:
                sel_term = st.selectbox("Term", ["1st Term", "2nd Term", "3rd Term"], key="set_term_term")
            submitted = st.form_submit_button("✅ Set as Active Term", type="primary")
            ActivityTracker.watch_form(submitted)
            if submitted:
                term_map = {"1st Term": "First", "2nd Term": "Second", "3rd Term": "Third"}
                internal_term = term_map[sel_term]
                if set_active_term(sel_session, internal_term, performed_by):
                    st.success(f"✅ Active term set to {sel_term} — {sel_session}.")
                    st.rerun()
                else:
                    st.error("❌ Failed to set active term.")

    st.markdown("---")

    # ── Session management ────────────────────────────────────────────────────
    col_create, col_delete = st.columns(2)

    with col_create:
        st.markdown("#### Create Session")
        with st.form("create_session_form"):
            new_session = st.text_input(
                "Session Name",
                placeholder="e.g. 2025/2026"
            )
            submitted_create = st.form_submit_button("➕ Create Session")
            ActivityTracker.watch_form(submitted_create)
            if submitted_create:
                if not new_session.strip():
                    st.error("❌ Please enter a session name.")
                else:
                    parts = new_session.strip().split('/')
                    if (len(parts) != 2
                            or not all(p.isdigit() and len(p) == 4 for p in parts)):
                        st.error("❌ Session must be in format YYYY/YYYY (e.g. 2025/2026).")
                    elif new_session.strip() in session_names:
                        st.error(f"❌ Session '{new_session.strip()}' already exists.")
                    else:
                        if create_session(new_session.strip()):
                            st.success(f"✅ Session '{new_session.strip()}' created.")
                            st.rerun()
                        else:
                            st.error("❌ Failed to create session.")

    with col_delete:
        st.markdown("#### Delete Session")
        if not session_names:
            st.info("No sessions to delete.")
        else:
            with st.form("delete_session_form"):
                session_to_del = st.selectbox(
                    "Select Session to Delete",
                    session_names,
                    key="del_session_select",
                    help="Deleting a session removes all associated class-session enrollments and scores."
                )
                submitted_delete = st.form_submit_button("🗑️ Delete Session", type="secondary")
                ActivityTracker.watch_form(submitted_delete)
                if submitted_delete:
                    st.session_state.session_to_delete_name = session_to_del
                    st.session_state.show_delete_session_confirm = True

    if st.session_state.show_delete_session_confirm and st.session_state.session_to_delete_name:
        sname = st.session_state.session_to_delete_name

        @st.dialog("Confirm Session Deletion")
        def confirm_delete_session():
            st.markdown("### Are you sure you want to delete this session?")
            st.error(f"**Session:** {sname}")
            st.markdown("---")
            st.warning("⚠️ **This action cannot be undone!**")
            st.warning("• All class enrollments for this session will be deleted")
            st.warning("• All student scores and results will be permanently lost")
            st.warning("• This session cannot be the currently active session")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚫 Cancel", key="cancel_delete_session", type="secondary", width='stretch'):
                    st.session_state.show_delete_session_confirm = False
                    st.session_state.session_to_delete_name = None
                    st.rerun()
            with col2:
                if st.button("❌ Delete Session", key="confirm_delete_session_btn", type="primary", width='stretch'):
                    ActivityTracker.update()
                    success, reason = delete_session(sname, str(performed_by))
                    st.session_state.show_delete_session_confirm = False
                    st.session_state.session_to_delete_name = None
                    if success:
                        st.success(f"✅ Session '{sname}' deleted successfully.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ {reason}")

        confirm_delete_session()

    st.markdown("---")
    st.markdown("#### All Sessions")
    if all_sessions:
        for s in all_sessions:
            sname = s['session'] if isinstance(s, dict) else s[0]
            is_active = (sname == active_session)
            badge = "✅ **Active**" if is_active else ""
            st.markdown(f"- {sname} {badge}")
    else:
        st.info("No sessions configured.")

    # ── Rename session ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### ✏️ Rename Session")
    if not session_names:
        st.info("No sessions available to rename.")
    else:
        with st.form("rename_session_form"):
            col1, col2 = st.columns(2)
            with col1:
                session_to_rename = st.selectbox("Session to Rename", session_names, key="rename_session_select")
            with col2:
                new_session_name = st.text_input("New Name", placeholder="e.g. 2025/2026")
            submitted_rename = st.form_submit_button("✏️ Rename Session")
            ActivityTracker.watch_form(submitted_rename)
            if submitted_rename:
                if not new_session_name.strip():
                    st.error("❌ New name cannot be blank.")
                else:
                    parts = new_session_name.strip().split('/')
                    if len(parts) != 2 or not all(p.isdigit() and len(p) == 4 for p in parts):
                        st.error("❌ Session must be in format YYYY/YYYY (e.g. 2025/2026).")
                    else:
                        success, reason = update_session(session_to_rename, new_session_name.strip(), str(performed_by))
                        if success:
                            st.success(f"✅ Session renamed to '{new_session_name.strip()}'.")
                            st.rerun()
                        else:
                            st.error(f"❌ {reason}")

    # ── Class-Session Enrollment ───────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 🏫 Open Classes for Active Session")
    st.info(
        "Before teachers can register students or enter scores, each class must be "
        "opened for the active session. Tick classes below and click **Open Selected Classes**. "
        "This is safe to run multiple times — already-open classes are skipped."
    )

    if not active_session:
        st.warning("⚠️ Set an active session above before opening classes.")
    else:
        all_cls = get_all_classes()
        if not all_cls:
            st.info("No classes defined yet. Create classes first.")
        else:
            already_open = {c["class_name"] for c in get_classes_for_session(active_session)}

            cls_cols = st.columns(3)
            class_checks = {}
            for i, c in enumerate(all_cls):
                cname = c["class_name"]
                is_open = cname in already_open
                label = f"{'✅' if is_open else '☐'} {cname}"
                class_checks[cname] = cls_cols[i % 3].checkbox(
                    label, value=False, key=f"open_class_{cname}",
                    disabled=is_open,
                    help="Already open for this session" if is_open else "Tick to open for current session"
                )

            selected_to_open = [cn for cn, checked in class_checks.items() if checked]

            if st.button("🔓 Open Selected Classes", key="open_classes_btn",
                         disabled=not selected_to_open, type="primary"):
                ActivityTracker.update()
                opened, skipped = 0, 0
                for cn in selected_to_open:
                    if open_class_for_session(cn, active_session):
                        opened += 1
                    else:
                        skipped += 1
                if opened:
                    st.success(f"✅ Opened {opened} class(es) for {active_session}.")
                if skipped:
                    st.info(f"{skipped} class(es) were already open.")
                st.rerun()


if __name__ == '__main__':
    admin_panel()