#!/usr/bin/env python3
"""
Enhanced Rule Learning Script for Bank Transaction Categorization

This script analyzes verified transactions from the database and generates new rules
to add to rules.py. It uses the v_transactions_with_category view for better data access.

Usage:
    python enhanced_learn_rules.py [--dry-run] [--min-frequency 2] [--min-confidence 0.8]
    
Options:
    --dry-run: Show what rules would be learned without updating rules.py
    --min-frequency: Minimum frequency for a pattern to be considered (default: 2)
    --min-confidence: Minimum confidence for a pattern to be considered (default: 0.8)
    --include-unreviewed: Include unreviewed transactions (default: only reviewed)
    --max-rules: Maximum number of rules to generate (default: 50)
"""

import os
import sys
import argparse
import mysql.connector
import re
from typing import List, Dict, Any, Set, Tuple
from collections import Counter, defaultdict

# Add current directory to path to import from app.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import database connection and rule loading from app.py
from app import get_conn, _load_rules_module, normalize_desc

class RuleLearner:
    def __init__(self, min_frequency: int = 2, min_confidence: float = 0.8, 
                 use_reviewed_only: bool = True, max_rules: int = 50):
        self.min_frequency = min_frequency
        self.min_confidence = min_confidence
        self.use_reviewed_only = use_reviewed_only
        self.max_rules = max_rules
        self.existing_keywords = self._load_existing_keywords()
        
    def _load_existing_keywords(self) -> Set[str]:
        """Load existing keywords from current rules to avoid duplicates"""
        existing_keywords = set()
        try:
            mod = _load_rules_module()
            if mod and hasattr(mod, "RULES"):
                for rule in mod.RULES:
                    existing_keywords.update(rule.get("any", []))
                # Also add salary names
                if hasattr(mod, "SALARY_NAME_MAP"):
                    for names in mod.SALARY_NAME_MAP.values():
                        existing_keywords.update(names)
        except Exception as e:
            print(f"Warning: Could not load existing keywords: {e}")
        return existing_keywords

    def learn_rules_from_database(self) -> List[Dict[str, Any]]:
        """
        Analyze transactions from database and generate new rules using the view
        """
        conn = get_conn()
        cur = conn.cursor()
        
        try:
            # Use the provided view for better data access
            base_query = """
            SELECT 
                id,
                raw_hash,
                posted_at,
                normalized_desc,
                amount,
                debit_credit,
                vendor_text,
                main_category_id,
                main_category_name,
                main_category_code,
                sub_category_text,
                confidence,
                source,
                reviewed_at,
                created_at
            FROM petgully_db.v_transactions_with_category
            WHERE normalized_desc IS NOT NULL
            AND normalized_desc != ''
            AND confidence >= %s
            """
            
            # Add reviewed filter if requested
            if self.use_reviewed_only:
                base_query += " AND reviewed_at IS NOT NULL"
            
            base_query += " ORDER BY created_at DESC"
            
            cur.execute(base_query, (self.min_confidence,))
            all_transactions = cur.fetchall()
            
            print(f"Found {len(all_transactions)} transactions to analyze...")
            
            # Group transactions by patterns for rule learning
            pattern_groups = self._group_transactions_by_patterns(all_transactions)
            
            # Generate rules from patterns
            new_rules = self._generate_rules_from_patterns(pattern_groups)
            
            # Sort by frequency and confidence, limit to max_rules
            new_rules.sort(key=lambda x: (x['frequency'], x['confidence']), reverse=True)
            return new_rules[:self.max_rules]
            
        except Exception as e:
            print(f"Error learning rules from database: {e}")
            return []
        finally:
            cur.close()
            conn.close()

    def _group_transactions_by_patterns(self, transactions: List[Tuple]) -> Dict[str, Dict]:
        """Group transactions by similar patterns"""
        pattern_groups = {}
        
        for row in transactions:
            (id, raw_hash, posted_at, normalized_desc, amount, debit_credit, 
             vendor_text, main_category_id, main_category_name, main_category_code,
             sub_category_text, confidence, source, reviewed_at, created_at) = row
            
            # Skip if no category information
            if not main_category_name or not sub_category_text:
                continue
            
            # Create pattern key based on vendor_text and key words from description
            pattern_key = self._create_pattern_key(normalized_desc, vendor_text)
            
            if pattern_key not in pattern_groups:
                pattern_groups[pattern_key] = {
                    'transactions': [],
                    'main_category': main_category_name,
                    'sub_category': sub_category_text,
                    'keywords': self._extract_keywords(normalized_desc, vendor_text),
                    'sample_descriptions': set(),
                    'vendor_texts': set()
                }
            
            pattern_groups[pattern_key]['transactions'].append(row)
            pattern_groups[pattern_key]['sample_descriptions'].add(normalized_desc)
            if vendor_text:
                pattern_groups[pattern_key]['vendor_texts'].add(vendor_text)
        
        return pattern_groups

    def _create_pattern_key(self, normalized_desc: str, vendor_text: str) -> str:
        """
        Create a pattern key for grouping similar transactions
        """
        # Use vendor_text as primary key if available and meaningful
        if vendor_text and len(vendor_text.strip()) > 2:
            vendor_clean = vendor_text.upper().strip()
            # Filter out generic transaction types
            if vendor_clean not in ["ACH", "NEFT", "IMPS", "UPI", "POS", "DR", "CR"]:
                return vendor_clean
        
        # Fallback to key words from description
        words = normalized_desc.upper().split()
        key_words = []
        
        for word in words:
            # Filter meaningful words
            if (len(word) >= 3 and 
                word not in ["PAYMENT", "TRANSFER", "NEFT", "IMPS", "ACH", "UPI", "POS", "DR", "CR", "THE", "AND", "FOR", "WITH", "FROM", "TO", "OF", "IN", "ON", "AT", "BY"] and
                not word.isdigit() and  # Not just numbers
                word.isalnum()):  # Only alphanumeric
                key_words.append(word)
        
        return " ".join(key_words[:3]) if key_words else normalized_desc.upper()[:50]

    def _extract_keywords(self, normalized_desc: str, vendor_text: str) -> List[str]:
        """
        Extract meaningful keywords from transaction description and vendor text
        """
        keywords = []
        
        # Extract from normalized description
        words = normalized_desc.upper().split()
        for word in words:
            if (len(word) >= 3 and 
                word not in ["THE", "AND", "FOR", "WITH", "FROM", "TO", "OF", "IN", "ON", "AT", "BY", 
                            "PAYMENT", "TRANSFER", "NEFT", "IMPS", "ACH", "UPI", "POS", "DR", "CR"] and
                not word.isdigit() and  # Not just numbers
                word.isalnum()):  # Only alphanumeric
                keywords.append(word)
        
        # Extract from vendor text
        if vendor_text and len(vendor_text.strip()) > 2:
            vendor_clean = vendor_text.upper().strip()
            if vendor_clean not in ["ACH", "NEFT", "IMPS", "UPI", "POS", "DR", "CR"]:
                keywords.append(vendor_clean)
        
        # Remove duplicates and return
        return list(set(keywords))

    def _generate_rules_from_patterns(self, pattern_groups: Dict[str, Dict]) -> List[Dict[str, Any]]:
        """Generate rules from grouped patterns"""
        new_rules = []
        
        for pattern_key, group_data in pattern_groups.items():
            frequency = len(group_data['transactions'])
            avg_confidence = sum(t[11] for t in group_data['transactions']) / frequency
            
            if frequency >= self.min_frequency and avg_confidence >= self.min_confidence:
                # Filter out existing keywords
                new_keywords = [kw for kw in group_data['keywords'] 
                              if kw not in self.existing_keywords and len(kw) >= 3]
                
                if new_keywords:
                    # Create rule name based on the most common keyword
                    keyword_counts = Counter(group_data['keywords'])
                    top_keyword = keyword_counts.most_common(1)[0][0]
                    
                    rule_name = f"Auto-learned: {top_keyword}"
                    if len(new_keywords) > 1:
                        rule_name += f" +{len(new_keywords)-1}"
                    
                    # Determine priority based on frequency and confidence
                    priority = self._calculate_priority(frequency, avg_confidence)
                    
                    new_rule = {
                        "name": rule_name,
                        "priority": priority,
                        "any": new_keywords[:3],  # Limit to top 3 keywords
                        "main": group_data['main_category'],
                        "sub": group_data['sub_category'],
                        "frequency": frequency,
                        "confidence": avg_confidence,
                        "sample_descriptions": list(group_data['sample_descriptions'])[:3],
                        "vendor_texts": list(group_data['vendor_texts'])[:3]
                    }
                    new_rules.append(new_rule)
        
        return new_rules

    def _calculate_priority(self, frequency: int, confidence: float) -> int:
        """Calculate rule priority based on frequency and confidence"""
        if frequency >= 10 and confidence >= 0.9:
            return 10  # High priority
        elif frequency >= 5 and confidence >= 0.8:
            return 20  # Medium-high priority
        elif frequency >= 3 and confidence >= 0.7:
            return 30  # Medium priority
        else:
            return 50  # Low priority

    def update_rules_file(self, new_rules: List[Dict[str, Any]]) -> bool:
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
            
            # Generate new rule entries with proper escaping
            new_rule_entries = []
            for rule in new_rules:
                # Properly escape all special characters
                def escape_string(s):
                    if not s:
                        return '""'
                    # Escape backslashes first, then quotes
                    s = str(s).replace('\\', '\\\\')
                    s = s.replace('"', '\\"')
                    s = s.replace('\n', '\\n')
                    s = s.replace('\r', '\\r')
                    s = s.replace('\t', '\\t')
                    return f'"{s}"'
                
                # Format the any list properly
                any_items = [escape_string(item) for item in rule["any"]]
                any_list = f"[{', '.join(any_items)}]"
                
                # Create the rule entry with proper escaping
                rule_entry = f'    {{"name":{escape_string(rule["name"])}, "priority":{rule["priority"]}, "any":{any_list}, "main":{escape_string(rule["main"])},"sub":{escape_string(rule["sub"])}}},'
                new_rule_entries.append(rule_entry)
            
            # Insert new rules before the closing bracket
            new_content = content[:rules_end] + "\n\n    # Auto-learned rules\n" + "\n".join(new_rule_entries) + "\n" + content[rules_end:]
            
            # Write back to file
            with open("rules.py", "w", encoding="utf-8") as f:
                f.write(new_content)
            
            # Validate the updated file by trying to compile it
            try:
                import ast
                with open("rules.py", "r", encoding="utf-8") as f:
                    ast.parse(f.read())
                print(f"Successfully added {len(new_rules)} new rules to rules.py")
                return True
            except SyntaxError as e:
                print(f"Syntax error in updated rules.py: {e}")
                # Restore original content
                with open("rules.py", "w", encoding="utf-8") as f:
                    f.write(content)
                return False
            
        except Exception as e:
            print(f"Error updating rules.py: {e}")
            return False

    def print_rule_summary(self, new_rules: List[Dict[str, Any]]):
        """
        Print a detailed summary of the new rules that would be learned
        """
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
                
                # Show vendor texts if available
                vendors = rule.get('vendor_texts', [])
                if vendors:
                    vendor_text = " | ".join(vendors)[:80]
                    print(f"   Vendors: {vendor_text}...")

def main():
    parser = argparse.ArgumentParser(description="Enhanced rule learning from database transactions")
    parser.add_argument("--dry-run", action="store_true", help="Show what rules would be learned without updating rules.py")
    parser.add_argument("--min-frequency", type=int, default=2, help="Minimum frequency for a pattern to be considered (default: 2)")
    parser.add_argument("--min-confidence", type=float, default=0.8, help="Minimum confidence for a pattern to be considered (default: 0.8)")
    parser.add_argument("--include-unreviewed", action="store_true", help="Include unreviewed transactions in rule learning (default: only reviewed)")
    parser.add_argument("--max-rules", type=int, default=50, help="Maximum number of rules to generate (default: 50)")
    
    args = parser.parse_args()
    
    print("🚀 Starting enhanced rule learning process...")
    print(f"Parameters: min_frequency={args.min_frequency}, min_confidence={args.min_confidence}, use_reviewed_only={not args.include_unreviewed}, max_rules={args.max_rules}")
    
    # Initialize rule learner
    learner = RuleLearner(
        min_frequency=args.min_frequency,
        min_confidence=args.min_confidence,
        use_reviewed_only=not args.include_unreviewed,
        max_rules=args.max_rules
    )
    
    # Learn new rules from database
    new_rules = learner.learn_rules_from_database()
    
    # Print summary
    learner.print_rule_summary(new_rules)
    
    if args.dry_run:
        print(f"\n[DRY RUN] Would learn {len(new_rules)} new rules")
        return
    
    if not new_rules:
        print("\n✅ No new rules to add.")
        return
    
    # Ask for confirmation
    response = input(f"\n🤔 Do you want to add these {len(new_rules)} rules to rules.py? (y/N): ")
    if response.lower() not in ['y', 'yes']:
        print("❌ Rule learning cancelled.")
        return
    
    # Update rules.py file
    success = learner.update_rules_file(new_rules)
    
    if success:
        print(f"\n✅ Successfully learned {len(new_rules)} new rules!")
        print("🎉 Rules have been added to rules.py and will be active immediately.")
        print("\n📊 Summary:")
        print(f"   - Total new rules: {len(new_rules)}")
        
        # Count by category
        by_category = defaultdict(int)
        for rule in new_rules:
            by_category[rule['main']] += 1
        
        for category, count in by_category.items():
            print(f"   - {category}: {count} rules")
    else:
        print("\n❌ Failed to update rules.py file")

if __name__ == "__main__":
    main()
