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
        all_infos = get_all_next_term_info()
        
        if not all_infos:
            st.info("📭 No configurations found yet. Create one in the 'Configure Next Term' tab.")
            return

        # Search and filter
        col1, col2 = st.columns([3, 1])
        with col1:
            search = st.text_input("🔍 Search", placeholder="Filter by term or session...", label_visibility="collapsed")
        with col2:
            st.metric("Total", len(all_infos))
        
        st.divider()

        # Filter entries
        filtered = [
            info for info in all_infos
            if not search or search.lower() in info['term'].lower() or search.lower() in info['session'].lower()
        ]

        # Display as elegant cards
        for info in filtered:
            with st.container():
                # Header row
                head_col1, head_col2, head_col3 = st.columns([3, 2, 1])
                
                with head_col1:
                    st.markdown(f"### {info['term']} — {info['session']}")
                
                with head_col2:
                    st.metric("Resumption Date", info['next_term_begins'])
                
                with head_col3:
                    delete_key = f"del_{info['id']}"
                    if st.button("🗑️ Delete", key=delete_key, type="secondary"):
                        confirm_key = f"confirm_{delete_key}"
                        if st.session_state.get(confirm_key, False):
                            if delete_next_term_info(info['term'], info['session']):
                                st.success("✅ Deleted")
                                del st.session_state[confirm_key]
                                st.rerun()
                            else:
                                st.error("❌ Failed")
                        else:
                            st.session_state[confirm_key] = True
                            st.warning("⚠️ Click again to confirm")
                            st.rerun()
                
                # Fees section
                st.markdown("**Fee Structure:**")
                fees_map = json.loads(info.get('fees_json', '{}'))
                
                if fees_map:
                    # Display fees in compact grid
                    fee_cols = st.columns(4)
                    for idx, (class_name, amount) in enumerate(fees_map.items()):
                        with fee_cols[idx % 4]:
                            st.caption(f"**{class_name}**")
                            st.write(f"₦{amount}")
                else:
                    st.caption("No fees configured")
                
                st.caption(f"🕒 Last updated: {info['updated_at']}")
                st.divider()