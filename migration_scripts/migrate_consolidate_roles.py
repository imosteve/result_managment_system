"""
migrate_consolidate_roles.py
─────────────────────────────────────────────────────────────────────────────
Migration: Drop admin_users table and consolidate role management.

What this migration does
────────────────────────
OLD design
  • users.role  = 'class_teacher' (default) | 'superadmin' | 'admin'
                  (column existed but was often ignored — real roles were
                   driven by admin_users table)
  • admin_users table  = (user_id, role) for 'superadmin' and 'admin' only

NEW design
  • users.role  = 'teacher' (default) | 'superadmin' | 'admin'
                  — single source of truth, no separate admin_users table
  • admin_users table  = DROPPED

Steps
─────
  1. Rename database file (optional --rename flag)
  2. Backup current database
  3. Add users.role column if absent  (DEFAULT 'class_teacher' as intermediate)
  4. Add users.email column if absent
  5. Populate NULL/empty emails as  username@suis.edu.ng
  6. Copy roles from admin_users → users.role  (superadmin / admin)
  7. Set users.role = 'teacher' for all rows not in admin_users
  8. Rebuild users table to finalise CHECK constraint & DEFAULT 'teacher'
     (SQLite requires a full table rebuild for this — 12-step approach)
  9. Drop the admin_users table
  10. Re-create performance indexes
  11. Verify

Usage (CLI)
───────────
    # Migrate in-place:
    python migrate_consolidate_roles.py --db path/to/suis.db

    # Rename first, then migrate:
    python migrate_consolidate_roles.py --db path/to/suis.db \\
                                        --rename path/to/suis_v2.db

    # Dry-run (no changes):
    python migrate_consolidate_roles.py --db path/to/suis.db --dry-run

Programmatic usage
──────────────────
    from migrate_consolidate_roles import run_migration

    run_migration(
        db_path="path/to/suis.db",
        new_db_path=None,   # omit to skip rename
        dry_run=False,
    )
"""

import argparse
import logging
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _table_exists(cursor: sqlite3.Cursor, table: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cursor.fetchone() is not None


def _get_columns(cursor: sqlite3.Cursor, table: str) -> list[str]:
    cursor.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cursor.fetchall()]


def _backup(db_path: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = f"{db_path}.{ts}.bak"
    shutil.copy2(db_path, bak)
    log.info(f"Backup created → {bak}")
    return bak


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — optional rename
# ─────────────────────────────────────────────────────────────────────────────

def _step_rename(db_path: str, new_db_path: str | None, dry_run: bool) -> str:
    if not new_db_path or Path(new_db_path).resolve() == Path(db_path).resolve():
        log.info("Step RENAME        – skipped (no new path supplied).")
        return db_path

    if dry_run:
        log.info(f"[DRY-RUN] Would rename:\n  {db_path}\n  → {new_db_path}")
        return new_db_path

    if os.path.exists(new_db_path):
        raise FileExistsError(
            f"Target path already exists: {new_db_path}\n"
            "Remove it manually or choose a different --rename path."
        )

    os.rename(db_path, new_db_path)
    log.info(f"Step RENAME        – OK  ({db_path} → {new_db_path})")
    return new_db_path


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — add users.role column if absent
#
# The OLD schema had no role column at all.  We add it here with the
# intermediate CHECK ('superadmin','admin','class_teacher') so that the
# subsequent copy-roles UPDATE (which writes 'superadmin'/'admin') passes
# the constraint.  The final rebuild in Step 7 changes this to 'teacher'.
# ─────────────────────────────────────────────────────────────────────────────

def _step_add_role_column(conn: sqlite3.Connection, dry_run: bool):
    cursor = conn.cursor()
    cols = _get_columns(cursor, "users")

    if "role" in cols:
        log.info("Step ADD role      – column already present; skipping.")
        return

    if dry_run:
        log.info(
            "[DRY-RUN] Would ADD COLUMN role TEXT DEFAULT 'class_teacher' "
            "CHECK(role IN ('superadmin','admin','class_teacher')) to users."
        )
        return

    # SQLite ADD COLUMN cannot include a CHECK inline, but we can add the
    # column with a default and enforce the constraint via the table rebuild
    # in Step 7.  The intermediate default 'class_teacher' is intentional —
    # it matches the old schema intent and will be coerced to 'teacher' later.
    cursor.execute(
        "ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'class_teacher'"
    )
    conn.commit()
    log.info("Step ADD role      – OK  (role column added with DEFAULT 'class_teacher')")


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — add users.email column if absent
# ─────────────────────────────────────────────────────────────────────────────

def _step_add_email_column(conn: sqlite3.Connection, dry_run: bool):
    cursor = conn.cursor()
    cols = _get_columns(cursor, "users")

    if "email" in cols:
        log.info("Step ADD email     – column already present; skipping.")
        return

    if dry_run:
        log.info("[DRY-RUN] Would ADD COLUMN email TEXT to users.")
        return

    cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
    conn.commit()
    log.info("Step ADD email     – OK  (email column added)")


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — populate NULL / empty email as  username@suis.edu.ng
# ─────────────────────────────────────────────────────────────────────────────

EMAIL_DOMAIN = "suis.edu.ng"

def _step_populate_emails(conn: sqlite3.Connection, dry_run: bool):
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, username FROM users
        WHERE email IS NULL OR TRIM(email) = ''
    """)
    rows = cursor.fetchall()

    if not rows:
        log.info("Step EMAILS        – all users already have an email; skipping.")
        return

    if dry_run:
        for uid, username in rows:
            log.info(
                f"[DRY-RUN] Would set email = '{username}@{EMAIL_DOMAIN}' "
                f"for user_id={uid} (username='{username}')"
            )
        return

    for uid, username in rows:
        email = f"{username.lower().strip()}@{EMAIL_DOMAIN}"
        cursor.execute(
            "UPDATE users SET email = ? WHERE id = ?",
            (email, uid)
        )

    conn.commit()
    log.info(f"Step EMAILS        – OK  ({len(rows)} email(s) populated as username@{EMAIL_DOMAIN})")


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — copy roles from admin_users → users.role
# ─────────────────────────────────────────────────────────────────────────────

def _step_copy_roles(conn: sqlite3.Connection, dry_run: bool) -> dict[int, str]:
    """
    Read every row from admin_users and return a mapping {user_id: role}.
    Also logs what would change for dry-run visibility.
    """
    cursor = conn.cursor()

    if not _table_exists(cursor, "admin_users"):
        log.info("Step COPY ROLES    – admin_users table not found; nothing to copy.")
        return {}

    cursor.execute("SELECT user_id, role FROM admin_users")
    rows = cursor.fetchall()

    role_map: dict[int, str] = {row[0]: row[1] for row in rows}

    if not role_map:
        log.info("Step COPY ROLES    – admin_users is empty; nothing to copy.")
        return role_map

    if dry_run:
        for uid, role in role_map.items():
            log.info(f"[DRY-RUN] Would set users.role = '{role}' for user_id={uid}")
        return role_map

    for user_id, role in role_map.items():
        cursor.execute(
            "UPDATE users SET role = ? WHERE id = ?",
            (role, user_id)
        )

    conn.commit()
    log.info(f"Step COPY ROLES    – OK  ({len(role_map)} admin/superadmin rows migrated)")
    return role_map


# ─────────────────────────────────────────────────────────────────────────────
# Step 6 — set remaining users.role = 'teacher'  (were NULL or 'class_teacher')
# ─────────────────────────────────────────────────────────────────────────────

def _step_normalise_teachers(conn: sqlite3.Connection, dry_run: bool):
    cursor = conn.cursor()

    # Count how many rows need updating
    cursor.execute("""
        SELECT COUNT(*) FROM users
        WHERE role IS NULL OR role NOT IN ('superadmin', 'admin')
    """)
    count = cursor.fetchone()[0]

    if count == 0:
        log.info("Step NORMALISE     – all non-admin users already have a valid role.")
        return

    if dry_run:
        log.info(
            f"[DRY-RUN] Would set users.role = 'teacher' "
            f"for {count} row(s) where role IS NULL or 'class_teacher'."
        )
        return

    cursor.execute("""
        UPDATE users
        SET role = 'teacher'
        WHERE role IS NULL OR role NOT IN ('superadmin', 'admin')
    """)
    conn.commit()
    log.info(f"Step NORMALISE     – OK  ({count} teacher rows normalised)")


# ─────────────────────────────────────────────────────────────────────────────
# Step 7 — rebuild users table to update CHECK constraint & default
#
# SQLite cannot ALTER a CHECK constraint or DEFAULT in-place.
# The standard 12-step approach:
#   1.  Create new_users with the correct definition
#   2.  Copy all data across
#   3.  Drop old users
#   4.  Rename new_users → users
#   5.  Re-create any indexes / foreign-key references on users
# ─────────────────────────────────────────────────────────────────────────────

def _step_rebuild_users_table(conn: sqlite3.Connection, dry_run: bool):
    cursor = conn.cursor()

    # Check whether the column definition already matches what we want.
    # We inspect the CREATE TABLE DDL stored in sqlite_master.
    cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
    )
    row = cursor.fetchone()
    if row is None:
        log.error("Step REBUILD USERS – users table not found!")
        return

    existing_ddl: str = row[0]

    # If the DDL already has the new constraint/default, skip.
    if ("DEFAULT 'teacher'" in existing_ddl and
            "'superadmin', 'admin', 'teacher'" in existing_ddl):
        log.info("Step REBUILD USERS – CHECK/DEFAULT already up-to-date; skipping.")
        return

    if dry_run:
        log.info(
            "[DRY-RUN] Would rebuild users table:\n"
            "  • Change DEFAULT 'class_teacher' → DEFAULT 'teacher'\n"
            "  • Change CHECK IN ('superadmin','admin','class_teacher') "
            "→ IN ('superadmin','admin','teacher')"
        )
        return

    # Disable FK checks while we rebuild (re-enabled after COMMIT)
    conn.execute("PRAGMA foreign_keys = OFF")

    try:
        # 1. Create the replacement table
        conn.execute("""
            CREATE TABLE users_new (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT    NOT NULL UNIQUE,
                password   TEXT    NOT NULL,
                email      TEXT    UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                role       TEXT    DEFAULT 'teacher'
                               CHECK(role IN ('superadmin', 'admin', 'teacher'))
            )
        """)

        # 2. Copy every row from the old table
        #    Coerce any legacy 'class_teacher' value to 'teacher' during copy.
        conn.execute("""
            INSERT INTO users_new (id, username, password, email, created_at, role)
            SELECT
                id,
                username,
                password,
                email,
                created_at,
                CASE
                    WHEN role IN ('superadmin', 'admin') THEN role
                    ELSE 'teacher'
                END
            FROM users
        """)

        # 3. Drop the old table
        conn.execute("DROP TABLE users")

        # 4. Rename
        conn.execute("ALTER TABLE users_new RENAME TO users")

        conn.commit()
        log.info("Step REBUILD USERS – OK  (CHECK/DEFAULT updated)")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


# ─────────────────────────────────────────────────────────────────────────────
# Step 8 — drop admin_users table
# ─────────────────────────────────────────────────────────────────────────────

def _step_drop_admin_users(conn: sqlite3.Connection, dry_run: bool):
    cursor = conn.cursor()

    if not _table_exists(cursor, "admin_users"):
        log.info("Step DROP admin_users – table already absent; skipping.")
        return

    if dry_run:
        log.info("[DRY-RUN] Would DROP TABLE admin_users.")
        return

    conn.execute("DROP TABLE admin_users")
    conn.commit()
    log.info("Step DROP admin_users – OK")


# ─────────────────────────────────────────────────────────────────────────────
# Step 9 — re-create performance indexes (they may reference users)
# ─────────────────────────────────────────────────────────────────────────────

def _step_recreate_indexes(conn: sqlite3.Connection, dry_run: bool):
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
        ("idx_users_email",
         "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)"),
    ]

    for name, sql in indexes:
        if dry_run:
            log.info(f"[DRY-RUN] Would ensure index: {name}")
            continue
        conn.execute(sql)
        log.info(f"Step INDEXES       – ensured: {name}")

    if not dry_run:
        conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Step 10 — verify
# ─────────────────────────────────────────────────────────────────────────────

def _step_verify(conn: sqlite3.Connection) -> bool:
    cursor = conn.cursor()
    ok = True

    # No NULL or empty emails should remain
    cursor.execute("""
        SELECT COUNT(*) FROM users
        WHERE email IS NULL OR TRIM(email) = ''
    """)
    null_email_count = cursor.fetchone()[0]
    if null_email_count > 0:
        log.error(f"Verification FAILED – {null_email_count} user(s) still have no email.")
        ok = False
    else:
        log.info("Verification – all users have an email ✓")

    # admin_users must be gone
    if _table_exists(cursor, "admin_users"):
        log.error("Verification FAILED – admin_users table still exists.")
        ok = False
    else:
        log.info("Verification – admin_users dropped ✓")

    # users.role column must exist
    cols = _get_columns(cursor, "users")
    if "role" not in cols:
        log.error("Verification FAILED – users.role column missing.")
        ok = False
    else:
        log.info("Verification – users.role column present ✓")

    # No 'class_teacher' values should remain
    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'class_teacher'")
    ct_count = cursor.fetchone()[0]
    if ct_count > 0:
        log.error(f"Verification FAILED – {ct_count} row(s) still have role='class_teacher'.")
        ok = False
    else:
        log.info("Verification – no 'class_teacher' values remain ✓")

    # Role distribution summary
    cursor.execute("SELECT role, COUNT(*) FROM users GROUP BY role")
    for role, count in cursor.fetchall():
        log.info(f"Verification – role='{role}': {count} user(s)")

    return ok


# ─────────────────────────────────────────────────────────────────────────────
# Public entry-point
# ─────────────────────────────────────────────────────────────────────────────

def run_migration(
    db_path: str,
    new_db_path: str | None = None,
    dry_run: bool = False,
    skip_backup: bool = False,
) -> bool:
    if not os.path.exists(db_path):
        log.error(f"Database not found: {db_path}")
        return False

    log.info("=" * 65)
    log.info("  Role consolidation migration  (admin_users → users.role)")
    log.info(f"  Source : {db_path}")
    log.info(f"  Target : {new_db_path or db_path}")
    log.info(f"  Mode   : {'DRY-RUN' if dry_run else 'LIVE'}")
    log.info("=" * 65)

    if not dry_run and not skip_backup:
        _backup(db_path)

    active_path = _step_rename(db_path, new_db_path, dry_run)
    connect_path = db_path if dry_run else active_path

    conn = sqlite3.connect(connect_path)
    conn.execute("PRAGMA journal_mode = WAL")

    try:
        # Step 2-4: schema additions must come BEFORE any data operations
        _step_add_role_column(conn, dry_run)
        _step_add_email_column(conn, dry_run)
        _step_populate_emails(conn, dry_run)

        # Step 5-6: now safe to read/write role values
        _step_copy_roles(conn, dry_run)
        _step_normalise_teachers(conn, dry_run)

        # Step 7-9: structural changes and cleanup
        _step_rebuild_users_table(conn, dry_run)
        _step_drop_admin_users(conn, dry_run)
        _step_recreate_indexes(conn, dry_run)

        if not dry_run:
            success = _step_verify(conn)
        else:
            log.info("[DRY-RUN] Verification skipped.")
            success = True

    except Exception as exc:
        log.exception(f"Migration failed: {exc}")
        success = False
    finally:
        conn.close()

    if success:
        log.info("Migration completed successfully ✓")
    else:
        log.error("Migration completed with errors ✗  – review the log above.")

    return success


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Migrate: drop admin_users, consolidate roles into users.role",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--db",          required=True, metavar="PATH")
    p.add_argument("--rename",      metavar="NEW_PATH", default=None)
    p.add_argument("--dry-run",     action="store_true")
    p.add_argument("--skip-backup", action="store_true")
    return p


if __name__ == "__main__":
    # ── Hardcoded paths (edit here if not using CLI flags) ─────────────────
    # To run without CLI arguments, replace the two strings below and set
    # USE_HARDCODED = True.
    USE_HARDCODED = True
    HARDCODED_DB      = r"C:\Users\imosteve\Documents\Result system\python system\student_results_app\data\schools\suis.db"
    HARDCODED_RENAME  = None   # e.g. r"...\data\suis_v2.db"  or None

    if USE_HARDCODED:
        ok = run_migration(
            db_path=HARDCODED_DB,
            new_db_path=HARDCODED_RENAME,
            dry_run=False,
            skip_backup=False,
        )
        sys.exit(0 if ok else 1)
    else:
        parser = _build_parser()
        args = parser.parse_args()
        ok = run_migration(
            db_path=args.db,
            new_db_path=args.rename,
            dry_run=args.dry_run,
            skip_backup=args.skip_backup,
        )
        sys.exit(0 if ok else 1)
