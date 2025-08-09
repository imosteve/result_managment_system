import streamlit as st
import time
from database import (
    get_all_classes, get_subjects_by_class,
    create_user, get_all_users, delete_user, assign_teacher, get_user_assignments,
    delete_assignment, get_database_stats
)
from utils import inject_login_css

def admin_interface():
    """Admin interface for user management and assignments"""
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    if st.session_state.role != "admin":
        st.error("⚠️ Access denied. Admins only.")
        st.switch_page("main.py")
        return

    user_id = st.session_state.get('user_id', None)
    role = st.session_state.get('role', None)

    if user_id is None or role is None:
        st.error("⚠️ Session state missing user_id or role. Please log out and log in again.")
        return

    st.set_page_config(page_title="Admin Interface", layout="wide")
    
    # Header
    st.markdown(
        """
        <div style='width: auto; margin: auto; text-align: center; background-color: #c6b7b1;'>
            <h2 style='color:#000; font-size:24px; margin-top:30px; margin-bottom:20px;'>
                Admin Dashboard
            </h2>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Dashboard Metrics
    stats = get_database_stats()
    col1, col2, col3, col4 = st.columns(4)
    inject_login_css("templates/metrics_styles.css")
    with col1:
        st.markdown(f"<div class='custom-metric'><div class='label'>Total Users</div><div class='value'>{stats['users']}</div></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='custom-metric'><div class='label'>Total Classes</div><div class='value'>{stats['classes']}</div></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='custom-metric'><div class='label'>Total Assignments</div><div class='value'>{stats['assignments']}</div></div>", unsafe_allow_html=True)
    with col4:
        st.markdown(f"<div class='custom-metric'><div class='label'>Total Comments</div><div class='value'>{stats['comments']}</div></div>", unsafe_allow_html=True)

    st.markdown("---")

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
        # Add refresh button
        col1, col2 = st.columns([4, 1])
        with col2:
            if st.button("🔄 Refresh Data", key="refresh_user_tab"):
                st.rerun()
                
        st.subheader("Current Users")
        users = get_all_users()
        if users:
            user_data = [{"Username": u[1], "Role": u[2], "Password": u[3]} for u in users]
            st.dataframe(user_data, use_container_width=True)
            user_id_to_delete = st.selectbox(
                "Select User to Delete",
                [u[0] for u in users],
                format_func=lambda x: next(u[1] for u in users if u[0] == x),
                key="delete_user_select"
            )
            if st.button("🗑️ Delete Selected User", key="delete_user_button"):
                if user_id_to_delete == user_id:
                    st.error("⚠️ Cannot delete your own account.")
                else:
                    delete_user(user_id_to_delete)
                    st.success(f"✅ User deleted successfully.")
                    st.rerun()
        else:
            st.info("No users found.")

    # Add New User Tab
    with tabs[1]:
        # Add refresh button
        col1, col2 = st.columns([4, 1])
        with col2:
            if st.button("🔄 Refresh Data", key="refresh_new_user"):
                st.rerun()

        with st.form("add_user_form"):
            st.subheader("Add New User")
            # Use a dynamic key based on a session state counter
            form_key = f"add_user_form_{st.session_state.get('form_submit_count', 0)}"
            username = st.text_input("Username", key=f"username_{form_key}")
            password = st.text_input("Password", type="password", key=f"password_{form_key}")
            role = st.selectbox("Role", ["admin", "class_teacher", "subject_teacher"], key=f"role_{form_key}")
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

    # View/Edit Teachers Assignment Tab
    with tabs[2]:
        # Add refresh button
        col1, col2 = st.columns([4, 1])
        with col2:
            if st.button("🔄 Refresh Data", key="refresh_teachers_tab"):
                st.rerun()

        st.subheader("Current Assignments")
        users = get_all_users()
        assignments = []
        for user in users:
            user_assignments = get_user_assignments(user[0])
            for a in user_assignments:
                assignments.append({
                    "ID": a[0],
                    "Teacher": user[1],
                    "Role": user[2],
                    "Class": f"{a['class_name']} - {a['term']} - {a['session']}",
                    "Subject": a['subject_name'] or "-"
                })
        if assignments:
            st.dataframe(assignments, use_container_width=True)
            assignment_id_to_edit = st.selectbox(
                "Select Assignment to Edit/Delete",
                [a["ID"] for a in assignments],
                format_func=lambda x: next(f"{a['Teacher']} - {a['Class']} - {a['Subject']}" for a in assignments if a["ID"] == x),
                key="edit_assignment_select"
            )
            selected_assignment = next((a for a in assignments if a["ID"] == assignment_id_to_edit), None)
            if selected_assignment:
                st.subheader("Edit Assignment")
                with st.form("edit_assignment_form"):
                    classes = get_fresh_classes()
                    class_options = [f"{cls['class_name']} - {cls['term']} - {cls['session']}" for cls in classes]
                    selected_class = st.selectbox(
                        "Select Class",
                        class_options,
                        index=class_options.index(selected_assignment["Class"]) if selected_assignment["Class"] in class_options else 0,
                        key="edit_class_select"
                    )
                    selected_index = class_options.index(selected_class)
                    class_data = classes[selected_index]
                    new_class_name, new_term, new_session = class_data['class_name'], class_data['term'], class_data['session']
                    new_subject_name = None
                    if selected_assignment["Role"] == "subject_teacher":
                        subjects = get_fresh_subjects(new_class_name, new_term, new_session)
                        subject_options = [s[1] for s in subjects]
                        if subject_options:
                            new_subject_name = st.selectbox(
                                "Select Subject",
                                subject_options,
                                index=subject_options.index(selected_assignment["Subject"]) if selected_assignment["Subject"] in subject_options else 0,
                                key="edit_subject_select"
                            )
                        else:
                            st.warning("⚠️ No subjects available for this class. Add subjects in the Manage Subjects section.")
                    submitted = st.form_submit_button(
                        "Update Assignment",
                        disabled=(selected_assignment["Role"] == "subject_teacher" and new_subject_name is None)
                    )
                    if submitted:
                        # Delete old assignment and create new one
                        delete_assignment(assignment_id_to_edit)
                        if assign_teacher(
                            user_id=next(u[0] for u in users if u[1] == selected_assignment["Teacher"]),
                            class_name=new_class_name,
                            term=new_term,
                            session=new_session,
                            subject_name=new_subject_name
                        ):
                            st.success(f"✅ Assignment updated for {selected_assignment['Teacher']}.")
                            st.rerun()
                        else:
                            st.error("❌ Failed to update assignment. It may already exist.")
                    if st.form_submit_button("Delete Assignment"):
                        delete_assignment(assignment_id_to_edit)
                        st.success(f"✅ Assignment deleted successfully.")
                        st.rerun()
        else:
            st.info("No assignments found.")

    # Assign/Delete Class Teacher Tab
    with tabs[3]:
        # Add refresh button
        col1, col2 = st.columns([4, 1])
        with col2:
            if st.button("🔄 Refresh Data", key="refresh_class_teacher"):
                st.rerun()
        
        # st.subheader("Assign Class Teacher")
        with st.form("assign_class_teacher_form"):
            users = get_all_users()
            user_options = [(u[0], u[1], u[2]) for u in users if u[2] == "class_teacher"]
            if not user_options:
                st.warning("⚠️ No class teachers available. Add teachers in the Add New User tab.")
                submitted = st.form_submit_button("Assign", disabled=True)
            else:
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
        
        st.subheader("Delete Class Teacher Assignment")
        class_teacher_assignments = [
            a for a in assignments if a["Role"] == "class_teacher"
        ]
        if class_teacher_assignments:
            assignment_id_to_delete = st.selectbox(
                "Select Class Teacher Assignment to Delete",
                [a["ID"] for a in class_teacher_assignments],
                format_func=lambda x: next(f"{a['Teacher']} - {a['Class']}" for a in class_teacher_assignments if a["ID"] == x),
                key="delete_class_teacher_select"
            )
            if st.button("🗑️ Delete Selected Assignment", key="delete_class_teacher_button"):
                delete_assignment(assignment_id_to_delete)
                st.success("✅ Class teacher assignment deleted successfully.")
                st.rerun()
        else:
            st.info("No class teacher assignments found.")

    # Assign/Delete Subject Teacher Tab
    with tabs[4]:
        # Add refresh button
        col1, col2 = st.columns([4, 1])
        with col2:
            if st.button("🔄 Refresh Data", key="refresh_subject_teacher"):
                st.rerun()
        
        # st.subheader("Assign Subject Teacher")
        
        # Initialize session state for dynamic updates
        if 'selected_class_for_subject' not in st.session_state:
            st.session_state.selected_class_for_subject = None
        
        users = get_all_users()
        user_options = [(u[0], u[1], u[2]) for u in users if u[2] == "subject_teacher"]
        
        if not user_options:
            st.warning("⚠️ No subject teachers available. Add teachers in the Add New User tab.")
        else:
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
                    st.info(f"Debug: Looking for subjects in {class_name} - {term} - {session}")
                    subject_name = None
                else:
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
        
        st.subheader("Delete Subject Teacher Assignment")
        subject_teacher_assignments = [
            a for a in assignments if a["Role"] == "subject_teacher"
        ]
        if subject_teacher_assignments:
            assignment_id_to_delete = st.selectbox(
                "Select Subject Teacher Assignment to Delete",
                [a["ID"] for a in subject_teacher_assignments],
                format_func=lambda x: next(f"{a['Teacher']} - {a['Class']} - {a['Subject']}" for a in subject_teacher_assignments if a["ID"] == x),
                key="delete_subject_teacher_select"
            )
            if st.button("🗑️ Delete Selected Assignment", key="delete_subject_teacher_button"):
                delete_assignment(assignment_id_to_delete)
                st.success("✅ Subject teacher assignment deleted successfully.")
                st.rerun()
        else:
            st.info("No subject teacher assignments found.")

if __name__ == "__main__":
    admin_interface()