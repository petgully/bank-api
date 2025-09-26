# Enhanced Rule Learning Guide

This guide explains how to use the enhanced rule learning script to automatically generate new categorization rules from your verified database transactions.

## Overview

The `enhanced_learn_rules.py` script analyzes verified transactions from your database and generates new rules to add to `rules.py`. It uses the `v_transactions_with_category` view for better data access and more accurate rule generation.

## Features

- **Smart Pattern Recognition**: Groups similar transactions and extracts meaningful keywords
- **Duplicate Prevention**: Avoids creating rules with keywords that already exist
- **Priority Assignment**: Automatically assigns rule priorities based on frequency and confidence
- **Safe Updates**: Validates syntax before updating `rules.py`
- **Detailed Reporting**: Shows comprehensive summaries of new rules
- **Dry Run Mode**: Preview rules before applying them

## Usage

### Basic Usage

```bash
# Learn rules from reviewed transactions only (recommended)
python enhanced_learn_rules.py

# Preview rules without updating rules.py
python enhanced_learn_rules.py --dry-run

# Include unreviewed transactions (use with caution)
python enhanced_learn_rules.py --include-unreviewed
```

### Advanced Options

```bash
# Customize learning parameters
python enhanced_learn_rules.py \
    --min-frequency 3 \
    --min-confidence 0.85 \
    --max-rules 30 \
    --dry-run

# Learn from all transactions (including unreviewed)
python enhanced_learn_rules.py \
    --include-unreviewed \
    --min-frequency 2 \
    --min-confidence 0.7
```

### Parameters

- `--dry-run`: Show what rules would be learned without updating `rules.py`
- `--min-frequency N`: Minimum number of transactions for a pattern to be considered (default: 2)
- `--min-confidence X`: Minimum confidence score for a pattern (default: 0.8)
- `--include-unreviewed`: Include unreviewed transactions in learning (default: only reviewed)
- `--max-rules N`: Maximum number of rules to generate (default: 50)

## How It Works

### 1. Data Analysis
- Queries the `v_transactions_with_category` view
- Filters transactions by confidence and review status
- Groups similar transactions by patterns

### 2. Pattern Recognition
- Extracts keywords from transaction descriptions
- Uses vendor text as primary pattern identifier
- Filters out generic transaction types (ACH, NEFT, etc.)

### 3. Rule Generation
- Creates rules for patterns with sufficient frequency
- Assigns priorities based on frequency and confidence
- Avoids duplicate keywords from existing rules

### 4. Safe Updates
- Validates syntax before updating `rules.py`
- Backs up original content if validation fails
- Provides detailed success/failure reporting

## Rule Priority System

Rules are assigned priorities based on their frequency and confidence:

- **Priority 10**: High frequency (10+ transactions) + High confidence (0.9+)
- **Priority 20**: Medium-high frequency (5+ transactions) + High confidence (0.8+)
- **Priority 30**: Medium frequency (3+ transactions) + Medium confidence (0.7+)
- **Priority 50**: Low frequency/confidence (default for auto-learned rules)

## Example Output

```
🚀 Starting enhanced rule learning process...
Parameters: min_frequency=2, min_confidence=0.8, use_reviewed_only=True, max_rules=50
Found 1250 transactions to analyze...

================================================================================
RULE LEARNING SUMMARY - 15 NEW RULES FOUND
================================================================================

📁 Office Overhead (5 rules)
------------------------------------------------------------

1. Auto-learned: SWIGGYINSTAMART +2
   Keywords: SWIGGYINSTAMART, SWIGGY, INSTAMART
   Sub-category: Swiggy
   Frequency: 8 transactions
   Confidence: 0.95
   Priority: 20
   Sample: UPI-SWIGGYINSTAMART-SWIGGYIN | UPI-SWIGGYINSTAMART-SWIGGYIN...

2. Auto-learned: WATER TANKER
   Keywords: WATER, TANKER, KRUPAKAR
   Sub-category: Water Tanker
   Frequency: 5 transactions
   Confidence: 0.88
   Priority: 30
   Sample: WATER TANKER KRUPAKAR | WATER TANKER KRUPAKAR...

📁 Loan EMI Payments (4 rules)
------------------------------------------------------------

3. Auto-learned: BAJAJ FINANCE
   Keywords: BAJAJ, FINANCE, LTD
   Sub-category: Bajaj Finance
   Frequency: 12 transactions
   Confidence: 0.92
   Priority: 10
   Sample: ACH D-BAJAJ FINANCE LTD-P400PH | ACH D-BAJAJ FINANCE LTD-P400PH...

🤔 Do you want to add these 15 rules to rules.py? (y/N): y

✅ Successfully learned 15 new rules!
🎉 Rules have been added to rules.py and will be active immediately.

📊 Summary:
   - Total new rules: 15
   - Office Overhead: 5 rules
   - Loan EMI Payments: 4 rules
   - Grooming Inventory: 3 rules
   - Fuel: 2 rules
   - Bank Charges: 1 rule
```

## Best Practices

### 1. Start with Dry Run
Always run with `--dry-run` first to preview the rules:

```bash
python enhanced_learn_rules.py --dry-run
```

### 2. Use Conservative Parameters
Start with default parameters and adjust based on results:

```bash
# Start conservative
python enhanced_learn_rules.py --min-frequency 3 --min-confidence 0.85

# If too few rules, lower thresholds
python enhanced_learn_rules.py --min-frequency 2 --min-confidence 0.8
```

### 3. Review Generated Rules
Check the sample descriptions to ensure rules make sense:

- Look for meaningful keywords
- Verify category assignments
- Check for false positives

### 4. Regular Learning
Run the script regularly as you add more verified transactions:

```bash
# Weekly rule learning
python enhanced_learn_rules.py --min-frequency 2 --min-confidence 0.8
```

### 5. Monitor Performance
After adding new rules, monitor how they perform:

- Check rule hit rates
- Verify categorization accuracy
- Remove or modify problematic rules

## Troubleshooting

### No Rules Found
If no rules are generated:

1. Check if you have enough verified transactions
2. Lower the `--min-frequency` parameter
3. Lower the `--min-confidence` parameter
4. Use `--include-unreviewed` (with caution)

### Too Many Rules
If too many rules are generated:

1. Increase the `--min-frequency` parameter
2. Increase the `--min-confidence` parameter
3. Lower the `--max-rules` parameter

### Syntax Errors
If `rules.py` update fails:

1. Check the error message for specific issues
2. The original file is automatically restored
3. Manually fix any syntax issues
4. Re-run the script

### Database Connection Issues
If database connection fails:

1. Check your environment variables
2. Verify database credentials
3. Ensure the database is accessible
4. Check if the view `v_transactions_with_category` exists

## Testing

Run the test script to verify everything works:

```bash
python test_enhanced_learn_rules.py
```

This will test:
- RuleLearner initialization
- Pattern key creation
- Keyword extraction
- Priority calculation
- Database connection
- Rule learning (dry run)

## Integration with Existing System

The enhanced rule learning script integrates seamlessly with your existing system:

1. **Uses existing database connection** from `app.py`
2. **Loads current rules** to avoid duplicates
3. **Updates `rules.py`** in the same format
4. **Hot-reloads** rules automatically in your FastAPI app

After running the script, new rules are immediately available for transaction categorization without restarting your application.