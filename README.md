# Polymarket Mispricing Recurrence

A data science project that detects mispricing events in Polymarket binary prediction
markets and predicts whether a market will experience repeated mispricings.

A mispricing event was defined as the yes and no token of a market not summing up to 1.00.
We introduced a deviation threshold of 0.001, so mispriced events had to exceed it in order to be counted
so as to not falsely include markets that had rounding errors.

---

## Group Contributions

**Mathew Pham**
- Designed and implemented the full API collection pipeline (`api_calls.py`, `run_api_calls.py`)
- Rebuilt the mispricing detector with SQL-native logic to resolve an out-of-memory error
on the VM from loading 20M+ rows via pandas (`run_detector.py`)
- Wrote the category and negRisk backfill scripts (`category_backfill.py`, `neg_risk_backfill.py`)
- Developed the data export script (`export_csv.py`)
- Developed the test files (with AI assistance, see AI Usage below)

**Darren Hung**
- Contributed to original mispricing detection logic in Python, later updated to PSQL
- Performed all EDA, feature engineering, model training, and class imbalance handling (`eda_and_modeling.ipynb`)
- Produced visualizations for EDA and model interpretation in the modeling notebook

---

## AI Usage

We used Claude as an AI assistant throughout this project for debugging, design discussion, and documentation.

The following test files were produced with substantial AI assistance:
- `test_api_calls.py`
- `test_database_backend.py`
- `test_end_to_end.py`
- `requirements.txt`

`explore_api.py` and `explore_api.ipynb` were written independently as exploratory scripts.

For all other files, AI was used to help debug errors and discuss design tradeoffs.
Implementation decisions, data analysis, and results are our own.

---

## Repository Structure

```
polymarket_mispricing/
│
├── polymarket/                
│   ├── api_calls.py            # Gamma and CLOB API collection logic
│   ├── database_backend.py     # PostgreSQL connection and insert functions
│   ├── category_backfill.py    # One-time script to backfill market categories
│   ├── neg_risk_backfill.py    # One-time script to backfill negRisk
│   └── __init__.py
│
├── data/
│   ├── export.csv              # 328-row modeling dataset (one row per mispricing event)
│   ├── eda_and_modeling.ipynb  # EDA and classification pipeline
│   ├── export_csv.py           # Script to export mispricing events from DB to CSV
│   └── polymarket_db.sql       # PostgreSQL schema for polymarket_db
|
├── run_api_calls.py            # Runs collect() every 5 minutes
├── run_detector.py             # Runs SQL-native mispricing detection
│
├── test_api_calls.py           # Tests for api_calls.py (AI-assisted)
├── test_database_backend.py    # Tests for database_backend.py (AI-assisted)
├── test_end_to_end.py          # Integration tests (requires local PostgreSQL + internet, AI-assisted)
├── explore_api.py              # Exploratory API script
├── explore_api.ipynb           # Exploratory notebook; extension of explore_api.py
│
└── requirements.txt            # Python dependencies
```

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/mcpham100/polymarket_mispricing.git
cd polymarket_mispricing
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root with your PostgreSQL credentials:

```
HOST=localhost
DBNAME=polymarket_db
DBUSER=your_username
PASSWORD=your_password
PORT=5432
TEST_DBNAME=polymarket_test_db
```

### 4. Set up the database (optional — for running the pipeline)

Apply the schema to create the required tables:

```bash
psql -U postgres -c "CREATE DATABASE polymarket_db;"
psql -U postgres -d polymarket_db -f data/polymarket_db.sql
```

---

## Running Tests

### Testing DB and API calls (no DB or internet required)

```bash
PYTHONPATH=. pytest test_api_calls.py test_database_backend.py -v
```

### End-to-end integration tests (requires live PostgreSQL + internet access)

Set up a test database first:

```bash
psql -U postgres -c "CREATE DATABASE polymarket_test_db;"
psql -U postgres -d polymarket_test_db -f data/polymarket_db.sql
```

Then run:

```bash
PYTHONPATH=. pytest test_end_to_end.py -v
```

---

## Running the Pipeline (VM deployment)

All scripts are run from the project root with `PYTHONPATH=.`:

```bash
# Start continuous data collection (runs every 5 minutes)
PYTHONPATH=. python3 run_api_calls.py

# Run mispricing detection (populates mispricing_events table)
PYTHONPATH=. python3 run_detector.py

# Export mispricing events to CSV for modeling
PYTHONPATH=. python3 data/export_csv.py
```

---

## Modeling

The notebook: `data/eda_and_modeling.ipynb`, runs entirely using data from the csv file:
`data/export.csv`. No database connection is needed.

The notebook covers:
- Exploratory data analysis and class imbalance visualization
- Feature engineering
- Logistic regression, random forest, and a fully connected neural network
- ROC curves, confusion matrices, and feature importance analysis