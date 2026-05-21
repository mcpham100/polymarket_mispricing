
'''
script to run mispricing detection and adding it to table
'''

# importing libraries
import pandas as pd
import logging
from polymarket import database_backend as db

# setup logging similar run_api_calls.py
logging.basicConfig(filename='detector.log', level=logging.INFO, format='%(asctime)s %(message)s')

def main():
        conn = None
        try:
            conn = db.get_connection() # using existing db logic
            
            # pull snapshots from the db
            # filter to only snapshots that are binary (not multi-outcome), liquidity >= 500, and are mispriced
            # add COUNT over each market to improve compile speed on vm
            # reduce the size of df significantly when read_sql is executed, preventing out of memory error with 20 million+ rows snapshots table
            query = "" \
            "SELECT m.market_id, m.neg_risk, s.yes_price, s.no_price, s.timestamp AS start_time, s.liquidity, " \
            "COUNT (*) OVER (PARTITION BY s.market_id) AS num_snapshots, " \
            "ABS(s.yes_price + s.no_price - 1) as deviation " \
            "FROM snapshots AS s " \
            "JOIN markets AS m ON s.market_id = m.market_id " \
            "WHERE m.neg_risk = False AND s.liquidity >= 500 " \
            "AND ABS(s.yes_price + s.no_price - 1) > 0.001 "

            # create df containing all the snapshots
            # use read_sql_query instead of read_sql to avoid SQLAlchemy warning due to having a psycopg2 connection
            mispricings = pd.read_sql_query(query, conn)

            # ensure mispricings isn't empty to prevent errors when executing other ops
            if not mispricings.empty:
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