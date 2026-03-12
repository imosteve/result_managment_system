# database_school/scores.py - UPDATED
"""
Score management — per-term, per-enrollment score entry and retrieval.

KEY BEHAVIOURS
══════════════
• Scores are keyed by UNIQUE(enrollment_id, subject_name, term).
• Switching to a new term creates NEW rows. Old term rows are untouched.
• save_score() uses ON CONFLICT ... DO UPDATE — calling it twice for the
  same student/subject/term is safe (no duplicates).
• grade and position are stored alongside scores (same as old schema).
  Use recalculate_positions() after a full subject's scores are saved.
• total_score is a GENERATED column (ca_score + exam_score) — never
  insert it directly.
"""

import sqlite3
import logging
from .connection import get_connection
from .students import get_enrollment_id

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════
# Write
# ═════════════════════════════════════════════════════════════════

def save_score(student_name: str, class_name: str, session: str,
               term: str, subject_name: str,
               ca_score: float, exam_score: float,
               grade: str = None, updated_by: str = "") -> bool:
    """
    Insert or update a score for one student/subject/term.

    Args:
        student_name, class_name, session: identify the enrollment
        term:         "First", "Second", or "Third"
        subject_name: subject being scored
        ca_score:     continuous assessment score
        exam_score:   examination score
        grade:        optional grade string (e.g. "A", "B"). Can be
                      computed and passed in, or set later via
                      recalculate_positions().
        updated_by:   username saving the score

    Returns True on success, False if enrollment not found or DB error.
    NOTE: total_score is auto-computed by the DB (ca_score + exam_score).
          Do NOT pass it as an argument.
    """
    enrollment_id = get_enrollment_id(student_name, class_name, session, term)
    if enrollment_id is None:
        logger.error(
            f"save_score: no enrollment for '{student_name}' "
            f"in '{class_name}' / '{session}'"
        )
        return False

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO scores
                (enrollment_id, student_name, class_name, session,
                 term, subject_name, ca_score, exam_score,
                 grade, updated_at, updated_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            ON CONFLICT(enrollment_id, subject_name, term) DO UPDATE SET
                ca_score   = excluded.ca_score,
                exam_score = excluded.exam_score,
                grade      = excluded.grade,
                updated_at = excluded.updated_at,
                updated_by = excluded.updated_by
        """, (
            enrollment_id, student_name, class_name, session,
            term, subject_name, ca_score, exam_score,
            grade, updated_by
        ))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving score: {e}")
        return False
    finally:
        conn.close()


def save_scores_bulk(scores: list, updated_by: str = "") -> dict:
    """
    Save multiple scores in a single transaction.

    Each item in scores must be a dict with keys:
        student_name, class_name, session, term,
        subject_name, ca_score, exam_score
    Optional key: grade

    Returns dict: {saved: int, failed: int, errors: [str]}
    """
    result = {"saved": 0, "failed": 0, "errors": []}
    conn = get_connection()
    cursor = conn.cursor()
    try:
        for s in scores:
            enrollment_id = get_enrollment_id(
                s["student_name"], s["class_name"], s["session"], s["term"]
            )
            if not enrollment_id:
                result["failed"] += 1
                result["errors"].append(
                    f"No enrollment: {s['student_name']} / {s['class_name']} / {s['session']} / {s['term']}"
                )
                continue
            try:
                cursor.execute("""
                    INSERT INTO scores
                        (enrollment_id, student_name, class_name, session,
                         term, subject_name, ca_score, exam_score,
                         grade, updated_at, updated_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                    ON CONFLICT(enrollment_id, subject_name, term) DO UPDATE SET
                        ca_score   = excluded.ca_score,
                        exam_score = excluded.exam_score,
                        grade      = excluded.grade,
                        updated_at = excluded.updated_at,
                        updated_by = excluded.updated_by
                """, (
                    enrollment_id, s["student_name"], s["class_name"],
                    s["session"], s["term"], s["subject_name"],
                    s.get("ca_score", 0), s.get("exam_score", 0),
                    s.get("grade"), updated_by
                ))
                result["saved"] += 1
            except Exception as e:
                result["failed"] += 1
                result["errors"].append(str(e))
        conn.commit()
    except Exception as e:
        logger.error(f"Bulk save error: {e}")
        result["errors"].append(str(e))
    finally:
        conn.close()
    return result


def recalculate_positions(class_name: str, session: str,
                           term: str, subject_name: str) -> bool:
    """
    Recalculate position rankings for all students in a subject/term.
    Call this after saving a full set of scores for a subject.
    Handles ties (tied students share the same position).

    Returns True on success.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, total_score
            FROM   scores
            WHERE  class_name = ? AND session = ?
              AND  term = ? AND subject_name = ?
            ORDER  BY total_score DESC
        """, (class_name, session, term, subject_name))
        rows = cursor.fetchall()

        for i, (score_id, total_score) in enumerate(rows):
            if i > 0 and total_score == rows[i - 1][1]:
                # Tied — inherit previous position
                cursor.execute(
                    "SELECT position FROM scores WHERE id = ?", (rows[i - 1][0],)
                )
                position = cursor.fetchone()[0]
            else:
                position = i + 1
            cursor.execute(
                "UPDATE scores SET position = ? WHERE id = ?",
                (position, score_id)
            )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error recalculating positions: {e}")
        return False
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════
# Read
# ═════════════════════════════════════════════════════════════════

def get_scores_for_class(class_name: str, session: str, term: str) -> list:
    """
    All scores for a class in a given session and term.
    Primary query for broadsheet / score entry views.

    Returns list of dicts:
        {student_name, subject_name, ca_score, exam_score,
         total_score, grade, position, enrollment_id}
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT student_name, subject_name,
               ca_score, exam_score, total_score,
               grade, position, enrollment_id
        FROM   scores
        WHERE  class_name = ? AND session = ? AND term = ?
        ORDER  BY student_name, subject_name
    """, (class_name, session, term))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_scores_for_student(student_name: str, class_name: str,
                            session: str, term: str) -> list:
    """
    All subject scores for one student in a given term.

    Returns list of dicts:
        {subject_name, ca_score, exam_score, total_score, grade, position}
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT subject_name, ca_score, exam_score,
               total_score, grade, position
        FROM   scores
        WHERE  student_name = ? AND class_name = ?
          AND  session = ? AND term = ?
        ORDER  BY subject_name
    """, (student_name, class_name, session, term))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_scores_for_subject(class_name: str, session: str,
                            term: str, subject_name: str) -> list:
    """
    Scores for a specific subject across all enrolled students.
    Students with no score yet are included with 0s (LEFT JOIN).
    Used by subject teachers entering scores.

    Returns list of dicts:
        {student_name, ca_score, exam_score, total_score,
         grade, position, enrollment_id}
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            css.student_name,
            sc.ca_score,
            sc.exam_score,
            sc.total_score,
            sc.grade,
            sc.position,
            css.id AS enrollment_id
        FROM  class_session_students css
        JOIN  class_sessions cs ON cs.id = css.class_session_id
        LEFT JOIN scores sc
               ON sc.enrollment_id = css.id
              AND sc.subject_name  = ?
              AND sc.term          = ?
        WHERE cs.class_name = ? AND cs.session = ? AND css.term = ?
        ORDER BY css.student_name
    """, (subject_name, term, class_name, session, term))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_student_all_terms(student_name: str, class_name: str,
                           session: str) -> dict:
    """
    All scores across all three terms for a student in one session.
    Used for cumulative / annual report cards.

    Returns dict:
        {
            "First":  {subject_name: {ca_score, exam_score, total_score, grade}, ...},
            "Second": {...},
            "Third":  {...}
        }
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT term, subject_name, ca_score, exam_score, total_score, grade
        FROM   scores
        WHERE  student_name = ? AND class_name = ? AND session = ?
        ORDER  BY term, subject_name
    """, (student_name, class_name, session))
    rows = cursor.fetchall()
    conn.close()

    result = {"First": {}, "Second": {}, "Third": {}}
    for r in rows:
        result[r["term"]][r["subject_name"]] = {
            "ca_score":    r["ca_score"],
            "exam_score":  r["exam_score"],
            "total_score": r["total_score"],
            "grade":       r["grade"],
        }
    return result

def get_grade_distribution(student_name: str, class_name: str,
                            session: str, term: str) -> str:
    """
    Return a grade-distribution summary string for a student in one term.
    For SSS2/SSS3: only counts subjects the student selected.
    Used by the broadsheet and report-card views.
    """
    import re as _re
    is_senior = bool(_re.match(r"SSS [23]", class_name))

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if is_senior:
        cursor.execute("""
            SELECT sc.total_score
            FROM   scores sc
            JOIN   class_session_students css
                       ON css.student_name = sc.student_name
                      AND css.term         = sc.term
            JOIN   class_sessions cs ON cs.id = css.class_session_id
            JOIN   student_subject_selections sss
                       ON sss.enrollment_id = css.id
                      AND sss.subject_name  = sc.subject_name
                      AND sss.term          = sc.term
            WHERE  sc.student_name = ? AND sc.class_name = ?
              AND  sc.session = ? AND sc.term = ?
              AND  cs.class_name = ? AND cs.session = ?
        """, (student_name, class_name, session, term, class_name, session))
    else:
        cursor.execute("""
            SELECT total_score FROM scores
            WHERE  student_name = ? AND class_name = ?
              AND  session = ? AND term = ?
        """, (student_name, class_name, session, term))

    scores = cursor.fetchall()
    conn.close()

    if not scores:
        return ""

    grade_order = ["A", "B", "C", "D", "E", "F"]
    counts: dict[str, int] = {}

    for row in scores:
        total = row["total_score"] or 0
        if total >= 80:
            grade = "A"
        elif total >= 70:
            grade = "B"
        elif total >= 60:
            grade = "C"
        elif total >= 50:
            grade = "D"
        elif total >= 45:
            grade = "E"
        else:
            grade = "F"
        counts[grade] = counts.get(grade, 0) + 1

    parts = [f"{counts[g]}{g}s" if counts[g] > 1 else f"{counts[g]}{g}" for g in grade_order if g in counts]
    return ", ".join(parts)


def get_student_grand_totals(class_name: str, session: str, term: str) -> list:
    """
    Grand totals and overall ranks for all students in a class/term.
    For SSS2/SSS3: only counts subjects the student actually selected,
    so unselected subjects never inflate or deflate the total.
    For all other classes: sums all scored subjects.

    Returns list of dicts:
        {student_name, grand_total, position}
    """
    import re as _re
    is_senior = bool(_re.match(r"SSS [23]", class_name))

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if is_senior:
        cursor.execute("""
            SELECT sc.student_name, SUM(sc.total_score) AS grand_total
            FROM   scores sc
            JOIN   class_session_students css
                       ON css.student_name = sc.student_name
                      AND css.term         = sc.term
            JOIN   class_sessions cs ON cs.id = css.class_session_id
            JOIN   student_subject_selections sss
                       ON sss.enrollment_id = css.id
                      AND sss.subject_name  = sc.subject_name
                      AND sss.term          = sc.term
            WHERE  sc.class_name = ? AND sc.session = ? AND sc.term = ?
              AND  cs.class_name = ? AND cs.session = ?
            GROUP  BY sc.student_name
            ORDER  BY grand_total DESC
        """, (class_name, session, term, class_name, session))
    else:
        cursor.execute("""
            SELECT student_name, SUM(total_score) AS grand_total
            FROM   scores
            WHERE  class_name = ? AND session = ? AND term = ?
            GROUP  BY student_name
            ORDER  BY grand_total DESC
        """, (class_name, session, term))
    rows = cursor.fetchall()
    conn.close()

    result = []
    current_rank = 1
    previous_total = None
    for i, r in enumerate(rows):
        if r["grand_total"] != previous_total:
            current_rank = i + 1
        result.append({
            "student_name": r["student_name"],
            "grand_total":  r["grand_total"],
            "position":     current_rank,
        })
        previous_total = r["grand_total"]
    return result


def has_scores_for_term(class_name: str, session: str, term: str) -> bool:
    """Return True if any scores exist for this class/session/term."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 1 FROM scores
        WHERE class_name = ? AND session = ? AND term = ?
        LIMIT 1
    """, (class_name, session, term))
    result = cursor.fetchone() is not None
    conn.close()
    return result


def get_student_average(student_name: str, class_name: str,
                         session: str, term: str) -> float:
    """Return a student's average total_score across all subjects in a term."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT AVG(total_score) FROM scores
        WHERE student_name = ? AND class_name = ?
          AND session = ? AND term = ?
    """, (student_name, class_name, session, term))
    row = cursor.fetchone()
    conn.close()
    return round(row[0], 2) if row and row[0] is not None else 0.0


# ═════════════════════════════════════════════════════════════════
# Delete
# ═════════════════════════════════════════════════════════════════

def delete_score(student_name: str, class_name: str, session: str,
                 term: str, subject_name: str) -> bool:
    """Delete a single score row."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM scores
            WHERE student_name = ? AND class_name = ?
              AND session = ? AND term = ? AND subject_name = ?
        """, (student_name, class_name, session, term, subject_name))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error deleting score: {e}")
        return False
    finally:
        conn.close()


def delete_scores_for_term(class_name: str, session: str, term: str) -> int:
    """
    Delete ALL scores for a class in a specific term.
    Returns row count deleted. Admin-only operation.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM scores
            WHERE class_name = ? AND session = ? AND term = ?
        """, (class_name, session, term))
        conn.commit()
        deleted = cursor.rowcount
        logger.warning(
            f"Deleted {deleted} scores for '{class_name}' / '{session}' / '{term}'"
        )
        return deleted
    except Exception as e:
        logger.error(f"Error deleting term scores: {e}")
        return 0
    finally:
        conn.close()