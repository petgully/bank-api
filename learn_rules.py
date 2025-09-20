#!/usr/bin/env python3
"""
Standalone script for learning rules from verified database transactions.
This can be run manually to update rules.py with new patterns found in the database.

Usage:
    python learn_rules.py [--dry-run] [--min-frequency 2] [--min-confidence 0.8]
    
Options:
    --dry-run: Show what rules would be learned without updating rules.py
    --min-frequency: Minimum frequency for a pattern to be considered (default: 2)
    --min-confidence: Minimum confidence for a pattern to be considered (default: 0.8)
"""

import os
import sys
import argparse
import mysql.connector
from typing import List, Dict, Any

# Add current directory to path to import from app.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import database connection and rule loading from app.py
from app import get_conn, _load_rules_module, normalize_desc

def learn_rules_from_database(min_frequency: int = 2, min_confidence: float = 0.8) -> List[Dict[str, Any]]:
    """
    Analyze verified transactions from database and generate new rules
    """
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Get verified transactions with their categories
        query = """
        SELECT 
            tc.normalized_desc,
            tc.vendor_text,
            tc.sub_category_text,
            cm.name as main_category,
            COUNT(*) as frequency,
            AVG(tc.confidence) as avg_confidence,
            GROUP_CONCAT(DISTINCT tc.normalized_desc SEPARATOR ' | ') as sample_descriptions
        FROM transactions_canonical tc
        LEFT JOIN categories_main cm ON tc.main_category_id = cm.id
        WHERE tc.reviewed_at IS NOT NULL 
        AND tc.confidence >= %s
        AND tc.normalized_desc IS NOT NULL
        AND tc.normalized_desc != ''
        GROUP BY tc.normalized_desc, tc.vendor_text, tc.sub_category_text, cm.name
        HAVING COUNT(*) >= %s
        ORDER BY frequency DESC, avg_confidence DESC
        """
        
        cur.execute(query, (min_confidence, min_frequency))
        results = cur.fetchall()
        
        new_rules = []
        existing_keywords = set()
        
        # Get existing rule keywords to avoid duplicates
        mod = _load_rules_module()
        if mod and hasattr(mod, "RULES"):
            for rule in mod.RULES:
                existing_keywords.update(rule.get("any", []))
        
        print(f"Found {len(results)} transaction patterns to analyze...")
        
        for row in results:
            normalized_desc, vendor_text, sub_category, main_category, frequency, avg_confidence, sample_descriptions = row
            
            if not main_category or not sub_category:
                continue
                
            # Extract potential keywords from normalized description
            words = normalized_desc.upper().split()
            keywords = []
            
            for word in words:
                # Filter out common words and short words
                if (len(word) >= 3 and 
                    word not in existing_keywords and
                    word not in ["THE", "AND", "FOR", "WITH", "FROM", "TO", "OF", "IN", "ON", "AT", "BY", "PAYMENT", "TRANSFER", "NEFT", "IMPS"]):
                    keywords.append(word)
            
            # Also check vendor text
            if vendor_text and len(vendor_text) >= 3:
                vendor_clean = vendor_text.upper().strip()
                if vendor_clean not in existing_keywords:
                    keywords.append(vendor_clean)
            
            if keywords and frequency >= min_frequency and avg_confidence >= min_confidence:
                # Create rule name
                rule_name = f"Auto-learned: {keywords[0]}"
                if len(keywords) > 1:
                    rule_name += f" +{len(keywords)-1}"
                
                new_rule = {
                    "name": rule_name,
                    "priority": 50,  # Medium priority for auto-learned rules
                    "any": keywords[:3],  # Limit to top 3 keywords
                    "main": main_category,
                    "sub": sub_category,
                    "frequency": frequency,
                    "confidence": avg_confidence,
                    "sample_descriptions": sample_descriptions
                }
                new_rules.append(new_rule)
        
        return new_rules
        
    except Exception as e:
        print(f"Error learning rules from database: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def update_rules_file(new_rules: List[Dict[str, Any]]) -> bool:
    """
    Update rules.py file with new learned rules
    """
    if not new_rules:
        print("No new rules to add.")
        return False
    
    try:
        # Read current rules.py
        with open("rules.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # Find the RULES list end
        rules_end = content.rfind("]")
        if rules_end == -1:
            print("Could not find RULES list in rules.py")
            return False
        
        # Generate new rule entries
        new_rule_entries = []
        for rule in new_rules:
            rule_entry = f'    {{"name":"{rule["name"]}", "priority":{rule["priority"]}, "any":{rule["any"]}, "main":"{rule["main"]}","sub":"{rule["sub"]}"}},'
            new_rule_entries.append(rule_entry)
        
        # Insert new rules before the closing bracket
        new_content = content[:rules_end] + "\n\n    # Auto-learned rules\n" + "\n".join(new_rule_entries) + "\n" + content[rules_end:]
        
        # Write back to file
        with open("rules.py", "w", encoding="utf-8") as f:
            f.write(new_content)
        
        print(f"Successfully added {len(new_rules)} new rules to rules.py")
        return True
        
    except Exception as e:
        print(f"Error updating rules.py: {e}")
        return False

def print_rule_summary(new_rules: List[Dict[str, Any]]):
    """
    Print a summary of the new rules that would be learned
    """
    if not new_rules:
        print("No new rules found to learn.")
        return
    
    print(f"\n{'='*60}")
    print(f"RULE LEARNING SUMMARY - {len(new_rules)} NEW RULES FOUND")
    print(f"{'='*60}")
    
    for i, rule in enumerate(new_rules, 1):
        print(f"\n{i}. {rule['name']}")
        print(f"   Keywords: {', '.join(rule['any'])}")
        print(f"   Category: {rule['main']} -> {rule['sub']}")
        print(f"   Frequency: {rule['frequency']} transactions")
        print(f"   Confidence: {rule['confidence']:.2f}")
        print(f"   Sample: {rule['sample_descriptions'][:100]}...")

def main():
    parser = argparse.ArgumentParser(description="Learn new rules from verified database transactions")
    parser.add_argument("--dry-run", action="store_true", help="Show what rules would be learned without updating rules.py")
    parser.add_argument("--min-frequency", type=int, default=2, help="Minimum frequency for a pattern to be considered (default: 2)")
    parser.add_argument("--min-confidence", type=float, default=0.8, help="Minimum confidence for a pattern to be considered (default: 0.8)")
    
    args = parser.parse_args()
    
    print("Starting rule learning process...")
    print(f"Parameters: min_frequency={args.min_frequency}, min_confidence={args.min_confidence}")
    
    # Learn new rules from database
    new_rules = learn_rules_from_database(args.min_frequency, args.min_confidence)
    
    # Print summary
    print_rule_summary(new_rules)
    
    if args.dry_run:
        print(f"\n[DRY RUN] Would learn {len(new_rules)} new rules")
        return
    
    if not new_rules:
        print("\nNo new rules to add.")
        return
    
    # Ask for confirmation
    response = input(f"\nDo you want to add these {len(new_rules)} rules to rules.py? (y/N): ")
    if response.lower() not in ['y', 'yes']:
        print("Rule learning cancelled.")
        return
    
    # Update rules.py file
    success = update_rules_file(new_rules)
    
    if success:
        print(f"\n✅ Successfully learned {len(new_rules)} new rules!")
        print("Rules have been added to rules.py and will be active immediately.")
    else:
        print("\n❌ Failed to update rules.py file")

if __name__ == "__main__":
    main()
