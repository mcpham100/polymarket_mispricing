
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
        conn = None
        try:
            conn = db.get_connection() # using existing db logic
            
            # pull snapshots from the db
            query = "SELECT m.market_id, m.neg_risk, s.yes_price, s.no_price, s.timestamp, s.liquidity " \
            "FROM snapshots AS s " \
            "JOIN markets AS m ON s.market_id = m.market_id " \
            "WHERE neg_risk = False AND liquidity >= 500"

            # create df containing all the snapshots
            df = pd.read_sql(query, conn)
            
            # run detection logic over all the snapshots
            mispricings = detector.detect_mispricings (df, threshold=0.001)
            
            # filter to only be mispriced columns
            mispricings = mispricings[mispricings['is_mispriced'] == True]

            # ensure mispricings isn't empty to prevent errors when executing other ops
            if not mispricings.empty:
                # create num_snapshots column
                # compute num_snapshots per market_id and retain original shape
                mispricings['num_snapshots'] = mispricings.groupby('market_id')['is_mispriced'].transform('sum')

                # loop through each mispriced event and insert it into mispricing_events
                for index, event in mispricings.iterrows():
                    db.insert_event(conn, event)

                # log successful insertions
                logging.info(f"Detected {len(mispricings)} mispricings.")

        # raise error if no mispricings were detected  
        except Exception as e:
            logging.error(f"Detector error: {e}")

        # close connection to prevent memory leaks
        finally:
            if conn:
                conn.close()

# execute main function
if __name__ == '__main__':
    main()