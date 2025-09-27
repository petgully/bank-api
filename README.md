# Bank Transaction Categorization System

## Overview
This is an automated bank transaction categorization system that processes bank statements from Google Sheets, applies database-driven rule-based and ML-based categorization, and stores the results in a MySQL database. The system features automatic rule learning from manual corrections and is designed to run on AWS Lightsail with Google Sheets integration.

## System Architecture

### Components
1. **FastAPI Application** (`app.py`) - Main API server with database-driven rules
2. **Database Rules System** - Rules stored in MySQL database (petgully_db.rules)
3. **Google Sheets Integration** - Data input and verification interface
4. **MySQL Database** - Rules storage and final data storage
5. **ML Model** (optional) - Machine learning fallback for categorization
6. **Automatic Rule Learning** - Self-improving system from manual corrections

## Workflow

### 1. Data Input Phase
- Bank statements are uploaded to Google Sheets in a standardized format
- Google Apps Script triggers the categorization process
- Data is sent to the FastAPI application running on AWS Lightsail

### 2. Categorization Phase
The system applies a multi-layered categorization approach:

#### Database-Driven Rule Categorization (Primary)
- **Rules Storage**: All rules stored in MySQL database (petgully_db.rules table)
- **73+ Active Rules** covering various expense categories:
  - Grooming Inventory (Vet India Pharma, Amazon, Nutan Medical, etc.)
  - Vehicle Subscription (Imobility)
  - Fuel expenses (Petrol, Diesel, BPCL, etc.)
  - Office Overhead (Swiggy, Water Tanker, Milk, Garbage, etc.)
  - Electricity bills
  - Telecom/Internet (Airtel)
  - Bank charges (IMPS, TDS)
  - Loan EMI payments (Bajaj, Godrej, HDFC, etc.)
  - Admin expenses (Slot Books, Vet Doctor)
  - Employee welfare (Hostel fees)
  - Customer refunds
  - Repair & maintenance (Generator, Plumbing, Water Wash)
  - Tax & duties (TDS, GST, EPFO)
  - Salary rules (26 employee names with salary keywords)
- **Rule Types**: Script rules, Auto-learned rules, Manual rules
- **Performance**: Rules cached for 5 minutes for optimal performance

#### Machine Learning Fallback (Secondary)
- Uses TF-IDF vectorization and Logistic Regression
- Activated when no rule matches
- Confidence threshold: 0.75 (configurable)

#### LLM Subcategory Generation (Tertiary)
- Uses OpenAI GPT-4o-mini for subcategory generation
- Only when no rule-based subcategory is available

### 3. Data Processing
- **Transaction Normalization**: Cleans and standardizes transaction descriptions
- **Vendor Extraction**: Extracts vendor names from descriptions
- **Hash Generation**: Creates unique transaction identifiers
- **Confidence Scoring**: Assigns confidence levels to categorizations

### 4. Verification Phase
- Categorized data is sent back to Google Sheets
- Manual verification and correction in `FinalMainCategory` field
- **Automatic Rule Learning**: Manual corrections automatically create new database rules

### 5. Automatic Rule Learning
- **Manual Corrections**: When you correct "Uncategorized" → specific category, system automatically:
  - Extracts keywords from transaction description
  - Creates new rule with priority 25 (medium-high)
  - Stores rule in database with `created_by = "manual"`
  - Makes rule immediately available for future transactions
- **Pattern Learning**: System learns from verified transactions and patterns
- **Duplicate Prevention**: Checks existing keywords to avoid duplicate rules

### 6. Database Storage
- Verified data is synced to MySQL database
- Three main tables:
  - `transactions_raw`: Original transaction data
  - `transactions_canonical`: Processed and categorized data
  - `rules`: Database-driven rules with JSON keywords, priorities, categories

## API Endpoints

### POST `/classify`
- **Purpose**: Categorize bank transactions using database rules
- **Input**: List of transaction rows
- **Output**: Categorized transactions with suggested categories and confidence scores
- **Authentication**: API key required

### POST `/sync`
- **Purpose**: Store verified transactions in database + auto-learn rules from corrections
- **Input**: Verified transaction data
- **Output**: Confirmation of database insertion
- **Authentication**: API key required
- **Auto-Learning**: Automatically creates new rules from manual corrections

### POST `/learn-rules`
- **Purpose**: Manually trigger rule learning from verified transactions
- **Input**: None (uses existing verified data)
- **Output**: Statistics about learned rules
- **Authentication**: API key required

### GET `/rule-stats`
- **Purpose**: Get statistics about current rules and database transactions
- **Input**: None
- **Output**: Rule counts, transaction statistics, category distribution
- **Authentication**: API key required

## Configuration

### Environment Variables
- `API_KEY`: Authentication key for API access
- `OPENAI_API_KEY`: OpenAI API key for LLM subcategory generation
- `DB_HOST`, `DB_USER`, `DB_PASS`, `DB_NAME`: MySQL database credentials
- `ML_THRESHOLD`: Confidence threshold for ML categorization (default: 0.75)

### Database Configuration
- **Rules Table**: `petgully_db.rules` with columns:
  - `id`, `name`, `priority`, `keywords` (JSON), `main_category`, `sub_category`
  - `is_active`, `frequency`, `confidence`, `created_at`, `updated_at`, `created_by`
- **Rule Types**: Script (priority 5-50), Manual (priority 25), Auto-learned (priority 50)

### Model Files
- `model/tfidf.joblib`: TF-IDF vectorizer
- `model/logreg.joblib`: Logistic regression model

## Data Models

### Input Schema (RowIn)
```python
{
    "row_index": int,
    "date": str,
    "description": str,
    "amount": float,
    "balance": float,
    "account": str,
    "currency": str
}
```

### Output Schema (PredOut)
```python
{
    "row_index": int,
    "date": str,
    "description": str,
    "amount": float,
    "balance": float,
    "account": str,
    "currency": str,
    "vendor": str,
    "rule_hit": str,
    "main_category_suggested": str,
    "sub_category_suggested": str,
    "confidence": float
}
```

## Key Features

### Database-Driven Rules System
- **No File Dependencies**: Rules stored in MySQL database
- **Hot-Reload Capability**: Rules update without application restart
- **Performance Optimization**: 5-minute rule caching
- **Flexible Management**: Add/edit/disable rules via SQL

### Automatic Rule Learning
- **Manual Corrections**: Auto-learn from user corrections in Google Sheets
- **Pattern Recognition**: Learn from verified transaction patterns
- **Duplicate Prevention**: Smart keyword checking to avoid duplicate rules
- **Immediate Availability**: New rules work instantly for future transactions

### Error Handling
- Graceful fallbacks for ML model failures
- OpenAI API error handling
- Database connection error management
- Rule loading error recovery

### Security
- API key authentication
- Input validation using Pydantic models
- SQL injection prevention with parameterized queries

## Deployment
- **AWS Lightsail**: Primary deployment platform
- **Docker Containerization**: Easy deployment and scaling
- **Environment-based Configuration**: Flexible setup
- **Database-driven Architecture**: No file dependencies

## Maintenance
- **Database Rules Management**: Add/edit/disable rules via SQL queries
- **Automatic Rule Learning**: Reduces manual maintenance workload
- **ML Model Updates**: Models can be retrained and replaced
- **Database Schema**: Supports category management and rule storage
- **Comprehensive Logging**: Detailed debugging and monitoring

## Business Logic
The system is specifically designed for a pet grooming business with categories covering:
- **Employee Salary Management**: 26 employee names with salary detection
- **Inventory Procurement**: Grooming supplies and medical equipment
- **Vehicle and Fuel Expenses**: Fleet management and fuel costs
- **Office Operations**: Overhead, utilities, and administrative costs
- **Customer Service**: Refunds and customer support
- **Financial Obligations**: Loan EMIs, taxes, and regulatory payments
- **Maintenance and Repairs**: Equipment and facility maintenance

## Rule Learning System
- **Three Learning Sources**:
  1. **Manual Corrections**: User corrections in Google Sheets → automatic rule creation
  2. **Verified Transactions**: Pattern analysis from reviewed transactions
  3. **Script Rules**: Initial rule set (73 rules) for business categories
- **Priority System**: Script (5-50), Manual (25), Auto-learned (50)
- **Smart Duplicate Prevention**: Checks existing keywords before creating new rules
- **Immediate Deployment**: New rules available instantly for future transactions
