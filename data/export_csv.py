
'''
script to run export data on vm to a csv
'''

# importing libraries
import pandas as pd
import logging
from polymarket import database_backend as db

# setup logging similar run_api_calls.py
logging.basicConfig(filename='export.log', level=logging.INFO, format='%(asctime)s %(message)s')

def main():
        conn = None
        try:
            conn = db.get_connection() # using existing db logic
            
            # select everything joinined on market_id 
            # AND snapshots.timestamp and mispricing_events.start_time
            query = "SELECT mis_e.*, m.*, s.* " \
            "FROM mispricing_events as mis_e " \
            "JOIN markets as m ON mis_e.market_id = m.market_id " \
            "JOIN snapshots as s ON mis_e.start_time = s.timestamp AND s.market_id = mis_e.market_id"

            # create df containing all the snapshots
            # use read_sql_query instead of read_sql to avoid SQLAlchemy warning due to having a psycopg2 connection
            df = pd.read_sql_query(query, conn)

            df.to_csv('data/export.csv',index = False)
            logging.info('Export completed successfully')

        # raise error if no mispricings were detected  
        except Exception as e:
            logging.error(f"Export error: {e}")

        # close connection to prevent memory leaks
        finally:
            if conn:
                conn.close()

# execute main function
if __name__ == '__main__':
    main()