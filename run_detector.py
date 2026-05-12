
'''
script to run mispricing detection and adding it to table
'''

import pandas as pd
import time
import logging
from polymarket import database_backend as db
from polymarket import detector

# setup logging similar run_api_calls.py
logging.basicConfig(filename='detector.log', level=logging.INFO, format='%(asctime)s %(message)s')

def main():
    while True:
        conn = None
        try:
            conn = db.get_connection() # using existing db logic
            
            # pull the most recent snapshots from the db
            query = "SELECT market_id, yes_price, no_price, timestamp, volume FROM snapshots"
            df = pd.read_sql(query, conn)
            
            # run detection logic
            results = detector.find_mispricings(df, threshold=0.001)
            
            if not results.empty:
                # handle results (print or save to a new 'mispricings' table)
                print(f"Detected {len(results)} mispriced events.")
                # results.to_sql('mispriced_events', conn, if_exists='append', index=False)
                logging.info(f"Detected {len(results)} mispricings.")
            
        except Exception as e:
            logging.error(f"Detector error: {e}")
        finally:
            if conn:
                conn.close()
        
        # wait before checking again (every 5 minutes)
        time.sleep(300)

if __name__ == '__main__':
    main()