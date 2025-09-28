#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script to add new categories from Google Sheets to the categories_main table.
This will add all the new categories you've created in your Google Sheet.
"""

import mysql.connector
import os

def load_env_file():
    """Load environment variables from .env file if it exists"""
    env_file = '.env'
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

# Load environment variables
load_env_file()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'petgully-dbserver.cmzwm2y64qh8.us-east-1.rds.amazonaws.com'),
    'user': os.getenv('DB_USER', 'admin'),
    'password': os.getenv('DB_PASS', 'care6886'),
    'database': os.getenv('DB_NAME', 'petgully_db'),
    'port': int(os.getenv('DB_PORT', 3306))
}

# New categories from your Google Sheet
NEW_CATEGORIES = [
    "IT and Software",
    "SBI Transfer", 
    "Loan From Director - Deepak",
    "Spotless HonerHomes",
    "Spotless DSR",
    "Razorpay",
    "Cash Deposit",
    "Advertising & Marketing",
    "Opening Balance"
]

def create_connection():
    """Create database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        print(f"✅ Connected to MySQL database: {DB_CONFIG['database']}")
        return connection
    except mysql.connector.Error as err:
        print(f"❌ Error connecting to MySQL: {err}")
        return None

def get_or_create_category_id(category_name, cur):
    """
    Get category ID from categories_main table, create if doesn't exist
    Returns the category ID
    """
    if not category_name:
        return None
    
    # First, try to find existing category
    cur.execute("SELECT id FROM categories_main WHERE name = %s", (category_name,))
    result = cur.fetchone()
    
    if result:
        print(f"✅ Category '{category_name}' already exists (ID: {result[0]})")
        return result[0]
    
    # Category doesn't exist, create it
    # Generate a code from the category name
    code = category_name.upper().replace(' ', '').replace('&', '').replace('-', '')[:8]
    
    # Make sure code is unique
    counter = 1
    original_code = code
    while True:
        cur.execute("SELECT id FROM categories_main WHERE code = %s", (code,))
        if not cur.fetchone():
            break
        code = f"{original_code}{counter}"
        counter += 1
    
    # Insert new category
    cur.execute("""
        INSERT INTO categories_main (code, name, is_active)
        VALUES (%s, %s, 1)
    """, (code, category_name))
    
    # Get the new category ID
    category_id = cur.lastrowid
    print(f"✅ Created new category: {category_name} (ID: {category_id}, Code: {code})")
    
    return category_id

def add_new_categories():
    """Add all new categories to the database"""
    connection = create_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        added_count = 0
        existing_count = 0
        
        print(f"\n📝 Processing {len(NEW_CATEGORIES)} new categories...")
        
        for category_name in NEW_CATEGORIES:
            category_id = get_or_create_category_id(category_name, cursor)
            if category_id:
                if "already exists" in str(category_id):
                    existing_count += 1
                else:
                    added_count += 1
        
        # Commit all changes
        connection.commit()
        
        print(f"\n📊 Summary:")
        print(f"   ✅ New categories added: {added_count}")
        print(f"   ℹ️  Categories already existed: {existing_count}")
        print(f"   📅 Total processed: {len(NEW_CATEGORIES)}")
        
        return True
        
    except mysql.connector.Error as err:
        print(f"❌ Database error: {err}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("🔌 Database connection closed")

def main():
    """Main entry point"""
    print("🚀 Adding new categories to database...")
    print(f"📋 Database: {DB_CONFIG['database']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}")
    
    success = add_new_categories()
    
    if success:
        print("\n🎉 All categories successfully processed!")
    else:
        print("\n⚠️  Some categories failed to process. Check the errors above.")

if __name__ == "__main__":
    main()
