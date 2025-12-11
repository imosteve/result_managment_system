#!/usr/bin/env python3
"""
Database Migration Script for Range-Based Comment System
This script updates the database schema to support the new range-based head teacher commenting system.

BACKUP YOUR DATABASE BEFORE RUNNING THIS SCRIPT!

Usage:
    python migrate_comment_system.py
"""

import sqlite3
import sys
import os
from datetime import datetime

# Database path - adjust if needed
DATABASE_PATH = "data/school.db"

def backup_database():
    """Create a backup of the database before migration"""
    if not os.path.exists(DATABASE_PATH):
        print(f"❌ Database not found at: {DATABASE_PATH}")
        return False
    
    backup_path = f"{DATABASE_PATH}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        import shutil
        shutil.copy2(DATABASE_PATH, backup_path)
        print(f"✅ Database backed up to: {backup_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to backup database: {e}")
        return False

def check_column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    return any(col[1] == column_name for col in columns)

def migrate_comment_templates_table(conn):
    """Migrate comment_templates table to add range columns"""
    cursor = conn.cursor()
    
    print("\n📝 Migrating comment_templates table...")
    
    # Check if columns already exist
    has_lower = check_column_exists(cursor, 'comment_templates', 'average_lower')
    has_upper = check_column_exists(cursor, 'comment_templates', 'average_upper')
    has_updated = check_column_exists(cursor, 'comment_templates', 'updated_at')
    
    if has_lower and has_upper and has_updated:
        print("✓ comment_templates table already has new columns")
        return True
    
    try:
        # Add new columns if they don't exist
        if not has_lower:
            cursor.execute("ALTER TABLE comment_templates ADD COLUMN average_lower REAL")
            print("  ✓ Added average_lower column")
        
        if not has_upper:
            cursor.execute("ALTER TABLE comment_templates ADD COLUMN average_upper REAL")
            print("  ✓ Added average_upper column")
        
        if not has_updated:
            # SQLite doesn't support DEFAULT CURRENT_TIMESTAMP in ALTER TABLE
            # Add column without default, then update existing rows
            cursor.execute("ALTER TABLE comment_templates ADD COLUMN updated_at TIMESTAMP")
            print("  ✓ Added updated_at column")
            
            # Update existing rows with current timestamp
            cursor.execute("""
                UPDATE comment_templates 
                SET updated_at = CURRENT_TIMESTAMP 
                WHERE updated_at IS NULL
            """)
            print("  ✓ Set default timestamps for existing rows")
        
        conn.commit()
        print("✅ comment_templates table migrated successfully")
        return True
        
    except Exception as e:
        print(f"❌ Failed to migrate comment_templates: {e}")
        conn.rollback()
        return False

def migrate_comments_table(conn):
    """Migrate comments table to add head_teacher_comment_custom column"""
    cursor = conn.cursor()
    
    print("\n📝 Migrating comments table...")
    
    # Check if column already exists
    has_custom = check_column_exists(cursor, 'comments', 'head_teacher_comment_custom')
    
    if has_custom:
        print("✓ comments table already has head_teacher_comment_custom column")
        return True
    
    try:
        # Add new column
        cursor.execute("ALTER TABLE comments ADD COLUMN head_teacher_comment_custom INTEGER DEFAULT 0")
        print("  ✓ Added head_teacher_comment_custom column")
        
        # Set all existing head teacher comments as custom (1) to preserve existing data
        cursor.execute("""
            UPDATE comments 
            SET head_teacher_comment_custom = 1 
            WHERE head_teacher_comment IS NOT NULL AND head_teacher_comment != ''
        """)
        
        affected = cursor.rowcount
        print(f"  ✓ Marked {affected} existing head teacher comments as custom")
        
        conn.commit()
        print("✅ comments table migrated successfully")
        return True
        
    except Exception as e:
        print(f"❌ Failed to migrate comments: {e}")
        conn.rollback()
        return False

def create_indexes(conn):
    """Create performance indexes for the new columns"""
    cursor = conn.cursor()
    
    print("\n📝 Creating performance indexes...")
    
    try:
        # Check if index exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='idx_comment_templates_type_range'
        """)
        
        if cursor.fetchone():
            print("✓ Index idx_comment_templates_type_range already exists")
        else:
            cursor.execute("""
                CREATE INDEX idx_comment_templates_type_range 
                ON comment_templates(comment_type, average_lower, average_upper)
            """)
            print("  ✓ Created index: idx_comment_templates_type_range")
        
        conn.commit()
        print("✅ Indexes created successfully")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create indexes: {e}")
        conn.rollback()
        return False

def verify_migration(conn):
    """Verify that the migration was successful"""
    cursor = conn.cursor()
    
    print("\n🔍 Verifying migration...")
    
    try:
        # Check comment_templates structure
        cursor.execute("PRAGMA table_info(comment_templates)")
        ct_columns = {col[1] for col in cursor.fetchall()}
        
        required_ct_columns = {'id', 'comment_text', 'comment_type', 'average_lower', 
                               'average_upper', 'created_by', 'created_at', 'updated_at'}
        
        if not required_ct_columns.issubset(ct_columns):
            missing = required_ct_columns - ct_columns
            print(f"❌ comment_templates missing columns: {missing}")
            return False
        
        print("  ✓ comment_templates structure verified")
        
        # Check comments structure
        cursor.execute("PRAGMA table_info(comments)")
        c_columns = {col[1] for col in cursor.fetchall()}
        
        required_c_columns = {'id', 'student_name', 'class_name', 'term', 'session',
                             'class_teacher_comment', 'head_teacher_comment', 
                             'head_teacher_comment_custom', 'created_at', 'updated_at'}
        
        if not required_c_columns.issubset(c_columns):
            missing = required_c_columns - c_columns
            print(f"❌ comments missing columns: {missing}")
            return False
        
        print("  ✓ comments structure verified")
        
        # Count templates
        cursor.execute("SELECT COUNT(*) FROM comment_templates")
        template_count = cursor.fetchone()[0]
        print(f"  ℹ️  Total comment templates: {template_count}")
        
        # Count comments
        cursor.execute("SELECT COUNT(*) FROM comments")
        comment_count = cursor.fetchone()[0]
        print(f"  ℹ️  Total student comments: {comment_count}")
        
        print("✅ Migration verification successful")
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

def main():
    """Main migration function"""
    print("=" * 60)
    print("DATABASE MIGRATION - Range-Based Comment System")
    print("=" * 60)
    
    # Check if database exists
    if not os.path.exists(DATABASE_PATH):
        print(f"\n❌ Database not found at: {DATABASE_PATH}")
        print("Please ensure the database exists before running migration.")
        return 1
    
    # Backup database
    print("\n🔄 Creating backup...")
    if not backup_database():
        print("\n❌ Migration aborted - could not create backup")
        return 1
    
    # Connect to database
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        print(f"\n✅ Connected to database: {DATABASE_PATH}")
    except Exception as e:
        print(f"\n❌ Failed to connect to database: {e}")
        return 1
    
    try:
        # Run migrations
        success = True
        
        success = migrate_comment_templates_table(conn) and success
        success = migrate_comments_table(conn) and success
        success = create_indexes(conn) and success
        
        if success:
            success = verify_migration(conn)
        
        if success:
            print("\n" + "=" * 60)
            print("✅ MIGRATION COMPLETED SUCCESSFULLY")
            print("=" * 60)
            print("\nNext steps:")
            print("1. Test the application to ensure everything works correctly")
            print("2. Add range-based templates in 'Manage Comment Templates'")
            print("3. The old comment templates remain unchanged (class teacher)")
            print("4. Existing head teacher comments are marked as 'custom'")
            return 0
        else:
            print("\n" + "=" * 60)
            print("❌ MIGRATION FAILED")
            print("=" * 60)
            print("\nThe database backup is available for restoration.")
            return 1
            
    except Exception as e:
        print(f"\n❌ Migration error: {e}")
        return 1
    finally:
        conn.close()

if __name__ == "__main__":
    sys.exit(main())