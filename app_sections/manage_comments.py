# app_sections/manage_comments.py

import streamlit as st
import pandas as pd
import re
from database import (
    get_all_classes, get_students_by_class, create_comment, get_comment, 
    delete_comment, create_psychomotor_rating, get_psychomotor_rating,
    delete_psychomotor_rating, get_all_comment_templates
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

    is_senior_class = bool(re.match(r"SSS [123].*$", class_name))
    is_junior_class = bool(re.match(r"JSS [123].*$", class_name))
    is_secondary_class = is_senior_class or is_junior_class
    
    is_kg_class = bool(re.match(r"KINDERGARTEN [12345].*$", class_name))
    is_nursery_class = bool(re.match(r"NURSERY [12345].*$", class_name))
    is_pri_class = bool(re.match(r"PRIMARY [123456].*$", class_name))
    is_primary_class = is_kg_class or is_nursery_class or is_pri_class

    # Inject CSS for tabs
    inject_login_css("templates/tabs_styles.css")

    # Create tabs
    tabs = st.tabs([
        "View/Delete Comments", 
        "Psychomotor & Comments", 
        "Batch CT Comments",
        "Batch HT Comments",
        "Batch Delete"
    ])

    with tabs[0]:
        render_view_delete_tab(students, class_name, term, session, is_secondary_class, is_primary_class)

    with tabs[1]:
        render_psychomotor_comments_tab(students, class_name, term, session, is_secondary_class, is_primary_class)

    with tabs[2]:
        render_batch_add_ct_tab(students, class_name, term, session)

    with tabs[3]:
        render_batch_add_ht_tab(students, class_name, term, session, is_secondary_class, is_primary_class)

    with tabs[4]:
        render_batch_delete_tab(students, class_name, term, session, is_secondary_class, is_primary_class)


def render_view_delete_tab(students, class_name, term, session, is_secondary_class, is_primary_class):
    """Render the View/Delete Comments tab"""
    st.subheader("View Comments and Psychomotor Ratings")
    
    # Display existing comments
    comments_data = []
    for idx, s in enumerate(students, 1):
        comment = get_comment(s[1], class_name, term, session)
        psychomotor = get_psychomotor_rating(s[1], class_name, term, session)
        
        if comment or psychomotor:
            comments_data.append({
                "S/N": str(idx),
                "Student": s[1],
                "Class Teacher Comment": comment['class_teacher_comment'] if comment and comment['class_teacher_comment'] else "-",
                "Head Teacher Comment": comment['head_teacher_comment'] if comment and comment['head_teacher_comment'] else "-",
                "Has Psychomotor": "✓" if psychomotor else "✗"
            })
    
    if comments_data:
        st.dataframe(
            pd.DataFrame(comments_data),
            column_config={
                "S/N": st.column_config.TextColumn("S/N", width=10),
                "Student": st.column_config.TextColumn("Student", width=100),
                "Class Teacher Comment": st.column_config.TextColumn("Class Teacher Comment", width=200),
                "Head Teacher Comment": st.column_config.TextColumn("Head Teacher Comment", width=200),
                "Has Psychomotor": st.column_config.TextColumn("Has Psychomotor", width=50)
            },
            hide_index=True,
            use_container_width=True
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
            student_to_delete = st.selectbox(
                "Select Student", 
                [""] + students_with_data,
                key="delete_student_select"
            )
            
            if student_to_delete:
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("🗑️ Delete Comment", key="delete_comment_btn"):
                        if delete_comment(student_to_delete, class_name, term, session):
                            st.success(f"✅ Comment deleted for {student_to_delete}")
                            st.rerun()
                        else:
                            st.error("❌ Failed to delete comment")
                
                with col2:
                    if st.button("🗑️ Delete Psychomotor", key="delete_psycho_btn"):
                        if delete_psychomotor_rating(student_to_delete, class_name, term, session):
                            st.success(f"✅ Psychomotor rating deleted for {student_to_delete}")
                            st.rerun()
                        else:
                            st.error("❌ Failed to delete psychomotor rating")
        else:
            st.info("No data available to delete.")


def render_psychomotor_comments_tab(students, class_name, term, session, is_secondary_class, is_primary_class):
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
        if st.button("Apply to All Students", key="apply_psycho_all", use_container_width=True):
            success_count = 0
            for student in students:
                if create_psychomotor_rating(student[1], class_name, term, session, ratings):
                    success_count += 1
            st.success(f"✅ Applied rating to {success_count}/{len(students)} students")
            st.rerun()

    st.markdown("---")
    
    # COMMENTS SECTION WITH TEMPLATE SUPPORT
    with st.expander("Add/Edit Comments", expanded=True):
        st.markdown("### Student Comments")
        
        # Get existing comments
        existing_comment = get_comment(selected_student, class_name, term, session)
        class_teacher_comment = ""
        head_teacher_comment = ""
        
        if existing_comment:
            class_teacher_comment = existing_comment['class_teacher_comment'] or ""
            head_teacher_comment = existing_comment['head_teacher_comment'] or ""
        
        # ============ CLASS TEACHER COMMENT ============
        st.markdown("#### Class Teacher Comment")
        
        # Get templates
        ct_templates = get_all_comment_templates('class_teacher')
        
        # Template selection or custom
        col_mode, col_template = st.columns([1, 3])
        
        with col_mode:
            ct_mode = st.radio(
                "Mode",
                ["Custom", "Template"],
                key=f"ct_mode_{selected_student}",
                label_visibility="collapsed",
                horizontal=True
            )
        
        with col_template:
            if ct_mode == "Template" and ct_templates:
                template_options = ["-- Select a template --"] + [t[1] for t in ct_templates]
                selected_ct_template = st.selectbox(
                    "Choose template",
                    template_options,
                    key=f"ct_template_{selected_student}",
                    label_visibility="collapsed"
                )
                
                if selected_ct_template != "-- Select a template --":
                    class_teacher_comment = selected_ct_template
        
        # Comment text area
        ct_comment = st.text_area(
            "Class Teacher Comment",
            value=class_teacher_comment,
            height=80,
            key=f"ct_comment_{selected_student}",
            placeholder="Type your comment here or select from template above..."
        )
        
        # Action buttons
        col_save_ct, col_space_ct, col_apply_ct = st.columns(3)
        
        with col_save_ct:
            if st.button("💾 Save CT Comment", key="save_ct_comment", use_container_width=True):
                if create_comment(selected_student, class_name, term, session, ct_comment, head_teacher_comment):
                    st.success(f"✅ Class Teacher comment saved")
                    st.rerun()
                else:
                    st.error("❌ Failed to save comment")
        
        with col_apply_ct:
            if st.button("Apply to All Students", key="apply_ct_all", use_container_width=True):
                success_count = 0
                for student in students:
                    existing = get_comment(student[1], class_name, term, session)
                    ht_existing = existing['head_teacher_comment'] if existing else ""
                    if create_comment(student[1], class_name, term, session, ct_comment, ht_existing):
                        success_count += 1
                st.success(f"✅ Applied to {success_count}/{len(students)} students")
                st.rerun()
        
        st.markdown("---")
        
        # ============ HEAD TEACHER COMMENT ============
        st.markdown(f"### {"Principal Comment" if is_secondary_class else "Head Teacher Comment" if is_primary_class else ""}")
        
        # Get templates
        ht_templates = get_all_comment_templates('head_teacher')
        
        # Template selection or custom
        col_mode_ht, col_template_ht = st.columns([1, 3])
        
        with col_mode_ht:
            ht_mode = st.radio(
                "Mode",
                ["Custom", "Template"],
                key=f"ht_mode_{selected_student}",
                label_visibility="collapsed",
                horizontal=True
            )
        
        with col_template_ht:
            if ht_mode == "Template" and ht_templates:
                ht_template_options = ["-- Select a template --"] + [t[1] for t in ht_templates]
                selected_ht_template = st.selectbox(
                    "Choose template",
                    ht_template_options,
                    key=f"ht_template_{selected_student}",
                    label_visibility="collapsed"
                )
                
                if selected_ht_template != "-- Select a template --":
                    head_teacher_comment = selected_ht_template
        
        # Comment text area
        ht_comment = st.text_area(
            f"{"Principal Comment" if is_secondary_class else "Head Teacher Comment" if is_primary_class else ""}",
            value=head_teacher_comment,
            height=80,
            key=f"ht_comment_{selected_student}",
            placeholder="Type your comment here or select from template above..."
        )
        
        # Action buttons
        col_save_ht, col_space_ht, col_apply_ht = st.columns(3)
        
        with col_save_ht:
            if st.button(f"{"💾 Save Principal Comment" if is_secondary_class else "💾 Save HT Comment" if is_primary_class else ""}", key="save_ht_comment", use_container_width=True):
                if create_comment(selected_student, class_name, term, session, ct_comment, ht_comment):
                    st.success(f"✅ Head Teacher comment saved")
                    st.rerun()
                else:
                    st.error("❌ Failed to save comment")
        
        with col_apply_ht:
            if st.button("Apply to All Students", key="apply_ht_all", use_container_width=True):
                success_count = 0
                for student in students:
                    existing = get_comment(student[1], class_name, term, session)
                    ct_existing = existing['class_teacher_comment'] if existing else ""
                    if create_comment(student[1], class_name, term, session, ct_existing, ht_comment):
                        success_count += 1
                st.success(f"✅ Applied to {success_count}/{len(students)} students")
                st.rerun()


def render_batch_add_ct_tab(students, class_name, term, session):
    """Render the Batch Add Class Teacher Comments tab"""
    st.subheader("Batch Add Class Teacher Comments")
    st.info("💡 Add or update Class Teacher comments for multiple students at once.")
    
    ct_templates = get_all_comment_templates('class_teacher')
    
    if 'batch_ct_counter' not in st.session_state:
        st.session_state.batch_ct_counter = 0
    
    with st.expander("Batch Class Teacher Comments", expanded=True):
        batch_comments = {}
        
        for idx, student in enumerate(students):
            student_name = student[1]
            existing_comment = get_comment(student_name, class_name, term, session)
            existing_ct = existing_comment['class_teacher_comment'] or "" if existing_comment else ""
            
            with st.container(border=True):
                st.markdown(f"#### {student_name}")
                
                # Template selection or custom
                col_mode_ct, col_template_ct = st.columns([1, 3], vertical_alignment="bottom")
                
                with col_mode_ct:
                    batch_ct_mode = st.radio(
                        "Mode",
                        ["Custom", "Template"],
                        key=f"batch_ct_mode_{idx}_{student_name}",
                        horizontal=True
                    )
                
                ct_comment = existing_ct
                
                with col_template_ct:
                    if batch_ct_mode == "Template":
                        if ct_templates:
                            template_options = ["-- Select a template --"] + [t[1] for t in ct_templates]
                            selected_ct_template = st.selectbox(
                                "Choose template",
                                template_options,
                                key=f"ct_template_{idx}_{student_name}",
                                label_visibility="collapsed"
                            )
                            
                            if selected_ct_template != "-- Select a template --":
                                ct_comment = selected_ct_template
                        else:
                            st.info("No templates available")
                
                ct_comment = st.text_area(
                    "Comment",
                    value=ct_comment,
                    height=80,
                    key=f"ct_comment_{idx}_{student_name}",
                    placeholder="Type your comment here..."
                )
                
                batch_comments[student_name] = ct_comment
        
        st.markdown("---")
        submit = st.button("💾 Save All CT Comments", key="save_batch_ct_comment", type="primary", use_container_width=True)
        
        if submit:
            success_count = 0
            for student_name, ct_comment in batch_comments.items():
                if ct_comment.strip():
                    existing = get_comment(student_name, class_name, term, session)
                    existing_ht = existing['head_teacher_comment'] if existing else ""
                    if create_comment(student_name, class_name, term, session, ct_comment, existing_ht):
                        success_count += 1
            
            if success_count > 0:
                st.success(f"✅ Successfully saved CT comments for {success_count} student(s).")
                st.session_state.batch_ct_counter += 1
                st.rerun()
            else:
                st.warning("⚠️ No CT comments to save.")


def render_batch_add_ht_tab(students, class_name, term, session, is_secondary_class, is_primary_class):
    """Render the Batch Add Head Teacher/Principal Comments tab"""
    ht_label = "Principal Comments" if is_secondary_class else "Head Teacher Comments"
    st.subheader(f"Batch Add {ht_label}")
    st.info(f"💡 Add or update {ht_label} for multiple students at once.")
    
    ht_templates = get_all_comment_templates('head_teacher')
    
    if 'batch_ht_counter' not in st.session_state:
        st.session_state.batch_ht_counter = 0
    
    with st.expander("Batch Principal Comments", expanded=True):
        batch_comments = {}
        
        for idx, student in enumerate(students):
            student_name = student[1]
            existing_comment = get_comment(student_name, class_name, term, session)
            existing_ht = existing_comment['head_teacher_comment'] or "" if existing_comment else ""
            
            with st.container(border=True):
                st.markdown(f"#### {student_name}")
                
                # Template selection or custom
                col_mode_ht, col_template_ht = st.columns([1, 3], vertical_alignment="bottom")
                
                with col_mode_ht:
                    ht_mode = st.radio(
                        "Mode",
                        ["Custom", "Template"],
                        key=f"ht_mode_{idx}_{student_name}",
                        label_visibility="collapsed",
                        horizontal=True
                    )
                
                ht_comment = existing_ht
                
                with col_template_ht:
                    if ht_mode == "Template":
                        if ht_templates:
                            template_options = ["-- Select a template --"] + [t[1] for t in ht_templates]
                            selected_ht_template = st.selectbox(
                                "Choose template",
                                template_options,
                                key=f"ht_template_{idx}_{student_name}",
                                label_visibility="collapsed"
                            )
                            
                            if selected_ht_template != "-- Select a template --":
                                ht_comment = selected_ht_template
                        else:
                            st.info("No templates available")
                
                ht_comment = st.text_area(
                    "Comment",
                    value=ht_comment,
                    height=80,
                    key=f"ht_comment_{idx}_{student_name}",
                    placeholder="Type your comment here..."
                )
                
                batch_comments[student_name] = ht_comment
        
        st.markdown("---")
        submit = st.button(f"💾 Save All {ht_label}", key=f"save_batch_{ht_label}_comment", type="primary", use_container_width=True)
        
        if submit:
            success_count = 0
            for student_name, ht_comment in batch_comments.items():
                if ht_comment.strip():
                    existing = get_comment(student_name, class_name, term, session)
                    existing_ct = existing['class_teacher_comment'] if existing else ""
                    if create_comment(student_name, class_name, term, session, existing_ct, ht_comment):
                        success_count += 1
            
            if success_count > 0:
                st.success(f"✅ Successfully saved {ht_label} for {success_count} student(s).")
                st.session_state.batch_ht_counter += 1
                st.rerun()
            else:
                st.warning(f"⚠️ No {ht_label} to save.")        


def render_batch_delete_tab(students, class_name, term, session, is_secondary_class, is_primary_class):
    """Render the Batch Delete tab"""
    st.subheader("Batch Delete Operations")
    st.warning("⚠️ **DANGER ZONE**: These actions will permanently delete data for the selected class.")
    
    st.markdown(" ")

    col1, col2 = st.columns(2, gap="large")
    
    # Delete all comments
    with col1:
        with st.container(border=True):
            st.markdown("#### Clear All Comments")
            
            comments_exist = any(get_comment(s[1], class_name, term, session) for s in students)
            
            if comments_exist:
                st.error("This will delete all class teacher and head teacher comments for this class.")
                
                confirm_delete_comments = st.checkbox(
                    "I understand this action cannot be undone",
                    key="confirm_delete_comments"
                )
                
                if st.button(
                    "🗑️ Delete All Comments",
                    disabled=not confirm_delete_comments,
                    key="delete_all_comments",
                    type="primary",
                    use_container_width=True
                ):
                    deleted_count = 0
                    for student in students:
                        if delete_comment(student[1], class_name, term, session):
                            deleted_count += 1
                    st.success(f"✅ Deleted comments for {deleted_count} student(s).")
                    st.rerun()
            else:
                st.info("✓ No comments to delete for this class.")
    
    # Delete all psychomotor ratings
    with col2:
        with st.container(border=True):
            st.markdown("#### Clear All Psychomotor Ratings")
            
            ratings_exist = any(get_psychomotor_rating(s[1], class_name, term, session) for s in students)
            
            if ratings_exist:
                st.error("This will delete all psychomotor ratings for this class.")
                
                confirm_delete_psycho = st.checkbox(
                    "I understand this action cannot be undone",
                    key="confirm_delete_psycho"
                )
                
                if st.button(
                    "🗑️ Delete All Psychomotor",
                    disabled=not confirm_delete_psycho,
                    key="delete_all_psycho",
                    type="primary",
                    use_container_width=True
                ):
                    deleted_count = 0
                    for student in students:
                        if delete_psychomotor_rating(student[1], class_name, term, session):
                            deleted_count += 1
                    st.success(f"✅ Deleted psychomotor ratings for {deleted_count} student(s).")
                    st.rerun()
            else:
                st.info("✓ No psychomotor ratings to delete for this class.")