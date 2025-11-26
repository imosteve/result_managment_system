# app_sections/system_dashboard.py

import streamlit as st
import math
import sqlite3
import os
import shutil
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from database import (
    get_database_stats, get_all_users, get_all_classes,
    get_classes_summary, database_health_check, backup_database,
    get_connection, create_performance_indexes, get_user_role
)
from utils import inject_login_css, render_page_header, format_ordinal, inject_metric_css
from config import DB_CONFIG, APP_CONFIG
from util.paginators import streamlit_paginator

logger = logging.getLogger(__name__)

def system_dashboard():
    """Comprehensive system dashboard for superadmin operations"""
    
    # Authentication check
    if not st.session_state.get("authenticated", False):
        st.error("⚠️ Please log in first.")
        st.switch_page("main.py")
        return

    # Role check - Only superadmin can access
    user_id = st.session_state.get('user_id', None)
    admin_role = get_user_role(user_id)
    
    if admin_role != "superadmin":
        st.error("⚠️ Access denied. Superadmin access only.")
        st.switch_page("main.py")
        return

    # Page configuration
    st.set_page_config(page_title="System Dashboard", layout="wide")
    render_page_header("🔧 System Dashboard")
    
    # Get system statistics
    stats = get_database_stats()
    
    # Display key metrics
    st.subheader("📊 System Overview")
    inject_login_css("templates/metrics_styles.css")
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.markdown(f"<div class='custom-metric'><div class='label'>Total Users</div><div class='value'>{stats['users']}</div></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='custom-metric'><div class='label'>Teachers</div><div class='value'>{stats['teachers']}</div></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='custom-metric'><div class='label'>Classes</div><div class='value'>{stats['classes']}</div></div>", unsafe_allow_html=True)
    with col4:
        st.markdown(f"<div class='custom-metric'><div class='label'>Students</div><div class='value'>{stats['students']}</div></div>", unsafe_allow_html=True)
    with col5:
        st.markdown(f"<div class='custom-metric'><div class='label'>Subjects</div><div class='value'>{stats['subjects']}</div></div>", unsafe_allow_html=True)
    with col6:
        st.markdown(f"<div class='custom-metric'><div class='label'>Score Records</div><div class='value'>{stats['scores']}</div></div>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Tab-based interface for different operations
    inject_login_css("templates/tabs_styles.css")
    
    tabs = st.tabs([
        "🏥 System Health",
        "💾 Database Management",
        "📊 Analytics & Reports",
        "🔧 Maintenance",
        "🔒 Security & Logs",
        "⚙️ System Settings"
    ])
    
    # TAB 1: System Health
    with tabs[0]:
        render_system_health_tab()
    
    # TAB 2: Database Management
    with tabs[1]:
        render_database_management_tab()
    
    # TAB 3: Analytics & Reports
    with tabs[2]:
        render_analytics_tab(stats)
    
    # TAB 4: Maintenance
    with tabs[3]:
        render_maintenance_tab()
    
    # TAB 5: Security & Logs
    with tabs[4]:
        render_security_logs_tab()
    
    # TAB 6: System Settings
    with tabs[5]:
        render_system_settings_tab()


def render_system_health_tab():
    """Render system health monitoring tab"""
    st.subheader("🏥 System Health Check")
    
    col1, col2 = st.columns([3, 1])
    
    with col2:
        if st.button("🔄 Run Health Check", type="primary", use_container_width=True):
            with st.spinner("Running comprehensive health check..."):
                time.sleep(1)  # Simulate check time
                
                # Database health
                db_health = database_health_check()
                
                # File system check
                fs_health = check_file_system_health()
                
                # Memory check
                memory_health = check_memory_health()
                
                # Store results
                st.session_state.health_check_results = {
                    'database': db_health,
                    'filesystem': fs_health,
                    'memory': memory_health,
                    'timestamp': datetime.now()
                }
                st.rerun()
    
    with col1:
        if 'health_check_results' in st.session_state:
            results = st.session_state.health_check_results
            st.info(f"Last check: {results['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Display health check results
    if 'health_check_results' in st.session_state:
        results = st.session_state.health_check_results
        
        st.markdown("### Health Check Results")
        
        # Database Health
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("#### 🗄️ Database")
            db_status = results['database']['status']
            if db_status == 'healthy':
                st.success("✅ Database: Healthy")
            else:
                st.error(f"❌ Database: {db_status}")
            
            with st.expander("Database Details"):
                st.json(results['database'])
        
        with col2:
            st.markdown("#### 📁 File System")
            if results['filesystem']['status']:
                st.success("✅ File System: Healthy")
            else:
                st.error("❌ File System: Issues Detected")
            
            with st.expander("File System Details"):
                st.json(results['filesystem'])
        
        with col3:
            st.markdown("#### 💻 Memory")
            mem_status = results['memory']['status']
            if mem_status:
                st.success("✅ Memory: Normal")
            else:
                st.warning("⚠️ Memory: High Usage")
            
            with st.expander("Memory Details"):
                st.json(results['memory'])
        
        # Database Statistics
        st.markdown("---")
        st.markdown("### 📈 Database Statistics")
        
        db_stats = get_database_info()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Database Size", db_stats['size'])
        with col2:
            st.metric("Total Tables", db_stats['table_count'])
        with col3:
            st.metric("Total Records", db_stats['total_records'])
        with col4:
            st.metric("Last Backup", db_stats['last_backup'])


def render_database_management_tab():
    """Render database management tab"""
    st.subheader("💾 Database Management")
    
    # Backup Section
    st.markdown("#### 📦 Database Backup")
    col1, col2 = st.columns([2, 1], vertical_alignment="bottom")
    
    with col1:
        st.info("Create a backup of the current database. Backups are stored in the backups directory.")
        backup_name = st.text_input(
            "Backup Name (optional)",
            placeholder=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            key="backup_name_input"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 Create Backup", type="primary", use_container_width=True):
            create_database_backup(backup_name if backup_name else None)
    
    # List existing backups
    st.markdown("---")
    st.markdown("#### 📋 Existing Backups")
    
    backups = list_database_backups()
    
    if backups:
        backup_data = []
        for backup in backups:
            backup_data.append({
                "Filename": backup['name'],
                "Size": backup['size'],
                "Created": backup['created'],
                "Age": backup['age']
            })
        
        streamlit_paginator(backup_data, table_name="backups")
        
        # Initialize session state for confirmations
        if 'show_restore_confirm' not in st.session_state:
            st.session_state.show_restore_confirm = False
        if 'show_delete_backup_confirm' not in st.session_state:
            st.session_state.show_delete_backup_confirm = False
        if 'selected_restore_backup' not in st.session_state:
            st.session_state.selected_restore_backup = None
        if 'selected_delete_backup' not in st.session_state:
            st.session_state.selected_delete_backup = None
        
        # Restore functionality
        with st.expander("🔄 Restore from Backup"):
            st.warning("⚠️ **Warning**: Restoring will replace the current database. This action cannot be undone!")
            
            backup_files = [b['name'] for b in backups]
            selected_backup = st.selectbox("Select Backup to Restore", backup_files, key="restore_backup_select")
            
            if st.button("🔄 Restore Database", type="primary", key="restore_backup_button"):
                st.session_state.selected_restore_backup = selected_backup
                st.session_state.show_restore_confirm = True
                st.rerun()
        
        # Restore confirmation dialog
        if st.session_state.show_restore_confirm and st.session_state.selected_restore_backup:
            @st.dialog("⚠️ CRITICAL: Confirm Database Restore", width="large")
            def confirm_restore_backup():
                backup_name = st.session_state.selected_restore_backup
                
                st.markdown("### 🚨 CRITICAL OPERATION WARNING 🚨")
                st.markdown("---")
                st.error(f"**You are about to restore from backup:**")
                st.error(f"### 📁 {backup_name}")
                st.markdown("---")
                
                st.markdown("#### ⚠️ **This action will:**")
                st.warning("• **COMPLETELY REPLACE** the current database")
                st.warning("• **DELETE ALL CURRENT DATA** not in the backup")
                st.warning("• **CANNOT BE UNDONE** after confirmation")
                st.warning("• Affect all users immediately")
                st.warning("• Potentially cause data loss if backup is outdated")
                
                st.markdown("---")
                st.info("✅ A backup of the current database will be created automatically before restore")
                
                st.markdown("---")
                st.markdown("#### 🔐 Final Confirmation Required")
                
                confirm_text = st.text_input(
                    "Type **RESTORE DATABASE** to confirm (case-sensitive):",
                    key="restore_confirm_text",
                    placeholder="RESTORE DATABASE"
                )
                
                st.markdown("---")
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("🚫 Cancel", key="cancel_restore", type="secondary", use_container_width=True):
                        st.session_state.show_restore_confirm = False
                        st.session_state.selected_restore_backup = None
                        st.rerun()
                
                with col2:
                    if st.button("🔄 RESTORE DATABASE", key="confirm_restore", type="primary", use_container_width=True):
                        if confirm_text == "RESTORE DATABASE":
                            restore_database_from_backup(backup_name)
                            st.session_state.show_restore_confirm = False
                            st.session_state.selected_restore_backup = None
                        else:
                            st.error("❌ Incorrect confirmation text. Please type exactly: RESTORE DATABASE")
            
            confirm_restore_backup()
        
        # Delete backup functionality
        with st.expander("🗑️ Delete Backup"):
            backup_to_delete = st.selectbox("Select Backup to Delete", backup_files, key="delete_backup_select")
            
            if st.button("🗑️ Delete Selected Backup", type="primary", key="delete_backup_button"):
                st.session_state.selected_delete_backup = backup_to_delete
                st.session_state.show_delete_backup_confirm = True
                st.rerun()
        
        # Delete backup confirmation dialog
        if st.session_state.show_delete_backup_confirm and st.session_state.selected_delete_backup:
            @st.dialog("⚠️ Confirm Backup Deletion", width="small")
            def confirm_delete_backup():
                backup_name = st.session_state.selected_delete_backup
                
                st.markdown("### Are you sure you want to delete this backup?")
                st.error(f"**Backup File:** {backup_name}")
                st.markdown("---")
                
                st.warning("⚠️ **This action cannot be undone!**")
                st.warning("• Backup file will be permanently deleted")
                st.warning("• You cannot recover this backup after deletion")
                st.warning("• Make sure you have other backups if needed")
                
                st.markdown("---")
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("🚫 Cancel", key="cancel_delete_backup", type="secondary", use_container_width=True):
                        st.session_state.show_delete_backup_confirm = False
                        st.session_state.selected_delete_backup = None
                        st.rerun()
                
                with col2:
                    if st.button("🗑️ Delete Backup", key="confirm_delete_backup", type="primary", use_container_width=True):
                        delete_backup_file(backup_name)
                        st.session_state.show_delete_backup_confirm = False
                        st.session_state.selected_delete_backup = None
            
            confirm_delete_backup()
    else:
        st.info("No backups found. Create your first backup above.")
    
    # Database optimization
    st.markdown("---")
    st.markdown("#### ⚡ Database Optimization")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Rebuild database file to reclaim unused space and improve performance.
        st.markdown("**Vacuum Database**")
        st.info("Rebuild database file to improve performance.")
        if st.button("🧹 Vacuum Database", use_container_width=True):
            vacuum_database()
    
    with col2:
        st.markdown("**Analyze Database**")
        st.info("Update database statistics for better query optimization.")
        if st.button("📊 Analyze Database", use_container_width=True):
            analyze_database()
    
    # Create indexes
    st.markdown("---")
    if st.button("🔍 Create/Update Performance Indexes", use_container_width=False):
        create_indexes()


def render_analytics_tab(stats):
    """Render analytics and reports tab"""
    st.subheader("📊 Analytics & Reports")
    
    # User distribution
    st.markdown("#### 👥 User Distribution")
    
    users = get_all_users()
    user_roles = {'Superadmin': 0, 'Admin': 0, 'Teacher': 0}
    
    for user in users:
        role = user[3] if user[3] else 'Teacher'
        if role == 'superadmin':
            user_roles['Superadmin'] += 1
        elif role == 'admin':
            user_roles['Admin'] += 1
        else:
            user_roles['Teacher'] += 1
    
    # Inject custom CSS for metric styling
    inject_metric_css()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Superadmins", user_roles['Superadmin'])
    with col2:
        st.metric("Admins", user_roles['Admin'])
    with col3:
        st.metric("Teachers", user_roles['Teacher'])
    
    # Class distribution
    st.markdown("---")
    st.markdown("#### 🏫 Class Overview")
    
    class_summary = get_classes_summary()
    
    if class_summary:
        class_data = [
            {
                "Class": row[0],
                "Term": row[1],
                "Session": row[2],
                "Students": row[3],
                "Subjects": row[4],
                "Scores": row[5]
            }
            for row in class_summary
        ]

        # Pagination settings
        items_per_page = 10
        total_items = len(class_data)
        total_pages = math.ceil(total_items / items_per_page)

        # Page selector
        page = st.number_input(
            "Page", min_value=1, max_value=total_pages, step=1, value=1, key="page_selector"
        )

        # Slice data
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_data = class_data[start_idx:end_idx]

        # Display current page
        st.dataframe(page_data, width="stretch")

        st.caption(f"Showing {start_idx + 1} – {min(end_idx, total_items)} of {total_items} entries")

    else:
        st.info("No classes found in the system.")

    # Activity statistics
    st.markdown("---")
    st.markdown("#### 📈 Activity Statistics")
    
    activity_stats = get_activity_statistics()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Active Classes", activity_stats['active_classes'])
    with col2:
        st.metric("Active Students", activity_stats['active_students'])
    with col3:
        st.metric("Score Completion", f"{activity_stats['score_completion']}%")
    with col4:
        st.metric("Assignments", stats['assignments'])


def render_maintenance_tab():
    """Render maintenance operations tab"""
    st.subheader("🔧 Maintenance Operations")
    
    st.warning("⚠️ **Warning**: Maintenance operations can affect system performance. Use with caution.")
    
    # Clear cache
    st.markdown("#### 🗑️ Clear System Cache")
    st.info("Clear Streamlit cache and temporary files to free up memory.")
    
    if st.button("🗑️ Clear Cache", use_container_width=False):
        clear_system_cache()
    
    # Database integrity check
    st.markdown("---")
    st.markdown("#### 🔍 Database Integrity Check")
    st.info("Check database for corruption or inconsistencies.")
    
    if st.button("🔍 Check Database Integrity", use_container_width=False):
        run_integrity_check()
    
    # Clean up orphaned records
    st.markdown("---")
    st.markdown("#### 🧹 Clean Orphaned Records")
    st.info("Remove records that reference deleted parents (should be automatic with CASCADE).")
    
    if st.button("🧹 Clean Orphaned Records", use_container_width=False):
        clean_orphaned_records()
    
    # System logs cleanup
    st.markdown("---")
    st.markdown("#### 📝 Log Management")
    
    col1, col2 = st.columns(2, vertical_alignment="bottom")
    
    with col1:
        log_info = get_log_files_info()
        st.info(f"**Total Log Size**: {log_info['total_size']}")
        st.info(f"**Log Files**: {log_info['file_count']}")
    
    with col2:
        days_to_keep = st.number_input("Keep logs from last (days)", min_value=1, max_value=365, value=30)
        if st.button("🗑️ Clean Old Logs"):
            clean_old_logs(days_to_keep)

def render_security_logs_tab():
    """Render security and logs tab"""
    st.subheader("🔒 Security & System Logs")
    
    # Display recent logs
    st.markdown("#### 📋 Recent System Logs")
    
    log_level = st.selectbox("Filter by Level", ["ALL", "INFO", "WARNING", "ERROR", "CRITICAL"])
    
    logs = read_recent_logs(log_level, limit=100)
    
    if logs:
        for log in logs:
            if "ERROR" in log or "CRITICAL" in log:
                st.error(log)
            elif "WARNING" in log:
                st.warning(log)
            else:
                st.info(log)
    else:
        st.info("No logs found.")
    
    # Download logs
    st.markdown("---")
    if st.button("⬇️ Download Full Logs"):
        download_logs()


def render_system_settings_tab():
    """Render system settings tab"""
    st.subheader("⚙️ System Settings")
    
    st.markdown("#### 🎨 Application Settings")
    
    # Display current settings
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**School Information**")
        st.info(f"**Name**: {APP_CONFIG['school_name']}")
        st.info(f"**App Version**: {APP_CONFIG['version']}")
        st.info(f"**Session Timeout**: {APP_CONFIG['session_timeout']} seconds")
    
    with col2:
        st.markdown("**Database Information**")
        st.info(f"**Path**: {DB_CONFIG['path']}")
        st.info(f"**Backup Dir**: {DB_CONFIG['backup_dir']}")
        st.info(f"**Foreign Keys**: {DB_CONFIG['enable_foreign_keys']}")
    
    # System information
    st.markdown("---")
    st.markdown("#### 💻 System Information")
    
    sys_info = get_system_information()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Python Version", sys_info['python_version'])
    with col2:
        st.metric("Streamlit Version", sys_info['streamlit_version'])
    with col3:
        st.metric("SQLite Version", sys_info['sqlite_version'])


# ==================== HELPER FUNCTIONS ====================

def check_file_system_health():
    """Check file system health"""
    try:
        required_dirs = ['logs', 'data', 'templates', DB_CONFIG['backup_dir']]
        missing_dirs = []
        writable_dirs = []
        
        for directory in required_dirs:
            if not os.path.exists(directory):
                missing_dirs.append(directory)
            else:
                # Check if writable
                test_file = os.path.join(directory, '.test_write')
                try:
                    with open(test_file, 'w') as f:
                        f.write('test')
                    os.remove(test_file)
                    writable_dirs.append(directory)
                except:
                    pass
        
        return {
            'status': len(missing_dirs) == 0,
            'required_dirs': required_dirs,
            'missing_dirs': missing_dirs,
            'writable_dirs': writable_dirs
        }
    except Exception as e:
        logger.error(f"File system check failed: {e}")
        return {'status': False, 'error': str(e)}


def check_memory_health():
    """Check memory usage"""
    try:
        import psutil
        memory = psutil.virtual_memory()
        return {
            'status': memory.percent < 80,
            'percent': f"{memory.percent}%",
            'available': f"{memory.available / (1024**3):.2f} GB",
            'total': f"{memory.total / (1024**3):.2f} GB"
        }
    except ImportError:
        return {
            'status': True,
            'message': "psutil not available - cannot check memory"
        }


def get_database_info():
    """Get database file information"""
    try:
        db_path = DB_CONFIG['path']
        if os.path.exists(db_path):
            size = os.path.getsize(db_path)
            size_mb = size / (1024 * 1024)
            
            # Get table count
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            
            # Get total records
            stats = get_database_stats()
            total_records = sum([
                stats['classes'], stats['students'], 
                stats['subjects'], stats['scores'],
                stats['users'], stats['assignments']
            ])
            
            conn.close()
            
            # Get last backup
            backups = list_database_backups()
            last_backup = backups[0]['created'] if backups else 'Never'
            
            return {
                'size': f"{size_mb:.2f} MB",
                'table_count': table_count,
                'total_records': total_records,
                'last_backup': last_backup
            }
        else:
            return {
                'size': 'N/A',
                'table_count': 0,
                'total_records': 0,
                'last_backup': 'Never'
            }
    except Exception as e:
        logger.error(f"Error getting database info: {e}")
        return {
            'size': 'Error',
            'table_count': 0,
            'total_records': 0,
            'last_backup': 'Error'
        }


def create_database_backup(backup_name=None):
    """Create database backup"""
    try:
        os.makedirs(DB_CONFIG['backup_dir'], exist_ok=True)
        
        if not backup_name:
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        elif not backup_name.endswith('.db'):
            backup_name += '.db'
        
        backup_path = os.path.join(DB_CONFIG['backup_dir'], backup_name)
        
        with st.spinner("Creating backup..."):
            success = backup_database(backup_path)
        
        if success:
            st.success(f"✅ Backup created successfully: {backup_name}")
            time.sleep(1)
            st.rerun()
        else:
            st.error("❌ Failed to create backup")
    except Exception as e:
        logger.error(f"Backup creation failed: {e}")
        st.error(f"❌ Error creating backup: {str(e)}")


def list_database_backups():
    """List all database backups"""
    try:
        backup_dir = DB_CONFIG['backup_dir']
        if not os.path.exists(backup_dir):
            return []
        
        backups = []
        for file in os.listdir(backup_dir):
            if file.endswith('.db'):
                file_path = os.path.join(backup_dir, file)
                size = os.path.getsize(file_path)
                created = datetime.fromtimestamp(os.path.getctime(file_path))
                age = datetime.now() - created
                
                backups.append({
                    'name': file,
                    'path': file_path,
                    'size': f"{size / (1024 * 1024):.2f} MB",
                    'created': created.strftime('%Y-%m-%d %H:%M:%S'),
                    'age': f"{age.days} days ago" if age.days > 0 else "Today"
                })
        
        # Sort by creation time (newest first)
        backups.sort(key=lambda x: x['created'], reverse=True)
        return backups
    except Exception as e:
        logger.error(f"Error listing backups: {e}")
        return []


def restore_database_from_backup(backup_name):
    """Restore database from backup"""
    try:
        backup_path = os.path.join(DB_CONFIG['backup_dir'], backup_name)
        
        if not os.path.exists(backup_path):
            st.error("❌ Backup file not found")
            return
        
        with st.spinner("Restoring database..."):
            # Create backup of current database first
            current_backup = f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            backup_database(os.path.join(DB_CONFIG['backup_dir'], current_backup))
            
            # Restore from selected backup
            shutil.copy2(backup_path, DB_CONFIG['path'])
            
            time.sleep(1)
        
        st.success(f"✅ Database restored from {backup_name}")
        st.info(f"Previous database backed up as: {current_backup}")
        time.sleep(2)
        st.rerun()
    except Exception as e:
        logger.error(f"Database restore failed: {e}")
        st.error(f"❌ Error restoring database: {str(e)}")


def delete_backup_file(backup_name):
    """Delete a backup file"""
    try:
        backup_path = os.path.join(DB_CONFIG['backup_dir'], backup_name)
        
        if os.path.exists(backup_path):
            os.remove(backup_path)
            st.success(f"✅ Backup deleted: {backup_name}")
            time.sleep(1)
            st.rerun()
        else:
            st.error("❌ Backup file not found")
    except Exception as e:
        logger.error(f"Backup deletion failed: {e}")
        st.error(f"❌ Error deleting backup: {str(e)}")


def vacuum_database():
    """Vacuum database to reclaim space"""
    try:
        with st.spinner("Vacuuming database..."):
            conn = get_connection()
            conn.execute("VACUUM")
            conn.close()
            time.sleep(1)
        
        st.success("✅ Database vacuumed successfully")
    except Exception as e:
        logger.error(f"Database vacuum failed: {e}")
        st.error(f"❌ Error vacuuming database: {str(e)}")


def analyze_database():
    """Analyze database for optimization"""
    try:
        with st.spinner("Analyzing database..."):
            conn = get_connection()
            conn.execute("ANALYZE")
            conn.close()
            time.sleep(1)
        
        st.success("✅ Database analyzed successfully")
    except Exception as e:
        logger.error(f"Database analysis failed: {e}")
        st.error(f"❌ Error analyzing database: {str(e)}")


def create_indexes():
    """Create performance indexes"""
    try:
        with st.spinner("Creating indexes..."):
            success = create_performance_indexes()
            time.sleep(1)
        
        if success:
            st.success("✅ Performance indexes created successfully")
        else:
            st.error("❌ Failed to create indexes")
    except Exception as e:
        logger.error(f"Index creation failed: {e}")
        st.error(f"❌ Error creating indexes: {str(e)}")


def get_activity_statistics():
    """Get activity statistics"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Active classes (with at least one student)
        cursor.execute("""
            SELECT COUNT(DISTINCT c.name || c.term || c.session)
            FROM classes c
            JOIN students s ON c.name = s.class_name 
                AND c.term = s.term AND c.session = s.session
        """)
        active_classes = cursor.fetchone()[0]
        
        # Active students (with at least one score)
        cursor.execute("""
            SELECT COUNT(DISTINCT student_name || class_name || term || session)
            FROM scores
        """)
        active_students = cursor.fetchone()[0]
        
        # Score completion percentage
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT s.name || sub.name) as expected,
                COUNT(DISTINCT sc.student_name || sc.subject_name) as actual
            FROM students s
            CROSS JOIN subjects sub ON s.class_name = sub.class_name 
                AND s.term = sub.term AND s.session = sub.session
            LEFT JOIN scores sc ON s.name = sc.student_name 
                AND sub.name = sc.subject_name
                AND s.class_name = sc.class_name
                AND s.term = sc.term 
                AND s.session = sc.session
        """)
        result = cursor.fetchone()
        expected, actual = result[0], result[1]
        score_completion = int((actual / expected * 100) if expected > 0 else 0)
        
        conn.close()
        
        return {
            'active_classes': active_classes,
            'active_students': active_students,
            'score_completion': score_completion
        }
    except Exception as e:
        logger.error(f"Error getting activity statistics: {e}")
        return {
            'active_classes': 0,
            'active_students': 0,
            'score_completion': 0
        }


def clear_system_cache():
    """Clear Streamlit cache"""
    try:
        st.cache_data.clear()
        st.cache_resource.clear()
        st.success("✅ System cache cleared successfully")
    except Exception as e:
        logger.error(f"Cache clearing failed: {e}")
        st.error(f"❌ Error clearing cache: {str(e)}")


def run_integrity_check():
    """Run database integrity check"""
    try:
        with st.spinner("Checking database integrity..."):
            health = database_health_check()
            time.sleep(1)
        
        if health['status'] == 'healthy':
            st.success("✅ Database integrity check passed")
            st.json(health)
        else:
            st.error("❌ Database integrity issues detected")
            st.json(health)
    except Exception as e:
        logger.error(f"Integrity check failed: {e}")
        st.error(f"❌ Error running integrity check: {str(e)}")


def clean_orphaned_records():
    """Clean orphaned records (should be automatic with CASCADE)"""
    try:
        with st.spinner("Checking for orphaned records..."):
            conn = get_connection()
            cursor = conn.cursor()
            
            # This is mostly informational since CASCADE should handle it
            cursor.execute("PRAGMA foreign_key_check")
            violations = cursor.fetchall()
            
            conn.close()
            time.sleep(1)
        
        if not violations:
            st.success("✅ No orphaned records found")
        else:
            st.warning(f"⚠️ Found {len(violations)} foreign key violations")
            st.json(violations)
    except Exception as e:
        logger.error(f"Orphan cleanup failed: {e}")
        st.error(f"❌ Error cleaning orphaned records: {str(e)}")


def get_log_files_info():
    """Get information about log files"""
    try:
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            return {'total_size': '0 MB', 'file_count': 0}
        
        total_size = 0
        file_count = 0
        
        for file in os.listdir(log_dir):
            if file.endswith('.log'):
                file_path = os.path.join(log_dir, file)
                total_size += os.path.getsize(file_path)
                file_count += 1
        
        return {
            'total_size': f"{total_size / (1024 * 1024):.2f} MB",
            'file_count': file_count
        }
    except Exception as e:
        logger.error(f"Error getting log info: {e}")
        return {'total_size': '0 MB', 'file_count': 0}


def clean_old_logs(days_to_keep):
    """Clean logs older than specified days"""
    try:
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            st.info("No logs directory found")
            return
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        deleted_count = 0
        
        with st.spinner(f"Cleaning logs older than {days_to_keep} days..."):
            for file in os.listdir(log_dir):
                if file.endswith('.log'):
                    file_path = os.path.join(log_dir, file)
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    if file_time < cutoff_date:
                        os.remove(file_path)
                        deleted_count += 1
            
            time.sleep(1)
        
        st.success(f"✅ Cleaned {deleted_count} old log files")
    except Exception as e:
        logger.error(f"Log cleanup failed: {e}")
        st.error(f"❌ Error cleaning logs: {str(e)}")


def read_recent_logs(level="ALL", limit=100):
    """Read recent log entries"""
    try:
        log_file = 'logs/app.log'
        if not os.path.exists(log_file):
            return []
        
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Get last 'limit' lines
        recent_lines = lines[-limit:]
        
        # Filter by level
        if level != "ALL":
            recent_lines = [line for line in recent_lines if level in line]
        
        return recent_lines
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        return []


def download_logs():
    """Download full log file"""
    try:
        log_file = 'logs/app.log'
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                log_content = f.read()
            
            st.download_button(
                label="⬇️ Download Logs",
                data=log_content,
                file_name=f"system_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
                mime="text/plain"
            )
        else:
            st.error("Log file not found")
    except Exception as e:
        logger.error(f"Error downloading logs: {e}")
        st.error(f"❌ Error downloading logs: {str(e)}")


def get_system_information():
    """Get system information"""
    try:
        import sys
        import streamlit
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT sqlite_version()")
        sqlite_version = cursor.fetchone()[0]
        conn.close()
        
        return {
            'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            'streamlit_version': streamlit.__version__,
            'sqlite_version': sqlite_version
        }
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return {
            'python_version': 'Unknown',
            'streamlit_version': 'Unknown',
            'sqlite_version': 'Unknown'
        }


if __name__ == "__main__":
    system_dashboard()