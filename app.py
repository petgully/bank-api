from fastapi import FastAPI, Depends, Header, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Tuple
import os, re, hashlib, importlib, sys
import joblib

# ---------- FastAPI ----------
app = FastAPI()

# ---------- Security ----------
API_KEY = os.getenv("API_KEY", "")

def require_key(x_api_key: str = Header(default="")):
    if not API_KEY or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

# ---------- Optional OpenAI for subcategory fallback ----------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

try:
    import openai
    if OPENAI_API_KEY:
        openai.api_key = OPENAI_API_KEY
except Exception:
    openai = None

# ---------- MySQL ----------
import mysql.connector

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")

def get_conn():
    return mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME
    )

# ---------- ML artifacts (optional) ----------
MODEL = None
VECT = None
ML_THRESHOLD = float(os.getenv("ML_THRESHOLD", "0.75"))  # used if model exists

def load_model():
    global MODEL, VECT
    try:
        VECT = joblib.load("model/tfidf.joblib")
        MODEL = joblib.load("model/logreg.joblib")
        print("ML model loaded.")
    except Exception as e:
        print(f"ML model not loaded: {e}")

load_model()

# ---------- Database Rules System ----------
import json
from typing import List, Dict, Tuple

# Cache for database rules
_db_rules_cache = None
_db_rules_timestamp = None
CACHE_DURATION = 300  # 5 minutes cache

def _load_rules_from_database():
    """Load rules from database with caching"""
    global _db_rules_cache, _db_rules_timestamp
    
    import time
    current_time = time.time()
    
    # Return cached rules if still valid
    if (_db_rules_cache is not None and 
        _db_rules_timestamp is not None and 
        current_time - _db_rules_timestamp < CACHE_DURATION):
        return _db_rules_cache
    
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Fetch all active rules from database
        query = """
        SELECT name, priority, keywords, main_category, sub_category, is_active
        FROM rules 
        WHERE is_active = 1 
        ORDER BY priority ASC
        """
        
        cur.execute(query)
        results = cur.fetchall()
        
        # Process rules into the expected format
        rules = []
        salary_rules = []
        
        for row in results:
            name, priority, keywords_json, main_category, sub_category, is_active = row
            
            if not is_active:
                continue
                
            # Parse keywords JSON
            try:
                keywords = json.loads(keywords_json) if keywords_json else []
            except (json.JSONDecodeError, TypeError):
                keywords = []
            
            # Check if this is a salary rule
            if name.startswith("Salary: "):
                salary_rules.append({
                    "name": name,
                    "priority": priority,
                    "keywords": keywords,
                    "main_category": main_category,
                    "sub_category": sub_category
                })
            else:
                rules.append({
                    "name": name,
                    "priority": priority,
                    "keywords": keywords,
                    "main_category": main_category,
                    "sub_category": sub_category
                })
        
        # Cache the results
        _db_rules_cache = {
            "rules": rules,
            "salary_rules": salary_rules
        }
        _db_rules_timestamp = current_time
        
        print(f"Loaded {len(rules)} regular rules and {len(salary_rules)} salary rules from database")
        
        cur.close()
        conn.close()
        
        return _db_rules_cache
        
    except Exception as e:
        print(f"Error loading rules from database: {e}")
        return None

def apply_rules_wrapper(narration: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Apply rules from database to categorize transaction narration
    Returns: (main_category, sub_category, rule_name) or (None, None, None)
    """
    if narration is None:
        return (None, None, None)
    
    # Load rules from database
    rules_data = _load_rules_from_database()
    if not rules_data:
        return (None, None, None)
    
    text = str(narration).upper()
    
    try:
        # 1) Check salary rules first (highest precedence)
        for rule in rules_data["salary_rules"]:
            if any(keyword in text for keyword in rule["keywords"]):
                return (rule["main_category"], rule["sub_category"], rule["name"])
        
        # 2) Check regular rules (by priority)
        for rule in rules_data["rules"]:
            if any(keyword in text for keyword in rule["keywords"]):
                return (rule["main_category"], rule["sub_category"], rule["name"])
        
        # 3) No rule matched
        return (None, None, None)
        
    except Exception as e:
        print(f"Error applying rules: {e}")
        return (None, None, None)

# ---------- Schemas ----------
class RowIn(BaseModel):
    row_index: Optional[int] = None
    date: str
    description: str
    amount: float
    balance: Optional[float] = None
    account: Optional[str] = ""
    currency: Optional[str] = "INR"

class PredOut(RowIn):
    vendor: Optional[str] = ""
    rule_hit: Optional[str] = ""
    main_category_suggested: str
    sub_category_suggested: str
    confidence: float

class Rows(BaseModel):
    rows: List[RowIn]

class SyncRowIn(RowIn):
    vendor: Optional[str] = None
    main_category: Optional[str] = None
    sub_category: Optional[str] = None
    confidence: Optional[float] = None
    rule_hit: Optional[str] = None
    raw_row: Optional[int] = None

class SyncRows(BaseModel):
    rows: List[SyncRowIn]

# ---------- Utils ----------
def normalize_desc(s: str) -> str:
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'[^A-Za-z0-9 &:/._-]', '', s)
    return s

def tx_hash(account: str, date: str, amount: float, norm_desc: str) -> str:
    return hashlib.sha256(f"{account}|{date}|{amount:.2f}|{norm_desc}".encode("utf-8")).hexdigest()

def ml_main_category(desc: str) -> Tuple[str, float]:
    if MODEL is None or VECT is None:
        return "Uncategorized", 0.0
    try:
        X = VECT.transform([desc])
        proba = MODEL.predict_proba(X)[0]
        idx = proba.argmax()
        label = MODEL.classes_[idx]
        conf = float(proba[idx])
        return label, conf
    except Exception:
        return "Uncategorized", 0.0

def llm_subcategory(desc: str, amount: float, main: str) -> str:
    if not (openai and OPENAI_API_KEY):
        return "Misc"

    prompt = f"""
You assign a short subcategory (2-5 words) for a business bank transaction.

Main category: {main}
Description: {desc}
Amount: {amount}

Rules:
- Be concise, noun-phrase style.
- Prefer consistent vendor-based labels if obvious.
- If unclear, return "Misc".

Only return the subcategory text, nothing else.
"""

    try:
        # If your OpenAI package uses the new API, adjust accordingly.
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}],
            temperature=0.1
        )
        text = resp["choices"][0]["message"]["content"].strip()
        return text[:40] if text else "Misc"
    except Exception:
        return "Misc"

# ---------- Rule Learning System ----------
def learn_rules_from_database():
    """
    Analyze verified transactions from database and generate new rules
    Returns: List of new rules to be added
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
            AVG(tc.confidence) as avg_confidence
        FROM transactions_canonical tc
        LEFT JOIN categories_main cm ON tc.main_category_id = cm.id
        WHERE tc.reviewed_at IS NOT NULL 
        AND tc.confidence > 0.8
        AND tc.normalized_desc IS NOT NULL
        AND tc.normalized_desc != ''
        GROUP BY tc.normalized_desc, tc.vendor_text, tc.sub_category_text, cm.name
        HAVING COUNT(*) >= 2
        ORDER BY frequency DESC, avg_confidence DESC
        """
        
        cur.execute(query)
        results = cur.fetchall()
        
        new_rules = []
        existing_keywords = set()
        
        # Get existing rule keywords from database to avoid duplicates
        rules_data = _load_rules_from_database()
        if rules_data:
            for rule in rules_data["rules"] + rules_data["salary_rules"]:
                existing_keywords.update(rule.get("keywords", []))
        
        for row in results:
            normalized_desc, vendor_text, sub_category, main_category, frequency, avg_confidence = row
            
            if not main_category or not sub_category:
                continue
                
            # Extract potential keywords from normalized description
            words = normalized_desc.upper().split()
            keywords = []
            
            for word in words:
                # Filter out common words, short words, and problematic characters
                if (len(word) >= 3 and 
                    word not in existing_keywords and
                    word not in ["THE", "AND", "FOR", "WITH", "FROM", "TO", "OF", "IN", "ON", "AT", "BY", "PAYMENT", "TRANSFER", "NEFT", "IMPS", "UPI"] and
                    word.isalnum() and  # Only alphanumeric characters
                    not word.isdigit()):  # Not just numbers
                    keywords.append(word)
            
            # Also check vendor text
            if vendor_text and len(vendor_text) >= 3:
                vendor_clean = vendor_text.upper().strip()
                if vendor_clean not in existing_keywords:
                    keywords.append(vendor_clean)
            
            if keywords and frequency >= 2 and avg_confidence > 0.8:
                # Create rule name
                rule_name = f"Auto-learned: {keywords[0]}"
                if len(keywords) > 1:
                    rule_name += f" +{len(keywords)-1}"
                
                new_rule = {
                    "name": rule_name,
                    "priority": 50,  # Medium priority for auto-learned rules
                    "keywords": keywords[:3],  # Limit to top 3 keywords
                    "main_category": main_category,
                    "sub_category": sub_category,
                    "frequency": frequency,
                    "confidence": avg_confidence
                }
                new_rules.append(new_rule)
        
        return new_rules
        
    except Exception as e:
        print(f"Error learning rules from database: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def add_rules_to_database(new_rules):
    """
    Add new learned rules to the database
    """
    if not new_rules:
        print("No new rules to add.")
        return False
    
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Clear cache to force reload
        global _db_rules_cache, _db_rules_timestamp
        _db_rules_cache = None
        _db_rules_timestamp = None
        
        added_count = 0
        
        for rule in new_rules:
            # Check if rule already exists
            check_query = "SELECT id FROM rules WHERE name = %s"
            cur.execute(check_query, (rule["name"],))
            if cur.fetchone():
                print(f"Rule '{rule['name']}' already exists, skipping")
                continue
            
            # Insert new rule
            insert_query = """
            INSERT INTO rules (name, priority, keywords, main_category, sub_category, is_active, frequency, confidence, created_at, updated_at, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s)
            """
            
            values = (
                rule["name"],
                rule["priority"],
                json.dumps(rule["keywords"]),
                rule["main_category"],
                rule["sub_category"],
                1,  # is_active
                rule.get("frequency", 0),
                rule.get("confidence", 0.95),
                "auto-learned"
            )
            
            cur.execute(insert_query, values)
            added_count += 1
            print(f"Added rule: {rule['name']}")
        
        conn.commit()
        print(f"Successfully added {added_count} new rules to database")
        
        cur.close()
        conn.close()
        
        return added_count > 0
        
    except Exception as e:
        print(f"Error adding rules to database: {e}")
        return False

def auto_learn_from_manual_corrections(manual_corrections):
    """
    Automatically learn rules from manual corrections made in Google Sheets
    Includes conflict detection and rule updating for better accuracy
    """
    if not manual_corrections:
        return
    
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Get existing rules for conflict detection
        rules_data = _load_rules_from_database()
        existing_keywords = set()
        if rules_data:
            for rule in rules_data["rules"] + rules_data["salary_rules"]:
                existing_keywords.update(rule.get("keywords", []))
        
        new_rules = []
        updated_rules = []
        
        for correction in manual_corrections:
            description = correction["description"].upper()
            vendor = correction["vendor"]
            main_category = correction["main_category"]
            sub_category = correction["sub_category"]
            
            # Extract keywords from description
            words = description.split()
            keywords = []
            
            for word in words:
                # Filter out common words and short words
                if (len(word) >= 3 and 
                    word not in ["THE", "AND", "FOR", "WITH", "FROM", "TO", "OF", "IN", "ON", "AT", "BY", "PAYMENT", "TRANSFER", "NEFT", "IMPS", "UPI"] and
                    word.isalnum() and
                    not word.isdigit()):
                    keywords.append(word)
            
            # Also check vendor text
            if vendor and len(vendor) >= 3:
                vendor_clean = vendor.upper().strip()
                if vendor_clean not in ["THE", "AND", "FOR", "WITH", "FROM", "TO", "OF", "IN", "ON", "AT", "BY", "PAYMENT", "TRANSFER", "NEFT", "IMPS", "UPI"]:
                    keywords.append(vendor_clean)
            
            if keywords:
                # Check for conflicting rules with same keywords but different categories
                conflicting_rules = []
                for keyword in keywords[:3]:  # Check top 3 keywords
                    cur.execute("""
                        SELECT id, name, main_category, sub_category, keywords 
                        FROM rules 
                        WHERE JSON_CONTAINS(keywords, %s) 
                        AND (main_category != %s OR sub_category != %s)
                        AND is_active = 1
                    """, (json.dumps(keyword), main_category, sub_category))
                    
                    conflicts = cur.fetchall()
                    conflicting_rules.extend(conflicts)
                
                if conflicting_rules:
                    # Update conflicting rules to match the manual correction
                    for conflict in conflicting_rules:
                        rule_id, old_name, old_main, old_sub, old_keywords = conflict
                        
                        # Update the conflicting rule
                        cur.execute("""
                            UPDATE rules 
                            SET main_category = %s, sub_category = %s, 
                                updated_at = NOW(), created_by = 'manual-updated'
                            WHERE id = %s
                        """, (main_category, sub_category, rule_id))
                        
                        updated_rules.append({
                            "id": rule_id,
                            "old_name": old_name,
                            "old_category": f"{old_main} → {old_sub}",
                            "new_category": f"{main_category} → {sub_category}"
                        })
                        
                        print(f"Updated conflicting rule: {old_name} ({old_main} → {old_sub}) → ({main_category} → {sub_category})")
                
                # Check if we need to create a new rule (no conflicts found)
                if not conflicting_rules:
                    # Check if exact rule already exists
                    cur.execute("""
                        SELECT id FROM rules 
                        WHERE main_category = %s AND sub_category = %s 
                        AND JSON_CONTAINS(keywords, %s)
                        AND is_active = 1
                    """, (main_category, sub_category, json.dumps(keywords[0])))
                    
                    if not cur.fetchone():
                        # Create new rule
                        rule_name = f"Manual: {keywords[0]}"
                        if len(keywords) > 1:
                            rule_name += f" +{len(keywords)-1}"
                        
                        new_rule = {
                            "name": rule_name,
                            "priority": 25,  # Medium-high priority for manual rules
                            "keywords": keywords[:3],  # Limit to top 3 keywords
                            "main_category": main_category,
                            "sub_category": sub_category,
                            "frequency": 1,
                            "confidence": 0.95
                        }
                        new_rules.append(new_rule)
        
        # Add new rules to database
        if new_rules:
            add_rules_to_database(new_rules)
            print(f"Auto-learned {len(new_rules)} new rules from manual corrections")
        
        if updated_rules:
            conn.commit()
            print(f"Updated {len(updated_rules)} conflicting rules based on manual corrections")
        
        # Clear cache to force reload
        global _db_rules_cache, _db_rules_timestamp
        _db_rules_cache = None
        _db_rules_timestamp = None
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error auto-learning from manual corrections: {e}")

# ---------- Endpoints ----------
@app.post("/classify", response_model=List[PredOut], dependencies=[Depends(require_key)])
def classify(rows: Rows):
    out: List[PredOut] = []
    for r in rows.rows:
        nd = normalize_desc(r.description)
        vendor = (nd.split(' ')[0][:40] if nd else "")

        # External rules first
        main, sub, rule = apply_rules_wrapper(nd)
        conf = 0.95 if main else 0.0

        # ML fallback only if no rule matched
        if not main:
            pred, pconf = ml_main_category(nd)
            if pconf >= ML_THRESHOLD:
                main, conf = pred, pconf
            else:
                main, conf = "Uncategorized", pconf

        # Subcategory: use rule sub if provided, else LLM fallback
        sub_final = sub if sub else llm_subcategory(nd, r.amount, main)

        out.append(PredOut(
            row_index=r.row_index, date=r.date, description=r.description, amount=r.amount,
            balance=r.balance, account=r.account, currency=r.currency,
            vendor=vendor, rule_hit=rule or "",
            main_category_suggested=main, sub_category_suggested=sub_final, confidence=conf
        ))
    return out

@app.post("/sync", dependencies=[Depends(require_key)])
def sync(rows: SyncRows):
    conn = get_conn(); cur = conn.cursor()

    ins_raw = """
    INSERT IGNORE INTO transactions_raw
    (hash, posted_at, description_raw, amount, balance_after, account, currency, created_at)
    VALUES (%s,%s,%s,%s,%s,%s,%s,NOW())
    """

    ins_can = """
    INSERT IGNORE INTO transactions_canonical
    (raw_hash, posted_at, normalized_desc, amount, debit_credit, vendor_text, main_category_id,
     sub_category_text, confidence, source, reviewed_at)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'sheet',NOW())
    """

    # Track manual corrections for rule learning
    manual_corrections = []
    
    for r in rows.rows:
        nd = normalize_desc(r.description)
        h = tx_hash(r.account or "", r.date, r.amount, nd)

        cur.execute(ins_raw, (h, r.date, r.description, r.amount, r.balance, r.account, r.currency))

        main_id = None
        if r.main_category:
            cur.execute("SELECT id FROM categories_main WHERE name=%s", (r.main_category,))
            row = cur.fetchone()
            if row:
                main_id = row[0]

        debit_credit = 'debit' if r.amount < 0 else 'credit'
        cur.execute(ins_can, (
            h, r.date, nd, r.amount, debit_credit,
            r.vendor, main_id, r.sub_category, r.confidence if r.confidence is not None else 0.0
        ))
        
        # Track manual corrections for potential rule learning
        if r.main_category and r.sub_category:
            manual_corrections.append({
                "description": nd,
                "vendor": r.vendor,
                "main_category": r.main_category,
                "sub_category": r.sub_category
            })

    conn.commit()
    
    # Auto-learn rules from manual corrections
    if manual_corrections:
        try:
            auto_learn_from_manual_corrections(manual_corrections)
        except Exception as e:
            print(f"Error auto-learning from manual corrections: {e}")
    
    cur.close(); conn.close()
    return {"ok": True, "inserted": len(rows.rows)}

@app.post("/learn-rules", dependencies=[Depends(require_key)])
def learn_rules():
    """
    Manually trigger rule learning from verified database transactions
    """
    try:
        print("Starting rule learning process...")
        
        # Learn new rules from database
        new_rules = learn_rules_from_database()
        
        if not new_rules:
            return {
                "ok": True, 
                "message": "No new rules found to learn",
                "rules_learned": 0
            }
        
        # Add new rules to database
        success = add_rules_to_database(new_rules)
        
        if success:
            return {
                "ok": True,
                "message": f"Successfully learned {len(new_rules)} new rules",
                "rules_learned": len(new_rules),
                "new_rules": [
                    {
                        "name": rule["name"],
                        "keywords": rule["keywords"],
                        "main_category": rule["main_category"],
                        "sub_category": rule["sub_category"],
                        "frequency": rule["frequency"],
                        "confidence": rule["confidence"]
                    } for rule in new_rules
                ]
            }
        else:
            return {
                "ok": False,
                "message": "Failed to add new rules to database",
                "rules_learned": 0
            }
            
    except Exception as e:
        print(f"Error in learn_rules endpoint: {e}")
        return {
            "ok": False,
            "message": f"Error learning rules: {str(e)}",
            "rules_learned": 0
        }

@app.get("/rule-stats", dependencies=[Depends(require_key)])
def get_rule_stats():
    """
    Get statistics about current rules and database transactions
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Get total rules count from database
        cur.execute("SELECT COUNT(*) FROM rules WHERE is_active = 1")
        total_rules = cur.fetchone()[0]
        
        # Get database stats
        cur.execute("""
            SELECT 
                COUNT(*) as total_transactions,
                COUNT(CASE WHEN reviewed_at IS NOT NULL THEN 1 END) as verified_transactions,
                COUNT(CASE WHEN confidence > 0.8 THEN 1 END) as high_confidence_transactions
            FROM transactions_canonical
        """)
        db_stats = cur.fetchone()
        
        # Get category distribution
        cur.execute("""
            SELECT 
                cm.name as main_category,
                COUNT(*) as transaction_count
            FROM transactions_canonical tc
            LEFT JOIN categories_main cm ON tc.main_category_id = cm.id
            WHERE tc.reviewed_at IS NOT NULL
            GROUP BY cm.name
            ORDER BY transaction_count DESC
            LIMIT 10
        """)
        category_stats = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {
            "ok": True,
            "total_rules": total_rules,
            "database_stats": {
                "total_transactions": db_stats[0],
                "verified_transactions": db_stats[1],
                "high_confidence_transactions": db_stats[2]
            },
            "top_categories": [
                {"category": row[0], "count": row[1]} 
                for row in category_stats
            ]
        }
        
    except Exception as e:
        print(f"Error getting rule stats: {e}")
        return {
            "ok": False,
            "message": f"Error getting statistics: {str(e)}"
        }
