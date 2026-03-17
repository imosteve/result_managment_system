# database_school/score_system.py
"""
Per-class, per-term score system management.

Stored in class_term_score_systems table:
    UNIQUE(class_name, term)  →  max_ca_score, max_exam_score

Valid systems:
    30/70 — 30 CA + 70 Exam  (default; also means "not yet explicitly set")
    40/60 — 40 CA + 60 Exam

Design rationale:
    Different terms can legitimately use different score systems.
    Stored separately from subjects so subjects stay session/term-independent.
    Schema uses CREATE TABLE IF NOT EXISTS — safe on first boot for new DBs.
    For existing DBs, schema.py's create_tables() is called at startup and
    will create the table automatically via CREATE TABLE IF NOT EXISTS.
"""

import sqlite3
import logging
from .connection import get_connection

logger = logging.getLogger(__name__)

#: The two supported systems. Key = display label used in UI.
SCORE_SYSTEMS = {
    "30/70": {"max_ca": 30, "max_exam": 70, "label": "30 CA / 70 Exam"},
    "40/60": {"max_ca": 40, "max_exam": 60, "label": "40 CA / 60 Exam"},
}

# Default values when no record exists — 30/70 is the standard system
_DEFAULT_CA   = 30
_DEFAULT_EXAM = 70


def get_class_score_system(class_name: str, term: str) -> dict:
    """
    Return the score system for a class/term.

    Always returns a dict — never None.
    If no explicit record exists, returns the default (30/70).
    30/70 is a valid system, not a "not set" state.

    Returns dict with keys:
        max_ca_score  (int)
        max_exam_score (int)
        system_key    ("30/70" or "40/60")
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT max_ca_score, max_exam_score
            FROM   class_term_score_systems
            WHERE  class_name = ? AND term = ?
        """, (class_name, term))
        row = cursor.fetchone()
    except Exception as e:
        logger.error(f"get_class_score_system error for '{class_name}'/'{term}': {e}")
        row = None
    finally:
        conn.close()

    if row:
        max_ca   = int(row["max_ca_score"])
        max_exam = int(row["max_exam_score"])
    else:
        max_ca   = _DEFAULT_CA
        max_exam = _DEFAULT_EXAM

    key = "40/60" if max_ca == 40 else "30/70"
    return {
        "max_ca_score":  max_ca,
        "max_exam_score": max_exam,
        "system_key":    key,
    }


def set_class_score_system(class_name: str, term: str,
                            max_ca: int, max_exam: int) -> bool:
    """
    Create or replace the score system for a class/term.

    Args:
        class_name: Target class
        term:       "First", "Second", or "Third"
        max_ca:     CA ceiling  — must be 30 or 40
        max_exam:   Exam ceiling — must be 60 or 70

    Returns True on success, False on invalid values or DB error.
    """
    if max_ca not in (30, 40) or max_exam not in (60, 70):
        logger.error(
            f"set_class_score_system: invalid system {max_ca}/{max_exam}"
        )
        return False
    if max_ca + max_exam != 100:
        logger.error(f"set_class_score_system: {max_ca}+{max_exam} != 100")
        return False

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO class_term_score_systems
                (class_name, term, max_ca_score, max_exam_score, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(class_name, term) DO UPDATE SET
                max_ca_score   = excluded.max_ca_score,
                max_exam_score = excluded.max_exam_score,
                updated_at     = CURRENT_TIMESTAMP
        """, (class_name, term, max_ca, max_exam))
        conn.commit()
        logger.info(
            f"Score system set for '{class_name}' / '{term}': {max_ca}/{max_exam}"
        )
        return True
    except Exception as e:
        logger.error(f"set_class_score_system error: {e}")
        return False
    finally:
        conn.close()


def get_all_score_systems_for_class(class_name: str) -> dict:
    """
    Return the score system for all three terms for a class.

    Returns dict keyed by term:
        {"First": {...}, "Second": {...}, "Third": {...}}
    Each value has the same shape as get_class_score_system().
    """
    return {
        term: get_class_score_system(class_name, term)
        for term in ("First", "Second", "Third")
    }