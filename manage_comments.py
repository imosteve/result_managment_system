import streamlit as st
from database import get_all_classes, get_students_by_class, create_comment, get_comment, delete_comment
from utils import inject_login_css

def manage_comments():
    """Manage report card comments for students"""
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    if st.session_state.role not in ["admin", "class_teacher"]:
        st.error("⚠️ Access denied. Admins and class teachers only.")
        st.switch_page("main.py")
        return

    user_id = st.session_state.get('user_id', None)
    role = st.session_state.get('role', None)

    if user_id is None or role is None:
        st.error("⚠️ Session state missing user_id or role. Please log out and log in again.")
        return

    st.set_page_config(page_title="Manage Report Card Comments", layout="wide")
    
    # Header
    st.markdown(
        """
        <div style='width: auto; margin: auto; text-align: center; background-color: #c6b7b1;'>
            <h2 style='color:#000; font-size:24px; margin-top:30px; margin-bottom:20px;'>
                Manage Report Card Comments
            </h2>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("---")

    # Comment Form
    with st.form("comment_form"):
        st.subheader("Add/Edit Student Comments")
        classes = get_all_classes(user_id, role)
        class_options = [f"{cls['class_name']} - {cls['term']} - {cls['session']}" for cls in classes]
        if not class_options:
            st.warning("⚠️ No classes available. Add a class in the Manage Classes section.")
            submitted = st.form_submit_button("Save Comments", disabled=True)
        else:
            selected_class = st.selectbox("Select Class", class_options, key="comment_class_select")
            selected_index = class_options.index(selected_class)
            class_data = classes[selected_index]
            class_name, term, session = class_data['class_name'], class_data['term'], class_data['session']

            students = get_students_by_class(class_name, term, session, user_id, role)
            student_names = [s[1] for s in students]
            if not student_names:
                st.warning("⚠️ No students available for this class. Add students in the Register Students section.")
                submitted = st.form_submit_button("Save Comments", disabled=True)
            else:
                selected_student = st.selectbox("Select Student", student_names, key="comment_student_select")

                class_teacher_comment = ""
                head_teacher_comment = ""
                if selected_student:
                    comment = get_comment(selected_student, class_name, term, session)
                    if comment:
                        class_teacher_comment = comment['class_teacher_comment'] or ""
                        head_teacher_comment = comment['head_teacher_comment'] or ""

                class_teacher_input = st.text_area("Class Teacher Comment", value=class_teacher_comment, height=100)
                head_teacher_input = st.text_area("Head Teacher Comment", value=head_teacher_comment, height=100)

                submitted = st.form_submit_button("Save Comments")
                if submitted:
                    if selected_student:
                        if create_comment(selected_student, class_name, term, session, class_teacher_input, head_teacher_input):
                            st.success(f"✅ Comments saved for {selected_student}.")
                            st.rerun()
                        else:
                            st.error("❌ Failed to save comments.")
                    else:
                        st.error("⚠️ Please select a student.")

    # Display Comments
    st.subheader("Existing Comments")
    comments = []
    for cls in classes:
        students = get_students_by_class(cls['class_name'], cls['term'], cls['session'], user_id, role)
        for s in students:
            comment = get_comment(s[1], cls['class_name'], cls['term'], cls['session'])
            if comment and (comment['class_teacher_comment'] or comment['head_teacher_comment']):
                comments.append({
                    "Student": s[1],
                    "Class": f"{cls['class_name']} - {cls['term']} - {cls['session']}",
                    "Class Teacher Comment": comment['class_teacher_comment'] or "-",
                    "Head Teacher Comment": comment['head_teacher_comment'] or "-"
                })
    if comments:
        st.dataframe(comments, use_container_width=True)
        comment_to_delete = st.selectbox(
            "Select Comment to Delete",
            [f"{c['Student']} - {c['Class']}" for c in comments],
            key="comment_delete_select"
        )
        if st.button("🗑️ Delete Selected Comment"):
            student_name, class_info = comment_to_delete.split(" - ", 1)
            class_name, term, session = class_info.split(" - ")
            delete_comment(student_name, class_name, term, session)
            st.success("✅ Comment deleted successfully.")
            st.rerun()
    else:
        st.info("No comments found.")