# database/__init__.py
"""
School database public API — single import point for all modules.

Usage:
    from database import (
        create_tables,
        get_active_term, set_active_term,
        get_all_sessions, create_session,
        get_all_classes, create_class, open_class_for_session,
        get_enrolled_students, enroll_student,
        save_score, get_scores_for_class,
        ...
    )
"""

from .schema import create_tables, _create_indexes as create_performance_indexes

# ── Academic context ─────────────────────────────────────────────────────────
from .academic_settings import (
    get_active_term,
    get_active_session,
    get_active_term_name,
    set_active_term,
    is_configured,
    get_all_sessions,
    create_session,
    delete_session,
    update_session,
)

# ── Classes ──────────────────────────────────────────────────────────────────
from .classes import (
    create_class,
    get_all_classes,
    get_class,
    update_class,
    delete_class,
    open_class_for_session,
    get_class_session_id,
    get_classes_for_session,
    get_classes_for_teacher,
    close_class_for_session,
    reopen_class_for_session,
    delete_class_session,
)

# ── Students & enrollment ─────────────────────────────────────────────────────
from .students import (
    create_student,
    get_all_students,
    student_exists,
    update_student,
    delete_student,
    enroll_student,
    bulk_enroll_students,
    unenroll_student,
    get_enrolled_students,
    get_enrollment_id,
    get_students_not_enrolled_in,
    import_students_from_class,
    enroll_student_all_terms,
    unenroll_student_all_terms,
    get_student_enrolled_terms,
)

# ── Scores ───────────────────────────────────────────────────────────────────
from .scores import (
    save_score,
    save_scores_bulk,
    recalculate_positions,
    get_scores_for_class,
    get_scores_for_student,
    get_scores_for_subject,
    get_student_all_terms,
    get_student_grand_totals,
    get_student_average,
    has_scores_for_term,
    get_grade_distribution,
    delete_score,
    delete_scores_for_term,
)

# ── Comments ─────────────────────────────────────────────────────────────────
from .comments import (
    create_comment,
    get_comment,
    delete_comment,
)

# ── Psychomotor ratings ───────────────────────────────────────────────────────
from .psychomotor import (
    create_psychomotor_rating,
    get_psychomotor_rating,
    delete_psychomotor_rating,
    get_all_psychomotor_ratings,
)

# ── Subjects ─────────────────────────────────────────────────────────────────
from .subjects import (
    create_subject,
    get_subjects_by_class,
    update_subject,
    delete_subject,
    clear_all_subjects,
)

# ── Score system ─────────────────────────────────────────────────────────────
from .score_system import (
    get_class_score_system,
    set_class_score_system,
    get_all_score_systems_for_class,
    SCORE_SYSTEMS,
)

# ── Student subject selections ────────────────────────────────────────────────
from .student_subjects import (
    get_student_selected_subjects,
    save_student_subject_selections,
    get_all_student_subject_selections,
)

# ── Next term info ────────────────────────────────────────────────────────────
from .next_term_data import (
    create_or_update_next_term_info,
    get_next_term_info,
    get_all_next_term_info,
    delete_next_term_info,
    get_next_term_begin_date,
)

# ── Comment templates ─────────────────────────────────────────────────────────
from .comment_templates import (
    add_comment_template,
    get_all_comment_templates,
    get_head_teacher_comment_by_average,
    delete_comment_template,
    update_comment_template,
    check_range_overlap,
)

# ── Users & teacher assignments ───────────────────────────────────────────────
from .users import (
    create_user,
    get_all_users,
    update_user,
    delete_user,
    get_user_role,
    get_user_assignments,
    assign_teacher,
    batch_assign_subject_teacher,
    delete_assignment,
    update_assignment,
)

# ── Utils ─────────────────────────────────────────────────────────────────────
from .utils import (
    get_database_stats,
    get_classes_summary,
    backup_database,
    restore_database,
    database_health_check,
)

# ── Connection (re-exported for callers that need a raw connection) ────────────
from .connection import (
    get_connection,
    get_db_connection,
)