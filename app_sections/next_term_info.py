# app_sections/next_term_info.py

import streamlit as st
from datetime import date
import json

from database import (
    get_all_classes,
    get_next_term_info,
    create_or_update_next_term_info,
    delete_next_term_info,
    get_all_next_term_info
)
from utils import render_page_header, inject_login_css, render_persistent_next_term_selector


def calculate_next_term(current_term, current_session):
    """Intelligently calculate the next term and session"""
    term_map = {"1st Term": "2nd Term", "2nd Term": "3rd Term", "3rd Term": "1st Term"}
    next_term = term_map.get(current_term, "1st Term")
    
    # If moving from 3rd term to 1st term, increment session
    if current_term == "3rd Term":
        year_parts = current_session.split('/')
        if len(year_parts) == 2:
            start_year = int(year_parts[0])
            end_year = int(year_parts[1])
            next_session = f"{start_year + 1}/{end_year + 1}"
        else:
            next_session = current_session
    else:
        next_session = current_session
    
    return next_term, next_session


def next_term_info():
    # AUTH CHECK
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.stop()

    if st.session_state.get('role') not in ("superadmin", "admin"):
        st.error("⚠️ Access denied. Only admins can manage next term information.")
        st.stop()

    user_id = st.session_state.get("user_id")

    st.set_page_config(page_title="Next Term Information", layout="wide")
    inject_login_css("templates/tabs_styles.css")
    render_page_header("Next Term Information")

    classes = get_all_classes(user_id, st.session_state.get('role'))
    if not classes:
        st.warning("⚠️ No classes available. Please create a class first.")
        return

    # Extract unique class names
    all_class_names = sorted({c["class_name"] for c in classes})

    tab1, tab2 = st.tabs(["Manage Information", "All Configurations"])

    # ---------------------------
    # Tab 1: Configure
    # ---------------------------
    with tab1:
        # Selector at top
        selected_class_data = render_persistent_next_term_selector(classes, widget_key="nt_class_selector")
        
        if not selected_class_data:
            st.info("Please select a term and session to continue")
            return
        
        # Get current term and session from the first class (they should all be the same)
        current_term = selected_class_data['term']
        current_session = selected_class_data['session']
        
        # Calculate next term intelligently
        next_term, next_session = calculate_next_term(current_term, current_session)

        # Show context with manual override option
        st.info(f"**Current Term:** {current_term} — {current_session}")

        st.markdown("#### Manage Next Term Information")
        with st.form("basic_info_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                # Manual override for term
                term_options = ["1st Term", "2nd Term", "3rd Term"]
                default_term_idx = term_options.index(next_term) if next_term in term_options else 0
                selected_next_term = st.selectbox(
                    "Next Term",
                    term_options,
                    index=default_term_idx,
                    key="next_term_select"
                )
            
            with col2:
                # Manual override for session
                selected_next_session = st.text_input(
                    "Next Session",
                    value=next_session,
                    key="next_session_select"
                )
            existing = get_next_term_info(selected_next_term, selected_next_session)
            
            if existing:
                st.success(f"✏️ Editing: **{selected_next_term}** — **{selected_next_session}**")
            else:
                st.info(f"🆕 Creating: **{selected_next_term}** — **{selected_next_session}**")

            with col3:
                resumption_date = st.date_input(
                    "Resumption Date",
                    value=date.fromisoformat(existing['next_term_begins']) if existing and existing.get('next_term_begins') else date.today()
                )
            
            submit_basic = st.form_submit_button("Save Basic Info", type="primary", width=300)

        st.markdown("#### Fee Structure")
        st.caption("Enter fees for each class")
        
        with st.form("fees_form"):
            existing_fees = existing.get('fees', {}) if existing else {}
            fees = {}
            
            # Display in 2-column grid
            for i in range(0, len(all_class_names), 4):
                cols = st.columns(4)
                for j, col in enumerate(cols):
                    idx = i + j
                    if idx < len(all_class_names):
                        class_name = all_class_names[idx]
                        pre_value = existing_fees.get(class_name, "0")
                        with col:
                            fees[class_name] = st.text_input(
                                class_name,
                                value=str(pre_value),
                                key=f"fee_{class_name}"
                            )
            
            submit_all = st.form_submit_button("💾 Save All Information", type="primary", width=300)

    # Handle submissions
    if submit_basic or submit_all:
        fees_json = json.dumps(fees if submit_all else existing_fees)
        
        if create_or_update_next_term_info(selected_next_term, selected_next_session, resumption_date.isoformat(), fees_json, user_id):
            st.success("✅ Information saved successfully!")
            st.balloons()
            st.rerun()
        else:
            st.error("❌ Failed to save. Please try again.")

    # ---------------------------
    # Tab 2: All Configurations
    # ---------------------------
    with tab2:
        st.subheader("All Next Term Configurations")
        
        # Initialize session state for delete dialogs
        if 'show_delete_basic_dialog' not in st.session_state:
            st.session_state.show_delete_basic_dialog = False
        if 'show_delete_fees_dialog' not in st.session_state:
            st.session_state.show_delete_fees_dialog = False
        if 'config_to_delete' not in st.session_state:
            st.session_state.config_to_delete = None
        if 'delete_type' not in st.session_state:
            st.session_state.delete_type = None
        
        all_infos = get_all_next_term_info()
        
        if not all_infos:
            st.info("📭 No configurations found yet. Create one in the 'Manage Information' tab.")
            return

        # Search filter
        search = st.text_input(
            "🔍 Search",
            placeholder="Search by term or session...",
            key="search_configs"
        )
        
        # Filter entries
        if search:
            filtered = [
                info for info in all_infos
                if search.lower() in info['term'].lower() or search.lower() in info['session'].lower()
            ]
        else:
            filtered = all_infos

        if not filtered:
            st.info("📭 No configurations found. Try adjusting your search.")
        else:
            st.success(f"📊 Found **{len(filtered)}** configuration(s)")

            # Display configurations in cards
            for info in filtered:
                with st.container(border=True):
                    # Main header
                    col1, col2 = st.columns([2.5, 1])
                    with col1:
                        st.markdown(f"##### Next term Information")
                    with col2:
                        st.caption(f"🕒 Last updated: {info['updated_at']}")
                    
                    # Basic Information Container
                    with st.container(border=True):
                        col_label, col_content, col_action = st.columns([1, 6, 0.5])
                        
                        with col_label:
                            st.markdown("**Basic Info**")
                        
                        with col_content:
                            col_1_1, col_1_2 = st.columns(2)
                            with col_1_1:
                                st.markdown(f"**Next Term — Session:** {info['term']} — {info['session']}")
                            with col_1_2:
                                st.markdown(f"**Next Term Begins:** {info['next_term_begins']}")
                        
                        with col_action:
                            if st.button("🗑️", key=f"del_basic_{info['id']}", help="Delete basic information", type="primary"):
                                st.session_state.config_to_delete = info
                                st.session_state.delete_type = "basic"
                                st.session_state.show_delete_basic_dialog = True
                                st.rerun()
                    
                    # Fee Structure Container
                    fees_map = json.loads(info.get('fees_json', '{}'))
                    
                    with st.container(border=True):
                        col_label, col_content, col_action = st.columns([1, 6, 0.5])
                        
                        with col_label:
                            st.markdown("**Fee Structure**")
                        
                        with col_content:
                            if fees_map:
                                # Display fees in compact grid
                                fee_items = list(fees_map.items())
                                for i in range(0, len(fee_items), 4):
                                    fee_cols = st.columns(4)
                                    for j, col in enumerate(fee_cols):
                                        idx = i + j
                                        if idx < len(fee_items):
                                            class_name, amount = fee_items[idx]
                                            with col:
                                                st.caption(f"**{class_name}:** ₦{amount}")
                            else:
                                st.caption("_No fees configured_")
                        
                        with col_action:
                            if fees_map:
                                if st.button("🗑️", key=f"del_fees_{info['id']}", help="Delete fee structure", type="primary"):
                                    st.session_state.config_to_delete = info
                                    st.session_state.delete_type = "fees"
                                    st.session_state.show_delete_fees_dialog = True
                                    st.rerun()

        # Delete Basic Information Confirmation Dialog
        if st.session_state.show_delete_basic_dialog and st.session_state.config_to_delete:
            info = st.session_state.config_to_delete
            
            @st.dialog("⚠️ Confirm Delete Basic Information")
            def confirm_delete_basic():
                st.warning(f"Are you sure you want to delete the entire configuration for:")
                st.info(f"**{info['term']} — {info['session']}**")
                st.error("⚠️ This will delete ALL information including fees for this term/session!")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Yes, Delete Everything", type="primary", use_container_width=True):
                        if delete_next_term_info(info['term'], info['session']):
                            st.success("✅ Configuration deleted successfully!")
                            st.session_state.show_delete_basic_dialog = False
                            st.session_state.config_to_delete = None
                            st.rerun()
                        else:
                            st.error("❌ Failed to delete configuration")
                
                with col2:
                    if st.button("❌ Cancel", use_container_width=True):
                        st.session_state.show_delete_basic_dialog = False
                        st.session_state.config_to_delete = None
                        st.rerun()
            
            confirm_delete_basic()

        # Delete Fees Confirmation Dialog
        if st.session_state.show_delete_fees_dialog and st.session_state.config_to_delete:
            info = st.session_state.config_to_delete
            
            @st.dialog("⚠️ Confirm Delete Fee Structure")
            def confirm_delete_fees():
                st.warning(f"Are you sure you want to delete the fee structure for:")
                st.info(f"**{info['term']} — {info['session']}**")
                st.caption("This will clear all class fees but keep the basic information.")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Yes, Delete Fees", type="primary", use_container_width=True):
                        # Update with empty fees
                        if create_or_update_next_term_info(
                            info['term'], 
                            info['session'], 
                            info['next_term_begins'], 
                            json.dumps({}), 
                            user_id
                        ):
                            st.success("✅ Fee structure deleted successfully!")
                            st.session_state.show_delete_fees_dialog = False
                            st.session_state.config_to_delete = None
                            st.rerun()
                        else:
                            st.error("❌ Failed to delete fee structure")
                
                with col2:
                    if st.button("❌ Cancel", use_container_width=True):
                        st.session_state.show_delete_fees_dialog = False
                        st.session_state.config_to_delete = None
                        st.rerun()
            
            confirm_delete_fees()