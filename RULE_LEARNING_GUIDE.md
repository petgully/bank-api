# Rule Learning System Guide

## Overview
The rule learning system automatically analyzes verified transactions from your database and generates new categorization rules. This helps improve the accuracy of transaction categorization over time.

## How It Works

### 1. Data Analysis
- Analyzes verified transactions from `transactions_canonical` table
- Looks for patterns in transaction descriptions and vendor names
- Only considers transactions with high confidence (>0.8) and multiple occurrences (≥2)

### 2. Rule Generation
- Extracts keywords from normalized transaction descriptions
- Filters out common words and existing rule keywords
- Creates rules with medium priority (50) for auto-learned patterns
- Generates both main category and subcategory mappings

### 3. Rule Integration
- Automatically updates `rules.py` file with new rules
- Rules are immediately active (hot-reload)
- Maintains existing rule structure and format

## Usage Methods

### Method 1: API Endpoint (Recommended)
```bash
# Learn new rules
curl -X POST "http://your-api-url/learn-rules" \
  -H "X-API-Key: your-api-key"

# Check rule statistics
curl -X GET "http://your-api-url/rule-stats" \
  -H "X-API-Key: your-api-key"
```

### Method 2: Standalone Script
```bash
# Dry run to see what rules would be learned
python learn_rules.py --dry-run

# Learn rules with custom parameters
python learn_rules.py --min-frequency 3 --min-confidence 0.85

# Learn rules with default parameters
python learn_rules.py
```

## Configuration Parameters

### Minimum Frequency
- **Default**: 2 transactions
- **Purpose**: Ensures pattern is not just a one-off occurrence
- **Recommendation**: Start with 2, increase to 3-5 as database grows

### Minimum Confidence
- **Default**: 0.8 (80%)
- **Purpose**: Only learns from high-confidence categorizations
- **Recommendation**: Keep at 0.8 for quality, lower to 0.7 for more rules

## Rule Learning Algorithm

### 1. Pattern Detection
```sql
SELECT 
    normalized_desc,
    vendor_text,
    sub_category_text,
    main_category,
    COUNT(*) as frequency,
    AVG(confidence) as avg_confidence
FROM transactions_canonical
WHERE reviewed_at IS NOT NULL 
AND confidence > 0.8
GROUP BY normalized_desc, vendor_text, sub_category_text, main_category
HAVING COUNT(*) >= 2
```

### 2. Keyword Extraction
- Splits transaction descriptions into words
- Filters out common words: "THE", "AND", "FOR", "WITH", "FROM", "TO", "OF", "IN", "ON", "AT", "BY", "PAYMENT", "TRANSFER", "NEFT", "IMPS"
- Removes words shorter than 3 characters
- Excludes keywords already in existing rules

### 3. Rule Creation
- Creates rules with format: `"Auto-learned: KEYWORD"`
- Assigns medium priority (50) to avoid conflicts with manual rules
- Limits to top 3 keywords per rule
- Maps to existing main and sub categories

## Example Output

### New Rule Example
```python
{
    "name": "Auto-learned: SWIGGY +2",
    "priority": 50,
    "any": ["SWIGGY", "INSTAMART", "FOOD"],
    "main": "Office Overhead",
    "sub": "Swiggy"
}
```

### API Response
```json
{
    "ok": true,
    "message": "Successfully learned 5 new rules",
    "rules_learned": 5,
    "new_rules": [
        {
            "name": "Auto-learned: SWIGGY +2",
            "keywords": ["SWIGGY", "INSTAMART", "FOOD"],
            "main_category": "Office Overhead",
            "sub_category": "Swiggy",
            "frequency": 15,
            "confidence": 0.92
        }
    ]
}
```

## Best Practices

### 1. Regular Learning
- Run rule learning weekly or monthly
- Monitor new rules before they become too numerous
- Review and clean up rules periodically

### 2. Quality Control
- Use higher minimum frequency (3-5) for production
- Review learned rules before applying
- Remove or modify rules that cause conflicts

### 3. Database Maintenance
- Ensure `reviewed_at` field is properly set for verified transactions
- Maintain high confidence scores for manual categorizations
- Regular cleanup of old, unused rules

## Monitoring and Statistics

### Rule Statistics Endpoint
```bash
curl -X GET "http://your-api-url/rule-stats" \
  -H "X-API-Key: your-api-key"
```

### Response Example
```json
{
    "ok": true,
    "total_rules": 192,
    "database_stats": {
        "total_transactions": 1250,
        "verified_transactions": 1100,
        "high_confidence_transactions": 950
    },
    "top_categories": [
        {"category": "Office Overhead", "count": 150},
        {"category": "Grooming Inventory", "count": 120}
    ]
}
```

## Troubleshooting

### Common Issues

1. **No rules learned**
   - Check if transactions have `reviewed_at` set
   - Verify confidence scores are above threshold
   - Ensure minimum frequency is not too high

2. **Too many rules learned**
   - Increase minimum frequency parameter
   - Increase minimum confidence threshold
   - Review and clean existing rules

3. **Rule conflicts**
   - Auto-learned rules have priority 50 (medium)
   - Manual rules typically have priority 10-40 (higher)
   - Lower priority rules are checked first

### Debug Mode
```bash
# Run with verbose output
python learn_rules.py --dry-run --min-frequency 1 --min-confidence 0.7
```

## Future Enhancements

1. **Automated Scheduling**: Cron job or scheduled task
2. **Rule Quality Scoring**: ML-based rule quality assessment
3. **Conflict Detection**: Automatic detection of rule conflicts
4. **Rule Performance Tracking**: Monitor rule effectiveness over time
5. **Category Suggestions**: Suggest new categories based on patterns
