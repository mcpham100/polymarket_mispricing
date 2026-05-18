'''
Live end-to-end tests for the full data pipeline.
Requires:
  - PostgreSQL running locally
  - polymarket_test_db created and schema applied from data/polymarket_db.sql
  - .env file with TEST_DBNAME=polymarket_test_db and valid credentials
  - Live internet access for real Polymarket API calls

Run from project root: pytest test_end_to_end.py -v
WARNING: This test hits real APIs and writes to your test database.



RUN: 
psql -U postgres -c "CREATE DATABASE polymarket_test_db;"
psql -U postgres -d polymarket_test_db -f data/polymarket_db.sql

to create test db
'''

import pytest
import psycopg2
import os
from dotenv import load_dotenv

from polymarket import api_calls
from polymarket import database_backend as db


# ──────────────────────────────────────────────
# Setup / Teardown
# ──────────────────────────────────────────────

def get_test_connection():
    '''
    Establishes a connection to polymarket_test_db using .env credentials.
    Uses TEST_DBNAME instead of DBNAME to avoid writing to production DB.
    '''
    load_dotenv()
    try:
        conn = psycopg2.connect(
            host=os.getenv('HOST'),
            dbname=os.getenv('TEST_DBNAME'),   # points to polymarket_test_db
            user=os.getenv('USER'),
            password=os.getenv('PASSWORD'),
            port=os.getenv('PORT')
        )
        return conn
    except psycopg2.OperationalError as e:
        pytest.fail(f'Could not connect to polymarket_test_db: {e}')


@pytest.fixture(scope='module')
def test_conn():
    '''
    Module-scoped fixture: connects once, yields connection, clears tables after all tests.
    scope='module' means setup and teardown run once for the entire file.
    '''
    conn = get_test_connection()
    yield conn

    # teardown: clear test data after all tests in this file complete
    cursor = conn.cursor()
    cursor.execute('DELETE FROM snapshots;')
    cursor.execute('DELETE FROM markets;')
    conn.commit()
    cursor.close()
    conn.close()


# ──────────────────────────────────────────────
# Patch collect() to use test DB connection
# ──────────────────────────────────────────────

def run_collect_with_test_db(test_conn):
    api_calls.collect(test_conn, max_pages=1)

# ──────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────

def test_live_collect_inserts_markets(test_conn):
    '''
    Runs collect() once against real Polymarket APIs and verifies at least
    one row was inserted into the markets table in polymarket_test_db.
    '''
    run_collect_with_test_db(test_conn)

    cursor = test_conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM markets;')
    count = cursor.fetchone()[0]
    cursor.close()

    assert count > 0, 'No rows found in markets table after collect()'


def test_live_collect_inserts_snapshots(test_conn):
    '''
    Verifies at least one row was inserted into the snapshots table.
    Assumes test_live_collect_inserts_markets has already run (module scope).
    '''
    cursor = test_conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM snapshots;')
    count = cursor.fetchone()[0]
    cursor.close()

    assert count > 0, 'No rows found in snapshots table after collect()'


def test_snapshot_prices_sum_to_one(test_conn):
    '''
    Verifies that yes_price + no_price is within a reasonable tolerance of 1.0
    for all snapshots. Polymarket binary markets should sum to ~1.0.
    Tolerance of 0.05 accounts for spread.
    '''
    cursor = test_conn.cursor()
    cursor.execute('SELECT yes_price, no_price FROM snapshots WHERE yes_price IS NOT NULL AND no_price IS NOT NULL;')
    rows = cursor.fetchall()
    cursor.close()

    assert len(rows) > 0, 'No valid snapshots found to validate prices'

    for yes_price, no_price in rows:
        price_sum = yes_price + no_price
        assert abs(price_sum - 1.0) <= 0.05, \
            f'Price sum out of tolerance: yes={yes_price}, no={no_price}, sum={price_sum}'


def test_snapshot_foreign_key_integrity(test_conn):
    '''
    Verifies every snapshot row references a market_id that exists in the markets table.
    Catches any FK constraint issues or orphaned rows.
    '''
    cursor = test_conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) FROM snapshots s
        LEFT JOIN markets m ON s.market_id = m.market_id
        WHERE m.market_id IS NULL;
    ''')
    orphaned = cursor.fetchone()[0]
    cursor.close()

    assert orphaned == 0, f'{orphaned} snapshot rows have no matching market in markets table'


def test_snapshot_no_null_prices(test_conn):
    '''
    Verifies no snapshot rows were inserted with NULL yes_price or no_price.
    NULL prices indicate a failed CLOB lookup that slipped through.
    '''
    cursor = test_conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) FROM snapshots
        WHERE yes_price IS NULL OR no_price IS NULL;
    ''')
    null_count = cursor.fetchone()[0]
    cursor.close()

    assert null_count == 0, f'{null_count} snapshots have NULL prices — check CLOB casting logic'
