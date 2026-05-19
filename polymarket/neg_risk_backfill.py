'''
One-time ran script to backfill negRisk into the markets table
Need to filter out negRisk = True when identifying snapshots due to the nature of multi-outcome markets
In multi-outcome markets, multiple binary outcomes share linked tokens, so tokens don't sum to 1.0
negRisk = False -> desired binary market
'''

# importing libraries
import requests
import json
import logging
import time
import psycopg2

# import database_backend
from polymarket import database_backend as db

# log to catch any errors when running script
logging.basicConfig(filename='negRiskBackfill.log', format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

def get_neg_risk(max_pages=None):
    """
    A generator that grabs negRisk from each market from Polymarket Gamma API.
    Pages through the /markets/keyset endpoint to get info.

    Args:
        max_pages (int, optional): the max number of pages to retrieve.
            used to limit data during testing. Defaults to None (all pages)

    Yields:
        list[tuple]: a list of tuples with market_id and negRisk
            (market_id, negRisk)
    """
    # define next_cursor (part of Gamma API to be used to load next page)
    next_cursor = None
    page_count = 0

    # loop through all pages 
    while True:
        # build market_neg_risk
        market_neg_risk = list()

        # additional params per Polymarket's API documentation
        params={"active": "true", "closed": "false", "limit": "100"}
        
        # updates params if it's not the first call
        if next_cursor is not None:
            params['after_cursor'] = next_cursor

        try:
            # call gamma api with necessary parameters
            response = requests.get("https://gamma-api.polymarket.com/markets/keyset",
            params = params,
            timeout=10 # add a timeout to prevent connections waiting indefinitely
            )

            # time delay to prevent rate limits; 300 req/10s; we make 100 req per call
            time.sleep(0.5)

            response.raise_for_status() # error if 4xx or 5xx from response status code (ex: 404 or 429 rate limit)

            # break down response into markets and next_cursor components
            response_json = response.json()
            markets = response_json['markets']
            next_cursor = response_json['next_cursor']

            # loop through markets of the page
            for m in markets:
                try:
                    # acquire and append market_id and negRisk
                    market_id = m['id']
                    neg_risk = m['negRisk']

                    market_neg_risk.append((market_id, neg_risk))
                
                # error if data not found or can't be decoded (improper JSON format) or found, log error
                except (KeyError, TypeError, json.JSONDecodeError) as e:
                    logging.error(f'Error appending negRisk: {e}')

            # create generator; returns market_neg_risk then re-runs
            yield market_neg_risk # returns a list of tuples [(market1), (market2)]

            # advance to next page of markets once reaching the end of current page
            page_count += 1
            
            # ensure no out of bounds errors
            if max_pages is not None and page_count >= max_pages:
                break

            # break out of loop once it reaches the last page
            if not next_cursor:
                break
        
        # error if API call fails, log error
        except requests.exceptions.RequestException as e:
            logging.error(f'Gamma API to backfill negRisk failed: {e}')
            break

def update_neg_risk(conn, neg_risk_data):
    '''
    Update a market record in markets table to fill in the proper neg_risk

    Args:
        conn (psycopg2.connection): active database connection from get_connection()
        neg_risk_data (dict): market metadata with keys:
            - market_id (str): unique Polymarket market identifier
            - neg_risk (bool): true if a negRisk market; false if not
    
    Returns:
        None
    '''
    # conn.cursor will return a cursor object, you can use this query to perform queries
    cursor = conn.cursor()

    try:
    # cursor.execute(SQL) allows for SQL queries within Python
    # query to add a row with given attributes
        cursor.execute("""
                    UPDATE markets
                    SET neg_risk = %(neg_risk)s
                    WHERE market_id = %(market_id)s
                    """,
                    ({'neg_risk': neg_risk_data['neg_risk'], 'market_id': neg_risk_data['market_id']}),
                    )
        
        # %s serves as placeholders value; pass in a dict as second arg to pass in actual value from python
        
        conn.commit() # no need to check for conflicts as only one write at a time (no concurrency occuring)

    # raise error and exit
    except psycopg2.Error as e:
        logging.error(f'Updating neg_risk failure: {e}')
        conn.rollback() # rollback changes (does not commit them)

    finally:
        # close to prevent memory leaks (deletes cursor object)
        cursor.close()
    return

# max_pages paramater used in testing; not actually used in deployment
def neg_risk_backfill(conn, max_pages=None):
    """
    Organizes the backfill for neg_risk.

    Grabs market_id and neg_risk and updates the neg_risk for each market.

    Args:
        conn (psycopg2.Connection): the database connection object
        max_pages (int, optional): the max number of Gamma API pages to process; used only in testing

    Returns:
        None
    """
    # getting market data through Gamma API
    for page in get_neg_risk(max_pages=max_pages):

        # loop through each market of the page
        for market in page:

            # get market data
            market_id  = market[0] # get market id
            neg_risk = market[1] # get negRisk
            market_data = {'market_id': market_id, 'neg_risk': neg_risk}

            # insert market data into market table from polymarket_db
            update_neg_risk(conn, market_data)

def main():

    # initialize conn for final guard
    conn = None
    
    try:
        # get db connection; create new connection every time script is ran
        conn = db.get_connection()
        # run the collect function, log successful to ensure running properly
        neg_risk_backfill(conn)
        logging.info('Backfill completed successfully')

    # log exception
    except Exception:
        logging.exception(f'Backfill script error')
        
    finally:
        # guard in case db.get_connection() fails to create a connection
        # close connection to prevent memory leaks
        if conn is not None:
            conn.close()

# execute main function
if __name__ == '__main__':
    main()
