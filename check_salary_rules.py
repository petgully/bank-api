#!/usr/bin/env python3
import mysql.connector
import json

try:
    # Connect to database
    print("Connecting to database...")
    conn = mysql.connector.connect(
        host='petgully-dbserver.cmzwm2y64qh8.us-east-1.rds.amazonaws.com',
        user='admin',
        password='care6886',
        database='petgully_db'
    )
    print("Connected successfully!")
    
    cur = conn.cursor()

    # Check salary rules
    print("Checking salary rules...")
    cur.execute("SELECT name, keywords, main_category, sub_category FROM rules WHERE name LIKE 'Salary:%' ORDER BY priority")
    salary_rules = cur.fetchall()

    print(f'=== SALARY RULES IN DATABASE ({len(salary_rules)} found) ===')
    for rule in salary_rules:
        name, keywords_json, main, sub = rule
        keywords = json.loads(keywords_json) if keywords_json else []
        print(f'{name}: {keywords} -> {main} -> {sub}')

    # Check for any rules with "DASARI" in keywords
    print("\nChecking for DASARI rules...")
    cur.execute("SELECT name, keywords, main_category, sub_category FROM rules WHERE keywords LIKE '%DASARI%'")
    dasari_rules = cur.fetchall()

    print(f'\n=== RULES WITH DASARI ({len(dasari_rules)} found) ===')
    for rule in dasari_rules:
        name, keywords_json, main, sub = rule
        keywords = json.loads(keywords_json) if keywords_json else []
        print(f'{name}: {keywords} -> {main} -> {sub}')

    cur.close()
    conn.close()
    print("Done!")

except Exception as e:
    print(f"Error: {e}")
