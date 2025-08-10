import streamlit as st
from database import get_all_classes, get_students_by_class, create_comment, get_comment, delete_comment
from utils import render_page_header, inject_login_css

def manage_comments():
    """Manage report card comments for students"""
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    if st.session_state.role not in ["superadmin", "admin", "class_teacher"]:
        st.error("⚠️ Access denied. Admins and class teachers only.")
        st.switch_page("main.py")
        return

    user_id = st.session_state.get('user_id', None)
    role = st.session_state.get('role', None)

    if user_id is None or role is None:
        st.error("⚠️ Session state missing user_id or role. Please log out and log in again.")
        return

    st.set_page_config(page_title="Manage Report Card Comments", layout="wide")
    
    # Subheader
    render_page_header("Manage Report Card Comments")
    # Class Selection
    classes = get_all_classes(user_id, role)
    if not classes:
        st.warning("⚠️ No classes available. Add a class in the Manage Classes section.")
        return

    # Create class display options with all three components
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

    selected_index = class_options.index(selected_class_display)
    class_data = classes[selected_index]
    class_name, term, session = class_data['class_name'], class_data['term'], class_data['session']

    students = get_students_by_class(class_name, term, session, user_id, role)
    if not students:
        st.warning(f"⚠️ No students found for {class_name} - {term} - {session}.")
        return

    # st.markdown("---")

    # Inject CSS to increase tab font size
    inject_login_css("templates/tabs_styles.css")

    # Tabs for different operations
    tabs = st.tabs(["View Comments", "Add Single Comment", "Delete Single Comment", "Batch Add Comments", "Batch Delete Comments", "Psychomotor Ratings"])

    with tabs[0]:
        st.subheader("Existing Comments")
        comments = []
        for s in students:
            comment = get_comment(s[1], class_name, term, session)
            if comment and (comment['class_teacher_comment'] or comment['head_teacher_comment']):
                comments.append({
                    "Student": s[1],
                    "Class Teacher Comment": comment['class_teacher_comment'] or "-",
                    "Head Teacher Comment": comment['head_teacher_comment'] or "-"
                })
        if comments:
            st.dataframe(comments, use_container_width=True)
        else:
            st.info("No comments found for this class.")

    with tabs[1]:
        st.subheader("Add Single Student Comment")
        # Initialize form counter for clearing
        if 'comment_form_counter' not in st.session_state:
            st.session_state.comment_form_counter = 0
            
        with st.form(f"single_comment_form_{st.session_state.comment_form_counter}"):
            student_names = [s[1] for s in students]
            selected_student = st.selectbox("Select Student", student_names, key="single_comment_student")

            class_teacher_comment = ""
            head_teacher_comment = ""
            if selected_student:
                comment = get_comment(selected_student, class_name, term, session)
                if comment:
                    class_teacher_comment = comment['class_teacher_comment'] or ""
                    head_teacher_comment = comment['head_teacher_comment'] or ""

            class_teacher_input = st.text_area("Class Teacher Comment", value=class_teacher_comment, height=100)
            head_teacher_input = st.text_area("Head Teacher Comment", value=head_teacher_comment, height=100)

            submitted = st.form_submit_button("💾 Save Comment")
            if submitted:
                if selected_student:
                    if create_comment(selected_student, class_name, term, session, class_teacher_input, head_teacher_input):
                        st.success(f"✅ Comments saved for {selected_student}.")
                        st.session_state.comment_form_counter += 1
                        st.rerun()
                    else:
                        st.error("❌ Failed to save comments.")

    with tabs[2]:
        st.subheader("Delete Single Comment")
        comments_for_delete = []
        for s in students:
            comment = get_comment(s[1], class_name, term, session)
            if comment and (comment['class_teacher_comment'] or comment['head_teacher_comment']):
                comments_for_delete.append(s[1])
        
        if comments_for_delete:
            student_to_delete = st.selectbox("Select Student Comment to Delete", comments_for_delete)
            if st.button("🗑️ Delete Comment", key="delete_single_comment"):
                delete_comment(student_to_delete, class_name, term, session)
                st.success("✅ Comment deleted successfully.")
                st.rerun()
        else:
            st.info("No comments available to delete.")

    with tabs[3]:
        st.subheader("Batch Add Comments")
        st.markdown("Add comments for multiple students at once.")
        
        # Initialize batch form counter
        if 'batch_comment_counter' not in st.session_state:
            st.session_state.batch_comment_counter = 0
            
        with st.form(f"batch_comment_form_{st.session_state.batch_comment_counter}"):
            batch_comments = {}
            for student in students:
                st.markdown(f"***{student[1]}***")
                col1, col2 = st.columns(2)
                with col1:
                    ct_comment = st.text_area(f"Class Teacher Comment", height=80, key=f"ct_{student[0]}_{st.session_state.batch_comment_counter}")
                with col2:
                    ht_comment = st.text_area(f"Head Teacher Comment", height=80, key=f"ht_{student[0]}_{st.session_state.batch_comment_counter}")
                batch_comments[student[1]] = {"ct": ct_comment, "ht": ht_comment}
            
            if st.form_submit_button("💾 Save All Comments"):
                success_count = 0
                for student_name, comments in batch_comments.items():
                    if comments["ct"].strip() or comments["ht"].strip():
                        if create_comment(student_name, class_name, term, session, comments["ct"], comments["ht"]):
                            success_count += 1
                
                if success_count > 0:
                    st.success(f"✅ Successfully saved comments for {success_count} student(s).")
                    st.session_state.batch_comment_counter += 1
                    st.rerun()

    with tabs[4]:
        st.subheader("Batch Delete Comments")
        st.warning("⚠️ This will delete ALL comments for the selected class.")
        
        comments_exist = any(get_comment(s[1], class_name, term, session) for s in students)
        
        if comments_exist:
            confirm_delete = st.checkbox("I confirm I want to delete all comments for this class")
            if st.button("🗑️ Delete All Comments", disabled=not confirm_delete):
                deleted_count = 0
                for student in students:
                    if delete_comment(student[1], class_name, term, session):
                        deleted_count += 1
                st.success(f"✅ Deleted comments for {deleted_count} student(s).")
                st.rerun()
        else:
            st.info("No comments available to delete for this class.")

    with tabs[5]:
        st.subheader("Psychomotor Ratings")
        st.info("🚧 Psychomotor ratings feature coming soon!")
        
        # Psychomotor categories based on HTML
        psychomotor_categories = {
            "Punctuality": 0, "Neatness": 0,
            "Honesty": 0, "Cooperation": 0,
            "Leadership": 0, "Perseverance": 0,
            "Politeness": 0, "Obedience": 0,
            "Attentiveness": 0, "Attitude to work": 0
        }
        
        st.markdown("**Rating Scale:** 5 - Exceptional | 4 - Excellent | 3 - Good | 2 - Average | 1 - Below Average")
        
        # Placeholder for psychomotor implementation
        selected_student_psycho = st.selectbox("Select Student for Psychomotor Rating", [s[1] for s in students], key="psycho_student")
        
        col1, col2 = st.columns(2)
        with col1:
            for i, category in enumerate(list(psychomotor_categories.keys())[:5]):
                st.slider(category, 1, 5, 3, key=f"psycho_{category}")
        with col2:
            for category in list(psychomotor_categories.keys())[5:]:
                st.slider(category, 1, 5, 3, key=f"psycho_{category}")
                
        if st.button("💾 Save Psychomotor Ratings", key="save_psychomotor"):
            st.info("Psychomotor ratings saved! (Feature in development)")