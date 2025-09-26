#!/usr/bin/env python3
"""
Test script for the improved learn_rules.py functionality
"""

import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from learn_rules import learn_rules_from_database, create_pattern_key, extract_keywords

def test_pattern_key_creation():
    """Test the pattern key creation logic"""
    print("Testing pattern key creation...")
    
    # Test cases
    test_cases = [
        ("ACH D-BAJAJ FINANCE LTD-P400PH", "ACH", "BAJAJ FINANCE"),
        ("UPI-SWIGGYINSTAMART-SWIGGYIN", "UPI-SWIGGYINSTAMART", "SWIGGYINSTAMART"),
        ("50100440274478-TPT-SALARY-KASIMALLA", "50100440274478-TPT-SALARY-KASIMALLA", "KASIMALLA"),
        ("IMPS-512212180520-HIMADIRECTOR", "IMPS-512212180520-HIMADIRECTOR", "HIMADIRECTOR")
    ]
    
    for desc, vendor, expected in test_cases:
        pattern_key = create_pattern_key(desc, vendor)
        print(f"  Description: {desc}")
        print(f"  Vendor: {vendor}")
        print(f"  Pattern Key: {pattern_key}")
        print(f"  Expected contains: {expected}")
        print()

def test_keyword_extraction():
    """Test the keyword extraction logic"""
    print("Testing keyword extraction...")
    
    test_cases = [
        ("ACH D-BAJAJ FINANCE LTD-P400PH", "ACH"),
        ("UPI-SWIGGYINSTAMART-SWIGGYIN", "UPI-SWIGGYINSTAMART"),
        ("50100440274478-TPT-SALARY-KASIMALLA", "50100440274478-TPT-SALARY-KASIMALLA"),
        ("IMPS-512212180520-HIMADIRECTOR", "IMPS-512212180520-HIMADIRECTOR")
    ]
    
    for desc, vendor in test_cases:
        keywords = extract_keywords(desc, vendor)
        print(f"  Description: {desc}")
        print(f"  Vendor: {vendor}")
        print(f"  Keywords: {keywords}")
        print()

def test_database_connection():
    """Test database connection and basic query"""
    print("Testing database connection...")
    
    try:
        from app import get_conn
        
        conn = get_conn()
        cur = conn.cursor()
        
        # Test basic query
        test_query = """
        SELECT COUNT(*) as total_transactions
        FROM petgully_db.transactions_canonical
        WHERE normalized_desc IS NOT NULL
        """
        
        cur.execute(test_query)
        result = cur.fetchone()
        
        print(f"  Total transactions with descriptions: {result[0]}")
        
        # Test reviewed transactions
        reviewed_query = """
        SELECT COUNT(*) as reviewed_transactions
        FROM petgully_db.transactions_canonical
        WHERE normalized_desc IS NOT NULL
        AND reviewed_at IS NOT NULL
        """
        
        cur.execute(reviewed_query)
        result = cur.fetchone()
        
        print(f"  Reviewed transactions: {result[0]}")
        
        cur.close()
        conn.close()
        
        print("  Database connection: SUCCESS")
        
    except Exception as e:
        print(f"  Database connection: FAILED - {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("TESTING IMPROVED LEARN_RULES.PY")
    print("=" * 60)
    
    test_pattern_key_creation()
    test_keyword_extraction()
    test_database_connection()
    
    print("=" * 60)
    print("TESTING COMPLETE")
    print("=" * 60)
