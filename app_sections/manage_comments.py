# app_sections/manage_comments.py

import streamlit as st
import pandas as pd
from database import (
    get_all_classes, get_students_by_class, create_comment, get_comment, 
    delete_comment, create_psychomotor_rating, get_psychomotor_rating,
    delete_psychomotor_rating, get_all_psychomotor_ratings
)
from utils import render_page_header, inject_login_css, render_persistent_class_selector

# Psychomotor categories with their display names
PSYCHOMOTOR_CATEGORIES = [
    "Punctuality", "Neatness", "Honesty", "Cooperation",
    "Leadership", "Perseverance", "Politeness", "Obedience",
    "Attentiveness", "Attitude to work"
]

def manage_comments():
    """Manage report card comments and psychomotor ratings for students"""
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

    st.set_page_config(page_title="Manage Comments & Ratings", layout="wide")
    
    # Page header
    render_page_header("Manage Comments & Psychomotor Ratings")
    
    # Class Selection
    classes = get_all_classes(user_id, role)
    if not classes:
        st.warning("⚠️ No classes available. Add a class in the Manage Classes section.")
        return

    selected_class_data = render_persistent_class_selector(
        classes, 
        widget_key="manage_comments_class"
    )

    if not selected_class_data:
        st.warning("⚠️ No class selected.")
        return

    class_name = selected_class_data['class_name']
    term = selected_class_data['term']
    session = selected_class_data['session']

    students = get_students_by_class(class_name, term, session, user_id, role)
    if not students:
        st.warning(f"⚠️ No students found for {class_name} - {term} - {session}.")
        return

    # Inject CSS for tabs
    inject_login_css("templates/tabs_styles.css")

    # Create tabs
    tabs = st.tabs([
        "View/Delete Comments", 
        "Psychomotor & Comments", 
        "Batch Add Comments",
        "Batch Delete"
    ])

    with tabs[0]:
        render_view_delete_tab(students, class_name, term, session)

    with tabs[1]:
        render_psychomotor_comments_tab(students, class_name, term, session)

    with tabs[2]:
        render_batch_add_tab(students, class_name, term, session)

    with tabs[3]:
        render_batch_delete_tab(students, class_name, term, session)


def render_view_delete_tab(students, class_name, term, session):
    """Render the View/Delete Comments tab"""
    st.subheader("View Comments and Psychomotor Ratings")
    
    # Display existing comments
    comments_data = []
    for s in students:
        comment = get_comment(s[1], class_name, term, session)
        psychomotor = get_psychomotor_rating(s[1], class_name, term, session)
        
        if comment or psychomotor:
            comments_data.append({
                "Student": s[1],
                "Class Teacher Comment": comment['class_teacher_comment'] if comment and comment['class_teacher_comment'] else "-",
                "Head Teacher Comment": comment['head_teacher_comment'] if comment and comment['head_teacher_comment'] else "-",
                "Has Psychomotor": "✓" if psychomotor else "✗"
            })
    
    if comments_data:
        st.dataframe(
            pd.DataFrame(comments_data),
            column_config={
                "Student": st.column_config.TextColumn("Student", width=100),
                "Class Teacher Comment": st.column_config.TextColumn("Class Teacher Comment", width=200),
                "Head Teacher Comment": st.column_config.TextColumn("Head Teacher Comment", width=200),
                "Has Psychomotor": st.column_config.TextColumn("Has Psychomotor", width=50)
            },
            hide_index=True,
            width="stretch"
        )
    else:
        st.info("No comments or ratings found for this class.")

    st.markdown("---")

    # Delete section - collapsible
    with st.expander("🗑️ Delete Comments/Ratings", expanded=False):
        st.markdown("### Delete Individual Student Data")
        
        # Get students with comments or psychomotor ratings
        students_with_data = []
        for s in students:
            comment = get_comment(s[1], class_name, term, session)
            psychomotor = get_psychomotor_rating(s[1], class_name, term, session)
            if comment or psychomotor:
                students_with_data.append(s[1])
        
        if students_with_data:
            # Initialize session state for delete selection
            if 'delete_selection_reset' not in st.session_state:
                st.session_state.delete_selection_reset = 0
            
            student_to_delete = st.selectbox(
                "Select Student", 
                [""] + students_with_data,
                key=f"delete_student_{st.session_state.delete_selection_reset}"
            )
            
            if student_to_delete:
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("🗑️ Delete Comment", key="delete_comment_btn"):
                        if delete_comment(student_to_delete, class_name, term, session):
                            st.success(f"✅ Comment deleted for {student_to_delete}")
                            st.session_state.delete_selection_reset += 1
                            st.rerun()
                        else:
                            st.error("❌ Failed to delete comment")
                
                with col2:
                    if st.button("🗑️ Delete Psychomotor", key="delete_psycho_btn"):
                        if delete_psychomotor_rating(student_to_delete, class_name, term, session):
                            st.success(f"✅ Psychomotor rating deleted for {student_to_delete}")
                            st.session_state.delete_selection_reset += 1
                            st.rerun()
                        else:
                            st.error("❌ Failed to delete psychomotor rating")
        else:
            st.info("No data available to delete.")


def render_psychomotor_comments_tab(students, class_name, term, session):
    """Render the Psychomotor Rating & Add Single Comment tab"""
    
    # Student selection
    student_names = [s[1] for s in students]
    selected_student = st.selectbox("Select Student", student_names, key="psycho_comment_student")
    
    if not selected_student:
        return
    
    # PSYCHOMOTOR RATING SECTION
    st.markdown("### 📊 Psychomotor Ratings")
    st.markdown("**Rating Scale:** 5 - Exceptional | 4 - Excellent | 3 - Good | 2 - Average | 1 - Below Average")
    
    # Get existing ratings
    existing_psychomotor = get_psychomotor_rating(selected_student, class_name, term, session)
    
    # Initialize ratings dictionary
    ratings = {}
    
    # Create sliders for each category
    col1, col2, col3, col4, col5 = st.columns([1, 0.1, 1, 0.1, 1])
    with col1:
        for i, category in enumerate(PSYCHOMOTOR_CATEGORIES[:4]):
            default_value = 3
            if existing_psychomotor and category.lower().replace(' ', '_') in existing_psychomotor:
                default_value = existing_psychomotor[category.lower().replace(' ', '_')]
            
            ratings[category] = st.slider(
                category, 
                1, 5, 
                default_value, 
                key=f"psycho_{selected_student}_{category}_{i}"
            )
    with col3:
        for i, category in enumerate(PSYCHOMOTOR_CATEGORIES[4:7]):
            default_value = 3
            if existing_psychomotor and category.lower().replace(' ', '_') in existing_psychomotor:
                default_value = existing_psychomotor[category.lower().replace(' ', '_')]
            
            ratings[category] = st.slider(
                category, 
                1, 5, 
                default_value, 
                key=f"psycho_{selected_student}_{category}_{i}"
            )
    with col5:
        for i, category in enumerate(PSYCHOMOTOR_CATEGORIES[7:]):
            default_value = 3
            if existing_psychomotor and category.lower().replace(' ', '_') in existing_psychomotor:
                default_value = existing_psychomotor[category.lower().replace(' ', '_')]
            
            ratings[category] = st.slider(
                category, 
                1, 5, 
                default_value, 
                key=f"psycho_{selected_student}_{category}_{i}"
            )
    
    # Save button for psychomotor
    col_save1, col_space1, col_apply1 = st.columns(3)
    
    with col_save1:
        if st.button("💾 Save Rating", key="save_psycho", use_container_width=True):
            if create_psychomotor_rating(selected_student, class_name, term, session, ratings):
                st.success(f"✅ Psychomotor rating saved for {selected_student}")
                st.rerun()
            else:
                st.error("❌ Failed to save psychomotor rating")
    
    with col_apply1:
        if st.button("📋 Apply to All", key="apply_psycho_all", use_container_width=True):
            success_count = 0
            for student in students:
                if create_psychomotor_rating(student[1], class_name, term, session, ratings):
                    success_count += 1
            st.success(f"✅ Applied rating to {success_count}/{len(students)} students")
            st.rerun()

    st.markdown("---")
    
    # COMMENTS SECTION
    with st.expander("Add/Edit Comments", expanded=True):
        st.markdown("### Student Comments")
        
        # Get existing comments
        existing_comment = get_comment(selected_student, class_name, term, session)
        class_teacher_comment = ""
        head_teacher_comment = ""
        
        if existing_comment:
            class_teacher_comment = existing_comment['class_teacher_comment'] or ""
            head_teacher_comment = existing_comment['head_teacher_comment'] or ""
        
        # Class Teacher Comment section
        st.markdown("**Class Teacher Comment**")
        ct_comment = st.text_area(
            "Class Teacher",
            value=class_teacher_comment,
            height=50,
            key=f"ct_comment_{selected_student}",
            label_visibility="collapsed"
        )
        
        # Save button for Class Teacher comment
        col_save_ct, col_space_ct, col_apply_ct = st.columns(3)
        with col_save_ct:
            if st.button("💾 Save Class Teacher Comment", key="save_ct_comment"):
                if create_comment(selected_student, class_name, term, session, ct_comment, head_teacher_comment):
                    st.success(f"✅ Class Teacher comment saved for {selected_student}")
                    st.rerun()
                else:
                    st.error("❌ Failed to save Class Teacher comment")
        
        with col_apply_ct:
            if st.button("📋 Apply CT Comment to All", key="apply_ct_comment_all"):
                success_count = 0
                for student in students:
                    existing = get_comment(student[1], class_name, term, session)
                    ht_existing = existing['head_teacher_comment'] if existing else ""
                    if create_comment(student[1], class_name, term, session, ct_comment, ht_existing):
                        success_count += 1
                st.success(f"✅ Applied Class Teacher comment to {success_count}/{len(students)} students")
                st.rerun()

        st.markdown("---")
        
        # Head Teacher Comment section
        st.markdown("**Head Teacher/Principal Comment**")
        ht_comment = st.text_area(
            "Head Teacher",
            value=head_teacher_comment,
            height=50,
            key=f"ht_comment_{selected_student}",
            label_visibility="collapsed"
        )
        
        # Save button for Head Teacher comment
        col_save_ht, col_space_ht, col_apply_ht = st.columns(3)
        with col_save_ht:
            if st.button("💾 Save HT/Principal Comment", key="save_ht_comment"):
                if create_comment(selected_student, class_name, term, session, ct_comment, ht_comment):
                    st.success(f"✅ Head Teacher/Principal comment saved for {selected_student}")
                    st.rerun()
                else:
                    st.error("❌ Failed to save Head Teacher/Principal comment")
        
        with col_apply_ht:
            if st.button("📋 Apply HT Comment to All", key="apply_ht_comment_all"):
                success_count = 0
                for student in students:
                    existing = get_comment(student[1], class_name, term, session)
                    ct_existing = existing['class_teacher_comment'] if existing else ""
                    if create_comment(student[1], class_name, term, session, ct_existing, ht_comment):
                        success_count += 1
                st.success(f"✅ Applied Head Teacher/Principal comment to {success_count}/{len(students)} students")
                st.rerun()


def render_batch_add_tab(students, class_name, term, session):
    """Render the Batch Add Comments tab"""
    st.subheader("Batch Add Comments")
    st.markdown("Add comments for multiple students at once.")
    
    # Initialize batch form counter
    if 'batch_comment_counter' not in st.session_state:
        st.session_state.batch_comment_counter = 0
    
    with st.form(f"batch_comment_form_{st.session_state.batch_comment_counter}"):
        batch_comments = {}
        
        for student in students:
            st.markdown(f"##### {student[1]}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                ct_comment = st.text_area(
                    "Class Teacher Comment",
                    height=50,
                    key=f"batch_ct_{student[0]}_{st.session_state.batch_comment_counter}"
                )
            
            with col2:
                ht_comment = st.text_area(
                    "Head Teacher/Principal Comment",
                    height=50,
                    key=f"batch_ht_{student[0]}_{st.session_state.batch_comment_counter}"
                )
            
            batch_comments[student[1]] = {"ct": ct_comment, "ht": ht_comment}
        
        col1, col2, col3 = st.columns(3)
        with col2:
            if st.form_submit_button("💾 Save All Comments", use_container_width=True):
                success_count = 0
                for student_name, comments in batch_comments.items():
                    if comments["ct"].strip() or comments["ht"].strip():
                        if create_comment(student_name, class_name, term, session, comments["ct"], comments["ht"]):
                            success_count += 1
                
                if success_count > 0:
                    st.success(f"✅ Successfully saved comments for {success_count} student(s).")
                    st.session_state.batch_comment_counter += 1
                    st.rerun()


def render_batch_delete_tab(students, class_name, term, session):
    """Render the Batch Delete tab"""
    st.subheader("🗑️ Batch Delete Operations")
    st.warning("⚠️ **DANGER ZONE**: These actions will permanently delete data for the selected class.")
    
    st.markdown(" ")

    col1, col2 = st.columns(
        2, 
        vertical_alignment="bottom", 
        border=True,
        gap="large"
    )
    
    # Delete all comments
    with col1:
        st.markdown("##### 🗑️ Clear All Comments")
        
        comments_exist = any(get_comment(s[1], class_name, term, session) for s in students)
        
        if comments_exist:
            confirm_delete_comments = st.checkbox(
                "I confirm I want to delete all comments",
                key="confirm_delete_comments"
            )
            
            if st.button(
                "🗑️ Delete All Comments",
                disabled=not confirm_delete_comments,
                key="delete_all_comments",
                type="primary"
            ):
                deleted_count = 0
                for student in students:
                    if delete_comment(student[1], class_name, term, session):
                        deleted_count += 1
                st.success(f"✅ Deleted comments for {deleted_count} student(s).")
                st.rerun()
        else:
            st.info("No comments available to delete for this class.")
    
    # Delete all psychomotor ratings
    with col2:
        st.markdown("##### 🗑️ Clear All Psychomotor Ratings")
        
        ratings_exist = any(get_psychomotor_rating(s[1], class_name, term, session) for s in students)
        
        if ratings_exist:
            confirm_delete_psycho = st.checkbox(
                "I confirm I want to delete all psychomotor ratings",
                key="confirm_delete_psycho"
            )
            
            if st.button(
                "🗑️ Delete All Psychomotor",
                disabled=not confirm_delete_psycho,
                key="delete_all_psycho",
                type="primary"
            ):
                deleted_count = 0
                for student in students:
                    if delete_psychomotor_rating(student[1], class_name, term, session):
                        deleted_count += 1
                st.success(f"✅ Deleted psychomotor ratings for {deleted_count} student(s).")
                st.rerun()
        else:
            st.info("No psychomotor ratings available to delete for this class.")