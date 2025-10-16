# app_sections/manage_subjects.py

import streamlit as st
import pandas as pd
import time
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

    # Initialize session state for delete confirmations
    if "show_delete_subject_confirm" not in st.session_state:
        st.session_state.show_delete_subject_confirm = False
    if "subject_to_delete_info" not in st.session_state:
        st.session_state.subject_to_delete_info = None
    if "show_clear_subjects_confirm" not in st.session_state:
        st.session_state.show_clear_subjects_confirm = False
    if "clear_subjects_info" not in st.session_state:
        st.session_state.clear_subjects_info = None
    if "show_clear_selections_confirm" not in st.session_state:
        st.session_state.show_clear_selections_confirm = False
    if "clear_selections_info" not in st.session_state:
        st.session_state.clear_selections_info = None

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
            class_options = []
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
    # is_senior_class = class_name in ["SSS 2", "SSS 3"]
    # is_senior_class = class_name.startswith("SSS")

    import re
    is_senior_class = bool(re.match(r"SSS [23].*$", class_name))


    # Confirmation dialog for deleting individual subject
    if st.session_state.show_delete_subject_confirm and st.session_state.subject_to_delete_info:
        @st.dialog("Confirm Subject Deletion")
        def confirm_delete_subject():
            subject_info = st.session_state.subject_to_delete_info
            st.markdown(f"### Are you sure you want to delete this subject?")
            st.error(f"**Subject Name:** {subject_info['subject_name']}")
            st.error(f"**Class:** {subject_info['class_name']} - {subject_info['term']} - {subject_info['session']}")
            st.markdown("---")
            st.warning("⚠️ **This action cannot be undone!**")
            st.warning("• All scores for this subject will be permanently deleted")
            st.warning("• Student records associated with this subject will be removed")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚫 Cancel", key="cancel_delete_subject", type="secondary", use_container_width=True):
                    st.session_state.show_delete_subject_confirm = False
                    st.session_state.subject_to_delete_info = None
                    st.rerun()
            with col2:
                if st.button("❌ Delete Subject", key="confirm_delete_subject", type="primary", use_container_width=True):
                    delete_subject(subject_info['subject_id'])
                    st.session_state.show_delete_subject_confirm = False
                    st.session_state.subject_to_delete_info = None
                    st.success(f"✅ Subject '{subject_info['subject_name']}' deleted successfully.")
                    time.sleep(1)
                    st.rerun()
        
        confirm_delete_subject()

    # Confirmation dialog for clearing all subjects
    if st.session_state.show_clear_subjects_confirm and st.session_state.clear_subjects_info:
        @st.dialog("Confirm Clear All Subjects")
        def confirm_clear_subjects():
            info = st.session_state.clear_subjects_info
            st.markdown(f"### Are you sure you want to clear all subjects?")
            st.error(f"**Class:** {info['class_name']} - {info['term']} - {info['session']}")
            st.error(f"**Total Subjects:** {info['subject_count']}")
            st.markdown("---")
            st.warning("⚠️ **THIS ACTION CANNOT BE UNDONE!**")
            st.warning("• All subjects will be permanently deleted")
            st.warning("• All scores for these subjects will be permanently deleted")
            st.warning("• All student records for these subjects will be removed")
            st.warning("• You will need to re-add subjects manually")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚫 Cancel", key="cancel_clear_subjects", type="secondary", use_container_width=True):
                    st.session_state.show_clear_subjects_confirm = False
                    st.session_state.clear_subjects_info = None
                    st.rerun()
            with col2:
                if st.button("🗑️ Clear All Subjects", key="confirm_clear_subjects", type="primary", use_container_width=True):
                    success = clear_all_subjects(info['class_name'], info['term'], info['session'])
                    st.session_state.show_clear_subjects_confirm = False
                    st.session_state.clear_subjects_info = None
                    if success:
                        st.success(f"✅ All subjects cleared successfully for {info['class_name']} - {info['term']} - {info['session']}!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Failed to clear subjects. Please try again.")
        
        confirm_clear_subjects()

    # Confirmation dialog for clearing all selections
    if st.session_state.show_clear_selections_confirm and st.session_state.clear_selections_info:
        @st.dialog("Confirm Clear All Subject Selections")
        def confirm_clear_selections():
            info = st.session_state.clear_selections_info
            st.markdown(f"### Are you sure you want to clear all subject selections?")
            st.error(f"**Class:** {info['class_name']} - {info['term']} - {info['session']}")
            st.error(f"**Total Students:** {info['student_count']}")
            st.markdown("---")
            st.warning("⚠️ **This action cannot be undone!**")
            st.warning("• All subject selections for all students will be removed")
            st.warning("• Students will have no subjects assigned")
            st.warning("• You will need to reassign subjects manually")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚫 Cancel", key="cancel_clear_selections", type="secondary", use_container_width=True):
                    st.session_state.show_clear_selections_confirm = False
                    st.session_state.clear_selections_info = None
                    st.rerun()
            with col2:
                if st.button("🗑️ Clear All Selections", key="confirm_clear_selections", type="primary", use_container_width=True):
                    try:
                        for student in info['students']:
                            student_name = student[1]
                            save_student_subject_selections(
                                student_name, 
                                [], 
                                info['class_name'], 
                                info['term'], 
                                info['session']
                            )
                        st.session_state.show_clear_selections_confirm = False
                        st.session_state.clear_selections_info = None
                        st.success("✅ All subject selections cleared successfully")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error clearing selections: {str(e)}")
        
        confirm_clear_selections()

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
                    st.session_state.show_delete_subject_confirm = True
                    st.session_state.subject_to_delete_info = {
                        "subject_id": subject[0],
                        "subject_name": subject[1],
                        "class_name": class_name,
                        "term": term,
                        "session": session
                    }
                    st.rerun()
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
            if subjects:
                if st.button("🗑️ Clear All Subjects", key="clear_all_subjects_btn"):
                    st.session_state.show_clear_subjects_confirm = True
                    st.session_state.clear_subjects_info = {
                        "class_name": class_name,
                        "term": term,
                        "session": session,
                        "subject_count": len(subjects)
                    }
                    st.rerun()
            else:
                st.info("No subjects available to clear.")

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

                # Display current selections summary
                selections = get_all_student_subject_selections(class_name, term, session)
                if selections:
                    # Create a summary DataFrame
                    selection_summary = {}
                    for student_name, subject_name in selections:
                        if student_name not in selection_summary:
                            selection_summary[student_name] = []
                        selection_summary[student_name].append(subject_name)

                    summary_data = []
                    for i, student in enumerate(students, 1):
                        student_name = student[1]
                        selected_subjects = selection_summary.get(student_name, [])
                        summary_data.append({
                            "S/N": str(i),
                            "Student Name": student_name,
                            "Selected Subjects": ", ".join(selected_subjects) if selected_subjects else "None",
                            "Number of Subjects": len(selected_subjects)
                        })

                    st.dataframe(
                        pd.DataFrame(summary_data),
                        column_config={
                            "S/N": st.column_config.TextColumn("S/N", width="small"),
                            "Student Name": st.column_config.TextColumn("Student Name", width="large"),
                            "Selected Subjects": st.column_config.TextColumn("Selected Subjects", width="large"),
                            "Number of Subjects": st.column_config.NumberColumn("Number of Subjects", width="small")
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.info("No subject selections made yet.")

                st.markdown("---")

                # Individual student subject selection
                st.markdown("### Manage Individual Student Selections")
                
                student_names = [s[1] for s in students]
                selected_student = st.selectbox("Select Student", [""] + student_names, key="student_select")

                if selected_student:
                    st.markdown(f"#### Subject Selection for **{selected_student}**")
                    
                    # Get current selections for this student
                    current_selections = get_student_selected_subjects(selected_student, class_name, term, session)
                    subject_names = [s[1] for s in subjects]
                    
                    # Create checkboxes for each subject
                    col1, col2 = st.columns(2)
                    selected_subjects = []
                    
                    for i, subject_name in enumerate(subject_names):
                        is_selected = subject_name in current_selections
                        col = col1 if i % 2 == 0 else col2
                        
                        if col.checkbox(
                            subject_name, 
                            value=is_selected,
                            key=f"subject_{selected_student}_{subject_name}"
                        ):
                            selected_subjects.append(subject_name)

                    # Save button
                    if st.button("💾 Save Subject Selections", key="save_selections"):
                        try:
                            save_student_subject_selections(
                                selected_student, 
                                selected_subjects, 
                                class_name, 
                                term, 
                                session
                            )
                            st.success(f"✅ Subject selections saved for {selected_student}")
                            # Reset the selectbox by deleting its session state
                            if "student_select" in st.session_state:
                                del st.session_state["student_select"]
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error saving selections: {str(e)}")

                st.markdown("---")

                # Batch operations
                st.markdown("### Batch Operations")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### Assign All Subjects to All Students")
                    if st.button("📚 Assign All Subjects", key="assign_all"):
                        try:
                            subject_names = [s[1] for s in subjects]
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
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error in batch assignment: {str(e)}")

                with col2:
                    st.markdown("#### Clear All Selections")
                    if st.button("🗑️ Clear All Selections", key="clear_all_selections_btn"):
                        st.session_state.show_clear_selections_confirm = True
                        st.session_state.clear_selections_info = {
                            "class_name": class_name,
                            "term": term,
                            "session": session,
                            "students": students,
                            "student_count": len(students)
                        }
                        st.rerun()