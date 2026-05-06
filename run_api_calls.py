
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

# log to catch any errors when running script
logging.basicConfig(filename='collector.log', format= '%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

def main():
    '''
    Script that runs collect every 5 minutes.
    Only ends with keyboardInterruption exception.
    '''
    # loops forever until keyboard interruption
    while True:

        try:
            # run the collect function, log successful to ensure running properly
            api_calls.collect()
            logging.info('Collection completed successfully')

        # log exception
        except Exception:
            logging.exception(f'Collect script error')
        
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