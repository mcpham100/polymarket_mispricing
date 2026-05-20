'''
Unit tests for polymarket/database_backend.py
All PostgreSQL interactions are mocked — no live DB required.
Run from project root: pytest test_database_backend.py
'''

import pytest
import sys
from unittest.mock import MagicMock, patch
import psycopg2

from polymarket import database_backend as db


# ──────────────────────────────────────────────
# get_connection()
# ──────────────────────────────────────────────

def test_get_connection_success():
    '''get_connection() returns a connection object when credentials are valid.'''
    with patch('polymarket.database_backend.psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        conn = db.get_connection()

        mock_connect.assert_called_once()
        assert conn == mock_conn


def test_get_connection_failure():
    '''get_connection() calls sys.exit(1) when psycopg2 raises OperationalError.'''
    with patch('polymarket.database_backend.psycopg2.connect',
               side_effect=psycopg2.OperationalError('bad credentials')):
        with pytest.raises(SystemExit) as exc_info:
            db.get_connection()
        assert exc_info.value.code == 1


# ──────────────────────────────────────────────
# insert_market()
# ──────────────────────────────────────────────

def make_mock_conn():
    '''Helper: returns a mock conn with a mock cursor.'''
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


def sample_market_data():
    return {
        'market_id': 'mkt_001',
        'question': 'Will X happen?',
        'category': None,
        'end_date': '2026-07-31T12:00:00Z'
    }


def test_insert_market_success():
    '''insert_market() calls execute and commit with correct market data.'''
    mock_conn, mock_cursor = make_mock_conn()
    data = sample_market_data()

    db.insert_market(mock_conn, data)

    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()
    mock_cursor.close.assert_called_once()

    # verify correct values passed into query
    call_args = mock_cursor.execute.call_args[0][1]
    assert call_args['market_id'] == 'mkt_001'
    assert call_args['question'] == 'Will X happen?'
    assert call_args['category'] is None


def test_insert_market_db_error():
    '''insert_market() calls rollback and closes cursor on psycopg2.Error.'''
    mock_conn, mock_cursor = make_mock_conn()
    mock_cursor.execute.side_effect = psycopg2.Error('insert failed')

    db.insert_market(mock_conn, sample_market_data())

    mock_conn.rollback.assert_called_once()
    mock_conn.commit.assert_not_called()
    mock_cursor.close.assert_called_once()


# ──────────────────────────────────────────────
# insert_snapshot()
# ──────────────────────────────────────────────

def sample_snapshot_data():
    return {
        'market_id': 'mkt_001',
        'yes_price': 0.55,
        'no_price': 0.45,
        'volume': 10000.0,
        'liquidity': 5000.0,
        'spread': 0.01
    }


def test_insert_snapshot_success():
    '''insert_snapshot() calls execute and commit with all 6 required fields.'''
    mock_conn, mock_cursor = make_mock_conn()
    data = sample_snapshot_data()

    db.insert_snapshot(mock_conn, data)

    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()
    mock_cursor.close.assert_called_once()

    call_args = mock_cursor.execute.call_args[0][1]
    assert call_args['yes'] == 0.55
    assert call_args['no'] == 0.45
    assert call_args['spread'] == 0.01


def test_insert_snapshot_db_error():
    '''insert_snapshot() calls rollback and closes cursor on psycopg2.Error.'''
    mock_conn, mock_cursor = make_mock_conn()
    mock_cursor.execute.side_effect = psycopg2.Error('snapshot insert failed')

    db.insert_snapshot(mock_conn, sample_snapshot_data())

    mock_conn.rollback.assert_called_once()
    mock_conn.commit.assert_not_called()
    mock_cursor.close.assert_called_once()

# ──────────────────────────────────────────────
# insert_event()
# ──────────────────────────────────────────────

def sample_event_data():
    return {
        'market_id': 'mkt_001',
        'start_time': '2026-05-01T12:00:00Z',
        'deviation': 0.05,
        'num_snapshots': 3
    }


def test_insert_event_success():
    '''insert_event() calls execute and commit with correct event data.'''
    mock_conn, mock_cursor = make_mock_conn()
    data = sample_event_data()

    db.insert_event(mock_conn, data)

    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()
    mock_cursor.close.assert_called_once()

    call_args = mock_cursor.execute.call_args[0][1]
    assert call_args['m_id'] == 'mkt_001'
    assert call_args['deviation'] == 0.05
    assert call_args['num_s'] == 3


def test_insert_event_db_error():
    '''insert_event() calls rollback and closes cursor on psycopg2.Error.'''
    mock_conn, mock_cursor = make_mock_conn()
    mock_cursor.execute.side_effect = psycopg2.Error('event insert failed')

    db.insert_event(mock_conn, sample_event_data())

    mock_conn.rollback.assert_called_once()
    mock_conn.commit.assert_not_called()
    mock_cursor.close.assert_called_once()