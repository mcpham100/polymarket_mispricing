import pandas as pd
import numpy as np

def detect_mispricings(df, threshold=0.001):
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