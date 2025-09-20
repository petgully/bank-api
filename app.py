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

# ---------- Rules module (external) with safe hot-reload ----------
# We reload rules.py automatically if its mtime changes.
from pathlib import Path

RULES_PATH = Path(__file__).with_name("rules.py")
_RULES_MTIME = None
_rules_mod = None

def _load_rules_module():
    global _RULES_MTIME, _rules_mod
    try:
        mtime = RULES_PATH.stat().st_mtime
    except FileNotFoundError:
        print("rules.py not found")
        return None

    if _rules_mod is None or _RULES_MTIME != mtime:
        importlib.invalidate_caches()
        if "rules" in sys.modules:
            _rules_mod = importlib.reload(sys.modules["rules"])
        else:
            _rules_mod = importlib.import_module("rules")
        _RULES_MTIME = mtime
        print("rules.py loaded/reloaded.")
    return _rules_mod

def apply_rules_wrapper(narration: Optional[str]):
    mod = _load_rules_module()
    if not mod or not hasattr(mod, "apply_rules"):
        return (None, None, None)
    try:
        return mod.apply_rules(narration)
    except Exception as e:
        print(f"apply_rules error: {e}")
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

    conn.commit()
    cur.close(); conn.close()
    return {"ok": True, "inserted": len(rows.rows)}
