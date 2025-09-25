# app_sections/manage_subjects.py

import streamlit as st
import time
import pandas as pd
from database import (
    get_all_classes, get_subjects_by_class, create_subject, delete_subject, update_subject, clear_all_subjects,
    get_students_by_class, get_student_selected_subjects, save_student_subject_selections, 
    get_all_student_subject_selections
)
from utils import clean_input, create_metric_4col, inject_login_css, render_page_header

def add_subjects():
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    if st.session_state.role not in ["superadmin", "admin", "class_teacher", "subject_teacher"]:
        st.error("⚠️ Access denied.")
        return

    user_id = st.session_state.get("user_id", None)
    role = st.session_state.get("role", None)

    st.set_page_config(page_title="Manage Subjects", layout="wide")

    # Custom CSS for better table styling
    inject_login_css("templates/tabs_styles.css")

    # Subheader
    render_page_header("Manage Subject Combination")

    classes = get_all_classes(user_id, role)
    if not classes:
        st.warning("⚠️ Please create at least one class first.")
        if role in ["class_teacher", "subject_teacher"]:
            st.info("You may need to select a class assignment in the 'Change Assignment' section.")
        return

    # Select class
    class_options = [f"{cls['class_name']} - {cls['term']} - {cls['session']}" for cls in classes]
    if role in ["class_teacher", "subject_teacher"]:
        assignment = st.session_state.get("assignment")
        if not assignment:
            st.warning("⚠️ No class assignment selected. Please select a class in the 'Change Assignment' section.")
            class_options = []  # Prevent class selection until assignment is set
            selected_class_display = None
        else:
            allowed_class = f"{assignment['class_name']} - {assignment['term']} - {assignment['session']}"
            if allowed_class not in class_options:
                st.error("⚠️ Assigned class not found in available classes. Please select a new assignment.")
                return
            class_options = [allowed_class]
            selected_class_display = st.selectbox("Select Class", class_options, disabled=True)
    else:
        selected_class_display = st.selectbox("Select Class", class_options)

    if not class_options:
        return

    selected_index = class_options.index(selected_class_display)
    selected_class_data = classes[selected_index]
    class_name = selected_class_data['class_name']
    term = selected_class_data['term']
    session = selected_class_data['session']

    # Get existing subjects
    subjects = get_subjects_by_class(class_name, term, session, user_id, role)

    # Check if this is SSS2 or SSS3 to show subject selection tab
    is_senior_class = class_name in ["SSS 2", "SSS 3"]

    # Tabs for different operations - add subject selection for senior classes
    if is_senior_class:
        tab1, tab2, tab3, tab4 = st.tabs(["View/Edit Subjects", "Add Subjects", "Clear All Subjects", "Student Subject Selection"])
    else:
        tab1, tab2, tab3 = st.tabs(["View/Edit Subjects", "Add Subjects", "Clear All Subjects"])

    with tab1:
        st.subheader("View/Edit Subjects")
        if subjects:
            # Display class metrics
            create_metric_4col(class_name, term, session, subjects, "subject")
            
            # Table header using columns
            header_cols = st.columns([0.5, 5, 1, 1])
            header_cols[0].markdown("**S/N**")
            header_cols[1].markdown("**Subject Name**")
            header_cols[2].markdown("**Update**")
            header_cols[3].markdown("**Delete**")

            for i, subject in enumerate(subjects):
                col1, col2, col3, col4 = st.columns([0.5, 5, 1, 1], gap="small", vertical_alignment="bottom")
                
                # Display serial number (S/N)
                col1.markdown(f"**{i+1}**")

                # Editable field for subject name
                new_subject_name = col2.text_input(
                    "Subject",
                    value=subject[1],
                    key=f"subject_name_{i}",
                    label_visibility="collapsed"
                ).upper()

                # Update button (disabled for subject_teacher)
                update_disabled = role == "subject_teacher"
                if col3.button("💾", key=f"update_{i}", disabled=update_disabled):
                    new_subject_name_upper = clean_input(new_subject_name, "subject").strip().upper()
                    # Check for duplicates (excluding the current subject)
                    if any(
                        other_subj[1].strip().upper() == new_subject_name_upper and
                        other_subj[0] != subject[0]
                        for other_subj in subjects
                    ):
                        st.markdown(f'<div class="error-container">⚠️ A subject with name \'{new_subject_name_upper}\' already exists for this class.</div>', unsafe_allow_html=True)
                    else:
                        success = update_subject(
                            subject_id=subject[0],
                            new_subject_name=new_subject_name_upper,
                            new_class_name=class_name,
                            new_term=term,
                            new_session=session
                        )
                        if success:
                            st.markdown(f'<div class="success-container">✅ Updated to {new_subject_name_upper}</div>', unsafe_allow_html=True)
                            st.rerun()
                        else:
                            st.markdown(f'<div class="error-container">⚠️ Failed to update \'{new_subject_name_upper}\'. It may already exist.</div>', unsafe_allow_html=True)

                # Delete button (disabled for subject_teacher)
                delete_disabled = role == "subject_teacher"
                if col4.button("❌", key=f"delete_{i}", disabled=delete_disabled):
                    st.session_state["delete_pending"] = {
                        "subject_id": subject[0],
                        "subject_name": subject[1],
                        "class_name": class_name,
                        "term": term,
                        "session": session,
                        "index": i
                    }
                    confirm_delete_single_subject()
        else:
            st.info("No subjects found for this class. Add subjects in the 'Add Subjects' tab.")

    with tab2:
        st.subheader("Add Subjects")
        if role == "subject_teacher":
            st.info("Subject Teachers cannot add new subjects.")
        else:
            # Initialize form counter for clearing input
            if 'subject_form_counter' not in st.session_state:
                st.session_state.subject_form_counter = 0
                
            with st.form(f"add_subject_form_{st.session_state.subject_form_counter}"):
                new_subjects_input = st.text_area(
                    "Enter subject names (one per line)",
                    height=150,
                    placeholder="Mathematics\nEnglish Language\nPhysics"
                )
                submitted = st.form_submit_button("➕ Add Subjects")
                if submitted:
                    new_subjects_raw = [clean_input(s, "subject").strip().upper() for s in new_subjects_input.split("\n") if s.strip()]
                    unique_new_subjects = list(set(new_subjects_raw))
                    existing_subject_names = {s[1].upper() for s in subjects}
                    if not unique_new_subjects:
                        st.markdown('<div class="error-container">⚠️ Please enter at least one valid subject.</div>', unsafe_allow_html=True)
                    else:
                        added, skipped = [], []
                        for subject in unique_new_subjects:
                            if subject in existing_subject_names:
                                skipped.append(subject)
                            else:
                                success = create_subject(subject, class_name, term, session)
                                if success:
                                    added.append(subject)
                                else:
                                    skipped.append(subject)
                        if added:
                            st.markdown(f'<div class="success-container">✅ Successfully added: {", ".join(added)}</div>', unsafe_allow_html=True)
                            # Clear the form by incrementing counter
                            st.session_state.subject_form_counter += 1
                            st.rerun()
                        if skipped:
                            st.markdown(f'<div class="error-container">⚠️ Skipped (duplicates or failed to add): {", ".join(skipped)}</div>', unsafe_allow_html=True)
    
    with tab3:
        st.subheader("Clear All Subjects")
        if role == "subject_teacher":
            st.info("Subject Teachers cannot clear subjects.")
        else:
            st.warning("⚠️ This action will permanently delete all subjects and their associated scores for the selected class. This cannot be undone.")
            
            # Initialize session state for delete confirmation
            if 'user_clear_all_subjects' not in st.session_state:
                st.session_state.user_clear_all_subjects = None

            if subjects:
                confirm_clear = st.checkbox("I confirm I want to clear all subjects for this class")
                clear_all_button = st.button("🗑️ Clear All Subjects", key="clear_all_subjects", disabled=not confirm_clear)
                
                # Confirmation dialog
                if clear_all_button and confirm_clear:
                    @st.dialog("Confirm Subjects Deletion")
                    def confirm_delete_all_subjects():
                        st.warning("⚠️ This action will permanently delete all subjects and their associated scores for the selected class. Do you want to proceed?")
                        
                        col1, col2 = st.columns(2)
                        # if col1:
                        if col1.button("🚫 Cancel", key="cancel_delete_subjects", type="secondary"):
                            st.session_state.user_clear_all_subjects = None
                            st.info("Deletion cancelled.")
                            st.rerun()
                        # if col2:
                        elif col2.button("❌ Delete", key="confirm_delete_subjects", type="primary"):
                            st.session_state.user_clear_all_subjects = clear_all_subjects(class_name, term, session)
                            if st.session_state.user_clear_all_subjects:
                                st.session_state.user_clear_all_subjects = None
                                st.markdown(f'<div class="success-container">✅ All subjects cleared successfully for {class_name} - {term} - {session}!</div>', unsafe_allow_html=True)
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.markdown(f'<div class="error-container">❌ Failed to clear subjects. Please try again.</div>', unsafe_allow_html=True)
                    confirm_delete_all_subjects()
            else:
                st.info("No subjects available to clear.")

        pass
    
    # Student Subject Selection Tab (only for SSS2 and SSS3)
    if is_senior_class:
        with tab4:
            st.subheader("Student Subject Selection")
            if role == "subject_teacher":
                st.info("Subject Teachers cannot manage student subject selections.")
            else:
                students = get_students_by_class(class_name, term, session, user_id, role)
                if not students:
                    st.warning(f"⚠️ No students found for {class_name} - {term} - {session}.")
                    return

                if not subjects:
                    st.warning("⚠️ No subjects available. Please add subjects first.")
                    return

                # Initialize session state for selections if not exists
                if 'student_selections' not in st.session_state:
                    st.session_state.student_selections = {}

                # Load current selections for all students
                selections = get_all_student_subject_selections(class_name, term, session)
                selection_dict = {}
                for student_name, subject_name in selections:
                    if student_name not in selection_dict:
                        selection_dict[student_name] = []
                    selection_dict[student_name].append(subject_name)

                subject_names = [s[1] for s in subjects]
                
                # Display table header
                # st.markdown("##### Subject Selection Matrix")
                
                # Create header with subject names
                header_cols = [0.6, 2, 0.6] + [0.6] * len(subject_names)  # SN, Name, Count, then subjects
                col_headers = st.columns(header_cols)
                
                col_headers[0].markdown("**S/N**")
                col_headers[1].markdown("**Student Name**")
                col_headers[2].markdown("**NOS**")
                
                # Subject headers
                for i, subject_name in enumerate(subject_names):
                    col_headers[3 + i].markdown(f"**{subject_name[:3]}**")

                # Display each student row with checkboxes
                for idx, student in enumerate(students):
                    student_name = student[1]
                    current_selections = selection_dict.get(student_name, [])
                    
                    # Create row columns
                    row_cols = st.columns(header_cols, vertical_alignment="center")
                    
                    # S/N
                    row_cols[0].markdown(f"**{idx + 1}**")
                    
                    # Student Name
                    row_cols[1].markdown(f"**{" ".join(student_name.split(" ")[:2])}**")
                    
                    # Count selected subjects and store selections
                    selected_subjects = []
                    
                    # Subject checkboxes
                    for i, subject_name in enumerate(subject_names):
                        is_selected = subject_name in current_selections
                        
                        # Use unique key for each checkbox
                        checkbox_key = f"student_{idx}_{subject_name}_{class_name}_{term}_{session}"
                        
                        if row_cols[3 + i].checkbox(
                            "subject name",  # Empty label since header shows subject name
                            value=is_selected,
                            key=checkbox_key,
                            label_visibility="collapsed"
                        ):
                            selected_subjects.append(subject_name)
                    
                    # Update session state with current selections
                    st.session_state.student_selections[student_name] = selected_subjects
                    
                    # Display count of selected subjects
                    row_cols[2].markdown(f"**{len(selected_subjects)}**")

                st.markdown("---")

                # Save all selections button
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    if st.button("💾 Save All Selections", key="save_all_selections", type="primary"):
                        try:
                            success_count = 0
                            for student_name, selected_subjects in st.session_state.student_selections.items():
                                save_student_subject_selections(
                                    student_name, 
                                    selected_subjects, 
                                    class_name, 
                                    term, 
                                    session
                                )
                                success_count += 1
                            
                            st.success(f"✅ Subject selections saved for {success_count} students")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error saving selections: {str(e)}")

                with col2:
                    if st.button("🔄 Refresh Data", key="refresh_selections"):
                        # Clear session state to reload fresh data
                        if 'student_selections' in st.session_state:
                            del st.session_state.student_selections
                        st.rerun()

                st.markdown("---")

                # Batch operations
                st.markdown("### Batch Operations")
                
                batch_col1, batch_col2, batch_col3 = st.columns(3)
                
                with batch_col1:
                    st.markdown("#### Select All Subjects")
                    if st.button("📚 Assign All Subjects to All Students", key="assign_all_subjects"):
                        try:
                            for student in students:
                                student_name = student[1]
                                save_student_subject_selections(
                                    student_name, 
                                    subject_names, 
                                    class_name, 
                                    term, 
                                    session
                                )
                            st.success("✅ All subjects assigned to all students")
                            # Clear session state to refresh display
                            if 'student_selections' in st.session_state:
                                del st.session_state.student_selections
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error in batch assignment: {str(e)}")

                with batch_col2:
                    st.markdown("#### Clear All Selections")
                    if st.button("🗑️ Clear All Student Selections", key="clear_all_student_selections"):
                        try:
                            for student in students:
                                student_name = student[1]
                                save_student_subject_selections(
                                    student_name, 
                                    [], 
                                    class_name, 
                                    term, 
                                    session
                                )
                            st.success("✅ All subject selections cleared")
                            # Clear session state to refresh display
                            if 'student_selections' in st.session_state:
                                del st.session_state.student_selections
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error clearing selections: {str(e)}")

                with batch_col3:
                    st.markdown("#### Select by Subject")
                    selected_subject_for_all = st.selectbox(
                        "Choose subject to assign to all students",
                        [""] + subject_names,
                        key="subject_for_all_students"
                    )
                    
                    if selected_subject_for_all and st.button(f"✅ Assign {selected_subject_for_all} to All", key="assign_single_subject"):
                        try:
                            for student in students:
                                student_name = student[1]
                                # Get current selections
                                current_selections = selection_dict.get(student_name, [])
                                # Add the selected subject if not already present
                                if selected_subject_for_all not in current_selections:
                                    current_selections.append(selected_subject_for_all)
                                
                                save_student_subject_selections(
                                    student_name, 
                                    current_selections, 
                                    class_name, 
                                    term, 
                                    session
                                )
                            st.success(f"✅ {selected_subject_for_all} assigned to all students")
                            # Clear session state to refresh display
                            if 'student_selections' in st.session_state:
                                del st.session_state.student_selections
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error assigning subject: {str(e)}")

                st.markdown("---")
                
                # Summary statistics
                st.markdown("### Selection Summary")
                if selections:
                    total_selections = len(selections)
                    students_with_selections = len(set(student_name for student_name, _ in selections))
                    avg_subjects_per_student = total_selections / len(students) if students else 0
                    
                    summary_col1, summary_col2, summary_col3 = st.columns(3)
                    summary_col1.metric("Total Selections", total_selections)
                    summary_col2.metric("Students with Selections", f"{students_with_selections}/{len(students)}")
                    summary_col3.metric("Avg Subjects per Student", f"{avg_subjects_per_student:.1f}")
                else:
                    st.info("No subject selections have been made yet.")    

# Define dialog once, outside loop
@st.dialog("Confirm Deletion")
def confirm_delete_single_subject():
    pending = st.session_state.get("delete_pending", None)
    if pending:
        st.warning(
            f"⚠️ Are you sure you want to delete '{pending['subject_name']}' "
            f"for {pending['class_name']} - {pending['term']} - {pending['session']}?"
        )
        confirm_col1, confirm_col2 = st.columns(2)
        if confirm_col1.button("✅ Delete"):
            delete_subject(pending["subject_id"])
            st.success(f"❌ Deleted {pending['subject_name']}")
            del st.session_state["delete_pending"]
            st.rerun()
        elif confirm_col2.button("❌ Cancel"):
            del st.session_state["delete_pending"]
            st.info("Deletion cancelled.")
            st.rerun()
