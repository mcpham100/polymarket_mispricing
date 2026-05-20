import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from polymarket import detector


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def make_snapshot(market_id, timestamp, yes_price, no_price, liquidity=1000.0, volume=1000.0):
    """builds a single snapshot row as a dict"""
    return {
        'market_id': market_id,
        'timestamp': timestamp,
        'yes_price': yes_price,
        'no_price': no_price,
        'liquidity': liquidity,
        'volume': volume
    }


def make_df(rows):
    """converts a list of snapshot dicts into a dataframe"""
    return pd.DataFrame(rows)


BASE_TIME = datetime(2026, 5, 1, 12, 0, 0)

def t(minutes):
    """helper to offset from BASE_TIME by N minutes"""
    return BASE_TIME + timedelta(minutes=minutes)


# ---------------------------------------------------------------------------
# detect_mispricings tests
# ---------------------------------------------------------------------------

class TestDetectMispricings:

    def test_empty_input_returns_empty(self):
        df = pd.DataFrame(columns=['market_id', 'timestamp', 'yes_price', 'no_price', 'liquidity', 'volume'])
        result = detector.detect_mispricings(df)
        assert result.empty

    def test_flags_mispriced_row(self):
        """yes + no > 1.0 + threshold should be flagged"""
        rows = [make_snapshot('A', t(0), yes_price=0.6, no_price=0.5)]  # sum = 1.1
        result = detector.detect_mispricings(make_df(rows))
        assert result['is_mispriced'].iloc[0] == True

    def test_does_not_flag_normal_row(self):
        """yes + no == 1.0 should not be flagged"""
        rows = [make_snapshot('A', t(0), yes_price=0.5, no_price=0.5)]  # sum = 1.0
        result = detector.detect_mispricings(make_df(rows))
        assert result['is_mispriced'].iloc[0] == False

    def test_deviation_calculated_correctly(self):
        """deviation should be abs(price_sum - 1.0)"""
        rows = [make_snapshot('A', t(0), yes_price=0.6, no_price=0.5)]  # deviation = 0.1
        result = detector.detect_mispricings(make_df(rows))
        assert abs(result['deviation'].iloc[0] - 0.1) < 1e-9

    def test_underpriced_market_flagged(self):
        """yes + no < 1.0 - threshold should also be flagged"""
        rows = [make_snapshot('A', t(0), yes_price=0.4, no_price=0.4)]  # sum = 0.8
        result = detector.detect_mispricings(make_df(rows))
        assert result['is_mispriced'].iloc[0] == True

    def test_custom_threshold(self):
        """row just below a higher threshold should not be flagged"""
        rows = [make_snapshot('A', t(0), yes_price=0.505, no_price=0.5)]  # deviation = 0.005
        result = detector.detect_mispricings(make_df(rows), threshold=0.01)
        assert result['is_mispriced'].iloc[0] == False

    def test_original_df_not_modified(self):
        """detect_mispricings should not mutate the input dataframe"""
        rows = [make_snapshot('A', t(0), yes_price=0.6, no_price=0.5)]
        df = make_df(rows)
        original_cols = set(df.columns)
        detector.detect_mispricings(df)
        assert set(df.columns) == original_cols

    def test_multiple_rows_mixed_flags(self):
        """only rows exceeding threshold should be flagged"""
        rows = [
            make_snapshot('A', t(0),  yes_price=0.6, no_price=0.5),   # mispriced
            make_snapshot('B', t(0),  yes_price=0.5, no_price=0.5),   # normal
            make_snapshot('C', t(0),  yes_price=0.55, no_price=0.5),  # mispriced
        ]
        result = detector.detect_mispricings(make_df(rows))
        assert result['is_mispriced'].tolist() == [True, False, True]


# ---------------------------------------------------------------------------
# num_snapshots tests
# ---------------------------------------------------------------------------

class TestNumSnapshots:

    def _get_flagged(self, rows):
        """runs detect_mispricings and filters to mispriced rows only, adds num_snapshots"""
        df = detector.detect_mispricings(make_df(rows))
        mispricings = df[df['is_mispriced'] == True].copy()
        mispricings['num_snapshots'] = mispricings.groupby('market_id')['is_mispriced'].transform('sum')
        return mispricings

    def test_single_snapshot_market_has_num_snapshots_one(self):
        """a market with one flagged snapshot should have num_snapshots == 1"""
        rows = [make_snapshot('A', t(0), yes_price=0.6, no_price=0.5)]
        result = self._get_flagged(rows)
        assert result['num_snapshots'].iloc[0] == 1

    def test_multiple_snapshots_same_market(self):
        """a market with three flagged snapshots should have num_snapshots == 3 on each row"""
        rows = [
            make_snapshot('A', t(0),  yes_price=0.6, no_price=0.5),
            make_snapshot('A', t(5),  yes_price=0.6, no_price=0.5),
            make_snapshot('A', t(10), yes_price=0.6, no_price=0.5),
        ]
        result = self._get_flagged(rows)
        assert (result['num_snapshots'] == 3).all()

    def test_different_markets_have_independent_counts(self):
        """market A with 2 snapshots and market B with 1 should have independent counts"""
        rows = [
            make_snapshot('A', t(0), yes_price=0.6, no_price=0.5),
            make_snapshot('A', t(5), yes_price=0.6, no_price=0.5),
            make_snapshot('B', t(0), yes_price=0.6, no_price=0.5),
        ]
        result = self._get_flagged(rows)
        assert result[result['market_id'] == 'A']['num_snapshots'].iloc[0] == 2
        assert result[result['market_id'] == 'B']['num_snapshots'].iloc[0] == 1

    def test_num_snapshots_not_present_on_normal_rows(self):
        """normal rows should be filtered out before num_snapshots is computed"""
        rows = [
            make_snapshot('A', t(0), yes_price=0.6, no_price=0.5),  # mispriced
            make_snapshot('B', t(0), yes_price=0.5, no_price=0.5),  # normal
        ]
        result = self._get_flagged(rows)
        assert len(result) == 1
        assert result['market_id'].iloc[0] == 'A'