# app_sections_master/__init__.py
"""
Public API for the platform admin sections.

Each section is a standalone callable that app_manager.py can wire
directly into the sidebar navigation dict — exactly the same pattern
used by app_sections_school modules.

Usage in app_manager.py:
    from app_sections_master import (
        platform_schools_section,
        platform_db_section,
        platform_audit_section,
        render_platform_header,
    )
"""

from app_sections_master._schools import render_schools_section as platform_schools_section
from app_sections_master._db_ops  import render_db_ops_section  as platform_db_section
from app_sections_master._audit   import render_audit_section    as platform_audit_section
from app_sections_master.platform_admin import render_platform_header

__all__ = [
    "platform_schools_section",
    "platform_db_section",
    "platform_audit_section",
    "render_platform_header",
]