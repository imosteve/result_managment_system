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
from database_school import (
    get_database_stats, get_all_users, get_all_classes,
    get_classes_summary, database_health_check, backup_database,
    get_connection, create_performance_indexes, get_user_role
)
from main_utils import inject_login_css, render_page_header, format_ordinal, inject_metric_css
from config import DB_CONFIG, APP_CONFIG
from utils.paginators import streamlit_paginator

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
    
    # ── CHANGE: get_user_role() now reads directly from users.role ──
    if admin_role != "superadmin":
        st.error("⚠️ Access denied. Superadmin access only.")
        st.switch_page("main.py")
        return

    # Page configuration
    st.set_page_config(page_title="System Dashboard", layout="wide")
    
    inject_login_css("templates/tabs_styles.css")

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
    
    
    tabs = st.tabs([
        "🏥 System Health",
        "💾 Database Management",
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
    
    # TAB 3: Maintenance
    with tabs[2]:
        render_maintenance_tab()
    
    # TAB 4: Security & Logs
    with tabs[3]:
        render_security_logs_tab()
    
    # TAB 5: System Settings
    with tabs[4]:
        render_system_settings_tab()


def render_system_health_tab():
    """Render system health monitoring tab"""
    st.subheader("🏥 System Health Check")
    
    col1, col2 = st.columns([3, 1])
    
    with col2:
        if st.button("🔄 Run Health Check", type="primary", width='stretch'):
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
    # Backup Section
    st.markdown("#### 📦 Database Backup", 
                help="Create a backup of the current database. Backups are stored in the backups directory."
                )
    col1, col2, download = st.columns([2, 1, 1], vertical_alignment="top")
    
    with col1:
        backup_name = st.text_input(
            "Backup Name (optional)",
            placeholder=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            key="backup_name_input"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 Create Backup", type="primary", width='stretch'):
            create_database_backup(backup_name if backup_name else None)
    
    with download:
        st.markdown("<br>", unsafe_allow_html=True)
        school_code = st.session_state.school_code
        
        # Read the actual file as bytes
        _db_path = st.session_state.get("school_db_path")
        if not _db_path:
            st.error("⚠️ School database path not found in session. Please log in again.")
            return
        with open(_db_path, "rb") as f:
            db_data = f.read()

        st.download_button(
            label="Download DB",
            data=db_data,
            file_name=f"{school_code}_database.db",
            mime="application/octet-stream",
            use_container_width=True
    )
    
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
        
        if len(backup_data) > 0:
            st.dataframe(
                backup_data, 
                width="stretch", 
                hide_index=True
                )
        
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
                    if st.button("🚫 Cancel", key="cancel_restore", type="secondary", width='stretch'):
                        st.session_state.show_restore_confirm = False
                        st.session_state.selected_restore_backup = None
                        st.rerun()
                
                with col2:
                    if st.button("🔄 RESTORE DATABASE", key="confirm_restore", type="primary", width='stretch'):
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
                    if st.button("🚫 Cancel", key="cancel_delete_backup", type="secondary", width='stretch'):
                        st.session_state.show_delete_backup_confirm = False
                        st.session_state.selected_delete_backup = None
                        st.rerun()
                
                with col2:
                    if st.button("🗑️ Delete Backup", key="confirm_delete_backup", type="primary", width='stretch'):
                        delete_backup_file(backup_name)
                        st.session_state.show_delete_backup_confirm = False
                        st.session_state.selected_delete_backup = None
                        st.rerun()
            
            confirm_delete_backup()
    else:
        st.info("No backups found. Create your first backup above.")
    
    # Database optimization
    st.markdown("---")
    st.markdown("#### ⚡ Database Optimization")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Vacuum Database**", help="Rebuild the database file to reclaim unused space and improve performance. This can help reduce file size and optimize query speed.")
        if st.button("🧹 Vacuum Database", width=200):
            vacuum_database()
    
    with col2:
        st.markdown("**Analyze Database**", help="Update database statistics for better query optimization.")
        if st.button("📊 Analyze Database", width=200):
            analyze_database()
    
    with col3:
        st.markdown("**Performance Indexes**", help="Create or update indexes on key columns to improve query performance. This can speed up data retrieval but may take time on large datasets.")
        if st.button("🔍 Create/Update PI", width=200):
            create_indexes()


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

    log_info = get_log_files_info()
    col1, col2, col3 = st.columns(3)
    col1.metric("Log Files", log_info['file_count'])
    col2.metric("Total Size", log_info['total_size'])

    st.markdown("**Clean old log entries**")
    col_days, col_btn = st.columns([2, 1], vertical_alignment="bottom")
    with col_days:
        days_to_keep = st.number_input(
            "Keep entries from last N days",
            min_value=1, max_value=365, value=30,
            key="log_days_to_keep"
        )
    with col_btn:
        if st.button("🗑️ Clean Old Logs", key="clean_logs_btn"):
            clean_old_logs(days_to_keep)
            st.rerun()


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
    
    # Download logs — must be rendered unconditionally (not inside a button click)
    st.markdown("---")
    download_logs()


def render_system_settings_tab():
    """Render system settings tab"""
    st.subheader("⚙️ System Settings")
    
    st.markdown("#### 🎨 Application Settings")
    
    col1, col2 = st.columns(2)
    school_name = st.session_state.school_name
    with col1:
        st.markdown("**School Information**")
        st.info(f"**Name**: {school_name}")
        st.info(f"**App Version**: {APP_CONFIG['version']}")
        st.info(f"**Session Timeout**: {APP_CONFIG['session_timeout']} seconds")
    
    with col2:
        st.markdown("**Database Information**")
        st.info(f"**Path**: {DB_CONFIG['schools_dir']}")
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
        db_path = st.session_state.get("school_db_path")
        if os.path.exists(db_path):
            size = os.path.getsize(db_path)
            size_mb = size / (1024 * 1024)
            
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            
            stats = get_database_stats()
            total_records = sum([
                stats['classes'], stats['students'], 
                stats['subjects'], stats['scores'],
                stats['users'], stats['assignments']
            ])
            
            conn.close()
            
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


def create_database_backup(backup_name):
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
            current_backup = f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            backup_database(os.path.join(DB_CONFIG['backup_dir'], current_backup))
            
            shutil.copy2(backup_path, DB_CONFIG['schools_dir'])
            
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
    """
    Get activity statistics.

    Updated for new schema:
      - classes no longer has (name, term, session) — permanent class definitions only
      - students no longer carries class_name/term/session — enrollment lives in
        class_session_students → class_sessions
      - subjects no longer has term/session — keyed on (class_name, subject_name) only
      - scores retains denormalised (enrollment_id, subject_name, term) columns
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Active class-sessions: class_sessions that have at least one enrolled student
        cursor.execute("""
            SELECT COUNT(DISTINCT cs.id)
            FROM   class_sessions cs
            JOIN   class_session_students css ON css.class_session_id = cs.id
        """)
        active_classes = cursor.fetchone()[0]

        # Active students: unique enrolled students who have at least one score
        cursor.execute("""
            SELECT COUNT(DISTINCT enrollment_id)
            FROM   scores
        """)
        active_students = cursor.fetchone()[0]

        # Score completion: compare expected vs actual score rows for the active
        # session/term. Falls back to all-time totals if academic_settings not set.
        cursor.execute("""
            SELECT current_session, current_term
            FROM   academic_settings
            WHERE  id = 1
        """)
        settings_row = cursor.fetchone()

        if settings_row and settings_row[0]:
            current_session, current_term = settings_row

            # Expected = one score per (enrolled student × subject) in active session
            cursor.execute("""
                SELECT COUNT(*)
                FROM   class_session_students css
                JOIN   class_sessions cs  ON cs.id  = css.class_session_id
                JOIN   subjects       sub ON sub.class_name = cs.class_name
                WHERE  cs.session = ?
            """, (current_session,))
            expected = cursor.fetchone()[0]

            # Actual = score rows recorded for the active session + term
            cursor.execute("""
                SELECT COUNT(*)
                FROM   scores sc
                JOIN   class_session_students css ON css.id = sc.enrollment_id
                JOIN   class_sessions         cs  ON cs.id  = css.class_session_id
                WHERE  cs.session = ? AND sc.term = ?
            """, (current_session, current_term))
            actual = cursor.fetchone()[0]
        else:
            # No active session configured — count across everything
            cursor.execute("""
                SELECT COUNT(*)
                FROM   class_session_students css
                JOIN   class_sessions cs  ON cs.id  = css.class_session_id
                JOIN   subjects       sub ON sub.class_name = cs.class_name
            """)
            expected = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM scores")
            actual = cursor.fetchone()[0]

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
    """Clean orphaned records"""
    try:
        with st.spinner("Checking for orphaned records..."):
            conn = get_connection()
            cursor = conn.cursor()
            
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
    """Get information about all log files (app.log + rotated backups)"""
    try:
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            return {'total_size': '0 MB', 'file_count': 0, 'files': []}

        total_size = 0
        file_count = 0
        files = []

        for fname in os.listdir(log_dir):
            fpath = os.path.join(log_dir, fname)
            if not os.path.isfile(fpath):
                continue
            # Match app.log, app.log.1, app.log.2, error.log, error.log.1 …
            if fname.endswith('.log') or (('.log.' in fname) and fname.split('.log.')[1].isdigit()):
                size = os.path.getsize(fpath)
                total_size += size
                file_count += 1
                files.append({'name': fname, 'path': fpath, 'size': size})

        return {
            'total_size': f"{total_size / (1024 * 1024):.2f} MB",
            'file_count': file_count,
            'files': files,
        }
    except Exception as e:
        logger.error(f"Error getting log info: {e}")
        return {'total_size': '0 MB', 'file_count': 0, 'files': []}


def clean_old_logs(days_to_keep):
    """
    Remove log lines older than `days_to_keep` days from every log file.
    Rotated backup files (app.log.1, app.log.2 …) are deleted entirely if
    their newest line is older than the cutoff.
    The active app.log is rewritten keeping only recent lines.
    """
    import re
    # Matches the standard log timestamp prefix: 2026-03-12 16:24:24,276
    TS_RE = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')

    def line_datetime(line):
        m = TS_RE.match(line)
        if m:
            try:
                return datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass
        return None

    try:
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            st.info("No logs directory found.")
            return

        cutoff = datetime.now() - timedelta(days=days_to_keep)
        cleaned_files = 0
        removed_lines = 0
        deleted_files = 0

        with st.spinner(f"Cleaning log entries older than {days_to_keep} day(s)..."):
            for fname in sorted(os.listdir(log_dir)):
                fpath = os.path.join(log_dir, fname)
                if not os.path.isfile(fpath):
                    continue
                is_log = fname.endswith('.log') or (
                    '.log.' in fname and fname.split('.log.')[1].isdigit()
                )
                if not is_log:
                    continue

                try:
                    with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                        lines = f.readlines()
                except Exception:
                    continue

                if not lines:
                    continue

                # For rotated backups: if the NEWEST line is older than cutoff, delete entirely
                is_rotated = '.log.' in fname
                if is_rotated:
                    newest_dt = None
                    for line in reversed(lines):
                        dt = line_datetime(line)
                        if dt:
                            newest_dt = dt
                            break
                    if newest_dt is None or newest_dt < cutoff:
                        os.remove(fpath)
                        deleted_files += 1
                        continue

                # For active logs: keep only lines newer than cutoff
                # Lines with no timestamp are attached to the preceding entry — keep them
                kept = []
                current_keep = True
                for line in lines:
                    dt = line_datetime(line)
                    if dt is not None:
                        current_keep = dt >= cutoff
                    if current_keep:
                        kept.append(line)
                    else:
                        removed_lines += 1

                if len(kept) < len(lines):
                    with open(fpath, 'w', encoding='utf-8') as f:
                        f.writelines(kept)
                    cleaned_files += 1

            time.sleep(0.5)

        parts = []
        if removed_lines:
            parts.append(f"{removed_lines} old line(s) removed from {cleaned_files} file(s)")
        if deleted_files:
            parts.append(f"{deleted_files} rotated backup file(s) deleted")
        if parts:
            st.success("✅ " + "; ".join(parts))
        else:
            st.info(f"ℹ️ No log entries older than {days_to_keep} day(s) found.")

    except Exception as e:
        logger.error(f"Log cleanup failed: {e}")
        st.error(f"❌ Error cleaning logs: {str(e)}")


def read_recent_logs(level="ALL", limit=100):
    """Read recent log entries from app.log"""
    try:
        log_file = 'logs/app.log'
        if not os.path.exists(log_file):
            return []

        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        # Filter by level first, then take the last `limit` lines
        if level != "ALL":
            lines = [l for l in lines if level in l]

        return lines[-limit:]
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        return []


def get_log_download_data():
    """Return (content, filename) for the full log file, or (None, None) if unavailable."""
    try:
        log_file = 'logs/app.log'
        if not os.path.exists(log_file):
            return None, None
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        filename = f"system_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        return content, filename
    except Exception as e:
        logger.error(f"Error reading log for download: {e}")
        return None, None


def download_logs():
    """Render a download button for the full log file (always visible — no nesting issue)."""
    content, filename = get_log_download_data()
    if content is not None:
        st.download_button(
            label="⬇️ Download Full Logs",
            data=content,
            file_name=filename,
            mime="text/plain",
            key="download_logs_btn",
        )
    else:
        st.info("No log file found.")


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