#!/usr/bin/env python3
"""
Quick setup script for the complete production database
"""

from database import (
    create_tables, create_user, get_all_users, 
    database_health_check, create_performance_indexes
)

def setup_production_database():
    """Set up the production database with default users"""
    
    print("🚀 Setting up production database...")
    
    # 1. Create all tables
    print("📋 Creating database tables...")
    create_tables()
    print("✅ Tables created successfully!")
    
    # 2. Run health check
    print("🏥 Running database health check...")
    health = database_health_check()
    print(f"✅ Database status: {health['status']}")
    
    # 3. Create default users
    print("👥 Creating default users...")
    
    default_users = [
        ("admin", "admin", "admin"),
        ("abas", "abas", "class_teacher"),
        ("imo", "imo", "subject_teacher"),
    ]
    
    created_count = 0
    for username, password, role in default_users:
        success = create_user(username, password, role)
        if success:
            print(f"✅ Created: {username} ({role})")
            created_count += 1
        else:
            print(f"⚠️  User {username} already exists")
    
    # 4. Display all users
    print(f"\n📊 Database setup complete! Created {created_count} new users.")
    print("\n👥 All users in system:")
    users = get_all_users()
    for user in users:
        print(f"   - {user['username']} ({user['role']})")
    
    print("\n🎉 Your production database is ready!")
    print("\n📝 Default login credentials:")
    print("   Admin: admin / admin123")
    print("   Class Teacher: class_teacher1 / teacher123") 
    print("   Subject Teacher: subject_teacher1 / subject123")

if __name__ == "__main__":
    setup_production_database()