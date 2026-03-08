# master_database/__init__.py
"""
Public API for the master database package.

All existing callers that do:
    from master_database import register_school, get_all_schools, ...
continue to work unchanged — everything is re-exported here.
"""

from .connection import (
    get_master_connection,
    MASTER_DB_PATH,
    SCHOOLS_DB_DIR,
)

from .setup import (
    create_master_tables,
)

from .schools import (
    register_school,
    get_all_schools,
    get_school_by_code,
    get_school_by_domain,
    get_school_db_path,
    resolve_school_from_email,
    update_school_status,
    update_school_info,
    delete_school,
)

from .platform_admins import (
    get_platform_admin_by_email,
    get_platform_admin_by_id,
    get_all_platform_admins,
    create_platform_admin,
    update_platform_admin_password,
    update_platform_admin_email,
    delete_platform_admin,
)

from .db_ops import (
    backup_master_db,
    restore_master_db,
    get_master_db_info,
    vacuum_master_db,
    master_db_health_check,
)

from .audit import (
    log_school_action,
    get_audit_log,
    get_audit_log_by_school,
)

__all__ = [
    # connection
    "get_master_connection",
    "MASTER_DB_PATH",
    "SCHOOLS_DB_DIR",
    # setup
    "create_master_tables",
    # schools
    "register_school",
    "get_all_schools",
    "get_school_by_code",
    "get_school_by_domain",
    "get_school_db_path",
    "resolve_school_from_email",
    "update_school_status",
    "update_school_info",
    "delete_school",
    # platform admins
    "get_platform_admin_by_email",
    "get_platform_admin_by_id",
    "get_all_platform_admins",
    "create_platform_admin",
    "update_platform_admin_password",
    "update_platform_admin_email",
    "delete_platform_admin",
    # db ops
    "backup_master_db",
    "restore_master_db",
    "get_master_db_info",
    "vacuum_master_db",
    "master_db_health_check",
    # audit
    "log_school_action",
    "get_audit_log",
    "get_audit_log_by_school",
]
