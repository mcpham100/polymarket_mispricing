import pandas as pd
import numpy as np

def find_mispricings(df, threshold=0.001):
    """
    core filtering which analyzes a dataframe of snapshots and flags individual mispriced rows
    """
    if df.empty:
        return pd.DataFrame()
    
    # create a copy to keep original data
    df = df.copy()

    # calculate the sum: yes_price + no_price
    df['price_sum'] = df['yes_price'] + df['no_price']
    
    # calculate abs deviation from 1.0
    df['deviation'] = (df['price_sum'] - 1.0).abs()
    
    # basic threshold flag
    df['is_mispriced'] = df['deviation'] > threshold
    
    return df


def group_snapshots_into_events(df):
    """
    groups consecutive mispriced snapshots for each market into one "arbitrage event".
    this allows us to record tracking start time, peak friction, and decay speed for
    one event group to prepare for analysis and modeling
    """
    # filter to only have rows that crossed threshold
    mispriced_df = df[df['is_mispriced'] == True].copy()
    
    if mispriced_df.empty:
        return pd.DataFrame()
    
    # ensure data is chronological for each market for accurate time-series clustering
    mispriced_df['timestamp'] = pd.to_datetime(mispriced_df['timestamp'])
    mispriced_df = mispriced_df.sort_values(by=['market_id', 'timestamp'])
    
    # calculate time difference btwn consecutive rows for the same market
    # polymarket snapshots happen every 5 min (300s)
    mispriced_df['time_diff'] = mispriced_df.groupby('market_id')['timestamp'].diff()
    
    # if the gap btwn snapshots is >7 min (420s),
    # it means the previous mispricing ended, and that this is a new event
    is_new_event = (mispriced_df['time_diff'].isnull()) | (mispriced_df['time_diff'].dt.total_seconds() > 420)
    
    # create a tracking id for each continuous window of mispricing
    mispriced_df['event_id'] = is_new_event.cumsum()
    
    # aggregate rows into unique analytical events
    events = mispriced_df.groupby('event_id').agg(
        market_id=('market_id', 'first'),
        start_time=('timestamp', 'min'),
        end_time=('timestamp', 'max'),
        initial_deviation=('deviation', 'first'),
        peak_deviation=('deviation', 'max'),
        starting_volume=('volume', 'first'),
        snapshot_count=('market_id', 'count')
    ).reset_index(drop=True)
    
    # calculate duration of the mispricing in minutes
    events['duration_min'] = (events['end_time'] - events['start_time']).dt.total_seconds() / 60.0
    
    return events