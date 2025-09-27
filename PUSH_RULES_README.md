# Push Rules to Database

This script pushes all rules from `rules.py` to the MySQL database table `petgully_db.rules`.

## Files Created

- `push_rules_to_db.py` - Main script to push rules to database
- `requirements_db.txt` - Python dependencies for database connection
- `db_config.env` - Database configuration template
- `push_rules.bat` - Windows batch file to run the script
- `PUSH_RULES_README.md` - This documentation

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements_db.txt
```

### 2. Configure Database Connection

Copy `db_config.env` to `.env` and update with your database credentials:

```bash
cp db_config.env .env
```

Edit `.env` file:
```
DB_HOST=your_database_host
DB_USER=your_username
DB_PASSWORD=your_password
DB_NAME=petgully_db
DB_PORT=3306
```

### 3. Run the Script

**Option A: Using the batch file (Windows)**
```bash
push_rules.bat
```

**Option B: Direct Python execution**
```bash
python push_rules_to_db.py
```

## What the Script Does

1. **Connects to MySQL database** using the configuration in `.env`
2. **Clears existing script-created rules** (rules with `created_by = 'script'`)
3. **Processes regular rules** from the `RULES` list in `rules.py`
4. **Processes salary rules** from the `SALARY_NAME_MAP` in `rules.py`
5. **Inserts all rules** into the `petgully_db.rules` table
6. **Provides detailed logging** of the insertion process

## Database Table Structure

The script expects a table with these columns:
- `id` (auto-increment primary key)
- `name` (rule name)
- `priority` (rule priority)
- `keywords` (JSON array of keywords)
- `main_category` (main category)
- `sub_category` (sub category)
- `is_active` (1 for active)
- `frequency` (0 by default)
- `confidence` (0.95 by default)
- `created_at` (timestamp)
- `updated_at` (timestamp)
- `created_by` ('script' for script-created rules)

## Rule Processing

### Regular Rules
- Extracts `name`, `priority`, `any` (keywords), `main`, `sub` from each rule
- Converts keywords array to JSON format
- Sets default values for `is_active=1`, `frequency=0`, `confidence=0.95`

### Salary Rules
- Creates individual rules for each employee name
- Combines employee name with salary keywords: `["SALARY", "EXPENSES", "NEFT DR", "IMPS", "TPT"]`
- Sets high priority (5) for salary rules
- Uses "Salaries & Wages" as main category

## Output

The script provides detailed console output:
- ✅ Successfully inserted rules
- ❌ Failed insertions with error details
- 📊 Summary statistics
- 🔌 Connection status

## Error Handling

- Database connection errors
- Individual rule insertion failures
- Missing environment variables
- Invalid JSON conversion

## Next Steps

After running this script successfully, all rules from `rules.py` will be available in the database table and can be used by your bank transaction categorization system.
