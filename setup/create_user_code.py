# Method 1: Python Interactive Shell
# Open terminal and run: python
# Then execute these commands:

from database import create_user, create_tables

# First, ensure tables exist
create_tables()

# Create users with different roles
create_user("admin", "admin123", "admin")
create_user("class_teacher1", "password123", "class_teacher") 
create_user("subject_teacher1", "password123", "subject_teacher")

print("Users created successfully!")

# Check if user was created
from database import get_all_users
users = get_all_users()
for user in users:
    print(f"ID: {user['id']}, Username: {user['username']}, Role: {user['role']}")

# ============================================

# Method 2: Create a separate script file
# Save this as create_users.py and run: python create_users.py

#!/usr/bin/env python3
"""Script to create users from command line"""

import sys
from database import create_user, create_tables, get_all_users

def main():
    # Ensure database tables exist
    create_tables()
    
    # Get user input
    print("=== User Creation Script ===")
    username = input("Enter username: ").strip()
    password = input("Enter password: ").strip()
    
    print("\nSelect role:")
    print("1. admin")
    print("2. class_teacher") 
    print("3. subject_teacher")
    
    role_choice = input("Enter choice (1-3): ").strip()
    
    role_map = {
        "1": "admin",
        "2": "class_teacher", 
        "3": "subject_teacher"
    }
    
    role = role_map.get(role_choice)
    if not role:
        print("Invalid role choice!")
        return
    
    # Validate input
    if not username or not password:
        print("Username and password are required!")
        return
    
    # Create user
    success = create_user(username, password, role)
    
    if success:
        print(f"\n✅ User '{username}' created successfully with role '{role}'!")
        
        # Show all users
        print("\nAll users in database:")
        users = get_all_users()
        for user in users:
            print(f"  - {user['username']} ({user['role']})")
    else:
        print(f"\n❌ Failed to create user. Username '{username}' may already exist.")

if __name__ == "__main__":
    main()

# ============================================

# Method 3: One-liner commands
# Run these directly in terminal:

# For Python 3:
# python -c "from database import create_user, create_tables; create_tables(); print('Admin created:', create_user('admin', 'admin123', 'admin'))"

# python -c "from database import create_user; print('Teacher created:', create_user('teacher1', 'password123', 'class_teacher'))"

# ============================================

# Method 4: Batch user creation script
# Save as batch_create_users.py

#!/usr/bin/env python3
"""Batch create multiple users"""

from database import create_user, create_tables, get_all_users

def create_default_users():
    """Create a set of default users for testing"""
    
    # Ensure tables exist
    create_tables()
    
    # Default users to create
    default_users = [
        ("admin", "admin123", "admin"),
        ("john_doe", "teacher123", "class_teacher"),
        ("jane_smith", "teacher123", "class_teacher"), 
        ("math_teacher", "subject123", "subject_teacher"),
        ("english_teacher", "subject123", "subject_teacher"),
        ("science_teacher", "subject123", "subject_teacher")
    ]
    
    print("Creating default users...")
    created_count = 0
    
    for username, password, role in default_users:
        success = create_user(username, password, role)
        if success:
            print(f"✅ Created: {username} ({role})")
            created_count += 1
        else:
            print(f"❌ Failed: {username} (may already exist)")
    
    print(f"\nCreated {created_count} users successfully!")
    
    # Show all users
    print("\nAll users in database:")
    users = get_all_users()
    for user in users:
        print(f"  - ID: {user['id']}, Username: {user['username']}, Role: {user['role']}")

if __name__ == "__main__":
    create_default_users()

# ============================================

# Method 5: Command line arguments script
# Save as create_user_cli.py

#!/usr/bin/env python3
"""Create user with command line arguments"""

import sys
from database import create_user, create_tables

def main():
    if len(sys.argv) != 4:
        print("Usage: python create_user_cli.py <username> <password> <role>")
        print("Roles: admin, class_teacher, subject_teacher")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2] 
    role = sys.argv[3]
    
    # Validate role
    valid_roles = ["admin", "class_teacher", "subject_teacher"]
    if role not in valid_roles:
        print(f"Invalid role. Must be one of: {', '.join(valid_roles)}")
        sys.exit(1)
    
    # Ensure tables exist
    create_tables()
    
    # Create user
    success = create_user(username, password, role)
    
    if success:
        print(f"✅ User '{username}' created successfully with role '{role}'!")
    else:
        print(f"❌ Failed to create user. Username '{username}' may already exist.")

if __name__ == "__main__":
    main()

# Usage: python create_user_cli.py admin admin123 admin