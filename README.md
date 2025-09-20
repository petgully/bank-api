# Bank Transaction Categorization System

## Overview
This is an automated bank transaction categorization system that processes bank statements from Google Sheets, applies rule-based and ML-based categorization, and stores the results in a MySQL database. The system is designed to run on AWS Lightsail and integrates with Google Sheets for data input and verification.

## System Architecture

### Components
1. **FastAPI Application** (`app.py`) - Main API server
2. **Rules Engine** (`rules.py`) - Rule-based categorization logic
3. **Google Sheets Integration** - Data input and verification interface
4. **MySQL Database** - Final data storage
5. **ML Model** (optional) - Machine learning fallback for categorization

## Workflow

### 1. Data Input Phase
- Bank statements are uploaded to Google Sheets in a standardized format
- Google Apps Script triggers the categorization process
- Data is sent to the FastAPI application running on AWS Lightsail

### 2. Categorization Phase
The system applies a multi-layered categorization approach:

#### Rule-Based Categorization (Primary)
- **Salary Detection**: Identifies employee salary payments by name matching
- **Keyword Rules**: 187+ predefined rules covering various expense categories:
  - Grooming Inventory (Vet India Pharma, Amazon, etc.)
  - Vehicle Subscription (Imobility)
  - Fuel expenses
  - Office Overhead (Swiggy, Water Tanker, etc.)
  - Electricity bills
  - Telecom/Internet (Airtel)
  - Bank charges
  - Loan EMI payments
  - Admin expenses
  - Employee welfare
  - Customer refunds
  - Repair & maintenance
  - Tax & duties

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
- Manual verification and correction of categories
- New categories are added to the rules system

### 5. Database Storage
- Verified data is synced to MySQL database
- Two main tables:
  - `transactions_raw`: Original transaction data
  - `transactions_canonical`: Processed and categorized data

## API Endpoints

### POST `/classify`
- **Purpose**: Categorize bank transactions
- **Input**: List of transaction rows
- **Output**: Categorized transactions with suggested categories and confidence scores
- **Authentication**: API key required

### POST `/sync`
- **Purpose**: Store verified transactions in database
- **Input**: Verified transaction data
- **Output**: Confirmation of database insertion
- **Authentication**: API key required

## Configuration

### Environment Variables
- `API_KEY`: Authentication key for API access
- `OPENAI_API_KEY`: OpenAI API key for LLM subcategory generation
- `DB_HOST`, `DB_USER`, `DB_PASS`, `DB_NAME`: MySQL database credentials
- `ML_THRESHOLD`: Confidence threshold for ML categorization (default: 0.75)

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

### Hot-Reload Rules
- Rules can be updated without restarting the application
- Automatic detection of `rules.py` file changes
- Dynamic module reloading

### Error Handling
- Graceful fallbacks for ML model failures
- OpenAI API error handling
- Database connection error management

### Security
- API key authentication
- Input validation using Pydantic models
- SQL injection prevention with parameterized queries

## Deployment
- Designed for AWS Lightsail deployment
- Docker containerization support
- Environment-based configuration

## Maintenance
- Rules can be updated by modifying `rules.py`
- ML models can be retrained and replaced
- Database schema supports category management
- Comprehensive logging for debugging

## Business Logic
The system is specifically designed for a pet grooming business with categories covering:
- Employee salary management
- Inventory procurement
- Vehicle and fuel expenses
- Office operations
- Customer service
- Financial obligations (loans, taxes)
- Maintenance and repairs
