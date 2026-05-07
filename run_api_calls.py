
'''
Data pipeline script. Ran on VM so that program is not required to constantly be ran locally. 
Takes snapshots of data every 5 minutes.
'''

# import libraries
import logging
import time
import sys

# import api_calls from polymarket folder
from polymarket import api_calls
from polymarket import datbase_backend as db

# log to catch any errors when running script
logging.basicConfig(filename='collector.log', format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

def main():
    '''
    Script that runs collect every 5 minutes.
    Only ends with keyboardInterruption exception.
    '''

    # loops forever until keyboard interruption
    while True:
        
        # initialize conn for final guard
        conn = None
        
        try:
            # get db connection; create new connection every time script is ran
            conn = db.get_connection()
            # run the collect function, log successful to ensure running properly
            api_calls.collect(conn)
            logging.info('Collection completed successfully')

        # log exception
        except Exception:
            logging.exception(f'Collect script error')
        
        finally:
            # guard in case db.get_connection() fails to create a connection
            # close connection to prevent memory leaks
            if conn is not None:
                conn.close()

        # run every 5 minutes (300 seconds)
        time.sleep(300)

# execute main function
if __name__ == '__main__':
    try:
        main()

    # only stop when deliberately interrupted (control-c or delete)
    except KeyboardInterrupt:
        logging.info('Collect stopped')
        sys.exit(0)