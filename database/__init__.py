# database/__init__.py

"""
Database package - Modular database operations for School Management System
"""

from .connection import get_connection, get_db_connection
from .schema import create_tables, create_performance_indexes

# Import all functions from modules
from .users import (
    create_user,
    get_user_by_username,
    get_user_role,
    delete_user,
    get_all_users,
    update_user,
    get_user_assignments,
    assign_teacher,
    batch_assign_subject_teacher,
    delete_assignment,
    update_assignment,
)

from .classes import (
    get_all_classes,
    create_class,
    update_class,
    delete_class,
    clear_all_classes,
)

from .students import (
    get_students_by_class,
    create_student,
    create_students_batch,
    update_student,
    delete_student,
    delete_all_students,
    get_students_with_paid_fees,
)

from .subjects import (
    get_subjects_by_class,
    create_subject,
    update_subject,
    delete_subject,
    clear_all_subjects,
)

from .scores import (
    get_scores_by_class_subject,
    get_all_scores_by_class,
    get_student_scores,
    save_scores,
    update_score,
    recalculate_positions,
    get_class_average,
    get_student_grand_totals,
    clear_all_scores,
    get_grade_distribution,
)

from .comments import (
    create_comment,
    get_comment,
    delete_comment,
)

from .psychomotor import (
    create_psychomotor_rating,
    get_psychomotor_rating,
    delete_psychomotor_rating,
    get_all_psychomotor_ratings,
)

from .student_subjects import (
    get_student_selected_subjects,
    save_student_subject_selections,
    get_all_student_subject_selections,
)

from .comment_templates import (
    add_comment_template,
    get_all_comment_templates,
    delete_comment_template,
    update_comment_template,
)

from .next_term_data import (
    create_or_update_next_term_info,
    get_next_term_info,
    get_all_next_term_info,
    delete_next_term_info,
    get_next_term_begin_date,
)

from .utils import (
    get_database_stats,
    get_classes_summary,
    backup_database,
    restore_database,
    database_health_check,
    validate_student_data,
    validate_score_data,
    migrate_old_database,
    migrate_add_school_fees_column,
)

__all__ = [
    # Connection
    'get_connection',
    'get_db_connection',
    
    # Schema
    'create_tables',
    'create_performance_indexes',
    
    # Users
    'create_user',
    'get_user_by_username',
    'get_user_role',
    'delete_user',
    'get_all_users',
    'update_user',
    
    # Teacher Assignments
    'get_user_assignments',
    'assign_teacher',
    'delete_assignment',
    'update_assignment',
    
    # Classes
    'get_all_classes',
    'create_class',
    'update_class',
    'delete_class',
    'clear_all_classes',
    
    # Students
    'get_students_by_class',
    'create_student',
    'create_students_batch',
    'update_student',
    'delete_student',
    'delete_all_students',
    'get_students_with_paid_fees',
    
    # Subjects
    'get_subjects_by_class',
    'create_subject',
    'update_subject',
    'delete_subject',
    'clear_all_subjects',
    
    # Scores
    'get_scores_by_class_subject',
    'get_all_scores_by_class',
    'get_student_scores',
    'save_scores',
    'update_score',
    'recalculate_positions',
    'get_class_average',
    'get_student_grand_totals',
    'clear_all_scores',
    'get_grade_distribution',
    
    # Comments
    'create_comment',
    'get_comment',
    'delete_comment',
    
    # Psychomotor
    'create_psychomotor_rating',
    'get_psychomotor_rating',
    'delete_psychomotor_rating',
    'get_all_psychomotor_ratings',
    
    # Student Subjects
    'get_student_selected_subjects',
    'save_student_subject_selections',
    'get_all_student_subject_selections',
    
    # Comment Templates
    'add_comment_template',
    'get_all_comment_templates',
    'delete_comment_template',
    'update_comment_template',
    
    # Next Term Info
    'create_or_update_next_term_info',
    'get_next_term_info',
    'get_all_next_term_info',
    'delete_next_term_info',
    'get_next_term_begin_date',
    
    # Utils
    'get_database_stats',
    'get_classes_summary',
    'backup_database',
    'restore_database',
    'database_health_check',
    'validate_student_data',
    'validate_score_data',
    'migrate_old_database',
    'migrate_add_school_fees_column',
]