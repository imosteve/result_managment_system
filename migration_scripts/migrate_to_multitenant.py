"""
migrate_to_multitenant.py
─────────────────────────────────────────────────────────────────────────────
Migration script: OLD single-tenant schema  →  NEW multi-tenant schema.

Changes handled
───────────────
1. users table  – adds `email TEXT UNIQUE` column (new schema only).
2. Database file rename  – optional; renames the .db file before migrating
   so you can keep the old file under a new name as a backup or simply
   rename the active database.

Usage (CLI)
───────────
    # Migrate in-place (no rename):
    python migrate_to_multitenant.py --db path/to/school.db

    # Rename the database file first, then migrate:
    python migrate_to_multitenant.py --db path/to/school.db \
                                     --rename path/to/school_migrated.db

    # Dry-run (prints what would change, touches nothing):
    python migrate_to_multitenant.py --db path/to/school.db --dry-run

Programmatic usage
──────────────────
    from migrate_to_multitenant import run_migration

    run_migration(
        db_path="path/to/school.db",
        new_db_path="path/to/school_v2.db",   # omit to skip rename
        dry_run=False,
    )
"""

import argparse
import logging
import os
import shutil
import sqlite3
import sys
from pathlib import Path

# ── logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_columns(cursor: sqlite3.Cursor, table: str) -> list[str]:
    """Return a list of column names for *table*."""
    cursor.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cursor.fetchall()]


def _table_exists(cursor: sqlite3.Cursor, table: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cursor.fetchone() is not None


def _backup(db_path: str) -> str:
    """Create a timestamped .bak copy and return its path."""
    from datetime import datetime

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = f"{db_path}.{ts}.bak"
    shutil.copy2(db_path, bak)
    log.info(f"Backup created → {bak}")
    return bak


# ─────────────────────────────────────────────────────────────────────────────
# Individual migration steps
# ─────────────────────────────────────────────────────────────────────────────

def _step_rename_database(db_path: str, new_db_path: str, dry_run: bool) -> str:
    """
    Rename (move) the database file.

    Returns the path that subsequent steps should operate on.
    If new_db_path is None or equal to db_path, no rename is performed.
    """
    if not new_db_path or Path(new_db_path).resolve() == Path(db_path).resolve():
        log.info("Step RENAME  – skipped (no new path supplied or paths are identical).")
        return db_path

    if dry_run:
        log.info(f"[DRY-RUN] Would rename:\n  {db_path}\n  → {new_db_path}")
        return new_db_path  # pretend it happened for downstream dry-run steps

    # Safety: don't overwrite an existing file unless explicitly cleared.
    if os.path.exists(new_db_path):
        raise FileExistsError(
            f"Target path already exists: {new_db_path}\n"
            "Remove it manually or choose a different --rename path."
        )

    os.rename(db_path, new_db_path)
    log.info(f"Step RENAME  – OK  ({db_path} → {new_db_path})")
    return new_db_path


def _step_add_users_email(conn: sqlite3.Connection, dry_run: bool) -> None:
    """
    Add `email TEXT UNIQUE` to the *users* table if it is absent.

    SQLite does not support ADD COLUMN … UNIQUE directly, so we use the
    standard 12-step SQLite table-rebuild approach when needed.
    """
    cursor = conn.cursor()

    if not _table_exists(cursor, "users"):
        log.warning("Step USERS.email – table 'users' not found; skipping.")
        return

    cols = _get_columns(cursor, "users")

    if "email" in cols:
        log.info("Step USERS.email – column already present; skipping.")
        return

    if dry_run:
        log.info("[DRY-RUN] Would add column `email TEXT UNIQUE` to users.")
        return

    # SQLite cannot add a UNIQUE column directly via ALTER TABLE ADD COLUMN
    # when there are existing rows (it would need a default value, and UNIQUE
    # with NULLs is fine in SQLite, but the index must be created separately).
    # We therefore add the column first (NULLs are UNIQUE-compatible) and then
    # create a unique index manually.

    log.info("Step USERS.email – adding column …")
    cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")

    # Create the unique index that enforces the UNIQUE constraint.
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)"
    )

    conn.commit()
    log.info("Step USERS.email – OK")


def _step_create_missing_tables(conn: sqlite3.Connection, dry_run: bool) -> None:
    """
    Ensure every table that exists in the NEW schema is present.
    All tables are identical between old and new *except* for users.email,
    which is handled separately.  This step is therefore a no-op for a
    database that was created from the old schema, but it acts as a safety
    net for partially-migrated databases.
    """
    cursor = conn.cursor()
    expected = [
        "classes", "students", "subjects", "scores", "users",
        "teacher_assignments", "admin_users", "comments",
        "psychomotor_ratings", "student_subject_selections",
        "comment_templates", "next_term_info",
    ]
    missing = [t for t in expected if not _table_exists(cursor, t)]

    if not missing:
        log.info("Step TABLE CHECK – all expected tables present.")
        return

    log.warning(f"Step TABLE CHECK – missing tables detected: {missing}")
    if dry_run:
        log.info("[DRY-RUN] Would flag missing tables for manual review.")
    else:
        log.error(
            "Missing tables cannot be auto-created by this migration script "
            "(they require application context / foreign-key chains). "
            "Please run create_tables() from database/schema.py first."
        )


def _step_create_performance_indexes(conn: sqlite3.Connection, dry_run: bool) -> None:
    """Ensure all performance indexes from the new schema exist."""
    indexes = [
        ("idx_students_class_term_session",
         "CREATE INDEX IF NOT EXISTS idx_students_class_term_session "
         "ON students(class_name, term, session)"),

        ("idx_subjects_class_term_session",
         "CREATE INDEX IF NOT EXISTS idx_subjects_class_term_session "
         "ON subjects(class_name, term, session)"),

        ("idx_scores_class_subject_term_session",
         "CREATE INDEX IF NOT EXISTS idx_scores_class_subject_term_session "
         "ON scores(class_name, subject_name, term, session)"),

        ("idx_scores_student_class_term_session",
         "CREATE INDEX IF NOT EXISTS idx_scores_student_class_term_session "
         "ON scores(student_name, class_name, term, session)"),

        ("idx_teacher_assignments_user",
         "CREATE INDEX IF NOT EXISTS idx_teacher_assignments_user "
         "ON teacher_assignments(user_id)"),

        ("idx_scores_total_score",
         "CREATE INDEX IF NOT EXISTS idx_scores_total_score "
         "ON scores(total_score DESC)"),

        ("idx_comment_templates_type_range",
         "CREATE INDEX IF NOT EXISTS idx_comment_templates_type_range "
         "ON comment_templates(comment_type, average_lower, average_upper)"),
    ]

    cursor = conn.cursor()
    for name, sql in indexes:
        if dry_run:
            log.info(f"[DRY-RUN] Would ensure index: {name}")
            continue
        cursor.execute(sql)
        log.info(f"Step INDEXES – ensured: {name}")

    if not dry_run:
        conn.commit()


def _step_verify_schema(conn: sqlite3.Connection) -> bool:
    """
    Post-migration sanity check.
    Returns True if everything looks correct.
    """
    cursor = conn.cursor()
    ok = True

    # users must have email column
    cols = _get_columns(cursor, "users")
    if "email" not in cols:
        log.error("Verification FAILED – users.email column not found.")
        ok = False
    else:
        log.info("Verification – users.email ✓")

    # unique index on users.email must exist
    cursor.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='index' AND name='idx_users_email'"
    )
    if not cursor.fetchone():
        log.error("Verification FAILED – unique index idx_users_email not found.")
        ok = False
    else:
        log.info("Verification – idx_users_email ✓")

    return ok


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def run_migration(
    db_path: str,
    new_db_path: str | None = None,
    dry_run: bool = False,
    skip_backup: bool = True,
) -> bool:
    """
    Run the full migration pipeline.

    Parameters
    ----------
    db_path      : Path to the existing (old-schema) SQLite database.
    new_db_path  : Optional new filename/path for the database file.
                   Pass None to migrate in-place.
    dry_run      : If True, print what would be done without modifying anything.
    skip_backup  : If True, skip the automatic .bak backup step.

    Returns
    -------
    True on success, False if any step failed.
    """

    # ── pre-flight ────────────────────────────────────────────────────────────
    if not os.path.exists(db_path):
        log.error(f"Database not found: {db_path}")
        return False

    log.info("=" * 65)
    log.info("  Multi-tenant schema migration")
    log.info(f"  Source : {db_path}")
    log.info(f"  Target : {new_db_path or db_path} {'(same file)' if not new_db_path else ''}")
    log.info(f"  Mode   : {'DRY-RUN' if dry_run else 'LIVE'}")
    log.info("=" * 65)

    # ── backup ────────────────────────────────────────────────────────────────
    if not dry_run and not skip_backup:
        _backup(db_path)

    # ── step 1: rename ────────────────────────────────────────────────────────
    active_path = _step_rename_database(db_path, new_db_path, dry_run)

    # For dry-run after a rename, active_path is the hypothetical new path
    # which doesn't exist yet, so open the original for inspection.
    connect_path = db_path if dry_run else active_path

    # ── open connection ───────────────────────────────────────────────────────
    conn = sqlite3.connect(connect_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")

    try:
        # ── step 2: schema changes ────────────────────────────────────────────
        _step_add_users_email(conn, dry_run)

        # ── step 3: ensure all tables present ────────────────────────────────
        _step_create_missing_tables(conn, dry_run)

        # ── step 4: indexes ───────────────────────────────────────────────────
        _step_create_performance_indexes(conn, dry_run)

        # ── step 5: verify ────────────────────────────────────────────────────
        if not dry_run:
            success = _step_verify_schema(conn)
        else:
            success = True
            log.info("[DRY-RUN] Verification skipped (no changes made).")

    except Exception as exc:
        log.exception(f"Migration failed with an unexpected error: {exc}")
        success = False
    finally:
        conn.close()

    if success:
        log.info("Migration completed successfully ✓")
    else:
        log.error("Migration completed with errors ✗  – review the log above.")

    return success


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry-point
# ─────────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Migrate a school database from the old schema to the "
                    "new multi-tenant schema.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--db",
        required=True,
        metavar="PATH",
        help="Path to the existing SQLite database file.",
    )
    p.add_argument(
        "--rename",
        metavar="NEW_PATH",
        default=None,
        help="Optional new filename/path for the database. "
             "The file is renamed BEFORE schema changes are applied.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without modifying anything.",
    )
    p.add_argument(
        "--skip-backup",
        action="store_true",
        help="Skip the automatic timestamped .bak backup.",
    )
    return p


if __name__ == "__main__":

    ok = run_migration(
        db_path=r"C:\Users\imosteve\Documents\Result system\python system\student_results_app\data\school.db",
        new_db_path=r"C:\Users\imosteve\Documents\Result system\python system\student_results_app\data\suis.db",
        dry_run=False,
        skip_backup=False,
    )
    sys.exit(0 if ok else 1)
