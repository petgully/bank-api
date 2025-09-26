#!/usr/bin/env python3
"""
Demo version of the enhanced rule learning script that shows how it would work
without requiring database connection.
"""

import sys
import os
from typing import List, Dict, Any, Set
from collections import Counter, defaultdict

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def demo_rule_learning():
    """Demonstrate how the enhanced rule learning would work"""
    
    print("🚀 Enhanced Rule Learning Demo")
    print("=" * 60)
    
    # Simulate some transaction data based on the image you provided
    sample_transactions = [
        {
            "normalized_desc": "ACH D-BAJAJ FINANCE LTD-P400PH",
            "vendor_text": "ACH",
            "main_category_name": "Loan EMI Payments",
            "sub_category_text": "Bajaj Finance",
            "confidence": 0.95
        },
        {
            "normalized_desc": "UPI-SWIGGYINSTAMART-SWIGGYIN",
            "vendor_text": "UPI-SWIGGYINSTAMART",
            "main_category_name": "Office Overhead",
            "sub_category_text": "Swiggy",
            "confidence": 0.95
        },
        {
            "normalized_desc": "50100541552099-TPT-EXPENSE-SALAVATH",
            "vendor_text": "50100541552099-TPT-EXPENSE-SALAVATH",
            "main_category_name": "Salaries & Wages",
            "sub_category_text": "Operations Team",
            "confidence": 0.95
        },
        {
            "normalized_desc": "IMPS-512212180520-HIMADIRECTOR",
            "vendor_text": "IMPS-512212180520-HIMADIRECTOR",
            "main_category_name": "Petty Cash",
            "sub_category_text": "Petty Cash (Mobile Grooming)",
            "confidence": 0.95
        },
        {
            "normalized_desc": "NEFT DR-KKBK0000564-PRASAD DR-",
            "vendor_text": "NEFT",
            "main_category_name": "Salaries & Wages",
            "sub_category_text": "Operations Team",
            "confidence": 0.95
        },
        {
            "normalized_desc": "POS 514834XXXXXX2870 AMAZON P",
            "vendor_text": "POS",
            "main_category_name": "Grooming Inventory",
            "sub_category_text": "Amazon",
            "confidence": 0.95
        }
    ]
    
    print(f"📊 Analyzing {len(sample_transactions)} sample transactions...")
    
    # Simulate pattern grouping
    pattern_groups = {}
    
    for transaction in sample_transactions:
        # Create pattern key
        pattern_key = create_pattern_key(transaction["normalized_desc"], transaction["vendor_text"])
        
        if pattern_key not in pattern_groups:
            pattern_groups[pattern_key] = {
                'transactions': [],
                'main_category': transaction["main_category_name"],
                'sub_category': transaction["sub_category_text"],
                'keywords': extract_keywords(transaction["normalized_desc"], transaction["vendor_text"]),
                'sample_descriptions': set()
            }
        
        pattern_groups[pattern_key]['transactions'].append(transaction)
        pattern_groups[pattern_key]['sample_descriptions'].add(transaction["normalized_desc"])
    
    print(f"🔍 Found {len(pattern_groups)} unique patterns")
    
    # Generate rules from patterns
    new_rules = []
    existing_keywords = {"BAJAJ", "FINANCE", "AMAZON", "SWIGGY"}  # Simulate existing keywords
    
    for pattern_key, group_data in pattern_groups.items():
        frequency = len(group_data['transactions'])
        avg_confidence = sum(t["confidence"] for t in group_data['transactions']) / frequency
        
        if frequency >= 1 and avg_confidence >= 0.8:  # Lower threshold for demo
            # Filter out existing keywords
            new_keywords = [kw for kw in group_data['keywords'] 
                          if kw not in existing_keywords and len(kw) >= 3]
            
            if new_keywords:
                # Create rule name
                rule_name = f"Auto-learned: {new_keywords[0]}"
                if len(new_keywords) > 1:
                    rule_name += f" +{len(new_keywords)-1}"
                
                # Calculate priority
                priority = calculate_priority(frequency, avg_confidence)
                
                new_rule = {
                    "name": rule_name,
                    "priority": priority,
                    "any": new_keywords[:3],
                    "main": group_data['main_category'],
                    "sub": group_data['sub_category'],
                    "frequency": frequency,
                    "confidence": avg_confidence,
                    "sample_descriptions": list(group_data['sample_descriptions'])
                }
                new_rules.append(new_rule)
    
    # Sort by frequency and confidence
    new_rules.sort(key=lambda x: (x['frequency'], x['confidence']), reverse=True)
    
    # Display results
    print_rule_summary(new_rules)
    
    return new_rules

def create_pattern_key(normalized_desc: str, vendor_text: str) -> str:
    """Create a pattern key for grouping similar transactions"""
    if vendor_text and len(vendor_text.strip()) > 2:
        vendor_clean = vendor_text.upper().strip()
        if vendor_clean not in ["ACH", "NEFT", "IMPS", "UPI", "POS", "DR", "CR"]:
            return vendor_clean
    
    # Fallback to key words from description
    words = normalized_desc.upper().split()
    key_words = []
    
    for word in words:
        if (len(word) >= 3 and 
            word not in ["PAYMENT", "TRANSFER", "NEFT", "IMPS", "ACH", "UPI", "POS", "DR", "CR", "THE", "AND", "FOR", "WITH", "FROM", "TO", "OF", "IN", "ON", "AT", "BY"] and
            not word.isdigit() and
            word.isalnum()):
            key_words.append(word)
    
    return " ".join(key_words[:3]) if key_words else normalized_desc.upper()[:50]

def extract_keywords(normalized_desc: str, vendor_text: str) -> List[str]:
    """Extract meaningful keywords from transaction description and vendor text"""
    keywords = []
    
    # Extract from normalized description
    words = normalized_desc.upper().split()
    for word in words:
        if (len(word) >= 3 and 
            word not in ["THE", "AND", "FOR", "WITH", "FROM", "TO", "OF", "IN", "ON", "AT", "BY", 
                        "PAYMENT", "TRANSFER", "NEFT", "IMPS", "ACH", "UPI", "POS", "DR", "CR"] and
            not word.isdigit() and
            word.isalnum()):
            keywords.append(word)
    
    # Extract from vendor text
    if vendor_text and len(vendor_text.strip()) > 2:
        vendor_clean = vendor_text.upper().strip()
        if vendor_clean not in ["ACH", "NEFT", "IMPS", "UPI", "POS", "DR", "CR"]:
            keywords.append(vendor_clean)
    
    return list(set(keywords))

def calculate_priority(frequency: int, confidence: float) -> int:
    """Calculate rule priority based on frequency and confidence"""
    if frequency >= 10 and confidence >= 0.9:
        return 10  # High priority
    elif frequency >= 5 and confidence >= 0.8:
        return 20  # Medium-high priority
    elif frequency >= 3 and confidence >= 0.7:
        return 30  # Medium priority
    else:
        return 50  # Low priority

def print_rule_summary(new_rules: List[Dict[str, Any]]):
    """Print a detailed summary of the new rules"""
    if not new_rules:
        print("No new rules found to learn.")
        return
    
    print(f"\n{'='*80}")
    print(f"RULE LEARNING SUMMARY - {len(new_rules)} NEW RULES FOUND")
    print(f"{'='*80}")
    
    # Group by main category for better organization
    by_category = defaultdict(list)
    for rule in new_rules:
        by_category[rule['main']].append(rule)
    
    for category, rules in by_category.items():
        print(f"\n📁 {category} ({len(rules)} rules)")
        print("-" * 60)
        
        for i, rule in enumerate(rules, 1):
            print(f"\n{i}. {rule['name']}")
            print(f"   Keywords: {', '.join(rule['any'])}")
            print(f"   Sub-category: {rule['sub']}")
            print(f"   Frequency: {rule['frequency']} transactions")
            print(f"   Confidence: {rule['confidence']:.2f}")
            print(f"   Priority: {rule['priority']}")
            
            # Show sample descriptions
            samples = rule['sample_descriptions']
            if samples:
                sample_text = " | ".join(samples)[:120]
                print(f"   Sample: {sample_text}...")

def show_rule_format():
    """Show how the rules would be formatted for rules.py"""
    print(f"\n{'='*80}")
    print("RULE FORMAT FOR rules.py")
    print(f"{'='*80}")
    
    sample_rules = [
        {
            "name": "Auto-learned: SWIGGYINSTAMART",
            "priority": 20,
            "any": ["SWIGGYINSTAMART", "SWIGGY", "INSTAMART"],
            "main": "Office Overhead",
            "sub": "Swiggy"
        },
        {
            "name": "Auto-learned: HIMADIRECTOR",
            "priority": 20,
            "any": ["HIMADIRECTOR", "IMPS", "512212180520"],
            "main": "Petty Cash",
            "sub": "Petty Cash (Mobile Grooming)"
        }
    ]
    
    print("The new rules would be added to rules.py in this format:")
    print()
    
    for rule in sample_rules:
        # Properly escape all special characters
        def escape_string(s):
            if not s:
                return '""'
            s = str(s).replace('\\', '\\\\')
            s = s.replace('"', '\\"')
            s = s.replace('\n', '\\n')
            s = s.replace('\r', '\\r')
            s = s.replace('\t', '\\t')
            return f'"{s}"'
        
        # Format the any list properly
        any_items = [escape_string(item) for item in rule["any"]]
        any_list = f"[{', '.join(any_items)}]"
        
        # Create the rule entry
        rule_entry = f'    {{"name":{escape_string(rule["name"])}, "priority":{rule["priority"]}, "any":{any_list}, "main":{escape_string(rule["main"])},"sub":{escape_string(rule["sub"])}}},'
        print(rule_entry)
    
    print()
    print("These rules would be inserted before the closing ']' in the RULES list.")

if __name__ == "__main__":
    # Run the demo
    new_rules = demo_rule_learning()
    
    # Show rule format
    show_rule_format()
    
    print(f"\n{'='*80}")
    print("DEMO COMPLETE")
    print(f"{'='*80}")
    print("✅ The enhanced rule learning script is ready to use!")
    print("📝 To use with your database, run:")
    print("   python enhanced_learn_rules.py --dry-run")
    print("   python enhanced_learn_rules.py")
    print("📚 See RULE_LEARNING_GUIDE.md for detailed usage instructions.")
