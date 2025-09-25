# app_sections/register_students.py

import streamlit as st
import pandas as pd
from database import get_all_classes, get_students_by_class, create_student, update_student, delete_student, delete_all_students
from utils import clean_input, create_metric_4col, inject_login_css, render_page_header

def register_students():
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    if st.session_state.role not in ["superadmin", "admin", "class_teacher"]:
        st.error("⚠️ Access denied. Admins and Class Teachers only.")
        return

    # Get user info for role-based access
    user_id = st.session_state.get('user_id')
    role = st.session_state.get('role')

    st.set_page_config(page_title="Register Students", layout="wide")

    # Custom CSS for better table styling
    inject_login_css("templates/tabs_styles.css")

    # Subheader
    render_page_header("Manage Students Data")

    # Get classes with proper parameters
    classes = get_all_classes(user_id, role)
    if not classes:
        st.warning("⚠️ No classes found.")
        return

    class_options = [f"{cls['class_name']} - {cls['term']} - {cls['session']}" for cls in classes]
    if role == "class_teacher":
        assignment = st.session_state.get("assignment")
        if not assignment:
            st.error("⚠️ Please select a class assignment first.")
            return
        allowed_class = f"{assignment['class_name']} - {assignment['term']} - {assignment['session']}"
        if allowed_class not in class_options:
            st.error("⚠️ Assigned class not found.")
            return
        class_options = [allowed_class]
        selected_class_display = st.selectbox("Select Class", class_options, disabled=True)
    else:
        selected_class_display = st.selectbox("Select Class", class_options)

    # Get selected class details
    selected_index = class_options.index(selected_class_display)
    selected_class_data = classes[selected_index]
    class_name = selected_class_data['class_name']
    term = selected_class_data['term']
    session = selected_class_data['session']

    # Load students with proper parameters
    students = get_students_by_class(class_name, term, session, user_id, role)
    if not students:
        st.info("No students found for this class. Add students below.")
        
    # Display class metrics
    create_metric_4col(class_name, term, session, students, "student")

    # Prepare DataFrame for existing students
    df_data = []
    for idx, student in enumerate(students, 1):
        df_data.append({
            "S/N": str(idx),  # Keep ID internally for updates
            "Name": student[1],
            "Gender": student[2],
            "Email": student[3]
        })

    df = pd.DataFrame(df_data) if df_data else pd.DataFrame(columns=["S/N", "Name", "Gender", "Email"])
    
    # Tabs for different operations
    # tab1, tab2, tab3, tab4, tab5 = st.tabs(["View/Edit Students", "Add New Student", "Delete Student", "Batch Add Students", "Delete All Students"])
    tab1, tab2, tab3, tab4 = st.tabs(["View/Edit Students", "Add New Student", "Batch Add Students", "Delete Student(s)"])

    with tab1:
        st.subheader("Student List")
        # Display only Name, Gender, Email in 3 columns
        display_df = df[["Name", "Gender", "Email"]] if not df.empty else pd.DataFrame(columns=["Name", "Gender", "Email"])
        edited_df = st.data_editor(
            display_df,
            column_config={
                "Name": st.column_config.TextColumn("Name", required=True, width="large"),
                "Gender": st.column_config.SelectboxColumn(
                    "Gender",
                    options=["M", "F"],
                    required=True,
                    width="medium"
                ),
                "Email": st.column_config.TextColumn(
                    "Email",
                    help="Enter a valid email address",
                    width="large"
                )
            },
            hide_index=True,
            use_container_width=True,
            key="student_editor"
        )

        if st.button("💾 Save Changes", key="save_changes"):
            errors = []
            processed_names = set()

            for idx, row in edited_df.iterrows():
                name = clean_input(str(row.get("Name", "")), "name")
                gender = str(row.get("Gender", ""))
                email = clean_input(str(row.get("Email", "")), "email")
                # Get student_id from original df using index
                student_id = df.iloc[idx]["ID"] if not df.empty and idx < len(df) else ""

                # Validation checks
                if not name:
                    errors.append(f"❌ Row {idx + 1}: Name is required")
                    continue
                if name.lower() in processed_names:
                    errors.append(f"❌ Row {idx + 1}: Duplicate student name '{name}'")
                    continue
                if gender not in ["M", "F"]:
                    errors.append(f"❌ Row {idx + 1}: Gender must be 'M' or 'F'")
                    continue
                if email and not "@" in email:
                    errors.append(f"❌ Row {idx + 1}: Invalid email format")
                    continue

                processed_names.add(name.lower())
                update_student(student_id, name, gender, email)
                st.rerun()

            if errors:
                st.markdown('<div class="error-container">', unsafe_allow_html=True)
                for err in errors:
                    st.error(err)
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="success-container">✅ Changes saved successfully!</div>', unsafe_allow_html=True)
                st.rerun()

    with tab2:
        st.subheader("Add New Student")\
        
        # Initialize form counter for clearing input
        if 'student_form_counter' not in st.session_state:
            st.session_state.student_form_counter = 0
            
        with st.form(f"add_student_form_{st.session_state.student_form_counter}"):
            new_name = st.text_input("Name", placeholder="Enter student name")
            new_gender = st.selectbox("Gender", ["M", "F"])
            new_email = st.text_input("Email", placeholder="Enter student email")
            submit_button = st.form_submit_button("➕ Add Student")

            if submit_button:
                errors = []
                new_name = clean_input(new_name, "name")
                new_email = clean_input(new_email, "email")

                if not new_name:
                    errors.append("❌ Name is required")
                if new_email and not "@" in new_email:
                    errors.append("❌ Invalid email format")
                if new_name.lower() in {s[1].lower() for s in students}:
                    errors.append("❌ Student name already exists")

                if not errors:
                    success = create_student(new_name, new_gender, new_email, class_name, term, session)
                    if success:
                        st.markdown('<div class="success-container">✅ Student added successfully!</div>', unsafe_allow_html=True)
                        # Clear the form by incrementing counter
                        st.session_state.student_form_counter += 1
                        st.rerun()
                    else:
                        errors.append("❌ Failed to add student. Name may already exist.")
                
                if errors:
                    st.markdown('<div class="error-container">', unsafe_allow_html=True)
                    for err in errors:
                        st.error(err)
                    st.markdown('</div>', unsafe_allow_html=True)

    with tab3:
        st.subheader("Batch Add Students")
        st.markdown("Enter multiple students below. Each row represents one student.")

        # Initialize batch form counter for clearing
        if 'batch_form_counter' not in st.session_state:
            st.session_state.batch_form_counter = 0

        # Initialize batch DataFrame with counter-based key
        batch_df = pd.DataFrame(columns=["Name", "Gender", "Email"])
        batch_df = pd.concat([batch_df, pd.DataFrame({"Name": [""]*3, "Gender": [""]*3, "Email": [""]*3})], ignore_index=True)

        edited_batch_df = st.data_editor(
            batch_df,
            column_config={
                "Name": st.column_config.TextColumn("Name", required=True),
                "Gender": st.column_config.SelectboxColumn(
                    "Gender",
                    options=["M", "F"],
                    required=True
                ),
                "Email": st.column_config.TextColumn(
                    "Email",
                    help="Enter a valid email address"
                )
            },
            num_rows="dynamic",
            hide_index=True,
            use_container_width=True,
            key=f"batch_student_editor_{st.session_state.batch_form_counter}"
        )

        if st.button("➕ Add Students in Batch", key=f"batch_add_{st.session_state.batch_form_counter}"):
            errors = []
            success_count = 0
            existing_names = {s[1].lower() for s in students}
            processed_names = set()

            # Check for duplicates within the batch
            batch_names = edited_batch_df["Name"].str.lower().str.strip()
            duplicate_mask = batch_names.duplicated(keep=False) & (batch_names != "")
            if duplicate_mask.any():
                duplicate_indices = edited_batch_df[duplicate_mask].index + 1
                errors.append(f"❌ Duplicate names found in batch at rows: {', '.join(map(str, duplicate_indices))}")

            for idx, row in edited_batch_df.iterrows():
                name = clean_input(str(row.get("Name", "")), "name")
                gender = str(row.get("Gender", ""))
                email = clean_input(str(row.get("Email", "")), "email")

                # Skip empty rows
                if not name:
                    continue

                # Validation checks
                if name.lower() in processed_names:
                    errors.append(f"❌ Row {idx + 1}: Duplicate name '{name}' in batch")
                    continue
                if name.lower() in existing_names:
                    errors.append(f"❌ Row {idx + 1}: Student name '{name}' already exists in class")
                    continue
                if gender not in ["M", "F"]:
                    errors.append(f"❌ Row {idx + 1}: Gender must be 'M' or 'F'")
                    continue
                if email and not "@" in email:
                    errors.append(f"❌ Row {idx + 1}: Invalid email format")
                    continue

                # Attempt to create student
                success = create_student(name, gender, email, class_name, term, session)
                if success:
                    success_count += 1
                    processed_names.add(name.lower())
                    existing_names.add(name.lower())
                else:
                    errors.append(f"❌ Row {idx + 1}: Failed to add student '{name}'")

            if errors:
                st.markdown('<div class="error-container">', unsafe_allow_html=True)
                for err in errors:
                    st.error(err)
                st.markdown('</div>', unsafe_allow_html=True)
            
            if success_count > 0:
                st.markdown(f'<div class="success-container">✅ Successfully added {success_count} student(s)!</div>', unsafe_allow_html=True)
                # Clear the batch form by incrementing counter
                st.session_state.batch_form_counter += 1
                st.rerun()

    with tab4:
        st.subheader("Delete Student")
        # Delete single student with expander
        with st.expander("**Delete Single Student**", expanded=True):
            if students:
                student_options = [f"{s[1]}" for s in students]
                student_to_delete = st.selectbox(
                    "Select student to delete",
                    student_options,
                    key="delete_student_select"
                )

                if 'delete_single_student' not in st.session_state:
                    st.session_state.delete_single_student = None

                # Confirmation dialog
                if st.button("❌ Delete Student", key="delete_student"):
                    @st.dialog("Confirm Student Deletion", width="small")
                    def confirm_delete_single_student():
                        st.warning(f"⚠️ Are you sure you want to delete **{student_to_delete}** from this class?")

                        # Get the student ID from the students list
                        selected_student_name = student_to_delete
                        student_id = None
                        for s in students:
                            if s[1] == selected_student_name:
                                student_id = s[0]
                                break

                        confirm_col1, confirm_col2 = st.columns(2)
                        if confirm_col1.button("✅ Delete", key=f"confirm_delete_student"):
                            if student_id:
                                st.session_state.delete_single_student = delete_student(student_id)
                                # if st.session_state.delete_single_student:
                                st.markdown('<div class="success-container">✅ Student deleted successfully!</div>', unsafe_allow_html=True)
                                st.session_state.delete_single_student = None
                                st.rerun()
                            else:
                                st.markdown('<div class="error-container">❌ Failed to delete student. Please try again.</div>', unsafe_allow_html=True)
                        elif confirm_col2.button("❌ Cancel", key=f"cancel_delete_student"):
                            st.session_state.delete_single_student = None
                            st.info("Deletion cancelled.")
                            st.rerun()

                    confirm_delete_single_student()
            else:
                st.info("No students available to delete.")

        st.subheader("Delete All Students")
        # Delete all students with expander
        with st.expander("**Delete All Students**", expanded=False):  
            st.warning("⚠️ This action will permanently delete all students in the selected class. This cannot be undone.")
            
            if "delete_all_students_in_class" not in st.session_state:
                st.session_state.delete_all_students_in_class = None
            
            if students:
                confirm_delete = st.checkbox("I confirm I want to delete all students in this class")
                delete_all_button = st.button("🗑️ Delete All Students", key="delete_all_students", disabled=not confirm_delete)
                
                if delete_all_button and confirm_delete:
                    @st.dialog("Confirm All Students Deletion", width="small")
                    def confirm_delete_all_student():
                        st.warning("⚠️ This action will permanently delete all students in this class. Do you want to proceed?")

                        confirm_col1, confirm_col2 = st.columns(2)
                        if confirm_col1.button("✅ Delete", key=f"confirm_delete_all_students"):
                            st.session_state.delete_all_students_in_class = delete_all_students(class_name, term, session)
                            # if not students:
                            st.markdown('<div class="success-container">✅ All students deleted successfully!</div>', unsafe_allow_html=True)
                            st.session_state.delete_all_students_in_class = None
                            st.rerun()
                            # else:
                            #     st.markdown('<div class="error-container">❌ Failed to delete all students. Please try again.</div>', unsafe_allow_html=True)
                        elif confirm_col2.button("❌ Cancel", key=f"cancel_delete_all_students"):
                            st.session_state.delete_all_students_in_class = None
                            st.info("Deletion cancelled.")
                            st.rerun()
                    confirm_delete_all_student()
            else:
                st.info("No students available to delete.")

    # with tab5:
    #     st.subheader("Delete All Students")

    #     # Delete user section with expander
    #     with st.expander("🗑️ Delete User", expanded=False):  
    #         st.warning("⚠️ This action will permanently delete all students in the selected class. This cannot be undone.")
            
    #         if "delete_all_students_in_class" not in st.session_state:
    #             st.session_state.delete_all_students_in_class = None
            
    #         if students:
    #             confirm_delete = st.checkbox("I confirm I want to delete all students in this class")
    #             delete_all_button = st.button("🗑️ Delete All Students", key="delete_all_students", disabled=not confirm_delete)
                
    #             if delete_all_button and confirm_delete:
    #                 @st.dialog("Confirm All Students Deletion", width="small")
    #                 def confirm_delete_all_student():
    #                     st.warning("⚠️ This action will permanently delete all students in this class. Do you want to proceed?")

    #                     confirm_col1, confirm_col2 = st.columns(2)
    #                     if confirm_col1.button("✅ Delete", key=f"confirm_delete_all_students"):
    #                         st.session_state.delete_all_students_in_class = delete_all_students(class_name, term, session)
    #                         # if not students:
    #                         st.markdown('<div class="success-container">✅ All students deleted successfully!</div>', unsafe_allow_html=True)
    #                         st.session_state.delete_all_students_in_class = None
    #                         st.rerun()
    #                         # else:
    #                         #     st.markdown('<div class="error-container">❌ Failed to delete all students. Please try again.</div>', unsafe_allow_html=True)
    #                     elif confirm_col2.button("❌ Cancel", key=f"cancel_delete_all_students"):
    #                         st.session_state.delete_all_students_in_class = None
    #                         st.info("Deletion cancelled.")
    #                         st.rerun()
    #                 confirm_delete_all_student()
    #         else:
    #             st.info("No students available to delete.")
