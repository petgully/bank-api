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

def learn_rules_from_database(min_frequency: int = 2, min_confidence: float = 0.8, use_reviewed_only: bool = True) -> List[Dict[str, Any]]:
    """
    Analyze transactions from database and generate new rules
    """
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Get transactions with their categories - using your suggested query structure
        base_query = """
        SELECT 
            t.id,
            t.raw_hash,
            t.posted_at,
            t.normalized_desc,
            t.amount,
            t.debit_credit,
            t.vendor_text,
            t.main_category_id,
            c.name AS main_category_name,
            c.code AS main_category_code,
            t.sub_category_text,
            t.confidence,
            t.source,
            t.reviewed_at,
            t.created_at
        FROM petgully_db.transactions_canonical AS t
        LEFT JOIN petgully_db.categories_main AS c
        ON t.main_category_id = c.id
        WHERE t.normalized_desc IS NOT NULL
        AND t.normalized_desc != ''
        AND t.confidence >= %s
        """
        
        # Add reviewed filter if requested
        if use_reviewed_only:
            base_query += " AND t.reviewed_at IS NOT NULL"
        
        base_query += " ORDER BY t.created_at DESC"
        
        cur.execute(base_query, (min_confidence,))
        all_transactions = cur.fetchall()
        
        print(f"Found {len(all_transactions)} transactions to analyze...")
        
        # Group transactions by patterns for rule learning
        pattern_groups = {}
        
        for row in all_transactions:
            (id, raw_hash, posted_at, normalized_desc, amount, debit_credit, 
             vendor_text, main_category_id, main_category_name, main_category_code,
             sub_category_text, confidence, source, reviewed_at, created_at) = row
            
            # Skip if no category information
            if not main_category_name or not sub_category_text:
                continue
            
            # Create pattern key based on vendor_text and key words from description
            pattern_key = create_pattern_key(normalized_desc, vendor_text)
            
            if pattern_key not in pattern_groups:
                pattern_groups[pattern_key] = {
                    'transactions': [],
                    'main_category': main_category_name,
                    'sub_category': sub_category_text,
                    'keywords': extract_keywords(normalized_desc, vendor_text),
                    'sample_descriptions': set()
                }
            
            pattern_groups[pattern_key]['transactions'].append(row)
            pattern_groups[pattern_key]['sample_descriptions'].add(normalized_desc)
        
        # Filter patterns by frequency and generate rules
        new_rules = []
        existing_keywords = set()
        
        # Get existing rule keywords to avoid duplicates
        mod = _load_rules_module()
        if mod and hasattr(mod, "RULES"):
            for rule in mod.RULES:
                existing_keywords.update(rule.get("any", []))
        
        for pattern_key, group_data in pattern_groups.items():
            frequency = len(group_data['transactions'])
            avg_confidence = sum(t[11] for t in group_data['transactions']) / frequency
            
            if frequency >= min_frequency and avg_confidence >= min_confidence:
                # Filter out existing keywords
                new_keywords = [kw for kw in group_data['keywords'] 
                              if kw not in existing_keywords and len(kw) >= 3]
                
                if new_keywords:
                    # Create rule name
                    rule_name = f"Auto-learned: {new_keywords[0]}"
                    if len(new_keywords) > 1:
                        rule_name += f" +{len(new_keywords)-1}"
                    
                    new_rule = {
                        "name": rule_name,
                        "priority": 50,  # Medium priority for auto-learned rules
                        "any": new_keywords[:3],  # Limit to top 3 keywords
                        "main": group_data['main_category'],
                        "sub": group_data['sub_category'],
                        "frequency": frequency,
                        "confidence": avg_confidence,
                        "sample_descriptions": list(group_data['sample_descriptions'])[:3]  # Top 3 samples
                    }
                    new_rules.append(new_rule)
        
        # Sort by frequency and confidence
        new_rules.sort(key=lambda x: (x['frequency'], x['confidence']), reverse=True)
        
        return new_rules
        
    except Exception as e:
        print(f"Error learning rules from database: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def create_pattern_key(normalized_desc: str, vendor_text: str) -> str:
    """
    Create a pattern key for grouping similar transactions
    """
    # Use vendor_text as primary key if available
    if vendor_text and len(vendor_text.strip()) > 0:
        return vendor_text.upper().strip()
    
    # Fallback to key words from description
    words = normalized_desc.upper().split()
    key_words = [w for w in words if len(w) >= 4 and w not in 
                ["PAYMENT", "TRANSFER", "NEFT", "IMPS", "ACH", "UPI", "POS"]]
    
    return " ".join(key_words[:3]) if key_words else normalized_desc.upper()[:50]

def extract_keywords(normalized_desc: str, vendor_text: str) -> List[str]:
    """
    Extract meaningful keywords from transaction description and vendor text
    """
    keywords = []
    
    # Extract from normalized description
    words = normalized_desc.upper().split()
    for word in words:
        if (len(word) >= 3 and 
            word not in ["THE", "AND", "FOR", "WITH", "FROM", "TO", "OF", "IN", "ON", "AT", "BY", 
                        "PAYMENT", "TRANSFER", "NEFT", "IMPS", "ACH", "UPI", "POS", "DR", "CR"]):
            keywords.append(word)
    
    # Extract from vendor text
    if vendor_text and len(vendor_text.strip()) > 0:
        vendor_clean = vendor_text.upper().strip()
        if len(vendor_clean) >= 3:
            keywords.append(vendor_clean)
    
    # Remove duplicates and return
    return list(set(keywords))

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
            # Escape quotes in rule name and categories
            name = rule["name"].replace('"', '\\"')
            main_cat = rule["main"].replace('"', '\\"')
            sub_cat = rule["sub"].replace('"', '\\"')
            
            rule_entry = f'    {{"name":"{name}", "priority":{rule["priority"]}, "any":{rule["any"]}, "main":"{main_cat}","sub":"{sub_cat}"}},'
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
        # Handle sample descriptions (could be list or string)
        samples = rule['sample_descriptions']
        if isinstance(samples, list):
            sample_text = " | ".join(samples)[:100]
        else:
            sample_text = str(samples)[:100]
        print(f"   Sample: {sample_text}...")

def main():
    parser = argparse.ArgumentParser(description="Learn new rules from database transactions")
    parser.add_argument("--dry-run", action="store_true", help="Show what rules would be learned without updating rules.py")
    parser.add_argument("--min-frequency", type=int, default=2, help="Minimum frequency for a pattern to be considered (default: 2)")
    parser.add_argument("--min-confidence", type=float, default=0.8, help="Minimum confidence for a pattern to be considered (default: 0.8)")
    parser.add_argument("--include-unreviewed", action="store_true", help="Include unreviewed transactions in rule learning (default: only reviewed)")
    
    args = parser.parse_args()
    
    print("Starting rule learning process...")
    print(f"Parameters: min_frequency={args.min_frequency}, min_confidence={args.min_confidence}, use_reviewed_only={not args.include_unreviewed}")
    
    # Learn new rules from database
    new_rules = learn_rules_from_database(args.min_frequency, args.min_confidence, not args.include_unreviewed)
    
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
