# database/utils.py

"""Database utility functions - stats, validation, backup/restore, migrations"""

import shutil
import sqlite3
import logging
from .connection import get_connection, DB_PATH, BACKUP_PATH
import json

logger = logging.getLogger(__name__)


def get_database_stats():
    """
    Get database statistics
    Uses new schema (admin_users table)
    Teachers are users NOT in admin_users
    
    Returns:
        dict: Dictionary with various database statistics
    """
    conn = get_connection()
    cursor = conn.cursor()

    stats = {}

    # Basic counts
    cursor.execute("SELECT COUNT(*) FROM classes")
    stats['classes'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM students")
    stats['students'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM subjects")
    stats['subjects'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM scores")
    stats['scores'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM comments")
    stats['comments'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM teacher_assignments")
    stats['assignments'] = cursor.fetchone()[0]

    # Teachers are users NOT in admin_users
    cursor.execute("""
        SELECT COUNT(*) 
        FROM users 
        WHERE id NOT IN (SELECT user_id FROM admin_users WHERE role IN ('admin', 'superadmin'))
    """)
    stats['teachers'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users")
    stats['users'] = cursor.fetchone()[0]

    conn.close()
    return stats


def get_classes_summary():
    """
    Get summary of all classes with counts
    
    Returns:
        list: List of class summaries with student, subject, and score counts
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            c.name as class_name,
            c.term,
            c.session,
            COUNT(DISTINCT s.id) as student_count,
            COUNT(DISTINCT sub.id) as subject_count,
            COUNT(DISTINCT sc.id) as score_count
        FROM classes c
        LEFT JOIN students s ON c.name = s.class_name AND c.term = s.term AND c.session = s.session
        LEFT JOIN subjects sub ON c.name = sub.class_name AND c.term = sub.term AND c.session = sub.session
        LEFT JOIN scores sc ON c.name = sc.class_name AND c.term = sc.term AND c.session = sc.session
        GROUP BY c.name, c.term, c.session
        ORDER BY c.session DESC, c.term, c.name
    """)
    results = cursor.fetchall()
    conn.close()
    return results


def backup_database(backup_path):
    """
    Create a backup of the database
    
    Args:
        backup_path: Path where backup should be saved
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        shutil.copy2(DB_PATH, backup_path)
        logger.info(f"Database backed up to {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Database backup failed: {str(e)}")
        return False


def restore_database(backup_path):
    """
    Restore database from backup
    
    Args:
        backup_path: Path to backup file
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        shutil.copy2(backup_path, DB_PATH)
        logger.info(f"Database restored from {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Database restore failed: {str(e)}")
        return False


def database_health_check():
    """
    Check database integrity and connectivity
    
    Returns:
        dict: Health check results with status, integrity check, and violations
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Test connectivity
        cursor.execute("SELECT 1")
        
        # Check foreign key constraints
        cursor.execute("PRAGMA foreign_key_check")
        fk_violations = cursor.fetchall()
        
        # Check database integrity
        cursor.execute("PRAGMA integrity_check")
        integrity_result = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'status': 'healthy' if integrity_result == 'ok' and not fk_violations else 'issues',
            'integrity': integrity_result,
            'foreign_key_violations': len(fk_violations),
            'details': fk_violations if fk_violations else None
        }
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return {'status': 'error', 'error': str(e)}


def validate_student_data(name, gender=None, email=None):
    """
    Validate student data before database insertion
    
    Args:
        name: Student name
        gender: Gender ('M' or 'F')
        email: Email address
    
    Returns:
        list: List of error messages (empty if valid)
    """
    errors = []
    
    if not name or not name.strip():
        errors.append("Student name is required")
    
    if gender and gender not in ['M', 'F']:
        errors.append("Gender must be 'M' or 'F'")
    
    if email and '@' not in email:
        errors.append("Invalid email format")
    
    return errors


def validate_score_data(test_score, exam_score):
    """
    Validate score data
    
    Args:
        test_score: Test score (should be 0-30)
        exam_score: Exam score (should be 0-70)
    
    Returns:
        list: List of error messages (empty if valid)
    """
    errors = []
    
    try:
        test = int(test_score)
        exam = int(exam_score)
        
        if test < 0 or test > 30:
            errors.append("Test score must be between 0 and 30")
        
        if exam < 0 or exam > 70:
            errors.append("Exam score must be between 0 and 70")
            
    except (ValueError, TypeError):
        errors.append("Scores must be valid numbers")
    
    return errors


def migrate_old_database():
    """
    Migrate old database structure to new one with term and session support
    This function checks if migration is needed and performs it
    
    Returns:
        bool: True if migration was performed or not needed, False on error
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA table_info(classes)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'term' not in columns or 'session' not in columns:
            logger.info("Migrating old database structure...")
            
            # Rename old tables
            cursor.execute("ALTER TABLE classes RENAME TO classes_old")
            cursor.execute("ALTER TABLE students RENAME TO students_old")
            cursor.execute("ALTER TABLE subjects RENAME TO subjects_old")
            cursor.execute("ALTER TABLE scores RENAME TO scores_old")
            
            # Create new tables (import to avoid circular dependency)
            from .schema import create_tables
            create_tables()
            
            # Migrate data with default term and session
            default_term = "1st Term"
            default_session = "2024/2025"
            
            cursor.execute("SELECT name FROM classes_old")
            old_classes = cursor.fetchall()
            for (name,) in old_classes:
                cursor.execute("INSERT INTO classes (name, term, session) VALUES (?, ?, ?)",
                              (name, default_term, default_session))
            
            # Drop old tables
            cursor.execute("DROP TABLE classes_old")
            cursor.execute("DROP TABLE students_old")
            cursor.execute("DROP TABLE subjects_old")
            cursor.execute("DROP TABLE scores_old")
            
            conn.commit()
            logger.info("Migration completed successfully!")
            return True
        else:
            logger.info("Database already has term and session columns - no migration needed")
            return True
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()


def migrate_add_school_fees_column():
    """
    Add school_fees_paid column to existing students table if it doesn't exist
    
    Returns:
        bool: True if successful or column already exists, False otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(students)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'school_fees_paid' not in columns:
            logger.info("Adding school_fees_paid column to students table...")
            cursor.execute("""
                ALTER TABLE students 
                ADD COLUMN school_fees_paid TEXT DEFAULT 'NO' CHECK(school_fees_paid IN ('NO', 'YES'))
            """)
            conn.commit()
            logger.info("Successfully added school_fees_paid column with default value 'NO' (unpaid)")
            return True
        else:
            logger.info("school_fees_paid column already exists")
            return True
        
    except Exception as e:
        logger.error(f"Error adding school_fees_paid column: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

def migrate_reduce_next_term_info_table():
    """
    Migration to replace the old large next_term_info table with the new minimal structure:
        term, session, next_term_begins, fees_json, updated_at, updated_by

    This migration:
    1. Creates a DB backup
    2. Checks if migration is needed
    3. Extracts minimal usable data from the old table
    4. Drops old table
    5. Recreates new minimal table
    6. Reinserts minimal records
    """
    from .schema import create_tables  # safe import

    backup_path = DB_PATH + ".bak"

    try:
        shutil.copy2(DB_PATH, backup_path)
        logger.info(f"Backup created at: {backup_path}")
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return False

    conn = get_connection()
    cur = conn.cursor()

    # Step 1: detect if migration needed
    cur.execute("PRAGMA table_info(next_term_info)")
    cols = [c[1] for c in cur.fetchall()]

    # New minimal structure = exactly 7 columns including fees_json
    if "fees_json" in cols and "next_term_begins" in cols and len(cols) == 7:
        logger.info("Next term info table already in new minimal format.")
        conn.close()
        return True

    logger.warning("Old next_term_info structure detected — migrating...")

    # Step 2: Try extracting useful data
    try:
        cur.execute("SELECT term, session, next_term_begins FROM next_term_info")
        old_data = cur.fetchall()
        logger.info(f"Extracted {len(old_data)} record(s) from old table.")
    except Exception:
        logger.warning("Old table has incompatible structure. Migrating without preserving data.")
        old_data = []

    # Step 3: Drop old table
    try:
        cur.execute("DROP TABLE IF EXISTS next_term_info")
        conn.commit()
    except Exception as e:
        logger.error(f"Failed dropping old next_term_info: {e}")
        conn.rollback()
        conn.close()
        return False

    # Step 4: Recreate new minimal table
    try:
        create_tables()
        logger.info("New minimal next_term_info table created.")
    except Exception as e:
        logger.error(f"Failed to recreate schema: {e}")
        conn.rollback()
        conn.close()
        return False

    # Step 5: Reinsert minimal data
    try:
        for (term, session, begin_date) in old_data:
            fees_json = json.dumps({})
            cur.execute("""
                INSERT INTO next_term_info (term, session, next_term_begins, fees_json)
                VALUES (?, ?, ?, ?)
            """, (term, session, begin_date, fees_json))
        conn.commit()
        logger.info("Old next term data migrated successfully.")
    except Exception as e:
        logger.error(f"Error reinserting migrated data: {e}")
        conn.rollback()
        conn.close()
        return False

    conn.close()
    logger.info("Minimal next_term_info migration completed.")
    return True
