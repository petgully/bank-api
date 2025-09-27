#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script to push all rules from rules.py to MySQL database table.
This script will insert all rules from the RULES list and SALARY_NAME_MAP into the petgully_db.rules table.
"""

import json
import mysql.connector
from datetime import datetime
from typing import Dict, List
import os
from rules import RULES, SALARY_NAME_MAP

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
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'petgully_db'),
    'port': int(os.getenv('DB_PORT', 3306))
}

def create_connection():
    """Create database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        print(f"✅ Connected to MySQL database: {DB_CONFIG['database']}")
        return connection
    except mysql.connector.Error as err:
        print(f"❌ Error connecting to MySQL: {err}")
        return None

def clear_existing_rules(cursor):
    """Clear existing rules from the table"""
    try:
        cursor.execute("DELETE FROM rules WHERE created_by = 'script'")
        print("🗑️  Cleared existing script-created rules")
    except mysql.connector.Error as err:
        print(f"⚠️  Warning: Could not clear existing rules: {err}")

def insert_rule(cursor, name, priority, keywords, main_category, sub_category, is_active=1, frequency=0, confidence=0.95, created_by='script'):
    """Insert a single rule into the database"""
    try:
        # Convert keywords list to JSON string
        keywords_json = json.dumps(keywords)
        
        current_time = datetime.now()
        
        insert_query = """
        INSERT INTO rules (name, priority, keywords, main_category, sub_category, is_active, frequency, confidence, created_at, updated_at, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        values = (
            name, priority, keywords_json, main_category, sub_category,
            is_active, frequency, confidence, current_time, current_time, created_by
        )
        
        cursor.execute(insert_query, values)
        return True
        
    except mysql.connector.Error as err:
        print(f"❌ Error inserting rule '{name}': {err}")
        return False

def push_rules_to_database():
    """Main function to push all rules to database"""
    connection = create_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Clear existing script-created rules
        clear_existing_rules(cursor)
        
        inserted_count = 0
        failed_count = 0
        
        print("\n📝 Processing regular rules from RULES list...")
        
        # Process regular rules from RULES list
        for rule in RULES:
            name = rule.get('name', '')
            priority = rule.get('priority', 100)
            keywords = rule.get('any', [])
            main_category = rule.get('main', '')
            sub_category = rule.get('sub', '')
            
            if insert_rule(cursor, name, priority, keywords, main_category, sub_category):
                inserted_count += 1
                print(f"✅ Inserted: {name}")
            else:
                failed_count += 1
        
        print(f"\n👥 Processing salary rules from SALARY_NAME_MAP...")
        
        # Process salary rules from SALARY_NAME_MAP
        for sub_category, names in SALARY_NAME_MAP.items():
            for name in names:
                # Create a rule name for salary
                rule_name = f"Salary: {name}"
                priority = 5  # Highest priority for salary rules
                keywords = [name] + ["SALARY", "EXPENSES", "NEFT DR", "IMPS", "TPT"]
                main_category = "Salaries & Wages"
                
                if insert_rule(cursor, rule_name, priority, keywords, main_category, sub_category):
                    inserted_count += 1
                    print(f"✅ Inserted: {rule_name}")
                else:
                    failed_count += 1
        
        # Commit all changes
        connection.commit()
        
        print(f"\n📊 Summary:")
        print(f"   ✅ Successfully inserted: {inserted_count} rules")
        print(f"   ❌ Failed to insert: {failed_count} rules")
        print(f"   📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return failed_count == 0
        
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
    print("🚀 Starting rules push to database...")
    print(f"📋 Database: {DB_CONFIG['database']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}")
    
    # Check if we can import rules
    try:
        total_rules = len(RULES) + sum(len(names) for names in SALARY_NAME_MAP.values())
        print(f"📊 Total rules to process: {total_rules}")
        print(f"   - Regular rules: {len(RULES)}")
        print(f"   - Salary rules: {sum(len(names) for names in SALARY_NAME_MAP.values())}")
    except ImportError as e:
        print(f"❌ Error importing rules: {e}")
        return
    
    success = push_rules_to_database()
    
    if success:
        print("\n🎉 All rules successfully pushed to database!")
    else:
        print("\n⚠️  Some rules failed to insert. Check the errors above.")

if __name__ == "__main__":
    main()
