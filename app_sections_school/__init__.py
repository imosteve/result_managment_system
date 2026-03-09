# app_sections/__init__.py
"""
App sections package
Contains all the main functional sections of the application
"""

from . import admin_panel
from . import user_profile
from . import manage_classes
from . import register_students
from . import manage_subjects
from . import enter_scores
from . import view_broadsheet
from . import manage_comments
from . import manage_comment_templates
from . import generate_reports
from . import next_term_info
from . import system_dashboard

__all__ = [
    'admin_panel',
    'user_profile',
    'manage_classes',
    'register_students',
    'manage_subjects',
    'enter_scores',
    'view_broadsheet',
    'manage_comments',
    'manage_comment_templates',
    'generate_reports',
    'next_term_info',
    'system_dashboard',
]
