#!/usr/bin/env python3
"""
Simple Rule Learning Script - Fixed version
"""

import os
import sys
import mysql.connector
from typing import List, Dict, Any, Set
from collections import Counter, defaultdict

class SimpleRuleLearner:
    def __init__(self):
        self.existing_keywords = self._load_existing_keywords()
        
    def _load_existing_keywords(self) -> Set[str]:
        """Load existing keywords from current rules to avoid duplicates"""
        existing_keywords = set()
        try:
            import rules
            if hasattr(rules, "RULES"):
                for rule in rules.RULES:
                    existing_keywords.update(rule.get("any", []))
                if hasattr(rules, "SALARY_NAME_MAP"):
                    for names in rules.SALARY_NAME_MAP.values():
                        existing_keywords.update(names)
        except Exception as e:
            print(f"Warning: Could not load existing keywords: {e}")
        return existing_keywords

    def get_db_connection(self):
        """Get database connection to remote server"""
        return mysql.connector.connect(
            host=os.getenv("DB_HOST", "petgully-dbserver.cmzwm2y64qh8.us-east-1.rds.amazonaws.com"),
            user=os.getenv("DB_USER", "admin"),
            password=os.getenv("DB_PASS", "care6886"),
            database=os.getenv("DB_NAME", "petgully_db")
        )

    def learn_rules_from_database(self) -> List[Dict[str, Any]]:
        """Analyze transactions from database and generate new rules"""
        conn = self.get_db_connection()
        cur = conn.cursor()
        
        try:
            base_query = """
            SELECT 
                id, raw_hash, posted_at, normalized_desc, amount, debit_credit,
                vendor_text, main_category_id, main_category_name, main_category_code,
                sub_category_text, confidence, source, reviewed_at, created_at
            FROM petgully_db.v_transactions_with_category
            WHERE normalized_desc IS NOT NULL
            AND normalized_desc != ''
            AND confidence >= 0.8
            AND reviewed_at IS NOT NULL
            ORDER BY created_at DESC
            """
            
            cur.execute(base_query)
            all_transactions = cur.fetchall()
            
            print(f"Found {len(all_transactions)} transactions to analyze...")
            
            # Group transactions by patterns
            pattern_groups = {}
            
            for row in all_transactions:
                (id, raw_hash, posted_at, normalized_desc, amount, debit_credit, 
                 vendor_text, main_category_id, main_category_name, main_category_code,
                 sub_category_text, confidence, source, reviewed_at, created_at) = row
                
                if not main_category_name or not sub_category_text:
                    continue
                
                # Create pattern key
                pattern_key = self._create_pattern_key(normalized_desc, vendor_text)
                
                if pattern_key not in pattern_groups:
                    pattern_groups[pattern_key] = {
                        'transactions': [],
                        'main_category': main_category_name,
                        'sub_category': sub_category_text,
                        'keywords': self._extract_keywords(normalized_desc, vendor_text),
                        'sample_descriptions': set()
                    }
                
                pattern_groups[pattern_key]['transactions'].append(row)
                pattern_groups[pattern_key]['sample_descriptions'].add(normalized_desc)
            
            # Generate rules from patterns
            new_rules = []
            
            for pattern_key, group_data in pattern_groups.items():
                frequency = len(group_data['transactions'])
                avg_confidence = sum(t[11] for t in group_data['transactions']) / frequency
                
                if frequency >= 2 and avg_confidence >= 0.8:
                    # Filter out existing keywords
                    new_keywords = [kw for kw in group_data['keywords'] 
                                  if kw not in self.existing_keywords and len(kw) >= 3]
                    
                    if new_keywords:
                        # Create rule name
                        rule_name = f"Auto-learned: {new_keywords[0]}"
                        if len(new_keywords) > 1:
                            rule_name += f" +{len(new_keywords)-1}"
                        
                        # Calculate priority
                        priority = 50
                        if frequency >= 10 and avg_confidence >= 0.9:
                            priority = 10
                        elif frequency >= 5 and avg_confidence >= 0.8:
                            priority = 20
                        elif frequency >= 3 and avg_confidence >= 0.7:
                            priority = 30
                        
                        new_rule = {
                            "name": rule_name,
                            "priority": priority,
                            "any": new_keywords[:3],
                            "main": group_data['main_category'],
                            "sub": group_data['sub_category'],
                            "frequency": frequency,
                            "confidence": avg_confidence
                        }
                        new_rules.append(new_rule)
            
            # Sort by frequency and confidence
            new_rules.sort(key=lambda x: (x['frequency'], x['confidence']), reverse=True)
            return new_rules[:10]  # Limit to 10 rules
            
        except Exception as e:
            print(f"Error learning rules from database: {e}")
            return []
        finally:
            cur.close()
            conn.close()

    def _create_pattern_key(self, normalized_desc: str, vendor_text: str) -> str:
        """Create a pattern key for grouping similar transactions"""
        if vendor_text and len(vendor_text.strip()) > 2:
            vendor_clean = vendor_text.upper().strip()
            if vendor_clean not in ["ACH", "NEFT", "IMPS", "UPI", "POS", "DR", "CR"]:
                return vendor_clean
        
        words = normalized_desc.upper().split()
        key_words = []
        
        for word in words:
            if (len(word) >= 3 and 
                word not in ["PAYMENT", "TRANSFER", "NEFT", "IMPS", "ACH", "UPI", "POS", "DR", "CR", "THE", "AND", "FOR", "WITH", "FROM", "TO", "OF", "IN", "ON", "AT", "BY"] and
                not word.isdigit() and
                word.isalnum()):
                key_words.append(word)
        
        return " ".join(key_words[:3]) if key_words else normalized_desc.upper()[:50]

    def _extract_keywords(self, normalized_desc: str, vendor_text: str) -> List[str]:
        """Extract meaningful keywords from transaction description and vendor text"""
        keywords = []
        
        words = normalized_desc.upper().split()
        for word in words:
            if (len(word) >= 3 and 
                word not in ["THE", "AND", "FOR", "WITH", "FROM", "TO", "OF", "IN", "ON", "AT", "BY", 
                            "PAYMENT", "TRANSFER", "NEFT", "IMPS", "ACH", "UPI", "POS", "DR", "CR"] and
                not word.isdigit() and
                word.isalnum()):
                keywords.append(word)
        
        if vendor_text and len(vendor_text.strip()) > 2:
            vendor_clean = vendor_text.upper().strip()
            if vendor_clean not in ["ACH", "NEFT", "IMPS", "UPI", "POS", "DR", "CR"]:
                keywords.append(vendor_clean)
        
        return list(set(keywords))

    def update_rules_file(self, new_rules: List[Dict[str, Any]]) -> bool:
        """Update rules.py file with new learned rules"""
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
            
            # Generate new rule entries - simple approach
            new_rule_entries = []
            for rule in new_rules:
                # Simple escaping - just replace quotes
                name = rule["name"].replace('"', '\\"')
                main_cat = rule["main"].replace('"', '\\"')
                sub_cat = rule["sub"].replace('"', '\\"')
                
                # Format keywords list
                keywords_str = ', '.join([f'"{kw}"' for kw in rule["any"]])
                
                rule_entry = f'    {{"name":"{name}", "priority":{rule["priority"]}, "any":[{keywords_str}], "main":"{main_cat}","sub":"{sub_cat}"}},'
                new_rule_entries.append(rule_entry)
            
            # Insert new rules before the closing bracket
            new_content = content[:rules_end] + "\n\n    # Auto-learned rules\n" + "\n".join(new_rule_entries) + "\n" + content[rules_end:]
            
            # Write back to file
            with open("rules.py", "w", encoding="utf-8") as f:
                f.write(new_content)
            
            # Validate the updated file
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
        """Print a summary of the new rules"""
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
            print(f"   Priority: {rule['priority']}")

def main():
    print("🏠 Starting SIMPLE rule learning process...")
    
    learner = SimpleRuleLearner()
    new_rules = learner.learn_rules_from_database()
    
    learner.print_rule_summary(new_rules)
    
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
        print("📝 Next steps:")
        print("   1. Review the updated rules.py file")
        print("   2. Commit and push to GitHub:")
        print("      git add rules.py")
        print("      git commit -m 'Add auto-learned rules'")
        print("      git push")
        print("   3. Pull on server: git pull")
    else:
        print("\n❌ Failed to update rules.py file")

if __name__ == "__main__":
    main()

