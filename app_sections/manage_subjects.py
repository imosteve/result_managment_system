import streamlit as st
from database import get_all_classes, get_subjects_by_class, create_subject, delete_subject, update_subject, clear_all_subjects
from utils import clean_input, create_metric_4col, inject_login_css, render_page_header

def add_subjects():
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    if st.session_state.role not in ["admin", "class_teacher", "subject_teacher"]:
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

    # Tabs for different operations
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

                # If delete is pending, show confirmation
                if "delete_pending" in st.session_state:
                    pending = st.session_state["delete_pending"]
                    if pending["index"] == i:
                        st.warning(f"⚠️ Are you sure you want to delete '{pending['subject_name']}' for {pending['class_name']} - {pending['term']} - {pending['session']}?")
                        confirm_col1, confirm_col2 = st.columns(2)
                        if confirm_col1.button("✅ Delete", key=f"confirm_delete_{i}"):
                            delete_subject(pending["subject_id"])
                            st.markdown(f'<div class="success-container">❌ Deleted {pending["subject_name"]}</div>', unsafe_allow_html=True)
                            del st.session_state["delete_pending"]
                            st.rerun()
                        elif confirm_col2.button("❌ Cancel", key=f"cancel_delete_{i}"):
                            del st.session_state["delete_pending"]
                            st.info("Deletion cancelled.")
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
                confirm_clear = st.checkbox("I confirm I want to clear all subjects for this class")
                clear_all_button = st.button("🗑️ Clear All Subjects", key="clear_all_subjects", disabled=not confirm_clear)
                if clear_all_button and confirm_clear:
                    success = clear_all_subjects(class_name, term, session)
                    if success:
                        st.markdown(f'<div class="success-container">✅ All subjects cleared successfully for {class_name} - {term} - {session}!</div>', unsafe_allow_html=True)
                        st.rerun()
                    else:
                        st.markdown(f'<div class="error-container">❌ Failed to clear subjects. Please try again.</div>', unsafe_allow_html=True)
            else:
                st.info("No subjects available to clear.")