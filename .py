[1mdiff --git a/learn_rules.py b/learn_rules.py[m
[1mindex d2cb47c..44b6c39 100644[m
[1m--- a/learn_rules.py[m
[1m+++ b/learn_rules.py[m
[36m@@ -24,38 +24,79 @@[m [msys.path.append(os.path.dirname(os.path.abspath(__file__)))[m
 # Import database connection and rule loading from app.py[m
 from app import get_conn, _load_rules_module, normalize_desc[m
 [m
[31m-def learn_rules_from_database(min_frequency: int = 2, min_confidence: float = 0.8) -> List[Dict[str, Any]]:[m
[32m+[m[32mdef learn_rules_from_database(min_frequency: int = 2, min_confidence: float = 0.8, use_reviewed_only: bool = True) -> List[Dict[str, Any]]:[m
     """[m
[31m-    Analyze verified transactions from database and generate new rules[m
[32m+[m[32m    Analyze transactions from database and generate new rules[m
     """[m
     conn = get_conn()[m
     cur = conn.cursor()[m
     [m
     try:[m
[31m-        # Get verified transactions with their categories[m
[31m-        query = """[m
[32m+[m[32m        # Get transactions with their categories - using your suggested query structure[m
[32m+[m[32m        base_query = """[m
         SELECT [m
[31m-            tc.normalized_desc,[m
[31m-            tc.vendor_text,[m
[31m-            tc.sub_category_text,[m
[31m-            cm.name as main_category,[m
[31m-            COUNT(*) as frequency,[m
[31m-            AVG(tc.confidence) as avg_confidence,[m
[31m-            GROUP_CONCAT(DISTINCT tc.normalized_desc SEPARATOR ' | ') as sample_descriptions[m
[31m-        FROM transactions_canonical tc[m
[31m-        LEFT JOIN categories_main cm ON tc.main_category_id = cm.id[m
[31m-        WHERE tc.reviewed_at IS NOT NULL [m
[31m-        AND tc.confidence >= %s[m
[31m-        AND tc.normalized_desc IS NOT NULL[m
[31m-        AND tc.normalized_desc != ''[m
[31m-        GROUP BY tc.normalized_desc, tc.vendor_text, tc.sub_category_text, cm.name[m
[31m-        HAVING COUNT(*) >= %s[m
[31m-        ORDER BY frequency DESC, avg_confidence DESC[m
[32m+[m[32m            t.id,[m
[32m+[m[32m            t.raw_hash,[m
[32m+[m[32m            t.posted_at,[m
[32m+[m[32m            t.normalized_desc,[m
[32m+[m[32m            t.amount,[m
[32m+[m[32m            t.debit_credit,[m
[32m+[m[32m            t.vendor_text,[m
[32m+[m[32m            t.main_category_id,[m
[32m+[m[32m            c.name AS main_category_name,[m
[32m+[m[32m            c.code AS main_category_code,[m
[32m+[m[32m            t.sub_category_text,[m
[32m+[m[32m            t.confidence,[m
[32m+[m[32m            t.source,[m
[32m+[m[32m            t.reviewed_at,[m
[32m+[m[32m            t.created_at[m
[32m+[m[32m        FROM petgully_db.transactions_canonical AS t[m
[32m+[m[32m        LEFT JOIN petgully_db.categories_main AS c[m
[32m+[m[32m        ON t.main_category_id = c.id[m
[32m+[m[32m        WHERE t.normalized_desc IS NOT NULL[m
[32m+[m[32m        AND t.normalized_desc != ''[m
[32m+[m[32m        AND t.confidence >= %s[m
         """[m
         [m
[31m-        cur.execute(query, (min_confidence, min_frequency))[m
[31m-        results = cur.fetchall()[m
[32m+[m[32m        # Add reviewed filter if requested[m
[32m+[m[32m        if use_reviewed_only:[m
[32m+[m[32m            base_query += " AND t.reviewed_at IS NOT NULL"[m
         [m
[32m+[m[32m        base_query += " ORDER BY t.created_at DESC"[m
[32m+[m[41m        [m
[32m+[m[32m        cur.execute(base_query, (min_confidence,))[m
[32m+[m[32m        all_transactions = cur.fetchall()[m
[32m+[m[41m        [m
[32m+[m[32m        print(f"Found {len(all_transactions)} transactions to analyze...")[m
[32m+[m[41m        [m
[32m+[m[32m        # Group transactions by patterns for rule learning[m
[32m+[m[32m        pattern_groups = {}[m
[32m+[m[41m        [m
[32m+[m[32m        for row in all_transactions:[m
[32m+[m[32m            (id, raw_hash, posted_at, normalized_desc, amount, debit_credit,[m[41m [m
[32m+[m[32m             vendor_text, main_category_id, main_category_name, main_category_code,[m
[32m+[m[32m             sub_category_text, confidence, source, reviewed_at, created_at) = row[m
[32m+[m[41m            [m
[32m+[m[32m            # Skip if no category information[m
[32m+[m[32m            if not main_category_name or not sub_category_text:[m
[32m+[m[32m                continue[m
[32m+[m[41m            [m
[32m+[m[32m            # Create pattern key based on vendor_text and key words from description[m
[32m+[m[32m            pattern_key = create_pattern_key(normalized_desc, vendor_text)[m
[32m+[m[41m            [m
[32m+[m[32m            if pattern_key not in pattern_groups:[m
[32m+[m[32m                pattern_groups[pattern_key] = {[m
[32m+[m[32m                    'transactions': [],[m
[32m+[m[32m                    'main_category': main_category_name,[m
[32m+[m[32m                    'sub_category': sub_category_text,[m
[32m+[m[32m                    'keywords': extract_keywords(normalized_desc, vendor_text),[m
[32m+[m[32m                    'sample_descriptions': set()[m
[32m+[m[32m                }[m
[32m+[m[41m            [m
[32m+[m[32m            pattern_groups[pattern_key]['transactions'].append(row)[m
[32m+[m[32m            pattern_groups[pattern_key]['sample_descriptions'].add(normalized_desc)[m
[32m+[m[41m        [m
[32m+[m[32m        # Filter patterns by frequency and generate rules[m
         new_rules = [][m
         existing_keywords = set()[m
         [m
[36m@@ -65,48 +106,35 @@[m [mdef learn_rules_from_database(min_frequency: int = 2, min_confidence: float = 0.[m
             for rule in mod.RULES:[m
                 existing_keywords.update(rule.get("any", []))[m
         [m
[31m-        print(f"Found {len(results)} transaction patterns to analyze...")[m
[31m-        [m
[31m-        for row in results:[m
[31m-            normalized_desc, vendor_text, sub_category, main_category, frequency, avg_confidence, sample_descriptions = row[m
[32m+[m[32m        for pattern_key, group_data in pattern_groups.items():[m
[32m+[m[32m            frequency = len(group_data['transactions'])[m
[32m+[m[32m            avg_confidence = sum(t[11] for t in group_data['transactions']) / frequency[m
             [m
[31m-            if not main_category or not sub_category:[m
[31m-                continue[m
[32m+[m[32m            if frequency >= min_frequency and avg_confidence >= min_confidence:[m
[32m+[m[32m                # Filter out existing keywords[m
[32m+[m[32m                new_keywords = [kw for kw in group_data['keywords'][m[41m [m
[32m+[m[32m                              if kw not in existing_keywords and len(kw) >= 3][m
                 [m
[31m-            # Extract potential keywords from normalized description[m
[31m-            words = normalized_desc.upper().split()[m
[31m-            keywords = [][m
[31m-            [m
[31m-            for word in words:[m
[31m-                # Filter out common words and short words[m
[31m-                if (len(word) >= 3 and [m
[31m-                    word not in existing_keywords and[m
[31m-                    word not in ["THE", "AND", "FOR", "WITH", "FROM", "TO", "OF", "IN", "ON", "AT", "BY", "PAYMENT", "TRANSFER", "NEFT", "IMPS"]):[m
[31m-                    keywords.append(word)[m
[31m-            [m
[31m-            # Also check vendor text[m
[31m-            if vendor_text and len(vendor_text) >= 3:[m
[31m-                vendor_clean = vendor_text.upper().strip()[m
[31m-                if vendor_clean not in existing_keywords:[m
[31m-                    keywords.append(vendor_clean)[m
[31m-            [m
[31m-            if keywords and frequency >= min_frequency and avg_confidence >= min_confidence:[m
[31m-                # Create rule name[m
[31m-                rule_name = f"Auto-learned: {keywords[0]}"[m
[31m-                if len(keywords) > 1:[m
[31m-                    r