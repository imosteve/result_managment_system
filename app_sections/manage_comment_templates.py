# app_sections/manage_comment_templates.py

import streamlit as st
import pandas as pd
from database import (
    add_comment_template,
    get_all_comment_templates,
    delete_comment_template,
    update_comment_template,
    check_range_overlap
)
from utils import render_page_header, inject_login_css, inject_metric_css


def manage_comment_templates():
    """Manage comment templates - Admin only"""
    
    # AUTH CHECK
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    if st.session_state.role not in ["superadmin", "admin"]:
        st.error("⚠️ Access denied. Only admins can manage comment templates.")
        st.switch_page("main.py")
        return

    user_id = st.session_state.get("user_id")
    
    st.set_page_config(page_title="Comment Templates", layout="wide")
    inject_login_css("templates/tabs_styles.css")
    
    render_page_header("Manage Comment Templates")

    # Initialize session state
    if "show_delete_dialog" not in st.session_state:
        st.session_state.show_delete_dialog = False
    if "template_to_delete" not in st.session_state:
        st.session_state.template_to_delete = None
    if "show_bulk_delete_dialog" not in st.session_state:
        st.session_state.show_bulk_delete_dialog = False
    if "templates_to_bulk_delete" not in st.session_state:
        st.session_state.templates_to_bulk_delete = []
    if "show_export_confirm" not in st.session_state:
        st.session_state.show_export_confirm = False
    if "show_clear_all_confirm" not in st.session_state:
        st.session_state.show_clear_all_confirm = False
    if "editing_template_id" not in st.session_state:
        st.session_state.editing_template_id = None

    # Create tabs
    tab1, tab2, tab3 = st.tabs(["View Templates", "Add Templates", "Bulk Operations"])

    # TAB 1 — VIEW AND EDIT TEMPLATES
    with tab1:
        st.subheader("View & Edit Comment Templates")
        
        # Filter options
        col1, col2 = st.columns([1, 1])
        with col1:
            filter_type = st.selectbox(
                "Filter by Type",
                ["All", "Class Teacher", "Head Teacher / Principal"],
                key="filter_type_view"
            )
        
        with col2:
            search_query = st.text_input(
                "🔍 Search",
                placeholder="Search templates...",
                key="search_templates"
            )
        
        # Get templates based on filter
        db_type = None
        if filter_type == "Class Teacher":
            db_type = "class_teacher"
        elif filter_type == "Head Teacher / Principal":
            db_type = "head_teacher"
        
        all_templates = get_all_comment_templates(db_type)
        
        # Apply search filter
        if search_query:
            templates = [t for t in all_templates if search_query.lower() in t[1].lower()]
        else:
            templates = all_templates
        
        if not templates:
            st.info("📭 No templates found." + (" Try adjusting your search." if search_query else ""))
        else:
            st.success(f"📊 Found **{len(templates)}** template(s)")
            st.markdown(f"🔵 **Class Teacher** &nbsp;&nbsp;&nbsp; 🟢 **Head Teacher / Principal**")

            # Display templates in cards
            for ix, template in enumerate(templates):
                template_id = template[0]
                text = template[1]
                t_type = template[2]
                avg_lower = template[3]
                avg_upper = template[4]
                created_at = template[5]
                
                with st.container(border=True):
                    # Check if this template is being edited
                    is_editing = st.session_state.editing_template_id == template_id
                    
                    col_badge, col_comment, col_actions = st.columns([0.3, 5, 1])
                    
                    with col_badge:
                        # Type badge
                        badge_color = "🔵" if t_type == "class_teacher" else "🟢"
                        st.markdown(f"{badge_color}")
                    
                    with col_actions:
                        col_edit, col_del = st.columns(2)
                        
                        with col_edit:
                            if not is_editing:
                                if st.button("✏️", key=f"edit_btn_{template_id}", help="Edit template"):
                                    st.session_state.editing_template_id = template_id
                                    st.rerun()
                        
                        with col_del:
                            if st.button("🗑️", key=f"delete_btn_{template_id}", help="Delete template", type="primary"):
                                badge_text = "Class Teacher" if t_type == "class_teacher" else "Head Teacher / Principal"
                                st.session_state.template_to_delete = {
                                    "id": template_id,
                                    "text": text,
                                    "type": badge_text,
                                    "range": f"{avg_lower}-{avg_upper}" if avg_lower is not None else None
                                }
                                st.session_state.show_delete_dialog = True
                                st.rerun()
                    
                    with col_comment:
                        # Show edit mode or display mode
                        if is_editing:
                            # Range inputs for head teacher templates
                            if t_type == "head_teacher":
                                col_lower, col_upper = st.columns(2)
                                with col_lower:
                                    edited_lower = st.number_input(
                                        "Lower Bound",
                                        min_value=0.0,
                                        max_value=100.0,
                                        value=float(avg_lower) if avg_lower is not None else 0.0,
                                        step=0.1,
                                        key=f"edit_lower_{template_id}"
                                    )
                                with col_upper:
                                    edited_upper = st.number_input(
                                        "Upper Bound",
                                        min_value=0.0,
                                        max_value=100.0,
                                        value=float(avg_upper) if avg_upper is not None else 100.0,
                                        step=0.1,
                                        key=f"edit_upper_{template_id}"
                                    )
                            else:
                                edited_lower = None
                                edited_upper = None
                            
                            edited_text = st.text_area(
                                "Edit comment text",
                                value=text,
                                height=80,
                                key=f"edit_area_{template_id}"
                            )
                            
                            col_save, col_cancel = st.columns(2)
                            
                            with col_save:
                                if st.button("💾 Save Changes", key=f"save_{template_id}", width='stretch'):
                                    # Validate for head teacher templates
                                    if t_type == "head_teacher":
                                        if edited_lower >= edited_upper:
                                            st.error("❌ Lower bound must be less than upper bound.")
                                        elif check_range_overlap(edited_lower, edited_upper, template_id):
                                            st.error("❌ This range overlaps with an existing template.")
                                        elif edited_text.strip():
                                            if update_comment_template(template_id, edited_text, edited_lower, edited_upper):
                                                st.success("✅ Template updated successfully!")
                                                st.session_state.editing_template_id = None
                                                st.rerun()
                                            else:
                                                st.error("❌ Failed to update template.")
                                        else:
                                            st.error("❌ Template text cannot be empty.")
                                    else:
                                        if edited_text.strip():
                                            if update_comment_template(template_id, edited_text):
                                                st.success("✅ Template updated successfully!")
                                                st.session_state.editing_template_id = None
                                                st.rerun()
                                            else:
                                                st.error("❌ Failed to update template.")
                                        else:
                                            st.error("❌ Template text cannot be empty.")
                            
                            with col_cancel:
                                if st.button("❌ Cancel", key=f"cancel_{template_id}", width='stretch'):
                                    st.session_state.editing_template_id = None
                                    st.rerun()
                        else:
                            # Display mode
                            if t_type == "head_teacher" and avg_lower is not None and avg_upper is not None:
                                st.markdown(f"**Range:** {avg_lower} - {avg_upper}")
                            st.markdown(f"**{text}**")
                            st.caption(f"Created: {created_at}")
    
    
    # DELETE CONFIRMATION DIALOG
    if st.session_state.show_delete_dialog and st.session_state.template_to_delete:
        @st.dialog("⚠️ Confirm Delete")
        def show_delete_confirmation():
            data = st.session_state.template_to_delete
            
            st.error("### This action cannot be undone!")
            st.warning(f"**Type:** {data['type']}")
            if data.get('range'):
                st.info(f"**Range:** {data['range']}")
            st.info(f"**Text:** {data['text']}")
            
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("❌ Cancel", key="cancel_delete", width='stretch'):
                    st.session_state.show_delete_dialog = False
                    st.session_state.template_to_delete = None
                    st.rerun()
            
            with col2:
                if st.button("🗑️ Delete", key="confirm_delete", type="primary", width='stretch'):
                    if delete_comment_template(data["id"]):
                        st.success("✅ Template deleted successfully!")
                        st.session_state.show_delete_dialog = False
                        st.session_state.template_to_delete = None
                        st.rerun()
                    else:
                        st.error("❌ Failed to delete template.")
        
        show_delete_confirmation()

    # TAB 2 — ADD NEW TEMPLATES
    with tab2:
        st.subheader("Add New Comment Templates")
        
        # Comment type selection
        comment_type = st.selectbox(
            "Comment Type",
            ["class_teacher", "head_teacher"],
            format_func=lambda x: "Class Teacher" if x == "class_teacher" else "Head Teacher / Principal",
            key="add_comment_type"
        )
        
        if comment_type == "head_teacher":
            st.info("💡 **Head Teacher / Principal comments are range-based.** Define an average range and the comment for students within that range.")
            
            with st.form("add_ht_template_form", clear_on_submit=True):
                col_lower, col_upper = st.columns(2)
                
                with col_lower:
                    avg_lower = st.number_input(
                        "Lower Bound",
                        min_value=0.0,
                        max_value=100.0,
                        value=0.0,
                        step=0.1,
                        key="ht_lower"
                    )
                
                with col_upper:
                    avg_upper = st.number_input(
                        "Upper Bound",
                        min_value=0.0,
                        max_value=100.0,
                        value=100.0,
                        step=0.1,
                        key="ht_upper"
                    )
                
                new_comment = st.text_area(
                    "Comment Text",
                    placeholder="Enter comment for this average range...",
                    height=100,
                    key="ht_comment_text"
                )
                
                submitted = st.form_submit_button("➕ Add Template", width='stretch', type="primary")
                
                if submitted:
                    if not new_comment.strip():
                        st.error("❌ Please enter a comment.")
                    elif avg_lower >= avg_upper:
                        st.error("❌ Lower bound must be less than upper bound.")
                    elif check_range_overlap(avg_lower, avg_upper):
                        st.error("❌ This range overlaps with an existing template. Please choose a different range.")
                    else:
                        if add_comment_template(new_comment, comment_type, user_id, avg_lower, avg_upper):
                            st.success("✅ Head Teacher / Principal template added successfully!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to add template (duplicate text).")
        
        else:  # class_teacher
            st.info("💡 **Tip:** You can add multiple comments at once by entering each on a new line.")
            
            with st.form("add_ct_template_form", clear_on_submit=True):
                new_comments = st.text_area(
                    "Comment Text",
                    placeholder="Enter one or multiple comments.\nEach line will be added as a separate template.\n\nExample:\nExcellent performance this term.\nShows great improvement in all subjects.\nNeeds to work on punctuality.",
                    height=200,
                    key="ct_comment_text"
                )
                
                submitted = st.form_submit_button("➕ Add Template(s)", width='stretch', type="primary")
                
                if submitted:
                    if not new_comments.strip():
                        st.error("❌ Please enter at least one comment.")
                    else:
                        comment_lines = [line.strip() for line in new_comments.split("\n") if line.strip()]
                        
                        added_count = 0
                        skipped_count = 0
                        
                        for comment_text in comment_lines:
                            if add_comment_template(comment_text, comment_type, user_id):
                                added_count += 1
                            else:
                                skipped_count += 1
                        
                        if added_count > 0:
                            st.success(f"✅ Successfully added **{added_count}** template(s)!")
                        
                        if skipped_count > 0:
                            st.warning(f"⚠️ Skipped **{skipped_count}** duplicate(s).")
                        
                        if added_count > 0:
                            st.rerun()
    
    # TAB 3 — BULK OPERATIONS
    with tab3:
        st.subheader("Bulk Operations")
        
        # Get all templates
        all_templates = get_all_comment_templates()
        
        if not all_templates:
            st.info("📭 No templates available for bulk operations.")
        else:
            # Statistics
            class_teacher_count = sum(1 for t in all_templates if t[2] == "class_teacher")
            head_teacher_count = sum(1 for t in all_templates if t[2] == "head_teacher")
            
            # Inject custom CSS for metric styling
            inject_metric_css()

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Templates", len(all_templates))
            with col2:
                st.metric("🔵 Class Teacher", class_teacher_count)
            with col3:
                st.metric("🟢 Head Teacher / Principal", head_teacher_count)
            
            st.markdown("---")
            
            st.markdown("### 🎯 Delete by Type")
            st.error("⚠️ **DANGER ZONE** - This will delete ALL templates permanently!")
            
            col_ct, col_ht, col_clear = st.columns(3)
            
            with col_ct:
                if class_teacher_count > 0:
                    if st.button(
                        f"🗑️ Delete All Class Teacher ({class_teacher_count})",
                        key="delete_ct_all",
                        type="secondary",
                        width='stretch'
                    ):
                        ct_ids = [t[0] for t in all_templates if t[2] == "class_teacher"]
                        st.session_state.templates_to_bulk_delete = ct_ids
                        st.session_state.bulk_delete_type = "Class Teacher"
                        st.session_state.show_bulk_delete_dialog = True
                        st.rerun()
                else:
                    st.caption("No templates to delete")
            
            with col_ht:
                if head_teacher_count > 0:
                    if st.button(
                        f"🗑️ Delete All Head Teacher ({head_teacher_count})",
                        key="delete_ht_all",
                        type="secondary",
                        width='stretch'
                    ):
                        ht_ids = [t[0] for t in all_templates if t[2] == "head_teacher"]
                        st.session_state.templates_to_bulk_delete = ht_ids
                        st.session_state.bulk_delete_type = "Head Teacher / Principal"
                        st.session_state.show_bulk_delete_dialog = True
                        st.rerun()
                else:
                    st.caption("No templates to delete")
            
            with col_clear:
                if st.button(
                    f"Delete ALL Templates ({len(all_templates)})",
                    key="clear_all_templates",
                    type="primary",
                    width='stretch'
                ):
                    st.session_state.templates_to_bulk_delete = [t[0] for t in all_templates]
                    st.session_state.bulk_delete_type = "ALL"
                    st.session_state.show_clear_all_confirm = True
                    st.rerun()
            
    # BULK DELETE CONFIRMATION DIALOG
    if st.session_state.show_bulk_delete_dialog and st.session_state.templates_to_bulk_delete:
        @st.dialog("⚠️ Confirm Bulk Delete")
        def show_bulk_delete_confirmation():
            delete_count = len(st.session_state.templates_to_bulk_delete)
            delete_type = st.session_state.get("bulk_delete_type", "selected")
            
            st.error(f"### You are about to delete {delete_count} template(s)!")
            
            if delete_type == "Class Teacher":
                st.warning("⚠️ This will delete ALL Class Teacher templates.")
            elif delete_type == "Head Teacher / Principal":
                st.warning("⚠️ This will delete ALL Head Teacher / Principal templates.")
            else:
                st.warning("⚠️ This action cannot be undone.")
            
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("❌ Cancel", key="cancel_bulk_delete", width='stretch'):
                    st.session_state.show_bulk_delete_dialog = False
                    st.session_state.templates_to_bulk_delete = []
                    st.session_state.bulk_delete_type = None
                    st.rerun()
            
            with col2:
                if st.button(
                    f"🗑️ Delete {delete_count} Template(s)",
                    key="confirm_bulk_delete",
                    type="primary",
                    width='stretch'
                ):
                    deleted = 0
                    failed = 0
                    
                    with st.spinner(f"Deleting {delete_count} templates..."):
                        for template_id in st.session_state.templates_to_bulk_delete:
                            if delete_comment_template(template_id):
                                deleted += 1
                            else:
                                failed += 1
                    
                    if deleted > 0:
                        st.success(f"✅ Successfully deleted {deleted} template(s)!")
                    
                    if failed > 0:
                        st.error(f"❌ Failed to delete {failed} template(s).")
                    
                    st.session_state.show_bulk_delete_dialog = False
                    st.session_state.templates_to_bulk_delete = []
                    st.session_state.bulk_delete_type = None
                    st.rerun()
        
        show_bulk_delete_confirmation()
    
    # CLEAR ALL CONFIRMATION DIALOG
    if st.session_state.show_clear_all_confirm and st.session_state.templates_to_bulk_delete:
        @st.dialog("💥 DANGER: Clear All Templates")
        def show_clear_all_confirmation():
            delete_count = len(st.session_state.templates_to_bulk_delete)
            
            st.error("### ⚠️ CRITICAL ACTION - ALL TEMPLATES WILL BE DELETED!")
            st.error("This will permanently delete ALL comment templates from the database.")
            st.warning(f"Total templates to delete: **{delete_count}**")
            
            st.markdown("---")
            
            st.markdown("### Type `DELETE ALL` to confirm:")
            confirmation_text = st.text_input(
                "Confirmation",
                key="clear_all_confirmation_text",
                label_visibility="collapsed",
                placeholder="Type DELETE ALL here..."
            )
            
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("❌ Cancel", key="cancel_clear_all", width='stretch'):
                    st.session_state.show_clear_all_confirm = False
                    st.session_state.templates_to_bulk_delete = []
                    st.session_state.bulk_delete_type = None
                    st.rerun()
            
            with col2:
                delete_button_disabled = confirmation_text.strip() != "DELETE ALL"
                
                if st.button(
                    f"Delete ALL",
                    key="confirm_clear_all",
                    type="primary",
                    width='stretch',
                    disabled=delete_button_disabled
                ):
                    deleted = 0
                    failed = 0
                    
                    with st.spinner(f"Deleting ALL {delete_count} templates..."):
                        for template_id in st.session_state.templates_to_bulk_delete:
                            if delete_comment_template(template_id):
                                deleted += 1
                            else:
                                failed += 1
                    
                    if deleted > 0:
                        st.success(f"✅ Successfully deleted ALL {deleted} template(s)!")
                    
                    if failed > 0:
                        st.error(f"❌ Failed to delete {failed} template(s).")
                    
                    st.session_state.show_clear_all_confirm = False
                    st.session_state.templates_to_bulk_delete = []
                    st.session_state.bulk_delete_type = None
                    st.rerun()
        
        show_clear_all_confirmation()