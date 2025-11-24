# app_sections/next_term_info.py

import streamlit as st
from datetime import datetime, date
from database import (
    get_all_classes,
    get_next_term_info,
    create_or_update_next_term_info,
    delete_next_term_info,
    get_all_next_term_info
)
from utils import render_page_header, inject_login_css, render_persistent_class_selector


def next_term_info():
    """Manage next term information - Admin only"""
    
    # AUTH CHECK
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    if st.session_state.role not in ["superadmin", "admin"]:
        st.error("⚠️ Access denied. Only admins can manage next term information.")
        st.switch_page("main.py")
        return

    user_id = st.session_state.get("user_id")
    role = st.session_state.get("role")
    
    st.set_page_config(page_title="Next Term Information", layout="wide")
    inject_login_css("templates/tabs_styles.css")
    
    render_page_header("📅 Next Term Information")

    # Initialize session state
    if "show_delete_term_dialog" not in st.session_state:
        st.session_state.show_delete_term_dialog = False
    if "term_to_delete" not in st.session_state:
        st.session_state.term_to_delete = None

    # Create tabs
    tab1, tab2, tab3 = st.tabs(["📝 Add/Edit Information", "👁️ View All", "📋 Quick View"])

    # ================================================================
    # TAB 1 — ADD/EDIT NEXT TERM INFORMATION
    # ================================================================
    with tab1:
        st.subheader("Add or Update Next Term Information")
        
        # Get all classes for term/session selection
        classes = get_all_classes(user_id, role)
        
        if not classes:
            st.warning("⚠️ No classes available. Please create a class first.")
            return
        
        # Class selection
        selected_class_data = render_persistent_class_selector(
            classes,
            widget_key="next_term_info_class"
        )
        
        if not selected_class_data:
            st.warning("⚠️ Please select a term and session.")
            return
        
        term = selected_class_data['term']
        session = selected_class_data['session']
        
        # Load existing information
        existing_info = get_next_term_info(term, session)
        
        if existing_info:
            st.info(f"ℹ️ Editing existing information for **{term}** - **{session}**")
        else:
            st.success(f"✨ Creating new information for **{term}** - **{session}**")
        
        # Helper function to get existing value
        def get_value(field_index, default=""):
            if existing_info and existing_info[field_index]:
                return existing_info[field_index]
            return default
        
        # Form for next term information
        with st.form("next_term_info_form"):
            st.markdown("### 📅 Important Dates")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                next_term_begins = st.date_input(
                    "Next Term Begins *",
                    value=datetime.strptime(get_value(3), "%Y-%m-%d").date() if get_value(3) else date.today(),
                    key="next_term_begins"
                )
                
                vacation_starts = st.date_input(
                    "Vacation Starts",
                    value=datetime.strptime(get_value(5), "%Y-%m-%d").date() if get_value(5) else None,
                    key="vacation_starts"
                )
                
                fees_due_date = st.date_input(
                    "Fees Due Date",
                    value=datetime.strptime(get_value(7), "%Y-%m-%d").date() if get_value(7) else None,
                    key="fees_due_date"
                )
            
            with col2:
                next_term_ends = st.date_input(
                    "Next Term Ends",
                    value=datetime.strptime(get_value(4), "%Y-%m-%d").date() if get_value(4) else None,
                    key="next_term_ends"
                )
                
                vacation_ends = st.date_input(
                    "Vacation Ends",
                    value=datetime.strptime(get_value(6), "%Y-%m-%d").date() if get_value(6) else None,
                    key="vacation_ends"
                )
                
                registration_starts = st.date_input(
                    "Registration Starts",
                    value=datetime.strptime(get_value(8), "%Y-%m-%d").date() if get_value(8) else None,
                    key="registration_starts"
                )
            
            with col3:
                registration_ends = st.date_input(
                    "Registration Ends",
                    value=datetime.strptime(get_value(9), "%Y-%m-%d").date() if get_value(9) else None,
                    key="registration_ends"
                )
                
                pta_meeting_date = st.date_input(
                    "PTA Meeting Date",
                    value=datetime.strptime(get_value(18), "%Y-%m-%d").date() if get_value(18) else None,
                    key="pta_meeting_date"
                )
                
                visiting_day = st.date_input(
                    "Visiting Day",
                    value=datetime.strptime(get_value(19), "%Y-%m-%d").date() if get_value(19) else None,
                    key="visiting_day"
                )
            
            st.markdown("---")
            st.markdown("### ⏰ School Timings")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                school_hours = st.text_input(
                    "School Hours",
                    value=get_value(10),
                    placeholder="e.g., 8:00 AM - 3:00 PM",
                    key="school_hours"
                )
            
            with col2:
                assembly_time = st.text_input(
                    "Assembly Time",
                    value=get_value(11),
                    placeholder="e.g., 7:45 AM",
                    key="assembly_time"
                )
            
            with col3:
                closing_time = st.text_input(
                    "Closing Time",
                    value=get_value(12),
                    placeholder="e.g., 3:00 PM",
                    key="closing_time"
                )
            
            st.markdown("---")
            st.markdown("### 🎉 Special Events")
            
            col1, col2 = st.columns(2)
            
            with col1:
                sports_day = st.date_input(
                    "Sports Day",
                    value=datetime.strptime(get_value(20), "%Y-%m-%d").date() if get_value(20) else None,
                    key="sports_day"
                )
                
                cultural_day = st.date_input(
                    "Cultural Day",
                    value=datetime.strptime(get_value(21), "%Y-%m-%d").date() if get_value(21) else None,
                    key="cultural_day"
                )
            
            with col2:
                events_schedule = st.text_area(
                    "Events Schedule",
                    value=get_value(15),
                    height=100,
                    placeholder="List important events and their dates...",
                    key="events_schedule"
                )
            
            st.markdown("---")
            st.markdown("### 📚 Academic Information")
            
            col1, col2 = st.columns(2)
            
            with col1:
                important_dates = st.text_area(
                    "Important Academic Dates",
                    value=get_value(13),
                    height=100,
                    placeholder="Exam dates, assignment deadlines, etc.",
                    key="important_dates"
                )
                
                holidays = st.text_area(
                    "Public Holidays",
                    value=get_value(14),
                    height=100,
                    placeholder="List holidays during the term...",
                    key="holidays"
                )
            
            with col2:
                book_list = st.text_area(
                    "Required Books/Materials",
                    value=get_value(17),
                    height=100,
                    placeholder="List required textbooks and materials...",
                    key="book_list"
                )
                
                uniform_requirements = st.text_area(
                    "Uniform Requirements",
                    value=get_value(16),
                    height=100,
                    placeholder="Describe uniform requirements...",
                    key="uniform_requirements"
                )
            
            st.markdown("---")
            st.markdown("### 🚌 Logistics & Facilities")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                bus_schedule = st.text_area(
                    "Bus Schedule",
                    value=get_value(29),
                    height=80,
                    placeholder="Bus routes and timings...",
                    key="bus_schedule"
                )
            
            with col2:
                cafeteria_info = st.text_area(
                    "Cafeteria Information",
                    value=get_value(30),
                    height=80,
                    placeholder="Meal times, menu info...",
                    key="cafeteria_info"
                )
            
            with col3:
                library_hours = st.text_area(
                    "Library Hours",
                    value=get_value(31),
                    height=80,
                    placeholder="Library opening hours...",
                    key="library_hours"
                )
            
            st.markdown("---")
            st.markdown("### 🏥 Health & Safety")
            
            col1, col2 = st.columns(2)
            
            with col1:
                health_requirements = st.text_area(
                    "Health Requirements",
                    value=get_value(23),
                    height=100,
                    placeholder="Medical checkups, vaccinations, etc.",
                    key="health_requirements"
                )
            
            with col2:
                excursion_info = st.text_area(
                    "Excursion/Trip Information",
                    value=get_value(22),
                    height=100,
                    placeholder="Planned trips and excursions...",
                    key="excursion_info"
                )
            
            st.markdown("---")
            st.markdown("### 📞 Contact Information")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                contact_person = st.text_input(
                    "Contact Person",
                    value=get_value(24),
                    placeholder="e.g., School Administrator",
                    key="contact_person"
                )
            
            with col2:
                contact_email = st.text_input(
                    "Contact Email",
                    value=get_value(25),
                    placeholder="contact@school.com",
                    key="contact_email"
                )
            
            with col3:
                contact_phone = st.text_input(
                    "Contact Phone",
                    value=get_value(26),
                    placeholder="+234 xxx xxx xxxx",
                    key="contact_phone"
                )
            
            st.markdown("---")
            st.markdown("### 💬 Messages & Instructions")
            
            principal_message = st.text_area(
                "Principal's Message",
                value=get_value(27),
                height=120,
                placeholder="Welcome message or important announcement from the principal...",
                key="principal_message"
            )
            
            special_instructions = st.text_area(
                "Special Instructions",
                value=get_value(28),
                height=120,
                placeholder="Any special instructions for parents/students...",
                key="special_instructions"
            )
            
            st.markdown("---")
            
            # Submit button
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                submitted = st.form_submit_button(
                    "💾 Save Information",
                    use_container_width=True,
                    type="primary"
                )
            
            if submitted:
                # Prepare data dictionary
                info_data = {
                    'next_term_begins': next_term_begins.strftime("%Y-%m-%d"),
                    'next_term_ends': next_term_ends.strftime("%Y-%m-%d") if next_term_ends else None,
                    'vacation_starts': vacation_starts.strftime("%Y-%m-%d") if vacation_starts else None,
                    'vacation_ends': vacation_ends.strftime("%Y-%m-%d") if vacation_ends else None,
                    'fees_due_date': fees_due_date.strftime("%Y-%m-%d") if fees_due_date else None,
                    'registration_starts': registration_starts.strftime("%Y-%m-%d") if registration_starts else None,
                    'registration_ends': registration_ends.strftime("%Y-%m-%d") if registration_ends else None,
                    'school_hours': school_hours or None,
                    'assembly_time': assembly_time or None,
                    'closing_time': closing_time or None,
                    'important_dates': important_dates or None,
                    'holidays': holidays or None,
                    'events_schedule': events_schedule or None,
                    'uniform_requirements': uniform_requirements or None,
                    'book_list': book_list or None,
                    'pta_meeting_date': pta_meeting_date.strftime("%Y-%m-%d") if pta_meeting_date else None,
                    'visiting_day': visiting_day.strftime("%Y-%m-%d") if visiting_day else None,
                    'sports_day': sports_day.strftime("%Y-%m-%d") if sports_day else None,
                    'cultural_day': cultural_day.strftime("%Y-%m-%d") if cultural_day else None,
                    'excursion_info': excursion_info or None,
                    'health_requirements': health_requirements or None,
                    'contact_person': contact_person or None,
                    'contact_email': contact_email or None,
                    'contact_phone': contact_phone or None,
                    'principal_message': principal_message or None,
                    'special_instructions': special_instructions or None,
                    'bus_schedule': bus_schedule or None,
                    'cafeteria_info': cafeteria_info or None,
                    'library_hours': library_hours or None
                }
                
                if create_or_update_next_term_info(term, session, info_data, user_id):
                    st.success("✅ Next term information saved successfully!")
                    st.rerun()
                else:
                    st.error("❌ Failed to save information. Please try again.")
    
    # ================================================================
    # TAB 2 — VIEW ALL ENTRIES
    # ================================================================
    with tab2:
        st.subheader("All Next Term Information Entries")
        
        all_infos = get_all_next_term_info()
        
        if not all_infos:
            st.info("📭 No next term information entries found.")
        else:
            st.success(f"📊 Found **{len(all_infos)}** entry(ies)")
            
            for info in all_infos:
                term_name, session_name, begin_date, updated = info
                
                with st.container(border=True):
                    col1, col2, col3 = st.columns([2, 2, 1])
                    
                    with col1:
                        st.markdown(f"### {term_name}")
                        st.caption(f"Session: {session_name}")
                    
                    with col2:
                        st.markdown(f"**Next Term Begins:** {begin_date}")
                        st.caption(f"Last updated: {updated}")
                    
                    with col3:
                        if st.button("🗑️ Delete", key=f"del_{term_name}_{session_name}", type="primary"):
                            st.session_state.term_to_delete = {
                                "term": term_name,
                                "session": session_name
                            }
                            st.session_state.show_delete_term_dialog = True
                            st.rerun()
    
    # Delete confirmation dialog
    if st.session_state.show_delete_term_dialog and st.session_state.term_to_delete:
        @st.dialog("⚠️ Confirm Delete")
        def show_delete_dialog():
            data = st.session_state.term_to_delete
            
            st.error("### This action cannot be undone!")
            st.warning(f"**Term:** {data['term']}")
            st.warning(f"**Session:** {data['session']}")
            
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("Cancel", key="cancel_delete_term", use_container_width=True):
                    st.session_state.show_delete_term_dialog = False
                    st.session_state.term_to_delete = None
                    st.rerun()
            
            with col2:
                if st.button("🗑️ Delete", key="confirm_delete_term", type="primary", use_container_width=True):
                    if delete_next_term_info(data["term"], data["session"]):
                        st.success("✅ Information deleted successfully!")
                        st.session_state.show_delete_term_dialog = False
                        st.session_state.term_to_delete = None
                        st.rerun()
                    else:
                        st.error("❌ Failed to delete information.")
        
        show_delete_dialog()
    
    # ================================================================
    # TAB 3 — QUICK VIEW
    # ================================================================
    with tab3:
        st.subheader("Quick View - Next Term Information")
        
        # Get all classes
        classes = get_all_classes(user_id, role)
        
        if not classes:
            st.warning("⚠️ No classes available.")
            return
        
        # Class selection
        selected = render_persistent_class_selector(
            classes,
            widget_key="quick_view_class"
        )
        
        if not selected:
            st.info("Please select a term and session to view information.")
            return
        
        term = selected['term']
        session = selected['session']
        
        info = get_next_term_info(term, session)
        
        if not info:
            st.info(f"ℹ️ No information found for **{term}** - **{session}**")
            st.markdown("Go to the **Add/Edit Information** tab to create it.")
        else:
            # Display information in a nice format
            st.success(f"### 📅 {term} - {session}")
            
            # Important Dates Section
            with st.expander("📅 Important Dates", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    if info[3]:
                        st.markdown(f"**Next Term Begins:** {info[3]}")
                    if info[4]:
                        st.markdown(f"**Next Term Ends:** {info[4]}")
                    if info[5]:
                        st.markdown(f"**Vacation Starts:** {info[5]}")
                    if info[6]:
                        st.markdown(f"**Vacation Ends:** {info[6]}")
                
                with col2:
                    if info[7]:
                        st.markdown(f"**Fees Due Date:** {info[7]}")
                    if info[8]:
                        st.markdown(f"**Registration Starts:** {info[8]}")
                    if info[9]:
                        st.markdown(f"**Registration Ends:** {info[9]}")
            
            # School Timings
            if info[10] or info[11] or info[12]:
                with st.expander("⏰ School Timings"):
                    if info[10]:
                        st.markdown(f"**School Hours:** {info[10]}")
                    if info[11]:
                        st.markdown(f"**Assembly Time:** {info[11]}")
                    if info[12]:
                        st.markdown(f"**Closing Time:** {info[12]}")
            
            # Special Events
            if info[20] or info[21] or info[15]:
                with st.expander("🎉 Special Events"):
                    if info[20]:
                        st.markdown(f"**Sports Day:** {info[20]}")
                    if info[21]:
                        st.markdown(f"**Cultural Day:** {info[21]}")
                    if info[15]:
                        st.markdown("**Events Schedule:**")
                        st.info(info[15])
            
            # Academic Information
            if info[13] or info[14] or info[16] or info[17]:
                with st.expander("📚 Academic Information"):
                    if info[13]:
                        st.markdown("**Important Dates:**")
                        st.info(info[13])
                    if info[14]:
                        st.markdown("**Holidays:**")
                        st.info(info[14])
                    if info[16]:
                        st.markdown("**Uniform Requirements:**")
                        st.info(info[16])
                    if info[17]:
                        st.markdown("**Required Books/Materials:**")
                        st.info(info[17])
            
            # Logistics & Facilities
            if info[29] or info[30] or info[31]:
                with st.expander("🚌 Logistics & Facilities"):
                    if info[29]:
                        st.markdown("**Bus Schedule:**")
                        st.info(info[29])
                    if info[30]:
                        st.markdown("**Cafeteria Information:**")
                        st.info(info[30])
                    if info[31]:
                        st.markdown("**Library Hours:**")
                        st.info(info[31])
            
            # Health & Safety
            if info[22] or info[23]:
                with st.expander("🏥 Health & Safety"):
                    if info[23]:
                        st.markdown("**Health Requirements:**")
                        st.info(info[23])
                    if info[22]:
                        st.markdown("**Excursion Information:**")
                        st.info(info[22])
            
            # Messages
            if info[27] or info[28]:
                with st.expander("💬 Messages", expanded=True):
                    if info[27]:
                        st.markdown("**Principal's Message:**")
                        st.info(info[27])
                    if info[28]:
                        st.markdown("**Special Instructions:**")
                        st.warning(info[28])
            
            # Contact Information
            if info[24] or info[25] or info[26]:
                with st.expander("📞 Contact Information"):
                    if info[24]:
                        st.markdown(f"**Contact Person:** {info[24]}")
                    if info[25]:
                        st.markdown(f"**Email:** {info[25]}")
                    if info[26]:
                        st.markdown(f"**Phone:** {info[26]}")
            
            # Special dates
            if info[18] or info[19]:
                with st.expander("📆 Special Dates"):
                    if info[18]:
                        st.markdown(f"**PTA Meeting:** {info[18]}")
                    if info[19]:
                        st.markdown(f"**Visiting Day:** {info[19]}")