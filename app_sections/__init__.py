# app_sections/__init__.py
"""
App sections package
Contains all the main functional sections of the application
"""

# Import all sections for easy access
from . import admin_panel
from . import manage_classes
from . import register_students
from . import manage_subjects
from . import enter_scores
from . import view_broadsheet
from . import manage_comments
from . import generate_reports
from . import system_dashboard

__all__ = [
    'admin_panel',
    'manage_classes',
    'register_students',
    'manage_subjects',
    'enter_scores',
    'view_broadsheet',
    'manage_comments',
    'generate_reports',
    'system_dashboard'
]