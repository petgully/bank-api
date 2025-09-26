# -*- coding: utf-8 -*-

"""
Rule-based categorization (first-pass) for bank transaction narration text.

Returns: (main_category, sub_category, rule_hit_name) or (None, None, None)
"""

from typing import Tuple, Optional, Dict, List

# --- First-pass rules based only on Narration text ---

SALARY_NAME_MAP: Dict[str, List[str]] = {
    "Back Office": [
        "DASARI VAMSHI", "DUSARI NARESH", "KARAN SINGH", "KOKI SRIHARI REDDY"
    ],
    "Operations Team": [
        "ARJUN DR EMP", "BALAJI GR", "GARIKAPATI PRADEEP", "KARTHIK DR",
        "KOLIPAKA BALAKRISHNA", "MALLESHWARI", "NANDI GAMA SHIVA KUMAR",
        "NELOJEE SAI KUMAR", "P SHIVA KUMAR", "PALTYA RAMESH", "PINAPOTHU RAMU",
        "PRASAD DR", "RAJESH DR", "SABAVATH SHIVA", "SACHIN GAUR",
        "SALAVATH SRINU", "THAMMICHETTY KOTESH", "NABADWIP DEBBARMA"
    ],
    "Customer Care": [
        "BOBBILI ARCHANA", "KASIMALLA VAMSHI VARDHAN", "SHAHEEDA", "YELIMALA PRAVEEN"
    ],
}

RULES: List[dict] = [
    # Grooming Inventory
    {"name":"Vet India Pharma", "priority":10, "any":["VET INDIA","PHARMACEUTICALS"], "main":"Grooming Inventory","sub":"Vet India Pharma (VIP)"},
    {"name":"Nutan Medical",   "priority":10, "any":["NUTAN MEDICAL"],              "main":"Grooming Inventory","sub":"Nutan Medical"},
    {"name":"ABK Imports",     "priority":10, "any":["ABK IMPORTS"],                "main":"Grooming Inventory","sub":"ABK Imports"},
    {"name":"Amazon",          "priority":20, "any":["AMAZON"],                     "main":"Grooming Inventory","sub":"Amazon"},
    {"name":"Pubscribe",       "priority":15, "any":["PUBSCRIBE"],                  "main":"Grooming Inventory","sub":"Pubscribe Enterprises"},
    {"name":"Anasuya",         "priority":15, "any":["ANASUYA"],                    "main":"Grooming Inventory","sub":"Anasuya Food Tech"},

    # Vehicle Subscription
    {"name":"Imobility",       "priority":10, "any":["IMOBILITI","IMOBILITY"],      "main":"Vehicle Subscription","sub":"Imobility Subscription"},

    # Fuel
    {"name":"Fuel Pump",       "priority":15, "any":["DEEPAKDIRECTORICICI"],        "main":"Fuel","sub":"Fuel - Diesel & Petrol"},
    {"name":"Fuel Generic",    "priority":30, "any":["PETROL","DIESEL","BPCL","UFILL","BP PETROL"], "main":"Fuel","sub":"Fuel - Diesel & Petrol"},

    # Office Overhead
    {"name":"Swiggy",          "priority":10, "any":["SWIGGY","INSTAMART"],         "main":"Office Overhead","sub":"Swiggy"},
    {"name":"Water Tanker",    "priority":30, "any":["TANKER","WATER TANKER","KRUPAKAR"], "main":"Office Overhead","sub":"Water Tanker"},
    {"name":"Milk",            "priority":30, "any":["MILK"],                       "main":"Office Overhead","sub":"Milk"},
    {"name":"Garbage",         "priority":30, "any":["GARBAGE"],                    "main":"Office Overhead","sub":"Garbage"},
    {"name":"Electrician",     "priority":30, "any":["ELECTRICIAN","ELECTRICAL"],   "main":"Office Overhead","sub":"Electrician"},
    {"name":"Water Bill",      "priority":40, "any":["BILLDKHYDERABADMETRO","HYDERABAD METRO"], "main":"Office Overhead","sub":"Water Bill"},

    # Electricity
    {"name":"Electricity Bill","priority":20, "any":["SOUTHERNPOWERDISTRIB"],       "main":"Electricity maintance & Bill","sub":"Electricity Bill"},

    # Telco/Internet
    {"name":"Airtel",          "priority":10, "any":["AIRTEL","AIRTELIN","WWW AIRTEL IN"], "main":"Telephone & Internet","sub":"Airtel Mobile and Internet"},

    # Bank Charges
    {"name":"IMPS P2P Fee",    "priority":20, "any":["IMPS P2P","MIR"],             "main":"Bank Charges","sub":"Processing Fee"},
    {"name":"ATM/Withdr TDS",  "priority":20, "any":["TDS CASH WITHDRAWAL"],        "main":"Bank Charges","sub":"Processing Fee"},

    # Petty Cash
    {"name":"Petty Cash HIMA", "priority":20, "any":["HIMADIRECTOR"],               "main":"Petty Cash","sub":"Petty Cash (Mobile Grooming)"},

    # Loan EMI Payments
    {"name":"Bajaj Finance",   "priority":10, "any":["BAJAJ FINANCE"],              "main":"Loan EMI Payments","sub":"Bajaj Finance"},
    {"name":"Godrej Finance",  "priority":10, "any":["GODREJFINANCE"],              "main":"Loan EMI Payments","sub":"Godrej Finance"},
    {"name":"UGRO Capital",    "priority":10, "any":["UGRO CAPITAL"],               "main":"Loan EMI Payments","sub":"UGRO CAPITAL"},
    {"name":"India Infoline",  "priority":10, "any":["INFOLINE"],                   "main":"Loan EMI Payments","sub":"India Infoline Finance"},
    {"name":"Unity Small",     "priority":10, "any":["UNITY SMALL","UNITYSMALL"],   "main":"Loan EMI Payments","sub":"Unity Small Finance"},
    {"name":"Shriram",         "priority":10, "any":["SHRIRAM"],                    "main":"Loan EMI Payments","sub":"Shriram Finance"},
    {"name":"HDFC EMI (CHQ)",  "priority":40, "any":["EMI "," CHQ S"],              "main":"Loan EMI Payments","sub":"HDFC Loan EMI"},
    {"name":"HandLoan Rao",    "priority":10, "any":["VENKATESWARA RAO"],           "main":"Loan EMI Payments","sub":"Venkateswara Rao HandLoan"},
    {"name":"HandLoan Sanjay", "priority":10, "any":["SANJAY PAN"],                 "main":"Loan EMI Payments","sub":"Sanjay Pan HandLoan"},

    # Admin Expenses
    {"name":"Slot Books",      "priority":25, "any":["SLOT","BOOKS"],               "main":"Admin Expenses","sub":"Slot Books"},
    {"name":"Vet Doctor",      "priority":30, "any":["DRKARTHEEK","VET","DOCTOR","KARTHEEK"], "main":"Admin Expenses","sub":"Veterinary Doctor Charges"},

    # Employee Welfare
    {"name":"Hostel Fee",      "priority":15, "any":["HOSTEL","SRIPAL REDDY"],      "main":"Employee Welfare","sub":"Hostel Fee for Employees"},

    # Customer Refund
    {"name":"Customer Refund", "priority":25, "any":["REFUND","CUSTOMER","SLOT"],   "main":"Customer Refund","sub":"Customer Refund of Slots"},

    # Repair & Maintenance
    {"name":"Generator Oil",   "priority":25, "any":["GENERATOR OIL"],              "main":"Repari & Maintenance","sub":"Generator Oil"},
    {"name":"Plumbing",        "priority":15, "any":["PLUMBING","MANOJ MALIK"],     "main":"Repari & Maintenance","sub":"Plumbing Maintenance"},
    {"name":"Water Wash",      "priority":25, "any":["WATER WASH"],                 "main":"Repari & Maintenance","sub":"Water Wash"},

    # Tax & Duties
    {"name":"TDS Payment",     "priority":25, "any":["CBDT"],                       "main":"Tax & Duties","sub":"TDS Payment"},
    {"name":"GST Payment",     "priority":25, "any":["GST"],                        "main":"Tax & Duties","sub":"GST Payment"},
    {"name":"EPFO",            "priority":15, "any":["PSIVR"],                      "main":"Tax & Duties","sub":"EPFO"},
]

def apply_rules(narration: Optional[str]):
    """
    Return (main_category, sub_category, rule_name) or (None, None, None)
    """
    if narration is None:
        return (None, None, None)

    text = str(narration).upper()

    # 1) Name-based salary rules first (highest precedence)
    for sub, names in SALARY_NAME_MAP.items():
        for nm in names:
            if nm in text and any(k in text for k in ("SALARY","EXPENSES","NEFT DR","IMPS","TPT")):
                return ("Salaries & Wages", sub, f"Salary name: {nm}")

    # 2) Keyword rules (by priority)
    for r in sorted(RULES, key=lambda x: x.get("priority", 100)):
        if any(tok in text for tok in r["any"]) and not any(tok in text for tok in r.get("not", [])):
            return (r["main"], r["sub"], r["name"])

    # 3) No rule
    return (None, None, None)
