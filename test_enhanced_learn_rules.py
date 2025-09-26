#!/usr/bin/env python3
"""
Test script for the enhanced learn_rules.py functionality
"""

import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from enhanced_learn_rules import RuleLearner

def test_rule_learner_initialization():
    """Test the RuleLearner class initialization"""
    print("Testing RuleLearner initialization...")
    
    try:
        learner = RuleLearner(min_frequency=2, min_confidence=0.8, use_reviewed_only=True, max_rules=50)
        print("  ✅ RuleLearner initialized successfully")
        print(f"  - Min frequency: {learner.min_frequency}")
        print(f"  - Min confidence: {learner.min_confidence}")
        print(f"  - Use reviewed only: {learner.use_reviewed_only}")
        print(f"  - Max rules: {learner.max_rules}")
        print(f"  - Existing keywords loaded: {len(learner.existing_keywords)}")
        return True
    except Exception as e:
        print(f"  ❌ RuleLearner initialization failed: {e}")
        return False

def test_pattern_key_creation():
    """Test the pattern key creation logic"""
    print("\nTesting pattern key creation...")
    
    learner = RuleLearner()
    
    # Test cases based on the image data
    test_cases = [
        ("ACH D-BAJAJ FINANCE LTD-P400PH", "ACH", "BAJAJ FINANCE"),
        ("UPI-SWIGGYINSTAMART-SWIGGYIN", "UPI-SWIGGYINSTAMART", "SWIGGYINSTAMART"),
        ("50100440274478-TPT-SALARY-KASIMALLA", "50100440274478-TPT-SALARY-KASIMALLA", "KASIMALLA"),
        ("IMPS-512212180520-HIMADIRECTOR", "IMPS-512212180520-HIMADIRECTOR", "HIMADIRECTOR"),
        ("NEFT DR-KKBK0000564-PRASAD DR-", "NEFT", "PRASAD"),
        ("POS 514834XXXXXX2870 AMAZON P", "POS", "AMAZON")
    ]
    
    for desc, vendor, expected in test_cases:
        pattern_key = learner._create_pattern_key(desc, vendor)
        print(f"  Description: {desc}")
        print(f"  Vendor: {vendor}")
        print(f"  Pattern Key: {pattern_key}")
        print(f"  Expected contains: {expected}")
        print(f"  ✅ Contains expected: {expected in pattern_key}")
        print()

def test_keyword_extraction():
    """Test the keyword extraction logic"""
    print("Testing keyword extraction...")
    
    learner = RuleLearner()
    
    test_cases = [
        ("ACH D-BAJAJ FINANCE LTD-P400PH", "ACH"),
        ("UPI-SWIGGYINSTAMART-SWIGGYIN", "UPI-SWIGGYINSTAMART"),
        ("50100440274478-TPT-SALARY-KASIMALLA", "50100440274478-TPT-SALARY-KASIMALLA"),
        ("IMPS-512212180520-HIMADIRECTOR", "IMPS-512212180520-HIMADIRECTOR"),
        ("NEFT DR-KKBK0000564-PRASAD DR-", "NEFT"),
        ("POS 514834XXXXXX2870 AMAZON P", "POS")
    ]
    
    for desc, vendor in test_cases:
        keywords = learner._extract_keywords(desc, vendor)
        print(f"  Description: {desc}")
        print(f"  Vendor: {vendor}")
        print(f"  Keywords: {keywords}")
        print()

def test_priority_calculation():
    """Test the priority calculation logic"""
    print("Testing priority calculation...")
    
    learner = RuleLearner()
    
    test_cases = [
        (15, 0.95, 10),  # High frequency, high confidence
        (8, 0.85, 20),   # Medium-high frequency, high confidence
        (5, 0.75, 30),   # Medium frequency, medium confidence
        (2, 0.65, 50),   # Low frequency, low confidence
    ]
    
    for frequency, confidence, expected in test_cases:
        priority = learner._calculate_priority(frequency, confidence)
        print(f"  Frequency: {frequency}, Confidence: {confidence:.2f}")
        print(f"  Priority: {priority} (expected: {expected})")
        print(f"  ✅ Correct: {priority == expected}")
        print()

def test_database_connection():
    """Test database connection and basic query"""
    print("Testing database connection...")
    
    try:
        from app import get_conn
        
        conn = get_conn()
        cur = conn.cursor()
        
        # Test basic query using the view
        test_query = """
        SELECT COUNT(*) as total_transactions
        FROM petgully_db.v_transactions_with_category
        WHERE normalized_desc IS NOT NULL
        """
        
        cur.execute(test_query)
        result = cur.fetchone()
        
        print(f"  Total transactions with descriptions: {result[0]}")
        
        # Test reviewed transactions
        reviewed_query = """
        SELECT COUNT(*) as reviewed_transactions
        FROM petgully_db.v_transactions_with_category
        WHERE normalized_desc IS NOT NULL
        AND reviewed_at IS NOT NULL
        """
        
        cur.execute(reviewed_query)
        result = cur.fetchone()
        
        print(f"  Reviewed transactions: {result[0]}")
        
        # Test transactions with categories
        categorized_query = """
        SELECT COUNT(*) as categorized_transactions
        FROM petgully_db.v_transactions_with_category
        WHERE normalized_desc IS NOT NULL
        AND main_category_name IS NOT NULL
        AND sub_category_text IS NOT NULL
        """
        
        cur.execute(categorized_query)
        result = cur.fetchone()
        
        print(f"  Categorized transactions: {result[0]}")
        
        cur.close()
        conn.close()
        
        print("  ✅ Database connection: SUCCESS")
        return True
        
    except Exception as e:
        print(f"  ❌ Database connection: FAILED - {e}")
        return False

def test_rule_learning_dry_run():
    """Test rule learning with dry run"""
    print("\nTesting rule learning (dry run)...")
    
    try:
        learner = RuleLearner(min_frequency=2, min_confidence=0.8, max_rules=10)
        new_rules = learner.learn_rules_from_database()
        
        print(f"  Found {len(new_rules)} potential new rules")
        
        if new_rules:
            print("  Sample rules:")
            for i, rule in enumerate(new_rules[:3], 1):
                print(f"    {i}. {rule['name']}")
                print(f"       Keywords: {', '.join(rule['any'])}")
                print(f"       Category: {rule['main']} -> {rule['sub']}")
                print(f"       Frequency: {rule['frequency']}, Confidence: {rule['confidence']:.2f}")
        
        print("  ✅ Rule learning test: SUCCESS")
        return True
        
    except Exception as e:
        print(f"  ❌ Rule learning test: FAILED - {e}")
        return False

if __name__ == "__main__":
    print("=" * 80)
    print("TESTING ENHANCED LEARN_RULES.PY")
    print("=" * 80)
    
    tests = [
        test_rule_learner_initialization,
        test_pattern_key_creation,
        test_keyword_extraction,
        test_priority_calculation,
        test_database_connection,
        test_rule_learning_dry_run
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"  ❌ Test failed with exception: {e}")
    
    print("\n" + "=" * 80)
    print(f"TESTING COMPLETE: {passed}/{total} tests passed")
    print("=" * 80)
    
    if passed == total:
        print("🎉 All tests passed! The enhanced rule learning script is ready to use.")
    else:
        print("⚠️  Some tests failed. Please check the issues above.")
