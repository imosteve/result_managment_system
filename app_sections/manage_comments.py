# app_sections/manage_comments.py

import streamlit as st
import pandas as pd
import re
from database import (
    get_all_classes, get_students_by_class, create_comment, get_comment, 
    delete_comment, create_psychomotor_rating, get_psychomotor_rating,
    delete_psychomotor_rating, get_all_comment_templates, get_student_average,
    get_head_teacher_comment_by_average
)
from main_utils import render_page_header, inject_login_css, render_persistent_class_selector
from auth.activity_tracker import ActivityTracker

# Psychomotor categories with their display names
PSYCHOMOTOR_CATEGORIES = [
    "Punctuality", "Neatness", "Honesty", "Cooperation",
    "Leadership", "Perseverance", "Politeness", "Obedience",
    "Attentiveness", "Attitude to work"
]

def manage_comments():
    """Manage report card comments and psychomotor ratings for students"""
    # Initialize activity tracker
    ActivityTracker.init()
    
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
    
    # Track class selector interaction
    if selected_class_data:
        ActivityTracker.watch_value(
            "manage_comments_class_selector",
            f"{selected_class_data['class_name']}_{selected_class_data['term']}_{selected_class_data['session']}"
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
    if role in ["admin", "superadmin"]:
        tabs = st.tabs([
            "View/Delete Comments", 
            "Psychomotor & Comments", 
            "Batch CT Comments", 
            "Batch HT Comments", 
            "Batch Delete"
        ])
    else:
        tabs = st.tabs([
            "View/Delete Comments", 
            "Psychomotor & Comments", 
            "Batch CT Comments",
            "Batch Delete"
        ])
    
    # Initialize tab tracker
    if "manage_comments_tab_tracker" not in st.session_state:
        st.session_state.manage_comments_tab_tracker = 0

    # Tab 1: View/Delete Comments
    with tabs[0]:
        if st.session_state.manage_comments_tab_tracker != 0:
            ActivityTracker.watch_tab("manage_comments_tabs", 0)
            st.session_state.manage_comments_tab_tracker = 0
        render_view_delete_tab(students, class_name, term, session, is_secondary_class, is_primary_class, user_id, role)

    # Tab 2: Psychomotor & Comments
    with tabs[1]:
        if st.session_state.manage_comments_tab_tracker != 1:
            ActivityTracker.watch_tab("manage_comments_tabs", 1)
            st.session_state.manage_comments_tab_tracker = 1
        render_psychomotor_comments_tab(role, students, class_name, term, session, is_secondary_class, is_primary_class, user_id)

    # Tab 3: Batch CT Comments
    with tabs[2]:
        if st.session_state.manage_comments_tab_tracker != 2:
            ActivityTracker.watch_tab("manage_comments_tabs", 2)
            st.session_state.manage_comments_tab_tracker = 2
        render_batch_add_ct_tab(students, class_name, term, session)

    # Tab 4: Batch HT Comments (admin/superadmin only)
    if role in ["admin", "superadmin"]:
        with tabs[3]:
            if st.session_state.manage_comments_tab_tracker != 3:
                ActivityTracker.watch_tab("manage_comments_tabs", 3)
                st.session_state.manage_comments_tab_tracker = 3
            render_batch_add_ht_tab(students, class_name, term, session, is_secondary_class, is_primary_class, user_id, role)

    # Tab 5: Batch Delete (last tab - index depends on role)
    with tabs[4 if role in ["admin", "superadmin"] else 3]:
        if role in ["admin", "superadmin"]:
            if st.session_state.manage_comments_tab_tracker != 4:
                ActivityTracker.watch_tab("manage_comments_tabs", 4)
                st.session_state.manage_comments_tab_tracker = 4
        else:
            if st.session_state.manage_comments_tab_tracker != 3:
                ActivityTracker.watch_tab("manage_comments_tabs", 3)
                st.session_state.manage_comments_tab_tracker = 3
        render_batch_delete_tab(students, class_name, term, session, is_secondary_class, is_primary_class)


def render_view_delete_tab(students, class_name, term, session, is_secondary_class, is_primary_class, user_id, role):
    """Render the View/Delete Comments tab"""
    st.subheader("View Comments and Psychomotor Ratings")
    
    # Display existing comments
    comments_data = []
    for idx, s in enumerate(students, 1):
        comment = get_comment(s[1], class_name, term, session)
        psychomotor = get_psychomotor_rating(s[1], class_name, term, session)
        
        # Get student average for display
        avg = get_student_average(s[1], class_name, term, session, user_id, role)
        
        if comment or psychomotor:
            ht_comment_display = comment['head_teacher_comment'] if comment and comment['head_teacher_comment'] else "-"
            is_custom = comment.get('head_teacher_comment_custom', 0) == 1 if comment else False
            
            comments_data.append({
                "S/N": str(idx),
                "Student": s[1],
                "Average": f"{avg:.2f}" if avg > 0 else "-",
                "Class Teacher Comment": comment['class_teacher_comment'] if comment and comment['class_teacher_comment'] else "-",
                "Head Teacher Comment": ht_comment_display + (" (Custom)" if is_custom else " (Auto)") if ht_comment_display != "-" else "-",
                "Has Psychomotor": "✓" if psychomotor else "✗"
            })
    
    if comments_data:
        st.dataframe(
            pd.DataFrame(comments_data),
            column_config={
                "S/N": st.column_config.TextColumn("S/N", width=10),
                "Student": st.column_config.TextColumn("Student", width=100),
                "Average": st.column_config.TextColumn("Average", width=50),
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
            student_to_delete = st.selectbox(
                "Select Student", 
                [""] + students_with_data,
                key="delete_student_select"
            )
            
            # Track student selection
            ActivityTracker.watch_value("delete_student_select_dropdown", student_to_delete)
            
            if student_to_delete:
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("🗑️ Delete Comment", key="delete_comment_btn"):
                        ActivityTracker.update()
                        if delete_comment(student_to_delete, class_name, term, session):
                            st.success(f"✅ Comment deleted for {student_to_delete}")
                            st.rerun()
                        else:
                            st.error("❌ Failed to delete comment")
                
                with col2:
                    if st.button("🗑️ Delete Psychomotor", key="delete_psycho_btn"):
                        ActivityTracker.update()
                        if delete_psychomotor_rating(student_to_delete, class_name, term, session):
                            st.success(f"✅ Psychomotor rating deleted for {student_to_delete}")
                            st.rerun()
                        else:
                            st.error("❌ Failed to delete psychomotor rating")
        else:
            st.info("No data available to delete.")


def render_psychomotor_comments_tab(role, students, class_name, term, session, is_secondary_class, is_primary_class, user_id):
    """Render the Psychomotor Rating & Add Single Comment tab"""
    
    # Student selection
    student_names = [s[1] for s in students]
    selected_student = st.selectbox("Select Student", student_names, key="psycho_comment_student")
    
    # Track student selection
    ActivityTracker.watch_value("psycho_comment_student_dropdown", selected_student)
    
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
            
            slider_key = f"psycho_{selected_student}_{category}_{i}"
            ratings[category] = st.slider(
                category, 
                1, 5, 
                default_value, 
                key=slider_key
            )
            ActivityTracker.watch_value(slider_key, ratings[category])
            
    with col3:
        for i, category in enumerate(PSYCHOMOTOR_CATEGORIES[4:7]):
            default_value = 3
            if existing_psychomotor and category.lower().replace(' ', '_') in existing_psychomotor:
                default_value = existing_psychomotor[category.lower().replace(' ', '_')]
            
            slider_key = f"psycho_{selected_student}_{category}_{i}"
            ratings[category] = st.slider(
                category, 
                1, 5, 
                default_value, 
                key=slider_key
            )
            ActivityTracker.watch_value(slider_key, ratings[category])
            
    with col5:
        for i, category in enumerate(PSYCHOMOTOR_CATEGORIES[7:]):
            default_value = 3
            if existing_psychomotor and category.lower().replace(' ', '_') in existing_psychomotor:
                default_value = existing_psychomotor[category.lower().replace(' ', '_')]
            
            slider_key = f"psycho_{selected_student}_{category}_{i}"
            ratings[category] = st.slider(
                category, 
                1, 5, 
                default_value, 
                key=slider_key
            )
            ActivityTracker.watch_value(slider_key, ratings[category])
    
    # Save button for psychomotor
    col_save1, col_space1, col_apply1 = st.columns(3)
    
    with col_save1:
        if st.button("💾 Save Rating", key="save_psycho", width="stretch"):
            ActivityTracker.update()
            if create_psychomotor_rating(selected_student, class_name, term, session, ratings):
                st.success(f"✅ Psychomotor rating saved for {selected_student}")
                st.rerun()
            else:
                st.error("❌ Failed to save psychomotor rating")
    
    with col_apply1:
        if st.button("Apply to All Students", key="apply_psycho_all", width="stretch"):
            ActivityTracker.update()
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
        is_ht_custom = False
        
        if existing_comment:
            class_teacher_comment = existing_comment['class_teacher_comment'] or ""
            head_teacher_comment = existing_comment['head_teacher_comment'] or ""
            is_ht_custom = existing_comment.get('head_teacher_comment_custom', 0) == 1
        
        # ============ CLASS TEACHER COMMENT ============
        st.markdown("##### Class Teacher Comment")
        
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
            ActivityTracker.watch_value(f"ct_mode_{selected_student}", ct_mode)
        
        with col_template:
            if ct_mode == "Template" and ct_templates:
                template_options = ["-- Select a template --"] + [t[1] for t in ct_templates]
                selected_ct_template = st.selectbox(
                    "Choose template",
                    template_options,
                    key=f"ct_template_{selected_student}",
                    label_visibility="collapsed"
                )
                ActivityTracker.watch_value(f"ct_template_{selected_student}", selected_ct_template)
                
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
            if st.button("💾 Save CT Comment", key="save_ct_comment", width="stretch"):
                ActivityTracker.update()
                if create_comment(selected_student, class_name, term, session, ct_comment, head_teacher_comment, 1 if is_ht_custom else 0):
                    st.success(f"✅ Class Teacher comment saved")
                    st.rerun()
                else:
                    st.error("❌ Failed to save comment")
        
        with col_apply_ct:
            if st.button("Apply to All Students", key="apply_ct_all", width="stretch"):
                ActivityTracker.update()
                success_count = 0
                for student in students:
                    existing = get_comment(student[1], class_name, term, session)
                    ht_existing = existing['head_teacher_comment'] if existing else ""
                    ht_custom_existing = existing.get('head_teacher_comment_custom', 0) if existing else 0
                    if create_comment(student[1], class_name, term, session, ct_comment, ht_existing, ht_custom_existing):
                        success_count += 1
                st.success(f"✅ Applied to {success_count}/{len(students)} students")
                st.rerun()
        
        if role in ["admin", "superadmin"]:
            st.markdown("---")
            
            # ============ HEAD TEACHER COMMENT - AUTO AND CUSTOM ============
            st.markdown(f"##### {"Principal Comment" if is_secondary_class else "Head Teacher Comment" if is_primary_class else ""}")
            
            # Get student average for auto-comment
            student_avg = get_student_average(selected_student, class_name, term, session, user_id, role)
            auto_comment = get_head_teacher_comment_by_average(student_avg) if student_avg > 0 else None
            
            # Show student average and auto comment
            if student_avg > 0:
                st.info(f"📊 **Student Average:** {student_avg:.2f}")
                if auto_comment:
                    st.success(f"🤖 **Auto Comment:** {auto_comment}")
                else:
                    st.warning("⚠️ No template found for this average range. Please add a template or use custom comment.")
            else:
                st.warning("⚠️ Student has no scores yet. Cannot auto-generate comment.")
            
            # Mode selection - Auto or Custom
            col_ht_mode = st.columns(1)[0]
            ht_comment_mode = st.radio(
                "Comment Mode",
                ["Auto (Range-based)", "Custom"],
                key=f"ht_comment_mode_{selected_student}",
                horizontal=True
            )
            ActivityTracker.watch_value(f"ht_comment_mode_{selected_student}", ht_comment_mode)
            
            if ht_comment_mode == "Auto (Range-based)":
                # Auto mode - use template based on average
                if auto_comment:
                    st.text_area(
                        "Auto-Generated Comment (Read-only)",
                        value=auto_comment,
                        height=80,
                        disabled=True,
                        key=f"ht_comment_auto_{selected_student}"
                    )
                    
                    if st.button("💾 Save Auto Comment", key="save_ht_auto", width="stretch"):
                        ActivityTracker.update()
                        if create_comment(selected_student, class_name, term, session, ct_comment, auto_comment, 0):
                            st.success("✅ Auto comment saved")
                            st.rerun()
                        else:
                            st.error("❌ Failed to save comment")
                else:
                    st.info("No auto comment available. Switch to Custom mode to enter manually.")
            
            else:  # Custom mode
                # Get templates for selection
                ht_templates = get_all_comment_templates('head_teacher')
                
                col_template_select = st.columns(1)[0]
                if ht_templates:
                    template_options = ["-- Type custom comment --"] + [f"{t[1]} ({t[3]}-{t[4]})" for t in ht_templates]
                    selected_ht_template = st.selectbox(
                        "Choose from templates or type custom",
                        template_options,
                        key=f"ht_template_custom_{selected_student}"
                    )
                    ActivityTracker.watch_value(f"ht_template_custom_{selected_student}", selected_ht_template)
                    
                    if selected_ht_template != "-- Type custom comment --":
                        # Extract comment text (everything before the range part)
                        head_teacher_comment = selected_ht_template.rsplit(" (", 1)[0]
                
                # Custom text area
                ht_comment_custom = st.text_area(
                    "Custom Comment",
                    value=head_teacher_comment,
                    height=80,
                    key=f"ht_comment_custom_{selected_student}",
                    placeholder="Type your custom comment here or select from templates above..."
                )
                
                col_save_ht, col_apply_ht = st.columns(2)
                
                with col_save_ht:
                    if st.button("💾 Save Custom Comment", key="save_ht_custom", width="stretch"):
                        ActivityTracker.update()
                        if create_comment(selected_student, class_name, term, session, ct_comment, ht_comment_custom, 1):
                            st.success("✅ Custom comment saved")
                            st.rerun()
                        else:
                            st.error("❌ Failed to save comment")
                
                with col_apply_ht:
                    if st.button("Apply to All Students", key="apply_ht_custom_all", width="stretch"):
                        ActivityTracker.update()
                        success_count = 0
                        for student in students:
                            existing = get_comment(student[1], class_name, term, session)
                            ct_existing = existing['class_teacher_comment'] if existing else ""
                            if create_comment(student[1], class_name, term, session, ct_existing, ht_comment_custom, 1):
                                success_count += 1
                        st.success(f"✅ Applied custom comment to {success_count}/{len(students)} students")
                        st.rerun()


def render_batch_add_ct_tab(students, class_name, term, session):
    """Render the Batch Add Class Teacher Comments tab"""
    st.subheader("Batch Add Class Teacher Comments")
    st.info("💡 Add or update Class Teacher comments for multiple students at once.")
    
    ct_templates = get_all_comment_templates('class_teacher')
    
    # Initialize session state for batch CT comments
    if 'batch_ct_comments' not in st.session_state:
        st.session_state.batch_ct_comments = {}
    
    # Process students in pairs for 2-column layout
    for i in range(0, len(students), 2):
        col1, col2 = st.columns(2)
        
        # First student in the pair
        with col1:
            student = students[i]
            student_name = student[1]
            existing_comment = get_comment(student_name, class_name, term, session)
            existing_ct = existing_comment['class_teacher_comment'] or "" if existing_comment else ""
            
            # Initialize in session state if not exists
            if student_name not in st.session_state.batch_ct_comments:
                st.session_state.batch_ct_comments[student_name] = existing_ct
            
            with st.container(border=True):
                st.markdown(f"#### {student_name}")
                
                # Mode selection
                ct_mode_key = f"batch_ct_mode_{i}_{student_name}"
                ct_mode = st.radio(
                    "Mode",
                    ["Custom", "Template"],
                    key=ct_mode_key,
                    horizontal=True,
                    label_visibility="collapsed"
                )
                ActivityTracker.watch_value(ct_mode_key, ct_mode)
                
                # Template selection
                if ct_mode == "Template" and ct_templates:
                    template_options = ["-- Select a template --"] + [t[1] for t in ct_templates]
                    template_key = f"batch_ct_template_{i}_{student_name}"
                    selected_template = st.selectbox(
                        "Choose template",
                        template_options,
                        key=template_key,
                        label_visibility="collapsed"
                    )
                    ActivityTracker.watch_value(template_key, selected_template)
                    
                    if selected_template != "-- Select a template --":
                        st.session_state.batch_ct_comments[student_name] = selected_template
                elif ct_mode == "Template" and not ct_templates:
                    st.info("No templates available")
                
                # Text area with session state value
                comment = st.text_area(
                    "Comment",
                    value=st.session_state.batch_ct_comments[student_name],
                    height=50,
                    key=f"batch_ct_comment_{i}_{student_name}",
                    label_visibility="collapsed",
                    placeholder="Type your comment here...",
                    on_change=lambda sn=student_name, key=f"batch_ct_comment_{i}_{student_name}": 
                        st.session_state.batch_ct_comments.update({sn: st.session_state[key]})
                )
        
        # Second student in the pair (if exists)
        with col2:
            if i + 1 < len(students):
                student = students[i + 1]
                student_name = student[1]
                existing_comment = get_comment(student_name, class_name, term, session)
                existing_ct = existing_comment['class_teacher_comment'] or "" if existing_comment else ""
                
                # Initialize in session state if not exists
                if student_name not in st.session_state.batch_ct_comments:
                    st.session_state.batch_ct_comments[student_name] = existing_ct
                
                with st.container(border=True):
                    st.markdown(f"#### {student_name}")
                    
                    # Mode selection
                    ct_mode_key = f"batch_ct_mode_{i+1}_{student_name}"
                    ct_mode = st.radio(
                        "Mode",
                        ["Custom", "Template"],
                        key=ct_mode_key,
                        horizontal=True,
                        label_visibility="collapsed"
                    )
                    ActivityTracker.watch_value(ct_mode_key, ct_mode)
                    
                    # Template selection
                    if ct_mode == "Template" and ct_templates:
                        template_options = ["-- Select a template --"] + [t[1] for t in ct_templates]
                        template_key = f"batch_ct_template_{i+1}_{student_name}"
                        selected_template = st.selectbox(
                            "Choose template",
                            template_options,
                            key=template_key,
                            label_visibility="collapsed"
                        )
                        ActivityTracker.watch_value(template_key, selected_template)
                        
                        if selected_template != "-- Select a template --":
                            st.session_state.batch_ct_comments[student_name] = selected_template
                    elif ct_mode == "Template" and not ct_templates:
                        st.info("No templates available")
                    
                    # Text area with session state value
                    comment = st.text_area(
                        "Comment",
                        value=st.session_state.batch_ct_comments[student_name],
                        height=50,
                        key=f"batch_ct_comment_{i+1}_{student_name}",
                        label_visibility="collapsed",
                        placeholder="Type your comment here...",
                        on_change=lambda sn=student_name, key=f"batch_ct_comment_{i+1}_{student_name}": 
                            st.session_state.batch_ct_comments.update({sn: st.session_state[key]})
                    )
    
    st.markdown("---")
    
    if st.button("💾 Save All CT Comments", type="primary", key="save_all_batch_ct"):
        ActivityTracker.update()
        success_count = 0
        for student_name, ct_comment in st.session_state.batch_ct_comments.items():
            if ct_comment and ct_comment.strip():
                existing = get_comment(student_name, class_name, term, session)
                existing_ht = existing['head_teacher_comment'] if existing else ""
                ht_custom = existing.get('head_teacher_comment_custom', 0) if existing else 0
                if create_comment(student_name, class_name, term, session, ct_comment, existing_ht, ht_custom):
                    success_count += 1
        
        if success_count > 0:
            st.success(f"✅ Successfully saved CT comments for {success_count} student(s).")
            # Clear session state after successful save
            st.session_state.batch_ct_comments = {}
            st.rerun()
        else:
            st.warning("⚠️ No CT comments to save.")


def render_batch_add_ht_tab(students, class_name, term, session, is_secondary_class, is_primary_class, user_id, role):
    """Render the Batch Add Head Teacher/Principal Comments tab"""
    ht_label = "Principal Comments" if is_secondary_class else "Head Teacher Comments"
    st.subheader(f"Batch Add {ht_label}")
    
    # Mode selection for batch operation
    batch_mode = st.radio(
        "Batch Mode",
        ["Auto (Apply range-based comments to all)", "Custom (Individual comments)"],
        key="batch_ht_mode",
        horizontal=True
    )
    
    if batch_mode == "Auto (Apply range-based comments to all)":
        st.info("💡 This will automatically apply range-based comments to all students based on their averages.")
        
        # Show preview of what will be applied
        st.markdown("### Preview Auto Comments")
        
        preview_data = []
        students_without_template = []
        students_without_scores = []
        
        for student in students:
            student_name = student[1]
            avg = get_student_average(student_name, class_name, term, session, user_id, role)
            
            if avg > 0:
                auto_comment = get_head_teacher_comment_by_average(avg)
                if auto_comment:
                    preview_data.append({
                        "Student": student_name,
                        "Average": f"{avg:.2f}",
                        "Comment": auto_comment
                    })
                else:
                    students_without_template.append((student_name, avg))
            else:
                students_without_scores.append(student_name)
        
        if preview_data:
            st.dataframe(
                pd.DataFrame(preview_data),
                column_config={
                    "Student": st.column_config.TextColumn("Student", width=150),
                    "Average": st.column_config.TextColumn("Average", width=80),
                    "Comment": st.column_config.TextColumn("Comment", width=400)
                },
                hide_index=True,
                width="stretch"
            )
        
        if students_without_template:
            st.warning(f"⚠️ **{len(students_without_template)} student(s)** have scores but no matching template:")
            for sname, savg in students_without_template:
                st.write(f"- {sname} (Average: {savg:.2f})")
            st.info("These students will be skipped. Add templates for their average ranges or use Custom mode.")
        
        if students_without_scores:
            st.warning(f"⚠️ **{len(students_without_scores)} student(s)** have no scores yet:")
            st.write(", ".join(students_without_scores))
            st.info("These students will be skipped.")
        
        st.markdown("---")
        
        if st.button("🤖 Apply Auto Comments to All Eligible Students", type="primary", width="stretch", key="apply_auto_ht_all"):
            ActivityTracker.update()
            success_count = 0
            skipped_count = 0
            
            with st.spinner("Applying auto comments..."):
                for student in students:
                    student_name = student[1]
                    avg = get_student_average(student_name, class_name, term, session, user_id, role)
                    
                    if avg > 0:
                        auto_comment = get_head_teacher_comment_by_average(avg)
                        if auto_comment:
                            existing = get_comment(student_name, class_name, term, session)
                            ct_existing = existing['class_teacher_comment'] if existing else ""
                            if create_comment(student_name, class_name, term, session, ct_existing, auto_comment, 0):
                                success_count += 1
                            else:
                                skipped_count += 1
                        else:
                            skipped_count += 1
                    else:
                        skipped_count += 1
            
            if success_count > 0:
                st.success(f"✅ Successfully applied auto comments to {success_count} student(s).")
            
            if skipped_count > 0:
                st.warning(f"⚠️ Skipped {skipped_count} student(s) (no scores or no matching template).")
            
            if success_count > 0:
                st.rerun()
    
    else:  # Custom mode
        st.info(f"💡 Add or update {ht_label} for multiple students individually.")
        
        ht_templates = get_all_comment_templates('head_teacher')
        
        # Initialize session state for batch HT comments
        if 'batch_ht_comments' not in st.session_state:
            st.session_state.batch_ht_comments = {}
        if 'batch_ht_custom_flags' not in st.session_state:
            st.session_state.batch_ht_custom_flags = {}
        
        # Process students in pairs for 2-column layout
        for i in range(0, len(students), 2):
            col1, col2 = st.columns(2)
            
            # First student in the pair
            with col1:
                student = students[i]
                student_name = student[1]
                existing_comment = get_comment(student_name, class_name, term, session)
                existing_ht = existing_comment['head_teacher_comment'] or "" if existing_comment else ""
                
                # Initialize in session state if not exists
                if student_name not in st.session_state.batch_ht_comments:
                    st.session_state.batch_ht_comments[student_name] = existing_ht
                if student_name not in st.session_state.batch_ht_custom_flags:
                    st.session_state.batch_ht_custom_flags[student_name] = 1  # Default to custom
                
                with st.container(border=True):
                    st.markdown(f"#### {student_name}")
                    
                    # Show student average
                    avg = get_student_average(student_name, class_name, term, session, user_id, role)
                    if avg > 0:
                        st.caption(f"Average: {avg:.2f}")
                    
                    # Template selection
                    if ht_templates:
                        template_options = ["-- Type custom comment --"] + [f"{t[1]} ({t[3]}-{t[4]})" for t in ht_templates]
                        template_key = f"batch_ht_template_{i}_{student_name}"
                        selected_template = st.selectbox(
                            "Choose template",
                            template_options,
                            key=template_key,
                            label_visibility="collapsed"
                        )
                        ActivityTracker.watch_value(template_key, selected_template)
                        
                        if selected_template != "-- Type custom comment --":
                            # Extract comment text (everything before the range part)
                            st.session_state.batch_ht_comments[student_name] = selected_template.rsplit(" (", 1)[0]
                    else:
                        st.info("No templates available")
                    
                    # Text area with session state value
                    comment = st.text_area(
                        "Comment",
                        value=st.session_state.batch_ht_comments[student_name],
                        height=80,
                        key=f"batch_ht_comment_{i}_{student_name}",
                        label_visibility="collapsed",
                        placeholder="Type your comment here...",
                        on_change=lambda sn=student_name, key=f"batch_ht_comment_{i}_{student_name}": 
                            st.session_state.batch_ht_comments.update({sn: st.session_state[key]})
                    )
            
            # Second student in the pair (if exists)
            with col2:
                if i + 1 < len(students):
                    student = students[i + 1]
                    student_name = student[1]
                    existing_comment = get_comment(student_name, class_name, term, session)
                    existing_ht = existing_comment['head_teacher_comment'] or "" if existing_comment else ""
                    
                    # Initialize in session state if not exists
                    if student_name not in st.session_state.batch_ht_comments:
                        st.session_state.batch_ht_comments[student_name] = existing_ht
                    if student_name not in st.session_state.batch_ht_custom_flags:
                        st.session_state.batch_ht_custom_flags[student_name] = 1  # Default to custom
                    
                    with st.container(border=True):
                        st.markdown(f"#### {student_name}")
                        
                        # Show student average
                        avg = get_student_average(student_name, class_name, term, session, user_id, role)
                        if avg > 0:
                            st.caption(f"Average: {avg:.2f}")
                        
                        # Template selection
                        if ht_templates:
                            template_options = ["-- Type custom comment --"] + [f"{t[1]} ({t[3]}-{t[4]})" for t in ht_templates]
                            template_key = f"batch_ht_template_{i+1}_{student_name}"
                            selected_template = st.selectbox(
                                "Choose template",
                                template_options,
                                key=template_key,
                                label_visibility="collapsed"
                            )
                            ActivityTracker.watch_value(template_key, selected_template)
                            
                            if selected_template != "-- Type custom comment --":
                                # Extract comment text (everything before the range part)
                                st.session_state.batch_ht_comments[student_name] = selected_template.rsplit(" (", 1)[0]
                        else:
                            st.info("No templates available")
                        
                        # Text area with session state value
                        comment = st.text_area(
                            "Comment",
                            value=st.session_state.batch_ht_comments[student_name],
                            height=80,
                            key=f"batch_ht_comment_{i+1}_{student_name}",
                            label_visibility="collapsed",
                            placeholder="Type your comment here...",
                            on_change=lambda sn=student_name, key=f"batch_ht_comment_{i+1}_{student_name}": 
                                st.session_state.batch_ht_comments.update({sn: st.session_state[key]})
                        )

        st.markdown("---")

        if st.button(f"💾 Save All {ht_label}", type="primary", width="stretch", key="save_all_batch_ht"):
            ActivityTracker.update()
            success_count = 0
            for student_name, ht_comment in st.session_state.batch_ht_comments.items():
                if ht_comment and ht_comment.strip():
                    existing = get_comment(student_name, class_name, term, session)
                    existing_ct = existing['class_teacher_comment'] if existing else ""
                    # All custom batch comments are marked as custom (1)
                    if create_comment(student_name, class_name, term, session, existing_ct, ht_comment, 1):
                        success_count += 1
            
            if success_count > 0:
                st.success(f"✅ Successfully saved {ht_label} for {success_count} student(s).")
                # Clear session state after successful save
                st.session_state.batch_ht_comments = {}
                st.session_state.batch_ht_custom_flags = {}
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
                ActivityTracker.watch_value("confirm_delete_comments_checkbox", confirm_delete_comments)
                
                if st.button(
                    "🗑️ Delete All Comments",
                    disabled=not confirm_delete_comments,
                    key="delete_all_comments",
                    type="primary",
                    width="stretch"
                ):
                    ActivityTracker.update()
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
                ActivityTracker.watch_value("confirm_delete_psycho_checkbox", confirm_delete_psycho)
                
                if st.button(
                    "🗑️ Delete All Psychomotor",
                    disabled=not confirm_delete_psycho,
                    key="delete_all_psycho",
                    type="primary",
                    width="stretch"
                ):
                    ActivityTracker.update()
                    deleted_count = 0
                    for student in students:
                        if delete_psychomotor_rating(student[1], class_name, term, session):
                            deleted_count += 1
                    st.success(f"✅ Deleted psychomotor ratings for {deleted_count} student(s).")
                    st.rerun()
            else:
                st.info("✓ No psychomotor ratings to delete for this class.")