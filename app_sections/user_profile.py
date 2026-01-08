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
        
        # # Quick actions
        # col1, col2 = st.columns(2)
        # with col1:
        #     if st.button("🔄 Refresh", use_container_width=True, type="secondary"):
        #         st.rerun()
        # with col2:
        #     if st.button("ℹ️ Help", use_container_width=True, type="secondary"):
        #         st.info("Contact your administrator for assistance.")
    
    return user_info_display
