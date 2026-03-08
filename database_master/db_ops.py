# master_database/db_ops.py
"""
Master database file operations: backup, restore, vacuum, health check.

All operations target master.db only.
For school-level DB operations, use database/utils.py or system_dashboard.py.
"""

import os
import shutil
import sqlite3
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from .connection import get_master_connection, MASTER_DB_PATH
from .audit import log_school_action

logger = logging.getLogger(__name__)

# Default backup directory for master DB backups
MASTER_BACKUP_DIR = os.path.join("data", "master_backups")


# ─────────────────────────────────────────────
# Backup
# ─────────────────────────────────────────────

def backup_master_db(
    backup_name:  Optional[str] = None,
    backup_dir:   Optional[str] = None,
    performed_by: str = "system",
) -> Dict[str, Any]:
    """
    Create a timestamped backup of master.db.

    Uses SQLite's online backup API (safe while DB is open/in use).

    Args:
        backup_name:  Optional filename override (auto-generated if None)
        backup_dir:   Directory to write backup into (default: data/master_backups/)
        performed_by: Actor for audit log

    Returns:
        Dict with keys: success (bool), path (str), size (str), error (str|None)
    """
    backup_dir = backup_dir or MASTER_BACKUP_DIR
    os.makedirs(backup_dir, exist_ok=True)

    if not backup_name:
        ts          = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"master_backup_{ts}.db"
    elif not backup_name.endswith(".db"):
        backup_name += ".db"

    backup_path = os.path.join(backup_dir, backup_name)

    try:
        # SQLite online backup — safe while the DB is open
        src  = sqlite3.connect(MASTER_DB_PATH)
        dest = sqlite3.connect(backup_path)
        src.backup(dest)
        dest.close()
        src.close()

        size_mb = os.path.getsize(backup_path) / (1024 * 1024)
        size    = f"{size_mb:.3f} MB"

        log_school_action(
            "platform", "MASTER_DB_BACKUP_CREATED", performed_by,
            f"Backup created: '{backup_path}' ({size})"
        )
        logger.info(f"Master DB backed up → {backup_path} ({size})")
        return {"success": True, "path": backup_path, "name": backup_name,
                "size": size, "error": None}

    except Exception as e:
        logger.error(f"backup_master_db error: {e}")
        return {"success": False, "path": None, "name": None,
                "size": None, "error": str(e)}


def list_master_backups(backup_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all .db files in the master backup directory.

    Returns:
        List of dicts with keys: name, path, size, created, age
        Sorted newest-first.
    """
    backup_dir = backup_dir or MASTER_BACKUP_DIR

    if not os.path.exists(backup_dir):
        return []

    backups = []
    for fname in os.listdir(backup_dir):
        if not fname.endswith(".db"):
            continue
        fpath   = os.path.join(backup_dir, fname)
        size    = os.path.getsize(fpath) / (1024 * 1024)
        created = datetime.fromtimestamp(os.path.getctime(fpath))
        age     = datetime.now() - created

        backups.append({
            "name":    fname,
            "path":    fpath,
            "size":    f"{size:.3f} MB",
            "created": created.strftime("%Y-%m-%d %H:%M:%S"),
            "age":     "Today" if age.days == 0 else f"{age.days} days ago",
        })

    backups.sort(key=lambda x: x["created"], reverse=True)
    return backups


def delete_master_backup(
    backup_name:  str,
    backup_dir:   Optional[str] = None,
    performed_by: str = "system",
) -> bool:
    """
    Delete a master DB backup file.

    Returns:
        True if deleted, False if not found or error
    """
    backup_dir  = backup_dir or MASTER_BACKUP_DIR
    backup_path = os.path.join(backup_dir, backup_name)

    if not os.path.exists(backup_path):
        logger.warning(f"delete_master_backup: '{backup_path}' not found")
        return False

    try:
        os.remove(backup_path)
        log_school_action(
            "platform", "MASTER_DB_BACKUP_DELETED", performed_by,
            f"Backup deleted: '{backup_name}'"
        )
        logger.info(f"Master DB backup deleted: {backup_name}")
        return True
    except Exception as e:
        logger.error(f"delete_master_backup error: {e}")
        return False


# ─────────────────────────────────────────────
# Restore
# ─────────────────────────────────────────────

def restore_master_db(
    backup_name:  str,
    backup_dir:   Optional[str] = None,
    performed_by: str = "system",
) -> Dict[str, Any]:
    """
    Restore master.db from a backup file.

    Automatically creates a pre-restore safety backup first.
    The app should be restarted after a restore for connections to refresh.

    Args:
        backup_name:  Filename of the backup to restore (in backup_dir)
        backup_dir:   Directory containing the backup (default: data/master_backups/)
        performed_by: Actor for audit log

    Returns:
        Dict with keys: success (bool), safety_backup (str|None), error (str|None)
    """
    backup_dir  = backup_dir or MASTER_BACKUP_DIR
    backup_path = os.path.join(backup_dir, backup_name)

    if not os.path.exists(backup_path):
        return {
            "success": False,
            "safety_backup": None,
            "error": f"Backup file not found: '{backup_path}'"
        }

    # Auto safety backup of current DB
    safety_result = backup_master_db(
        backup_name=f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
        backup_dir=backup_dir,
        performed_by=performed_by,
    )
    safety_backup = safety_result.get("name") if safety_result["success"] else None

    try:
        shutil.copy2(backup_path, MASTER_DB_PATH)

        log_school_action(
            "platform", "MASTER_DB_RESTORED", performed_by,
            f"Restored from '{backup_name}'. "
            f"Safety backup: '{safety_backup or 'FAILED'}'"
        )
        logger.warning(
            f"Master DB restored from '{backup_name}'. "
            "Restart the application to refresh all connections."
        )
        return {"success": True, "safety_backup": safety_backup, "error": None}

    except Exception as e:
        logger.error(f"restore_master_db error: {e}")
        return {"success": False, "safety_backup": safety_backup, "error": str(e)}


# ─────────────────────────────────────────────
# Info / stats
# ─────────────────────────────────────────────

def get_master_db_info() -> Dict[str, Any]:
    """
    Return file stats and table row counts for master.db.

    Returns:
        Dict with keys: size, table_count, schools_total, schools_active,
        schools_inactive, platform_admins, audit_entries, last_backup
    """
    try:
        size = 0
        if os.path.exists(MASTER_DB_PATH):
            size = os.path.getsize(MASTER_DB_PATH) / (1024 * 1024)

        conn = get_master_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        )
        table_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM schools")
        schools_total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM schools WHERE status = 'active'")
        schools_active = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM platform_admins")
        admins = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM school_audit_log")
        audit_entries = cursor.fetchone()[0]

        conn.close()

        backups    = list_master_backups()
        last_backup = backups[0]["created"] if backups else "Never"

        return {
            "size":             f"{size:.3f} MB",
            "table_count":      table_count,
            "schools_total":    schools_total,
            "schools_active":   schools_active,
            "schools_inactive": schools_total - schools_active,
            "platform_admins":  admins,
            "audit_entries":    audit_entries,
            "last_backup":      last_backup,
        }
    except Exception as e:
        logger.error(f"get_master_db_info error: {e}")
        return {
            "size": "Error", "table_count": 0,
            "schools_total": 0, "schools_active": 0,
            "schools_inactive": 0, "platform_admins": 0,
            "audit_entries": 0, "last_backup": "Error",
        }


# ─────────────────────────────────────────────
# Maintenance
# ─────────────────────────────────────────────

def vacuum_master_db(performed_by: str = "system") -> bool:
    """
    VACUUM master.db to reclaim space and defragment.

    Returns:
        True on success, False on error
    """
    try:
        conn = sqlite3.connect(MASTER_DB_PATH)
        conn.execute("VACUUM")
        conn.close()
        log_school_action(
            "platform", "MASTER_DB_VACUUMED", performed_by,
            "VACUUM executed on master.db"
        )
        logger.info("master.db vacuumed successfully")
        return True
    except Exception as e:
        logger.error(f"vacuum_master_db error: {e}")
        return False


def master_db_health_check() -> Dict[str, Any]:
    """
    Run integrity_check and foreign_key_check on master.db.

    Returns:
        Dict with keys: status ('healthy'|'degraded'|'error'),
        integrity (str), fk_violations (list), details (str)
    """
    try:
        conn = get_master_connection()
        cursor = conn.cursor()

        cursor.execute("PRAGMA integrity_check")
        integrity_rows = [r[0] for r in cursor.fetchall()]
        integrity_ok   = integrity_rows == ["ok"]

        cursor.execute("PRAGMA foreign_key_check")
        fk_violations = cursor.fetchall()

        conn.close()

        status = "healthy" if (integrity_ok and not fk_violations) else "degraded"

        return {
            "status":        status,
            "integrity":     integrity_rows[0] if integrity_rows else "unknown",
            "fk_violations": [dict(r) for r in fk_violations],
            "details":       (
                "All checks passed."
                if status == "healthy"
                else f"Integrity: {integrity_rows}. "
                     f"FK violations: {len(fk_violations)}"
            ),
        }
    except Exception as e:
        logger.error(f"master_db_health_check error: {e}")
        return {
            "status":        "error",
            "integrity":     "error",
            "fk_violations": [],
            "details":       str(e),
        }
