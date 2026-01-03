# app_sections/user_profile.py

import streamlit as st
import logging

logger = logging.getLogger(__name__)
 
def create_user_info_page(role: str, username: str):
    """Create a user info display page"""
    def user_info_display():
        # Format role display
        if role is None:
            role_display = "Teacher (No Assignment)"
        elif role in ["admin", "superadmin"]:
            role_display = role.replace('_', ' ').title()
        else:
            role_display = role.replace('_', ' ').title()
        
        login_time = st.session_state.get('login_time', 'Unknown')
        
        # Display user information with nice formatting
        st.markdown("""
        <style>
            .user-profile-card {
                background: linear-gradient(135deg, #2E8B57 0%, #228B22 100%);
                padding: 25px;
                border-radius: 15px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                max-width: 400px !important;
                margin: auto;
            }
            .profile-header {
                text-align: center;
                color: white;
                margin-bottom: 20px;
            }
            .profile-avatar {
                font-size: 60px;
                margin-bottom: 10px;
            }
            .profile-name {
                font-size: 24px;
                font-weight: bold;
                margin-bottom: 5px;
            }
            .profile-role {
                font-size: 14px;
                opacity: 0.9;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .profile-details {
                background: rgba(255, 255, 255, 0.1);
                padding: 15px;
                border-radius: 10px;
                margin-top: 15px;
            }
            .profile-detail-item {
                display: flex;
                justify-content: space-between;
                padding: 8px 0;
                border-bottom: 1px solid rgba(255, 255, 255, 0.2);
                color: white;
            }
            .profile-detail-item:last-child {
                border-bottom: none;
            }
            .detail-label {
                font-weight: 600;
                opacity: 0.8;
            }
            .detail-value {
                font-weight: 400;
            }
        </style>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="user-profile-card">
            <div class="profile-header">
                <div class="profile-avatar">👤</div>
                <div class="profile-name">{username.title()}</div>
                <div class="profile-role">{role_display}</div>
            </div>
            <div class="profile-details">
                <div class="profile-detail-item">
                    <span class="detail-label">🕐 Login Time:</span>
                    <span class="detail-value">{login_time}</span>
                </div>
                <div class="profile-detail-item">
                    <span class="detail-label">📊 Status:</span>
                    <span class="detail-value">Active</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("  ")
        
        # Quick actions
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Refresh", use_container_width=True, type="secondary"):
                st.rerun()
        with col2:
            if st.button("ℹ️ Help", use_container_width=True, type="secondary"):
                st.info("Contact your administrator for assistance.")
    
    return user_info_display


def get_role_navigation_config(role: str):
    """
    Get navigation configuration for a specific role
    Returns dict of sections with their pages
    """
    # Import functions
    from app_sections import (
        manage_comments, manage_classes, register_students, manage_subjects,
        enter_scores, view_broadsheet, generate_reports, system_dashboard,
        admin_panel, manage_comment_templates, next_term_info
    )
    from auth.assignment_selection import select_assignment
    
    # Define navigation configurations for each role
    role_configs = {
        "superadmin": {
            "Admin Interface": [
                ("System Dashboard", ":material/dashboard:", system_dashboard.system_dashboard, True),
                ("Admin Panel", ":material/admin_panel_settings:", admin_panel.admin_panel, False),
                ("Next Term Info", ":material/event:", next_term_info.next_term_info, False),
                ("Comments Template", ":material/comment:", manage_comment_templates.manage_comment_templates, False),
            ],
            "Academic Management": [
                ("Manage Classes", ":material/school:", manage_classes.create_class_section, False),
                ("Register Students", ":material/group_add:", register_students.register_students, False),
                ("Manage Subjects", ":material/book:", manage_subjects.add_subjects, False),
            ],
            "Assessment & Reports": [
                ("Enter Scores", ":material/edit_note:", enter_scores.enter_scores, False),
                ("Manage Comments", ":material/rate_review:", manage_comments.manage_comments, False),
                ("View Broadsheet", ":material/table_chart:", view_broadsheet.generate_broadsheet, False),
                ("Generate Reports", ":material/description:", generate_reports.report_card_section, False),
            ]
        },
        "admin": {
            "Admin Interface": [
                ("Admin Panel", ":material/admin_panel_settings:", admin_panel.admin_panel, True),
                ("Next Term Info", ":material/event:", next_term_info.next_term_info, False),
                ("Comments Template", ":material/comment:", manage_comment_templates.manage_comment_templates, False),
            ],
            "Academic Management": [
                ("Manage Classes", ":material/school:", manage_classes.create_class_section, False),
                ("Register Students", ":material/group_add:", register_students.register_students, False),
                ("Manage Subjects", ":material/book:", manage_subjects.add_subjects, False),
            ],
            "Assessment & Reports": [
                ("Enter Scores", ":material/edit_note:", enter_scores.enter_scores, False),
                ("Manage Comments", ":material/rate_review:", manage_comments.manage_comments, False),
                ("View Broadsheet", ":material/table_chart:", view_broadsheet.generate_broadsheet, False),
                ("Generate Reports", ":material/description:", generate_reports.report_card_section, False),
            ]
        },
        "class_teacher": {
            "Class Management": [
                ("Register Students", ":material/group_add:", register_students.register_students, True),
                ("Manage Subjects", ":material/book:", manage_subjects.add_subjects, False),
            ],
            "Assessment & Reports": [
                ("Manage Comments", ":material/rate_review:", manage_comments.manage_comments, False),
                ("View Broadsheet", ":material/table_chart:", view_broadsheet.generate_broadsheet, False),
                ("Generate Reports", ":material/description:", generate_reports.report_card_section, False),
            ],
            "Assignment": [
                ("Change Assignment", ":material/swap_horiz:", select_assignment, False),
            ]
        },
        "subject_teacher": {
            "Assessment & Reports": [
                ("Enter Scores", ":material/edit_note:", enter_scores.enter_scores, True),
                ("View Broadsheet", ":material/table_chart:", view_broadsheet.generate_broadsheet, False),
            ],
            "Assignment": [
                ("Change Assignment", ":material/swap_horiz:", select_assignment, False),
            ]
        }
    }
    
    return role_configs.get(role, {})


def get_navigation_options(role: str, username: str) -> dict:
    """
    Get navigation options organized by sections based on user role
    NOW INCLUDES USER INFO AS FIRST SECTION
    
    Returns:
        Dict with section names as keys and list of page configs as values
    """
    try:
        # Create user info section (always first)
        user_info_section = {
            "👤 User Profile": [
                {
                    "title": "My Profile",
                    "icon": ":material/account_circle:",
                    "function": create_user_info_page(role, username),
                    "default": False
                }
            ]
        }
        
        # Get role-specific navigation
        role_config = get_role_navigation_config(role)
        
        # Convert role config to navigation structure
        navigation_structure = {}
        for section_name, pages in role_config.items():
            navigation_structure[section_name] = [
                {
                    "title": title,
                    "icon": icon,
                    "function": function,
                    "default": is_default
                }
                for title, icon, function, is_default in pages
            ]
        
        # Combine user info with role navigation
        return {**user_info_section, **navigation_structure}
        
    except ImportError as e:
        logger.error(f"Error importing navigation modules: {e}")
        # Return minimal navigation with user info
        return {
            **user_info_section,
            "System": [
                {
                    "title": "Dashboard",
                    "icon": ":material/dashboard:",
                    "function": lambda: st.error("Navigation modules not available"),
                    "default": True
                }
            ]
        }