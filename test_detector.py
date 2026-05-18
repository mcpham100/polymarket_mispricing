import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from polymarket import detector


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def make_snapshot(market_id, timestamp, yes_price, no_price, volume=1000.0):
    """builds a single snapshot row as a dict"""
    return {
        'market_id': market_id,
        'timestamp': timestamp,
        'yes_price': yes_price,
        'no_price': no_price,
        'volume': volume
    }


def make_df(rows):
    """converts a list of snapshot dicts into a dataframe"""
    return pd.DataFrame(rows)


BASE_TIME = datetime(2026, 5, 1, 12, 0, 0)  # arbitrary start time

def t(minutes):
    """helper to offset from BASE_TIME by N minutes"""
    return BASE_TIME + timedelta(minutes=minutes)


# ---------------------------------------------------------------------------
# find_mispricings tests
# ---------------------------------------------------------------------------

class TestFindMispricings:

    def test_empty_input_returns_empty(self):
        df = pd.DataFrame(columns=['market_id', 'timestamp', 'yes_price', 'no_price', 'volume'])
        result = detector.find_mispricings(df)
        assert result.empty

    def test_flags_mispriced_row(self):
        """yes + no > 1.0 + threshold should be flagged"""
        rows = [make_snapshot('A', t(0), yes_price=0.6, no_price=0.5)]  # sum = 1.1
        df = make_df(rows)
        result = detector.find_mispricings(df)
        assert result['is_mispriced'].iloc[0] == True

    def test_does_not_flag_normal_row(self):
        """yes + no == 1.0 should not be flagged"""
        rows = [make_snapshot('A', t(0), yes_price=0.5, no_price=0.5)]  # sum = 1.0
        df = make_df(rows)
        result = detector.find_mispricings(df)
        assert result['is_mispriced'].iloc[0] == False

    def test_deviation_calculated_correctly(self):
        """deviation should be abs(price_sum - 1.0)"""
        rows = [make_snapshot('A', t(0), yes_price=0.6, no_price=0.5)]  # sum = 1.1, deviation = 0.1
        df = make_df(rows)
        result = detector.find_mispricings(df)
        assert abs(result['deviation'].iloc[0] - 0.1) < 1e-9

    def test_underpriced_market_flagged(self):
        """yes + no < 1.0 - threshold should also be flagged (abs deviation)"""
        rows = [make_snapshot('A', t(0), yes_price=0.4, no_price=0.4)]  # sum = 0.8
        df = make_df(rows)
        result = detector.find_mispricings(df)
        assert result['is_mispriced'].iloc[0] == True

    def test_custom_threshold(self):
        """row just below a higher threshold should not be flagged"""
        rows = [make_snapshot('A', t(0), yes_price=0.505, no_price=0.5)]  # deviation = 0.005
        df = make_df(rows)
        result = detector.find_mispricings(df, threshold=0.01)
        assert result['is_mispriced'].iloc[0] == False

    def test_original_df_not_modified(self):
        """find_mispricings should not mutate the input dataframe"""
        rows = [make_snapshot('A', t(0), yes_price=0.6, no_price=0.5)]
        df = make_df(rows)
        original_cols = set(df.columns)
        detector.find_mispricings(df)
        assert set(df.columns) == original_cols


# ---------------------------------------------------------------------------
# group_snapshots_into_events tests
# ---------------------------------------------------------------------------

class TestGroupSnapshotsIntoEvents:

    def _flag(self, df, threshold=0.001):
        """runs find_mispricings so group_snapshots_into_events has is_mispriced col"""
        return detector.find_mispricings(df, threshold=threshold)

    def test_empty_input_returns_empty(self):
        df = pd.DataFrame(columns=['market_id', 'timestamp', 'yes_price', 'no_price', 'volume'])
        flagged = self._flag(df)
        result = detector.group_snapshots_into_events(flagged)
        assert result.empty

    def test_no_mispricings_returns_empty(self):
        """all normal rows should produce no events"""
        rows = [
            make_snapshot('A', t(0), 0.5, 0.5),
            make_snapshot('A', t(5), 0.5, 0.5),
        ]
        flagged = self._flag(make_df(rows))
        result = detector.group_snapshots_into_events(flagged)
        assert result.empty

    def test_consecutive_snapshots_form_one_event(self):
        """two consecutive mispriced snapshots for one market = one event"""
        rows = [
            make_snapshot('A', t(0),  yes_price=0.6, no_price=0.5),
            make_snapshot('A', t(5),  yes_price=0.6, no_price=0.5),
        ]
        flagged = self._flag(make_df(rows))
        result = detector.group_snapshots_into_events(flagged)
        assert len(result) == 1

    def test_gap_creates_two_events(self):
        """same market, two mispricing windows separated by >7 min gap = two events"""
        rows = [
            make_snapshot('A', t(0),  yes_price=0.6, no_price=0.5),
            make_snapshot('A', t(5),  yes_price=0.6, no_price=0.5),
            # gap of 15 minutes
            make_snapshot('A', t(20), yes_price=0.6, no_price=0.5),
            make_snapshot('A', t(25), yes_price=0.6, no_price=0.5),
        ]
        flagged = self._flag(make_df(rows))
        result = detector.group_snapshots_into_events(flagged)
        assert len(result) == 2

    def test_different_markets_dont_bleed(self):
        """market A and market B mispriced at same time = two separate events"""
        rows = [
            make_snapshot('A', t(0), yes_price=0.6, no_price=0.5),
            make_snapshot('B', t(0), yes_price=0.6, no_price=0.5),
            make_snapshot('A', t(5), yes_price=0.6, no_price=0.5),
            make_snapshot('B', t(5), yes_price=0.6, no_price=0.5),
        ]
        flagged = self._flag(make_df(rows))
        result = detector.group_snapshots_into_events(flagged)
        assert len(result) == 2
        assert set(result['market_id']) == {'A', 'B'}

    def test_single_snapshot_event(self):
        """one flagged snapshot = valid event with start_time == end_time and duration == 0"""
        rows = [make_snapshot('A', t(0), yes_price=0.6, no_price=0.5)]
        flagged = self._flag(make_df(rows))
        result = detector.group_snapshots_into_events(flagged)
        assert len(result) == 1
        assert result['start_time'].iloc[0] == result['end_time'].iloc[0]
        assert result['duration'].iloc[0] == 0.0

    def test_start_time_is_earliest_timestamp(self):
        rows = [
            make_snapshot('A', t(0), yes_price=0.6, no_price=0.5),
            make_snapshot('A', t(5), yes_price=0.6, no_price=0.5),
            make_snapshot('A', t(10), yes_price=0.6, no_price=0.5),
        ]
        flagged = self._flag(make_df(rows))
        result = detector.group_snapshots_into_events(flagged)
        assert pd.Timestamp(result['start_time'].iloc[0]) == pd.Timestamp(t(0))

    def test_end_time_is_latest_timestamp(self):
        rows = [
            make_snapshot('A', t(0),  yes_price=0.6, no_price=0.5),
            make_snapshot('A', t(5),  yes_price=0.6, no_price=0.5),
            make_snapshot('A', t(10), yes_price=0.6, no_price=0.5),
        ]
        flagged = self._flag(make_df(rows))
        result = detector.group_snapshots_into_events(flagged)
        assert pd.Timestamp(result['end_time'].iloc[0]) == pd.Timestamp(t(10))

    def test_max_deviation_is_correct(self):
        """max_deviation should be the highest deviation across all snapshots in the event"""
        rows = [
            make_snapshot('A', t(0),  yes_price=0.55, no_price=0.5),   # deviation = 0.05
            make_snapshot('A', t(5),  yes_price=0.65, no_price=0.5),   # deviation = 0.15
            make_snapshot('A', t(10), yes_price=0.51, no_price=0.5),   # deviation = 0.01
        ]
        flagged = self._flag(make_df(rows))
        result = detector.group_snapshots_into_events(flagged)
        assert abs(result['peak_deviation'].iloc[0] - 0.15) < 1e-9

    def test_initial_deviation_is_first_snapshot(self):
        """initial_deviation should be the deviation of the first snapshot in the event"""
        rows = [
            make_snapshot('A', t(0),  yes_price=0.55, no_price=0.5),   # deviation = 0.05
            make_snapshot('A', t(5),  yes_price=0.65, no_price=0.5),   # deviation = 0.15
        ]
        flagged = self._flag(make_df(rows))
        result = detector.group_snapshots_into_events(flagged)
        assert abs(result['initial_deviation'].iloc[0] - 0.05) < 1e-9

    def test_duration_calculated_correctly(self):
        """duration should be (end_time - start_time) in minutes"""
        rows = [
            make_snapshot('A', t(0),  yes_price=0.6, no_price=0.5),
            make_snapshot('A', t(5),  yes_price=0.6, no_price=0.5),
            make_snapshot('A', t(10), yes_price=0.6, no_price=0.5),
        ]
        flagged = self._flag(make_df(rows))
        result = detector.group_snapshots_into_events(flagged)
        assert result['duration'].iloc[0] == 10.0

    def test_multiple_markets_multiple_events(self):
        """stress test: two markets, two events each = four total events"""
        rows = [
            # market A event 1
            make_snapshot('A', t(0),  yes_price=0.6, no_price=0.5),
            make_snapshot('A', t(5),  yes_price=0.6, no_price=0.5),
            # market A event 2 (gap)
            make_snapshot('A', t(20), yes_price=0.6, no_price=0.5),
            make_snapshot('A', t(25), yes_price=0.6, no_price=0.5),
            # market B event 1
            make_snapshot('B', t(0),  yes_price=0.6, no_price=0.5),
            make_snapshot('B', t(5),  yes_price=0.6, no_price=0.5),
            # market B event 2 (gap)
            make_snapshot('B', t(20), yes_price=0.6, no_price=0.5),
            make_snapshot('B', t(25), yes_price=0.6, no_price=0.5),
        ]
        flagged = self._flag(make_df(rows))
        result = detector.group_snapshots_into_events(flagged)
        assert len(result) == 4

