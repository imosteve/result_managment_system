# database.py

import sqlite3
import os
import bcrypt
import logging
from contextlib import contextmanager
from utils import assign_grade

# Database file path
DB_PATH = os.getenv('DATABASE_PATH', os.path.join("data", "school.db"))
BACKUP_PATH = os.getenv('BACKUP_PATH', os.path.join("backups"))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_connection():
    """Get database connection"""
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
    conn.row_factory = sqlite3.Row  # Enable row factory for dict-like access
    return conn

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def create_tables():
    """Create all database tables"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Classes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            term TEXT NOT NULL,
            session TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, term, session)
        )
    """)
    
    # Students table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            gender TEXT CHECK(gender IN ('M', 'F')),
            email TEXT,
            class_name TEXT NOT NULL,
            term TEXT NOT NULL,
            session TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_name, term, session) REFERENCES classes(name, term, session) ON DELETE CASCADE,
            UNIQUE(name, class_name, term, session)
        )
    """)
    
    # Subjects table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            class_name TEXT NOT NULL,
            term TEXT NOT NULL,
            session TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_name, term, session) REFERENCES classes(name, term, session) ON DELETE CASCADE,
            UNIQUE(name, class_name, term, session)
        )
    """)
    
    # Scores table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            subject_name TEXT NOT NULL,
            class_name TEXT NOT NULL,
            term TEXT NOT NULL,
            session TEXT NOT NULL,
            test_score REAL DEFAULT 0,
            exam_score REAL DEFAULT 0,
            total_score REAL DEFAULT 0,
            grade TEXT,
            position INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_name, term, session) REFERENCES classes(name, term, session) ON DELETE CASCADE,
            FOREIGN KEY (student_name, class_name, term, session) REFERENCES students(name, class_name, term, session) ON DELETE CASCADE,
            FOREIGN KEY (subject_name, class_name, term, session) REFERENCES subjects(name, class_name, term, session) ON DELETE CASCADE,
            UNIQUE(student_name, subject_name, class_name, term, session)
        )
    """)
    
    # Users table for RBAC
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('superadmin', 'admin', 'class_teacher', 'subject_teacher')),
            UNIQUE(username, role)
        )
    """)
    
    # Teacher assignments table for RBAC
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teacher_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            class_name TEXT,
            term TEXT,
            session TEXT,
            subject_name TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (class_name, term, session) REFERENCES classes(name, term, session) ON DELETE CASCADE,
            FOREIGN KEY (subject_name, class_name, term, session) 
                REFERENCES subjects(name, class_name, term, session) ON DELETE CASCADE,
            UNIQUE(user_id, class_name, term, session, subject_name)
        )
    """)
    
    # Comments table for dynamic report card comments
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            class_name TEXT NOT NULL,
            term TEXT NOT NULL,
            session TEXT NOT NULL,
            class_teacher_comment TEXT,
            head_teacher_comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_name, term, session) REFERENCES classes(name, term, session) ON DELETE CASCADE,
            FOREIGN KEY (student_name, class_name, term, session) REFERENCES students(name, class_name, term, session) ON DELETE CASCADE,
            UNIQUE(student_name, class_name, term, session)
        )
    """)
    
    create_student_subject_selections_table()
    
    conn.commit()
    conn.close()
    
    # Create performance indexes
    create_performance_indexes()

# ==================== USER OPERATIONS ====================
def create_user(username, password, role):
    """Create a new user with hashed password"""
    # hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    # Require at least 8 characters
    if len(password) < 4:
        logger.error(f"Password for user '{username}' is too short (length: {len(password)})")
        return False
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO users (username, password, role)
            VALUES (?, ?, ?)
        """, (username, password, role))
        conn.commit()
        logger.info(f"User '{username}' created successfully with role '{role}'")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Failed to create user '{username}' with role '{role} - may already exist")
        return False
    finally:
        conn.close()

def get_user_by_username(username):
    """Retrieve user by username"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    return user

def delete_user(user_id):
    """Delete a user and their assignments (CASCADE)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_all_users():
    """Get all users including password"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role, password FROM users ORDER BY username")
    users = cursor.fetchall()
    conn.close()
    return users

def get_user_assignments(user_id):
    """Get class/subject assignments for a user"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, class_name, term, session, subject_name
            FROM teacher_assignments
            WHERE user_id = ?
            ORDER BY session DESC, term, class_name, subject_name
        """, (user_id,))
        assignments = cursor.fetchall()
        conn.close()
        
        logger.info(f"Retrieved {len(assignments)} assignments for user {user_id}")
        return assignments
    except Exception as e:
        logger.error(f"Error getting assignments for user {user_id}: {str(e)}")
        return []

def assign_teacher(user_id, class_name, term, session, subject_name=None):
    """Assign a class or class/subject to a teacher"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Check for duplicate assignment
        cursor.execute("""
            SELECT id FROM teacher_assignments
            WHERE user_id = ? AND class_name = ? AND term = ? AND session = ? AND subject_name IS ?
        """, (user_id, class_name, term, session, subject_name))
        if cursor.fetchone():
            conn.close()
            return False
        cursor.execute("""
            INSERT INTO teacher_assignments (user_id, class_name, term, session, subject_name)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, class_name, term, session, subject_name))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def delete_assignment(assignment_id):
    """Delete a teacher assignment"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM teacher_assignments WHERE id = ?", (assignment_id,))
    conn.commit()
    conn.close()

def update_user(user_id, new_username, new_password=None):
    """Update user's username and optionally password"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if new_password:
            # Update both username and password
            if len(new_password) < 4:
                logger.error(f"Password for user '{new_username}' is too short")
                return False
            cursor.execute("""
                UPDATE users 
                SET username = ?, password = ?
                WHERE id = ?
            """, (new_username, new_password, user_id))
        else:
            # Update only username
            cursor.execute("""
                UPDATE users 
                SET username = ?
                WHERE id = ?
            """, (new_username, user_id))
        
        conn.commit()
        logger.info(f"User {user_id} updated successfully")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Failed to update user - username may already exist")
        return False
    finally:
        conn.close()

def update_assignment(assignment_id, new_class_name, new_term, new_session, new_subject_name=None):
    """Update a teacher assignment"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE teacher_assignments
            SET class_name = ?, term = ?, session = ?, subject_name = ?
            WHERE id = ?
        """, (new_class_name, new_term, new_session, new_subject_name, assignment_id))
        conn.commit()
        logger.info(f"Assignment {assignment_id} updated successfully")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Failed to update assignment - may already exist")
        return False
    finally:
        conn.close()

def create_comment(student_name, class_name, term, session, class_teacher_comment=None, head_teacher_comment=None):
    """Create or update a comment for a student"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO comments (
                student_name, class_name, term, session, 
                class_teacher_comment, head_teacher_comment, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (student_name, class_name, term, session, class_teacher_comment, head_teacher_comment))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_comment(student_name, class_name, term, session):
    """Get comments for a student"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT class_teacher_comment, head_teacher_comment
        FROM comments
        WHERE student_name = ? AND class_name = ? AND term = ? AND session = ?
    """, (student_name, class_name, term, session))
    comment = cursor.fetchone()
    conn.close()
    return comment

def delete_comment(student_name, class_name, term, session):
    """Delete a comment for a student"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM comments
        WHERE student_name = ? AND class_name = ? AND term = ? AND session = ?
    """, (student_name, class_name, term, session))
    conn.commit()
    conn.close()

# ==================== CLASS OPERATIONS ====================
def get_all_classes(user_id=None, role=None):
    """Get all classes, with restrictions for non-admins"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # FIXED: Admins should see ALL classes without restrictions
    if role in ["", "superadmin", "admin"]:
        cursor.execute("""
            SELECT name, term, session 
            FROM classes 
            ORDER BY session DESC, term, name
        """)
    elif role in ["class_teacher", "subject_teacher"] and user_id:
        cursor.execute("""
            SELECT DISTINCT c.name, c.term, c.session
            FROM classes c
            JOIN teacher_assignments ta ON c.name = ta.class_name 
                AND c.term = ta.term AND c.session = ta.session
            WHERE ta.user_id = ?
            ORDER BY c.session DESC, c.term, c.name
        """, (user_id,))
    else:
        conn.close()
        return []
        
    rows = cursor.fetchall()
    classes = [
        {"class_name": row[0], "term": row[1], "session": row[2]}
        for row in rows
    ]
    conn.close()
    return classes

def create_class(class_name, term, session):
    """Create a new class"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO classes (name, term, session) VALUES (?, ?, ?)",
            (class_name, term, session)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def update_class(original_class_name, original_term, original_session, new_class_name, new_term, new_session):
    """Update an existing class entry"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE classes
        SET name = ?, term = ?, session = ?
        WHERE name = ? AND term = ? AND session = ?
    """, (new_class_name, new_term, new_session, original_class_name, original_term, original_session))
    conn.commit()
    conn.close()

def delete_class(class_name, term, session):
    """Delete a class and all associated data (CASCADE)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM classes WHERE name = ? AND term = ? AND session = ?", (class_name, term, session))
    conn.commit()
    conn.close()

def clear_all_classes():
    """Delete all classes and associated data (students, subjects, scores) via CASCADE"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM classes")
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error clearing classes: {e}")
        return False
    finally:
        conn.close()

# ==================== STUDENT OPERATIONS ====================
def get_students_by_class(class_name, term, session, user_id=None, role=None):
    """Get all students in a class for specific term and session with role-based restrictions"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # FIXED: Admins should see ALL students without restrictions
    if role in ["superadmin", "admin"]:
        cursor.execute("""
            SELECT id, name, gender, email 
            FROM students 
            WHERE class_name = ? AND term = ? AND session = ?
            ORDER BY name
        """, (class_name, term, session))
    elif role == "class_teacher" and user_id:
        cursor.execute("""
            SELECT s.id, s.name, s.gender, s.email 
            FROM students s
            JOIN teacher_assignments ta ON s.class_name = ta.class_name 
                AND s.term = ta.term AND s.session = ta.session
            WHERE s.class_name = ? AND s.term = ? AND s.session = ? 
                AND ta.user_id = ? AND ta.subject_name IS NULL
            ORDER BY s.name
        """, (class_name, term, session, user_id))
    elif role == "subject_teacher" and user_id:
        cursor.execute("""
            SELECT s.id, s.name, s.gender, s.email 
            FROM students s
            JOIN teacher_assignments ta ON s.class_name = ta.class_name 
                AND s.term = ta.term AND s.session = ta.session
            WHERE s.class_name = ? AND s.term = ? AND s.session = ? 
                AND ta.user_id = ? AND ta.subject_name IS NOT NULL
            ORDER BY s.name
        """, (class_name, term, session, user_id))
    else:
        conn.close()
        return []
    students = cursor.fetchall()
    conn.close()
    return students

def create_student(name, gender, email, class_name, term, session):
    """Create a new student"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO students (name, gender, email, class_name, term, session) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, gender or None, email or None, class_name, term, session))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def create_students_batch(students_data, class_name, term, session):
    """Create multiple students in a single transaction"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.executemany("""
            INSERT INTO students (name, gender, email, class_name, term, session) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, [(s['name'], s.get('gender'), s.get('email'), class_name, term, session) 
              for s in students_data])
        conn.commit()
        return True
    except sqlite3.IntegrityError as e:
        logger.error(f"Batch student creation failed: {str(e)}")
        return False
    finally:
        conn.close()

def update_student(student_id, name, gender, email):
    """Update student information"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE students 
        SET name = ?, gender = ?, email = ? 
        WHERE id = ?
    """, (name, gender or None, email or None, student_id))
    conn.commit()
    conn.close()

def delete_student(student_id):
    """Delete a student and all associated scores (CASCADE)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
    conn.commit()
    conn.close()

def delete_all_students(class_name, term, session):
    """Delete all students for a specific class, term, and session"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM students 
        WHERE class_name = ? AND term = ? AND session = ?
    """, (class_name, term, session))
    conn.commit()
    conn.close()

# ==================== SUBJECT OPERATIONS ====================
def get_subjects_by_class(class_name, term, session, user_id=None, role=None):
    """Get all subjects for a class in specific term and session with role-based restrictions"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # FIXED: Admins should see ALL subjects without restrictions
    if role in ["", "superadmin", "admin"]:
        cursor.execute("""
            SELECT id, name 
            FROM subjects 
            WHERE class_name = ? AND term = ? AND session = ?
            ORDER BY name
        """, (class_name, term, session))
    elif role == "class_teacher" and user_id:
        cursor.execute("""
            SELECT s.id, s.name 
            FROM subjects s
            JOIN teacher_assignments ta ON s.class_name = ta.class_name 
                AND s.term = ta.term AND s.session = ta.session
            WHERE s.class_name = ? AND s.term = ? AND s.session = ? 
                AND ta.user_id = ? AND ta.subject_name IS NULL
            ORDER BY s.name
        """, (class_name, term, session, user_id))
    elif role == "subject_teacher" and user_id:
        cursor.execute("""
            SELECT s.id, s.name 
            FROM subjects s
            JOIN teacher_assignments ta ON s.class_name = ta.class_name 
                AND s.term = ta.term AND s.session = ta.session 
                AND s.name = ta.subject_name
            WHERE s.class_name = ? AND s.term = ? AND s.session = ? 
                AND ta.user_id = ?
            ORDER BY s.name
        """, (class_name, term, session, user_id))
    else:
        conn.close()
        return []
    subjects = cursor.fetchall()
    conn.close()
    return subjects

def create_subject(subject_name, class_name, term, session):
    """Create a new subject for a class in specific term and session"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO subjects (name, class_name, term, session) 
            VALUES (?, ?, ?, ?)
        """, (subject_name, class_name, term, session))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def update_subject(subject_id, new_subject_name, new_class_name, new_term, new_session):
    """Update an existing subject entry"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE subjects
            SET name = ?, class_name = ?, term = ?, session = ?
            WHERE id = ?
        """, (new_subject_name, new_class_name, new_term, new_session, subject_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def delete_subject(subject_id):
    """Delete a subject and all associated scores (CASCADE)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
    conn.commit()
    conn.close()

def clear_all_subjects(class_name, term, session):
    """Delete all subjects for a specific class, term, and session"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM subjects 
            WHERE class_name = ? AND term = ? AND session = ?
        """, (class_name, term, session))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error clearing subjects: {e}")
        return False
    finally:
        conn.close()

# ==================== SCORE OPERATIONS ====================
def get_scores_by_class_subject(class_name, subject_name, term, session, user_id=None, role=None):
    """Get all scores for a specific class and subject in specific term and session with role-based restrictions"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # FIXED: Admins should see ALL scores without restrictions
    if role in ["superadmin", "admin"]:
        cursor.execute("""
            SELECT id, student_name, subject_name, test_score, exam_score, 
                   total_score, grade, position
            FROM scores 
            WHERE class_name = ? AND subject_name = ? AND term = ? AND session = ?
            ORDER BY total_score DESC
        """, (class_name, subject_name, term, session))
    elif role == "class_teacher" and user_id:
        cursor.execute("""
            SELECT s.id, s.student_name, s.subject_name, s.test_score, s.exam_score, 
                   s.total_score, s.grade, s.position
            FROM scores s
            JOIN teacher_assignments ta ON s.class_name = ta.class_name 
                AND s.term = ta.term AND s.session = ta.session
            WHERE s.class_name = ? AND s.subject_name = ? 
                AND s.term = ? AND s.session = ? 
                AND ta.user_id = ? AND ta.subject_name IS NULL
            ORDER BY s.total_score DESC
        """, (class_name, subject_name, term, session, user_id))
    elif role == "subject_teacher" and user_id:
        cursor.execute("""
            SELECT s.id, s.student_name, s.subject_name, s.test_score, s.exam_score, 
                   s.total_score, s.grade, s.position
            FROM scores s
            JOIN teacher_assignments ta ON s.class_name = ta.class_name 
                AND s.term = ta.term AND s.session = ta.session 
                AND s.subject_name = ta.subject_name
            WHERE s.class_name = ? AND s.subject_name = ? 
                AND s.term = ? AND s.session = ? 
                AND ta.user_id = ?
            ORDER BY s.total_score DESC
        """, (class_name, subject_name, term, session, user_id))
    else:
        conn.close()
        return []
    scores = cursor.fetchall()
    conn.close()
    return scores

def get_all_scores_by_class(class_name, term, session, user_id=None, role=None):
    """Get all scores for a class in specific term and session with role-based restrictions"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # FIXED: Admins should see ALL scores without restrictions
    if role in ["superadmin", "admin"]:
        cursor.execute("""
            SELECT id, student_name, subject_name, test_score, exam_score, 
                   total_score, grade, position
            FROM scores 
            WHERE class_name = ? AND term = ? AND session = ?
            ORDER BY student_name, subject_name
        """, (class_name, term, session))
    elif role == "class_teacher" and user_id:
        cursor.execute("""
            SELECT s.id, s.student_name, s.subject_name, s.test_score, s.exam_score, 
                   s.total_score, s.grade, s.position
            FROM scores s
            JOIN teacher_assignments ta ON s.class_name = ta.class_name 
                AND s.term = ta.term AND s.session = ta.session
            WHERE s.class_name = ? AND s.term = ? AND s.session = ? 
                AND ta.user_id = ? AND ta.subject_name IS NULL
            ORDER BY s.student_name, s.subject_name
        """, (class_name, term, session, user_id))
    elif role == "subject_teacher" and user_id:
        cursor.execute("""
            SELECT s.id, s.student_name, s.subject_name, s.test_score, s.exam_score, 
                   s.total_score, s.grade, s.position
            FROM scores s
            JOIN teacher_assignments ta ON s.class_name = ta.class_name 
                AND s.term = ta.term AND s.session = ta.session 
                AND s.subject_name = ta.subject_name
            WHERE s.class_name = ? AND s.term = ? AND s.session = ? 
                AND ta.user_id = ?
            ORDER BY s.student_name, s.subject_name
        """, (class_name, term, session, user_id))
    else:
        conn.close()
        return []
    scores = cursor.fetchall()
    conn.close()
    return scores

def get_student_scores(student_name, class_name, term, session, user_id=None, role=None):
    """Get all scores for a specific student in specific term and session with role-based restrictions"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # FIXED: Admins should see ALL scores without restrictions
    if role in ["superadmin", "admin"]:
        cursor.execute("""
            SELECT id, student_name, subject_name, test_score, exam_score, 
                   total_score, grade, position
            FROM scores 
            WHERE student_name = ? AND class_name = ? AND term = ? AND session = ?
            ORDER BY subject_name
        """, (student_name, class_name, term, session))
    elif role == "class_teacher" and user_id:
        cursor.execute("""
            SELECT s.id, s.student_name, s.subject_name, s.test_score, s.exam_score, 
                   s.total_score, s.grade, s.position
            FROM scores s
            JOIN teacher_assignments ta ON s.class_name = ta.class_name 
                AND s.term = ta.term AND s.session = ta.session
            WHERE s.student_name = ? AND s.class_name = ? 
                AND s.term = ? AND s.session = ? 
                AND ta.user_id = ? AND ta.subject_name IS NULL
            ORDER BY s.subject_name
        """, (student_name, class_name, term, session, user_id))
    elif role == "subject_teacher" and user_id:
        cursor.execute("""
            SELECT s.id, s.student_name, s.subject_name, s.test_score, s.exam_score, 
                   s.total_score, s.grade, s.position
            FROM scores s
            JOIN teacher_assignments ta ON s.class_name = ta.class_name 
                AND s.term = ta.term AND s.session = ta.session 
                AND s.subject_name = ta.subject_name
            WHERE s.student_name = ? AND s.class_name = ? 
                AND s.term = ? AND s.session = ? 
                AND ta.user_id = ?
            ORDER BY s.subject_name
        """, (student_name, class_name, term, session, user_id))
    else:
        conn.close()
        return []
    scores = cursor.fetchall()
    conn.close()
    return scores

def save_scores(scores_data, class_name, subject_name, term, session):
    """Save multiple scores with position calculation"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Sort scores by total for position calculation
    sorted_scores = sorted(scores_data, key=lambda x: x['total'], reverse=True)
    
    # Assign positions
    for i, score in enumerate(sorted_scores):
        if i > 0 and score['total'] == sorted_scores[i-1]['total']:
            score['position'] = sorted_scores[i-1]['position']
        else:
            score['position'] = i + 1
    
    # Delete existing scores for this class, subject, term, and session
    cursor.execute("""
        DELETE FROM scores 
        WHERE class_name = ? AND subject_name = ? AND term = ? AND session = ?
    """, (class_name, subject_name, term, session))
    
    # Insert new scores
    for score in sorted_scores:
        cursor.execute("""
            INSERT INTO scores (
                student_name, subject_name, class_name, term, session,
                test_score, exam_score, total_score, grade, position
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            score['student'], score['subject'], score['class'], score['term'], score['session'],
            score['test'], score['exam'], score['total'], 
            score['grade'], score['position']
        ))
    
    conn.commit()
    conn.close()

def update_score(student_name, subject_name, class_name, term, session, test_score, exam_score):
    """Update individual score"""
    conn = get_connection()
    cursor = conn.cursor()
    
    total_score = test_score + exam_score
    grade = assign_grade(total_score)
    
    cursor.execute("""
        INSERT OR REPLACE INTO scores (
            student_name, subject_name, class_name, term, session,
            test_score, exam_score, total_score, grade, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (student_name, subject_name, class_name, term, session, test_score, exam_score, total_score, grade))
    
    conn.commit()
    
    # Recalculate positions for this subject, class, term, and session
    recalculate_positions(class_name, subject_name, term, session)
    
    conn.close()

def recalculate_positions(class_name, subject_name, term, session):
    """Recalculate positions for a subject in a class for specific term and session"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get all scores for this class, subject, term, and session, ordered by total desc
    cursor.execute("""
        SELECT id, total_score 
        FROM scores 
        WHERE class_name = ? AND subject_name = ? AND term = ? AND session = ?
        ORDER BY total_score DESC
    """, (class_name, subject_name, term, session))
    
    scores = cursor.fetchall()
    
    # Update positions
    for i, (score_id, total_score) in enumerate(scores):
        if i > 0 and total_score == scores[i-1][1]:
            # Same score as previous, get their position
            cursor.execute("SELECT position FROM scores WHERE id = ?", (scores[i-1][0],))
            position = cursor.fetchone()[0]
        else:
            position = i + 1
        
        cursor.execute("UPDATE scores SET position = ? WHERE id = ?", (position, score_id))
    
    conn.commit()
    conn.close()

# def get_class_average(class_name, term, session, user_id=None, role=None):
#     """Calculate the average total score for all students in a class for a term and session with role-based restrictions"""
#     conn = get_connection()
#     cursor = conn.cursor()
#     try:
#         # FIXED: Admins should see ALL averages without restrictions
#         if role in ["superadmin", "admin"]:
#             cursor.execute("""
#                 SELECT AVG(total_score)
#                 FROM scores
#                 WHERE class_name = ? AND term = ? AND session = ?
#             """, (class_name, term, session))
#         elif role == "class_teacher" and user_id:
#             cursor.execute("""
#                 SELECT AVG(s.total_score)
#                 FROM scores s
#                 JOIN teacher_assignments ta ON s.class_name = ta.class_name 
#                     AND s.term = ta.term AND s.session = ta.session
#                 WHERE s.class_name = ? AND s.term = ? AND s.session = ? 
#                     AND ta.user_id = ? AND ta.subject_name IS NULL
#             """, (class_name, term, session, user_id))
#         elif role == "subject_teacher" and user_id:
#             cursor.execute("""
#                 SELECT AVG(s.total_score)
#                 FROM scores s
#                 JOIN teacher_assignments ta ON s.class_name = ta.class_name 
#                     AND s.term = ta.term AND s.session = ta.session 
#                     AND s.subject_name = ta.subject_name
#                 WHERE s.class_name = ? AND s.term = ? AND s.session = ? 
#                     AND ta.user_id = ?
#             """, (class_name, term, session, user_id))
#         else:
#             conn.close()
#             return 0
#         avg = cursor.fetchone()[0]
#         conn.close()
#         return round(avg, 2) if avg is not None else 0
#     except sqlite3.Error as e:
#         logger.error(f"Error calculating class average: {e}")
#         conn.close()
#         return 0

def get_class_average(class_name, term, session, user_id, role):
    """
    Calculate class average based on individual student averages (same as broadsheet calculation)
    This ensures consistency between broadsheet and report card
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get all students in the class
        students = get_students_by_class(class_name, term, session, user_id, role)
        if not students:
            return 0
        
        # Calculate average for each student
        student_averages = []
        for student in students:
            student_name = student[1]
            scores = get_student_scores(student_name, class_name, term, session, user_id, role)
            
            if scores:
                # Calculate student's average from their total scores
                total_score = sum(score[5] for score in scores)  # score[5] is total
                student_avg = total_score / len(scores)
                student_averages.append(student_avg)
        
        # Calculate class average from student averages
        if student_averages:
            class_average = sum(student_averages) / len(student_averages)
            return round(class_average, 2)
        return 0
        
    except Exception as e:
        logger.error(f"Error calculating class average: {str(e)}")
        return 0
    finally:
        conn.close()

def get_student_grand_totals(class_name, term, session, user_id=None, role=None):
    """Get grand totals and ranks for all students in a class, term, and session with role-based restrictions"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # FIXED: Admins should see ALL grand totals without restrictions
        if role in ["superadmin", "admin"]:
            cursor.execute("""
                SELECT student_name, SUM(total_score) as grand_total
                FROM scores
                WHERE class_name = ? AND term = ? AND session = ?
                GROUP BY student_name
                ORDER BY grand_total DESC
            """, (class_name, term, session))
        elif role == "class_teacher" and user_id:
            cursor.execute("""
                SELECT s.student_name, SUM(s.total_score) as grand_total
                FROM scores s
                JOIN teacher_assignments ta ON s.class_name = ta.class_name 
                    AND s.term = ta.term AND s.session = ta.session
                WHERE s.class_name = ? AND s.term = ? AND s.session = ? 
                    AND ta.user_id = ? AND ta.subject_name IS NULL
                GROUP BY s.student_name
                ORDER BY grand_total DESC
            """, (class_name, term, session, user_id))
        elif role == "subject_teacher" and user_id:
            cursor.execute("""
                SELECT s.student_name, SUM(s.total_score) as grand_total
                FROM scores s
                JOIN teacher_assignments ta ON s.class_name = ta.class_name 
                    AND s.term = ta.term AND s.session = ta.session 
                    AND s.subject_name = ta.subject_name
                WHERE s.class_name = ? AND s.term = ? AND s.session = ? 
                    AND ta.user_id = ?
                GROUP BY s.student_name
                ORDER BY grand_total DESC
            """, (class_name, term, session, user_id))
        else:
            conn.close()
            return []
        student_totals = cursor.fetchall()

        # Assign ranks, handling ties
        result = []
        current_rank = 1
        previous_total = None
        for i, (student_name, grand_total) in enumerate(student_totals):
            if grand_total != previous_total:
                current_rank = i + 1
            result.append({
                'student_name': student_name,
                'grand_total': grand_total,
                'position': current_rank
            })
            previous_total = grand_total

        conn.close()
        return result
    except sqlite3.Error as e:
        logger.error(f"Error fetching grand totals: {e}")
        conn.close()
        return []

def clear_all_scores(class_name, subject_name, term, session):
    """Delete all scores for a specific class, subject, term, and session"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM scores 
            WHERE class_name = ? AND subject_name = ? AND term = ? AND session = ?
        """, (class_name, subject_name, term, session))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error clearing scores: {e}")
        return False
    finally:
        conn.close()

# ==================== UTILITY FUNCTIONS ====================
def get_database_stats():
    """Get database statistics"""
    conn = get_connection()
    cursor = conn.cursor()
    
    stats = {}
    
    # Count classes
    cursor.execute("SELECT COUNT(*) FROM classes")
    stats['classes'] = cursor.fetchone()[0]
    
    # Count students
    cursor.execute("SELECT COUNT(*) FROM students")
    stats['students'] = cursor.fetchone()[0]
    
    # Count subjects
    cursor.execute("SELECT COUNT(*) FROM subjects")
    stats['subjects'] = cursor.fetchone()[0]
    
    # Count scores
    cursor.execute("SELECT COUNT(*) FROM scores")
    stats['scores'] = cursor.fetchone()[0]
    
    # Count users
    cursor.execute("SELECT COUNT(*) FROM users")
    stats['users'] = cursor.fetchone()[0]
    
    # Count assignments
    cursor.execute("SELECT COUNT(*) FROM teacher_assignments")
    stats['assignments'] = cursor.fetchone()[0]
    
    # Count comments
    cursor.execute("SELECT COUNT(*) FROM comments")
    stats['comments'] = cursor.fetchone()[0]
    
    conn.close()
    return stats

def get_classes_summary():
    """Get summary of all classes with counts"""
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
    """Create a backup of the database"""
    import shutil
    try:
        shutil.copy2(DB_PATH, backup_path)
        logger.info(f"Database backed up to {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Database backup failed: {str(e)}")
        return False

def restore_database(backup_path):
    """Restore database from backup"""
    import shutil
    try:
        shutil.copy2(backup_path, DB_PATH)
        logger.info(f"Database restored from {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Database restore failed: {str(e)}")
        return False

def migrate_old_database():
    """Migrate old database structure to new one with term and session support"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if old structure exists (classes table without composite key)
    cursor.execute("PRAGMA table_info(classes)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'term' not in columns or 'session' not in columns:
        # This is an old database, needs migration
        logger.info("Migrating old database structure...")
        
        # Backup old tables
        cursor.execute("ALTER TABLE classes RENAME TO classes_old")
        cursor.execute("ALTER TABLE students RENAME TO students_old")
        cursor.execute("ALTER TABLE subjects RENAME TO subjects_old")
        cursor.execute("ALTER TABLE scores RENAME TO scores_old")
        
        # Create new tables
        create_tables()
        
        # Migrate data (you'll need to handle default term/session values)
        default_term = "1st Term"
        default_session = "2024/2025"
        
        # Migrate classes
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
        logger.info("Migration completed!")
    
    conn.close()

# ==================== ENHANCED PRODUCTION FUNCTIONS ====================
def database_health_check():
    """Check database integrity and connectivity"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Test basic connectivity
        cursor.execute("SELECT 1")
        
        # Check foreign key constraints
        cursor.execute("PRAGMA foreign_key_check")
        fk_violations = cursor.fetchall()
        
        # Check integrity
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

def create_performance_indexes():
    """Create indexes for better query performance"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Indexes for common queries
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_students_class_term_session ON students(class_name, term, session)",
            "CREATE INDEX IF NOT EXISTS idx_subjects_class_term_session ON subjects(class_name, term, session)",  
            "CREATE INDEX IF NOT EXISTS idx_scores_class_subject_term_session ON scores(class_name, subject_name, term, session)",
            "CREATE INDEX IF NOT EXISTS idx_scores_student_class_term_session ON scores(student_name, class_name, term, session)",
            "CREATE INDEX IF NOT EXISTS idx_teacher_assignments_user ON teacher_assignments(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_scores_total_score ON scores(total_score DESC)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        
        conn.commit()
        logger.info("Performance indexes created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating indexes: {str(e)}")
        return False
    finally:
        conn.close()

def validate_student_data(name, gender=None, email=None):
    """Validate student data before database insertion"""
    errors = []
    
    if not name or not name.strip():
        errors.append("Student name is required")
    
    if gender and gender not in ['M', 'F']:
        errors.append("Gender must be 'M' or 'F'")
    
    if email and '@' not in email:
        errors.append("Invalid email format")
    
    return errors

def validate_score_data(test_score, exam_score):
    """Validate score data"""
    errors = []
    
    try:
        test = float(test_score)
        exam = float(exam_score)
        
        if test < 0 or test > 30:
            errors.append("Test score must be between 0 and 30")
        
        if exam < 0 or exam > 70:
            errors.append("Exam score must be between 0 and 70")
            
    except (ValueError, TypeError):
        errors.append("Scores must be valid numbers")
    
    return errors


# UPDATES
# Add these functions to database.py
def create_student_subject_selections_table():
    """Create student_subject_selections table for SSS2 and SSS3 subject choices"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_subject_selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            subject_name TEXT NOT NULL,
            class_name TEXT NOT NULL,
            term TEXT NOT NULL,
            session TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_name, term, session) REFERENCES classes(name, term, session) ON DELETE CASCADE,
            FOREIGN KEY (student_name, class_name, term, session) REFERENCES students(name, class_name, term, session) ON DELETE CASCADE,
            FOREIGN KEY (subject_name, class_name, term, session) REFERENCES subjects(name, class_name, term, session) ON DELETE CASCADE,
            UNIQUE(student_name, subject_name, class_name, term, session)
        )
    """)
    conn.commit()
    conn.close()

def get_student_selected_subjects(student_name, class_name, term, session):
    """Get subjects selected by a specific student"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT subject_name
        FROM student_subject_selections
        WHERE student_name = ? AND class_name = ? AND term = ? AND session = ?
    """, (student_name, class_name, term, session))
    subjects = [row[0] for row in cursor.fetchall()]
    conn.close()
    return subjects

def save_student_subject_selections(student_name, selected_subjects, class_name, term, session):
    """Save/update subject selections for a student"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Clear existing selections
    cursor.execute("""
        DELETE FROM student_subject_selections
        WHERE student_name = ? AND class_name = ? AND term = ? AND session = ?
    """, (student_name, class_name, term, session))
    
    # Insert new selections
    for subject in selected_subjects:
        cursor.execute("""
            INSERT INTO student_subject_selections (student_name, subject_name, class_name, term, session)
            VALUES (?, ?, ?, ?, ?)
        """, (student_name, subject, class_name, term, session))
    
    conn.commit()
    conn.close()

def get_all_student_subject_selections(class_name, term, session):
    """Get all student subject selections for a class"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT student_name, subject_name
        FROM student_subject_selections
        WHERE class_name = ? AND term = ? AND session = ?
        ORDER BY student_name, subject_name
    """, (class_name, term, session))
    selections = cursor.fetchall()
    conn.close()
    return selections

# # Update the create_tables function to include the new table
# def create_tables():
#     """Create all database tables"""
#     # ... existing code ...
    
#     # Add this at the end before conn.commit()
#     create_student_subject_selections_table()
    
#     # ... rest of existing code ...