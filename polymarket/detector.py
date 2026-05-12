import pandas as pd

def find_mispricings(df, threshold=0.001):
    """
    Analyzes a dataframe of snapshots and returns only mispriced rows.
    Expects columns: market_id, yes_price, no_price, timestamp, volume
    """
    # create a copy to keep original data
    df = df.copy()
    
    # calculate the sum: yes_price + no_price
    df['price_sum'] = df['yes_price'] + df['no_price']
    
    # calculate absolute deviation from 1.0
    df['deviation'] = (df['price_sum'] - 1.0).abs()
    
    # filter based on the threshold
    mispriced_events = df[df['deviation'] > threshold].copy()
    
    return mispriced_events