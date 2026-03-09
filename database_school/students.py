# database/students.py
"""
Student management — master registry and per-session enrollment.

CONCEPTS
════════
• students table  = master registry. One row per student, ever.
  student_name is the natural key used across all related tables.

• class_session_students = enrollment. Links a student to a
  class_session (class + academic year). Replaces the old per-term
  student registration. Done ONCE per session — valid all 3 terms.

• IMPORT / PROMOTION: use import_students_from_class() to bulk-enroll
  students from a previous class into a new one (e.g. P4 → P5).
"""

import sqlite3
import logging
from .connection import get_connection

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════
# Master student registry
# ═════════════════════════════════════════════════════════════════

def create_student(student_name: str, gender: str = None,
                   email: str = None, date_of_birth: str = None,
                   admission_number: str = None,
                   school_fees_paid: str = "NO") -> bool:
    """
    Add a new student to the master registry.
    Returns True on success, False if name or admission_number already exists.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO students
                (student_name, gender, email, date_of_birth,
                 admission_number, school_fees_paid)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (student_name.strip(), gender, email,
              date_of_birth, admission_number, school_fees_paid))
        conn.commit()
        logger.info(f"Student '{student_name}' added to master registry")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Student '{student_name}' already exists")
        return False
    except Exception as e:
        logger.error(f"Error creating student: {e}")
        return False
    finally:
        conn.close()


def get_all_students() -> list:
    """
    Return every student in the master registry, ordered by name.
    Returns list of dicts:
        {id, student_name, gender, email, date_of_birth,
         admission_number, school_fees_paid, created_at}
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, student_name, gender, email, date_of_birth,
               admission_number, school_fees_paid, created_at
        FROM   students
        ORDER  BY student_name
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def student_exists(student_name: str) -> bool:
    """Return True if a student with this name exists."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM students WHERE student_name = ?", (student_name,))
    result = cursor.fetchone() is not None
    conn.close()
    return result


def update_student(student_name: str, new_name: str = None,
                   gender: str = None, email: str = None,
                   date_of_birth: str = None,
                   admission_number: str = None,
                   school_fees_paid: str = None) -> bool:
    """
    Update student details.
    Renaming student_name cascades to class_session_students,
    scores, comments etc. via ON UPDATE CASCADE.
    Returns True on success, False on conflict or error.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        updates = {}
        if new_name and new_name.strip() != student_name:
            updates["student_name"] = new_name.strip()
        if gender is not None:
            updates["gender"] = gender
        if email is not None:
            updates["email"] = email
        if date_of_birth is not None:
            updates["date_of_birth"] = date_of_birth
        if admission_number is not None:
            updates["admission_number"] = admission_number
        if school_fees_paid is not None:
            updates["school_fees_paid"] = school_fees_paid

        if not updates:
            return True  # nothing to update

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [student_name]
        cursor.execute(
            f"UPDATE students SET {set_clause} WHERE student_name = ?",
            values
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Update failed for '{student_name}' — conflict on unique field")
        return False
    except Exception as e:
        logger.error(f"Error updating student: {e}")
        return False
    finally:
        conn.close()


def delete_student(student_name: str) -> bool:
    """
    Delete a student from the master registry.
    CASCADE removes all their enrollments, scores, comments, etc.
    Use with caution — destroys all historical data for this student.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM students WHERE student_name = ?", (student_name,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error deleting student: {e}")
        return False
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════
# Enrollment (class_session_students)
# ═════════════════════════════════════════════════════════════════

def enroll_student(student_name: str, class_name: str,
                   session: str) -> tuple:
    """
    Enroll a student in a class for a session.
    Auto-creates the student in the master registry if not already there.
    The enrollment is valid for all three terms of the session.

    Args:
        student_name: student's full name
        class_name:   must have an open class_sessions row for this session
        session:      e.g. "2024/2025"

    Returns:
        (True, enrollment_id) on success
        (False, reason_string) on failure
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Ensure student exists in master registry
        cursor.execute(
            "INSERT OR IGNORE INTO students (student_name) VALUES (?)",
            (student_name.strip(),)
        )

        # Resolve class_session_id
        cursor.execute("""
            SELECT id FROM class_sessions
            WHERE class_name = ? AND session = ?
        """, (class_name, session))
        row = cursor.fetchone()
        if not row:
            return (
                False,
                f"'{class_name}' is not open for session '{session}'. "
                "Ask an admin to open it first."
            )
        class_session_id = row[0]

        # Enroll (idempotent)
        cursor.execute("""
            INSERT OR IGNORE INTO class_session_students
                (class_session_id, student_name, class_name, session)
            VALUES (?, ?, ?, ?)
        """, (class_session_id, student_name.strip(), class_name, session))
        conn.commit()

        # Return enrollment id
        cursor.execute("""
            SELECT id FROM class_session_students
            WHERE class_session_id = ? AND student_name = ?
        """, (class_session_id, student_name.strip()))
        enrollment_id = cursor.fetchone()[0]
        logger.info(f"Enrolled '{student_name}' in '{class_name}' / '{session}'")
        return True, enrollment_id
    except Exception as e:
        logger.error(f"Error enrolling student: {e}")
        return False, str(e)
    finally:
        conn.close()


def bulk_enroll_students(student_names: list, class_name: str,
                          session: str) -> dict:
    """
    Enroll multiple students at once.
    Returns dict: {enrolled: [names], skipped: [names], errors: [{name, reason}]}
    """
    results = {"enrolled": [], "skipped": [], "errors": []}
    for name in student_names:
        name = name.strip()
        if not name:
            continue
        ok, detail = enroll_student(name, class_name, session)
        if ok:
            results["enrolled"].append(name)
        else:
            results["errors"].append({"name": name, "reason": detail})
    return results


def unenroll_student(student_name: str, class_name: str,
                     session: str) -> bool:
    """
    Remove a student's enrollment from a class-session.
    CASCADE deletes all their scores, comments, subject selections
    for that session across all three terms.
    USE WITH CAUTION.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM class_session_students
            WHERE student_name = ?
              AND class_session_id = (
                  SELECT id FROM class_sessions
                  WHERE class_name = ? AND session = ?
              )
        """, (student_name, class_name, session))
        conn.commit()
        deleted = cursor.rowcount
        if deleted:
            logger.info(f"Unenrolled '{student_name}' from '{class_name}' / '{session}'")
        return deleted > 0
    except Exception as e:
        logger.error(f"Error unenrolling student: {e}")
        return False
    finally:
        conn.close()


def get_enrolled_students(class_name: str, session: str) -> list:
    """
    Return all students enrolled in a class for a session.
    Returns list of dicts:
        {enrollment_id, student_name, class_name, session,
         gender, admission_number, school_fees_paid, enrollment_date}
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            css.id              AS enrollment_id,
            css.student_name,
            css.class_name,
            css.session,
            s.gender,
            s.admission_number,
            s.school_fees_paid,
            css.enrollment_date
        FROM  class_session_students css
        JOIN  students s           ON s.student_name = css.student_name
        JOIN  class_sessions cs    ON cs.id = css.class_session_id
        WHERE cs.class_name = ? AND cs.session = ?
        ORDER BY css.student_name
    """, (class_name, session))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_enrollment_id(student_name: str, class_name: str,
                      session: str) -> int | None:
    """
    Return class_session_students.id for a student in a class/session.
    Used as the FK when writing scores, comments, psychomotor, etc.
    Returns None if student is not enrolled.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT css.id
        FROM   class_session_students css
        JOIN   class_sessions cs ON cs.id = css.class_session_id
        WHERE  css.student_name = ?
          AND  cs.class_name   = ?
          AND  cs.session      = ?
    """, (student_name, class_name, session))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def get_students_not_enrolled_in(class_name: str, session: str) -> list:
    """
    Return master registry students NOT yet enrolled in this class/session.
    Useful for the 'add students' picker UI.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.student_name, s.gender, s.admission_number
        FROM   students s
        WHERE  s.student_name NOT IN (
            SELECT css.student_name
            FROM   class_session_students css
            JOIN   class_sessions cs ON cs.id = css.class_session_id
            WHERE  cs.class_name = ? AND cs.session = ?
        )
        ORDER BY s.student_name
    """, (class_name, session))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ═════════════════════════════════════════════════════════════════
# Student import / promotion
# ═════════════════════════════════════════════════════════════════

def import_students_from_class(source_class: str, source_session: str,
                                target_class: str, target_session: str) -> dict:
    """
    Copy student enrollments from one class-session to another.

    Typical use: promotion.  E.g. copy all "Primary 4 / 2024-2025"
    students into "Primary 5 / 2025-2026".

    Target class_session must already exist (admin opens it first).
    Existing enrollments in the target are skipped (INSERT OR IGNORE).

    Returns:
        dict: {imported: int, skipped: int, error: str or None}
    """
    source_students = get_enrolled_students(source_class, source_session)
    if not source_students:
        return {
            "imported": 0, "skipped": 0,
            "error": f"No students found in '{source_class}' / '{source_session}'."
        }

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Verify target class_session exists
        cursor.execute("""
            SELECT id FROM class_sessions
            WHERE class_name = ? AND session = ?
        """, (target_class, target_session))
        row = cursor.fetchone()
        if not row:
            return {
                "imported": 0, "skipped": 0,
                "error": (
                    f"'{target_class}' is not open for session '{target_session}'. "
                    "Open it first."
                )
            }
        target_cs_id = row[0]

        imported = skipped = 0
        for s in source_students:
            name = s["student_name"]
            cursor.execute(
                "INSERT OR IGNORE INTO students (student_name) VALUES (?)", (name,)
            )
            cursor.execute("""
                INSERT OR IGNORE INTO class_session_students
                    (class_session_id, student_name, class_name, session)
                VALUES (?, ?, ?, ?)
            """, (target_cs_id, name, target_class, target_session))
            if cursor.rowcount:
                imported += 1
            else:
                skipped += 1

        conn.commit()
        logger.info(
            f"Imported {imported} students from "
            f"'{source_class}/{source_session}' → '{target_class}/{target_session}'"
        )
        return {"imported": imported, "skipped": skipped, "error": None}
    except Exception as e:
        logger.error(f"Error importing students: {e}")
        return {"imported": 0, "skipped": 0, "error": str(e)}
    finally:
        conn.close()
