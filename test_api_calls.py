'''
Unit tests for polymarket/api_calls.py
All API calls and DB interactions are mocked — no live connections required.
Run from project root: pytest test_api_calls.py
'''

import pytest
import json
from unittest.mock import MagicMock, patch, call

from polymarket import api_calls


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def make_fake_market(market_id='001', question='Will X happen?'):
    '''Returns a fake market dict matching Gamma API structure.'''
    tokens = [f'yes_token_{market_id}', f'no_token_{market_id}']
    return {
        'id': market_id,
        'question': question,
        'liquidity': '5000.0',
        'volume': '10000.0',
        'spread': '0.01',
        'endDate': '2026-07-31T12:00:00Z',
        'clobTokenIds': json.dumps(tokens)
    }


def make_fake_gamma_response(markets, next_cursor=None):
    '''Returns a mock requests.Response for Gamma API.'''
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        'markets': markets,
        'next_cursor': next_cursor
    }
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def make_fake_clob_response(token_prices):
    '''Returns a mock requests.Response for CLOB API.'''
    mock_resp = MagicMock()
    mock_resp.json.return_value = token_prices
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# ──────────────────────────────────────────────
# gamma_markets()
# ──────────────────────────────────────────────

def test_gamma_markets_success():
    '''gamma_markets() yields a list of market tuples from a single page.'''
    fake_market = make_fake_market('001', 'Will X happen?')
    fake_response = make_fake_gamma_response([fake_market], next_cursor=None)

    with patch('polymarket.api_calls.requests.get', return_value=fake_response):
        pages = list(api_calls.gamma_markets())

    assert len(pages) == 1
    assert len(pages[0]) == 1
    market_tuple = pages[0][0]
    assert market_tuple[0] == '001'         # market_id
    assert market_tuple[1] == 'Will X happen?'  # question
    assert market_tuple[2] is None          # category always None


def test_gamma_markets_pagination():
    '''gamma_markets() passes after_cursor on second page request.'''
    market1 = make_fake_market('001')
    market2 = make_fake_market('002')
    page1 = make_fake_gamma_response([market1], next_cursor='cursor_abc')
    page2 = make_fake_gamma_response([market2], next_cursor=None)

    with patch('polymarket.api_calls.requests.get', side_effect=[page1, page2]) as mock_get:
        pages = list(api_calls.gamma_markets())

    assert len(pages) == 2
    # second call should include after_cursor param
    second_call_params = mock_get.call_args_list[1][1]['params']
    assert second_call_params['after_cursor'] == 'cursor_abc'


def test_gamma_markets_request_error():
    '''gamma_markets() breaks cleanly and yields nothing on RequestException.'''
    import requests as req
    with patch('polymarket.api_calls.requests.get',
               side_effect=req.exceptions.RequestException('timeout')):
        pages = list(api_calls.gamma_markets())

    assert pages == []


def test_gamma_markets_bad_market_data():
    '''gamma_markets() skips malformed markets and continues to next.'''
    good_market = make_fake_market('001')
    bad_market = {'id': '002'}  # missing required keys

    fake_response = make_fake_gamma_response([bad_market, good_market], next_cursor=None)

    with patch('polymarket.api_calls.requests.get', return_value=fake_response):
        pages = list(api_calls.gamma_markets())

    # only the good market should be in results
    assert len(pages[0]) == 1
    assert pages[0][0][0] == '001'


# ──────────────────────────────────────────────
# clob_midpoints()
# ──────────────────────────────────────────────

def test_clob_midpoints_success():
    '''clob_midpoints() returns dict of {token_id: price} on success.'''
    tokens = [('yes_token_001', 'no_token_001')]
    fake_prices = {'yes_token_001': '0.55', 'no_token_001': '0.45'}
    fake_response = make_fake_clob_response(fake_prices)

    with patch('polymarket.api_calls.requests.post', return_value=fake_response):
        result = api_calls.clob_midpoints(tokens)

    assert result == fake_prices


def test_clob_midpoints_request_error():
    '''clob_midpoints() returns empty dict on RequestException.'''
    import requests as req
    with patch('polymarket.api_calls.requests.post',
               side_effect=req.exceptions.RequestException('connection error')):
        result = api_calls.clob_midpoints([('yes_token_001', 'no_token_001')])

    assert result == {}


# ──────────────────────────────────────────────
# collect()
# ──────────────────────────────────────────────

def test_collect_inserts_market_and_snapshot():
    '''collect() calls insert_market and insert_snapshot once per market.'''
    fake_market = make_fake_market('001')
    fake_page = make_fake_gamma_response([fake_market], next_cursor=None)
    fake_prices = {'yes_token_001': '0.55', 'no_token_001': '0.45'}
    fake_clob = make_fake_clob_response(fake_prices)
    mock_conn = MagicMock()

    with patch('polymarket.api_calls.requests.get', return_value=fake_page), \
         patch('polymarket.api_calls.requests.post', return_value=fake_clob), \
         patch('polymarket.api_calls.db.insert_market') as mock_insert_market, \
         patch('polymarket.api_calls.db.insert_snapshot') as mock_insert_snapshot:

        api_calls.collect(mock_conn)

    mock_insert_market.assert_called_once()
    mock_insert_snapshot.assert_called_once()

    snapshot_arg = mock_insert_snapshot.call_args[0][1]
    assert snapshot_arg['market_id'] == '001'


def test_collect_float_casting_none():
    '''collect() skips a market gracefully when CLOB returns None for token price.'''
    fake_market = make_fake_market('001')
    fake_page = make_fake_gamma_response([fake_market], next_cursor=None)
    fake_clob = make_fake_clob_response({})
    mock_conn = MagicMock()

    with patch('polymarket.api_calls.requests.get', return_value=fake_page), \
         patch('polymarket.api_calls.requests.post', return_value=fake_clob), \
         patch('polymarket.api_calls.db.insert_market'), \
         patch('polymarket.api_calls.db.insert_snapshot') as mock_insert_snapshot:

        api_calls.collect(mock_conn)

    mock_insert_snapshot.assert_not_called()