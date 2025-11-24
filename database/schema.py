# database/schema.py

"""Database schema definitions and table creation"""

import logging
from .connection import get_connection

logger = logging.getLogger(__name__)


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
            school_fees_paid TEXT DEFAULT 'NO' CHECK(school_fees_paid IN ('NO', 'YES')),
            class_name TEXT NOT NULL,
            term TEXT NOT NULL,
            session TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_name, term, session)
                REFERENCES classes(name, term, session)
                ON DELETE CASCADE
                ON UPDATE CASCADE,
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
            FOREIGN KEY (class_name, term, session) 
                   REFERENCES classes(name, term, session) 
                   ON DELETE CASCADE
                   ON UPDATE CASCADE,
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
            FOREIGN KEY (class_name, term, session) 
                   REFERENCES classes(name, term, session) 
                   ON DELETE CASCADE
                   ON UPDATE CASCADE,
            FOREIGN KEY (student_name, class_name, term, session) 
                   REFERENCES students(name, class_name, term, session) 
                   ON DELETE CASCADE ON UPDATE CASCADE,
            FOREIGN KEY (subject_name, class_name, term, session) 
                   REFERENCES subjects(name, class_name, term, session) 
                   ON DELETE CASCADE ON UPDATE CASCADE,
            UNIQUE(student_name, subject_name, class_name, term, session)
        )
    """)
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Teacher assignments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teacher_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            class_name TEXT NOT NULL,
            term TEXT NOT NULL,
            session TEXT NOT NULL,
            subject_name TEXT,
            assignment_type TEXT NOT NULL CHECK(assignment_type IN ('class_teacher', 'subject_teacher')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
            FOREIGN KEY (class_name, term, session) 
                REFERENCES classes(name, term, session) ON DELETE CASCADE ON UPDATE CASCADE,
            FOREIGN KEY (subject_name, class_name, term, session) 
                REFERENCES subjects(name, class_name, term, session) ON DELETE CASCADE ON UPDATE CASCADE,
            UNIQUE(user_id, class_name, term, session, subject_name, assignment_type)
        )
    """)
    
    # Admin users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            role TEXT NOT NULL CHECK(role IN ('superadmin', 'admin')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE
        )
    """)
    
    # Comments table
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
            FOREIGN KEY (class_name, term, session) 
                REFERENCES classes(name, term, session) ON DELETE CASCADE ON UPDATE CASCADE,
            FOREIGN KEY (student_name, class_name, term, session) 
                REFERENCES students(name, class_name, term, session) ON DELETE CASCADE ON UPDATE CASCADE,
            UNIQUE(student_name, class_name, term, session)
        )
    """)
    
    # Psychomotor ratings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS psychomotor_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            class_name TEXT NOT NULL,
            term TEXT NOT NULL,
            session TEXT NOT NULL,
            punctuality INTEGER CHECK(punctuality BETWEEN 1 AND 5),
            neatness INTEGER CHECK(neatness BETWEEN 1 AND 5),
            honesty INTEGER CHECK(honesty BETWEEN 1 AND 5),
            cooperation INTEGER CHECK(cooperation BETWEEN 1 AND 5),
            leadership INTEGER CHECK(leadership BETWEEN 1 AND 5),
            perseverance INTEGER CHECK(perseverance BETWEEN 1 AND 5),
            politeness INTEGER CHECK(politeness BETWEEN 1 AND 5),
            obedience INTEGER CHECK(obedience BETWEEN 1 AND 5),
            attentiveness INTEGER CHECK(attentiveness BETWEEN 1 AND 5),
            attitude_to_work INTEGER CHECK(attitude_to_work BETWEEN 1 AND 5),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_name, term, session) 
                REFERENCES classes(name, term, session) ON DELETE CASCADE ON UPDATE CASCADE,
            FOREIGN KEY (student_name, class_name, term, session) 
                REFERENCES students(name, class_name, term, session) ON DELETE CASCADE ON UPDATE CASCADE,
            UNIQUE(student_name, class_name, term, session)
        )
    """)
    
    # Student subject selections table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_subject_selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            subject_name TEXT NOT NULL,
            class_name TEXT NOT NULL,
            term TEXT NOT NULL,
            session TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_name, term, session) 
                REFERENCES classes(name, term, session) ON DELETE CASCADE ON UPDATE CASCADE,
            FOREIGN KEY (student_name, class_name, term, session) 
                REFERENCES students(name, class_name, term, session) ON DELETE CASCADE ON UPDATE CASCADE,
            FOREIGN KEY (subject_name, class_name, term, session) 
                REFERENCES subjects(name, class_name, term, session) ON DELETE CASCADE ON UPDATE CASCADE,
            UNIQUE(student_name, subject_name, class_name, term, session)
        )
    """)
    
    # Comment templates table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comment_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_text TEXT NOT NULL,
            comment_type TEXT NOT NULL CHECK(comment_type IN ('class_teacher', 'head_teacher')),
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(comment_text, comment_type)
        )
    """)
    
    # Next term info table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS next_term_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            term TEXT NOT NULL,
            session TEXT NOT NULL,
            next_term_begins DATE NOT NULL,
            next_term_ends DATE,
            vacation_starts DATE,
            vacation_ends DATE,
            fees_due_date DATE,
            registration_starts DATE,
            registration_ends DATE,
            school_hours TEXT,
            assembly_time TEXT,
            closing_time TEXT,
            important_dates TEXT,
            holidays TEXT,
            events_schedule TEXT,
            uniform_requirements TEXT,
            book_list TEXT,
            pta_meeting_date DATE,
            visiting_day DATE,
            sports_day DATE,
            cultural_day DATE,
            excursion_info TEXT,
            health_requirements TEXT,
            contact_person TEXT,
            contact_email TEXT,
            contact_phone TEXT,
            principal_message TEXT,
            special_instructions TEXT,
            bus_schedule TEXT,
            cafeteria_info TEXT,
            library_hours TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by INTEGER,
            FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL,
            UNIQUE(term, session)
        )
    """)
    
    conn.commit()
    conn.close()
    
    # Create performance indexes
    create_performance_indexes()
    
    logger.info("Database tables created successfully")


def create_performance_indexes():
    """Create indexes for better query performance"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
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