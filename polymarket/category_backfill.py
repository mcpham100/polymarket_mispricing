'''
One-time ran script to backfill category into the markets table
Category comes from a different endpoint: /events{id}
{id}: comes from Gamma /markets endpoint; can be acquired via {market}[0]['events']['id]
Category used in sub-category analysis
No acquiring sub category due to limited dataset size (only 328 mispricing events)
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
logging.basicConfig(filename='catBackfill.log', format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

def get_category(mispricing_ids, max_pages=None):
    """
    A generator that grabs category from each market from Polymarket Gamma API (/events{id} endpoint).
    Pages through the /markets/keyset endpoint to get info.

    Args:
        mispricing_ids (set): set of all market_ids in mispricing_events; markets that need to be backfilled
        max_pages (int, optional): the max number of pages to retrieve.
            used to limit data during testing. Defaults to None (all pages)

    Yields:
        list[tuple]: a list of tuples with market_id and category
            (market_id, category)
    """
    # define next_cursor (part of Gamma API to be used to load next page)
    next_cursor = None
    page_count = 0

    # loop through all pages 
    while True:
        # build market_category
        market_category = list()

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
                    # filter to check if it's one of the markets that needs to be backfilled
                    if m['id'] in mispricing_ids:

                        # acquire event_id for that market
                        event_id = m['events'][0]['id']

                        # gamma api to /events/{event_id} endpoint to acquire category
                        event = requests.get(f"https://gamma-api.polymarket.com/events/{event_id}",
                            timeout=10, # add a timeout to prevent connections waiting indefinitely
                            )
                        
                        # time delay to prevent rate limits
                        time.sleep(0.5)

                        # acquire and append market_id and category
                        market_id = m['id']
                        category = event.json()['tags'][0]['label']

                        market_category.append((market_id, category))
                
                # error if data not found or can't be decoded (improper JSON format) or found, log error
                except (KeyError, TypeError, IndexError, json.JSONDecodeError) as e:
                    logging.error(f'Error appending category: {e}')

            # create generator; returns market_category then re-runs
            yield market_category # returns a list of tuples [(market1), (market2)]

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
            logging.error(f'Gamma API to backfill category failed: {e}')
            break

def update_category(conn, category_data):
    '''
    Update a market record in markets table to fill in the proper category

    Args:
        conn (psycopg2.connection): active database connection from get_connection()
        category_data (dict): market metadata with keys:
            - market_id (str): unique Polymarket market identifier
            - category (str): category of the market listed on Polymarket (ex: Politics, Sports, Culture, etc.)
    
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
                    SET category = %(category)s
                    WHERE market_id = %(market_id)s
                    """,
                    ({'category': category_data['category'], 'market_id': category_data['market_id']}),
                    )
        
        # %s serves as placeholders value; pass in a dict as second arg to pass in actual value from python
        
        conn.commit() # no need to check for conflicts as only one write at a time (no concurrency occuring)

    # raise error and exit
    except psycopg2.Error as e:
        logging.error(f'Updating category failure: {e}')
        conn.rollback() # rollback changes (does not commit them)

    finally:
        # close to prevent memory leaks (deletes cursor object)
        cursor.close()
    return

# max_pages paramater used in testing; not actually used in deployment
def category_backfill(conn, mispricing_ids, max_pages=None):
    """
    Organizes the backfill for category.

    Grabs market_id and category and updates the category for each market.

    Args:
        conn (psycopg2.Connection): the database connection object
        mispricing_ids (set): set of all market_ids in mispricing_events; markets that need to be backfilled
        max_pages (int, optional): the max number of Gamma API pages to process; used only in testing

    Returns:
        None
    """
    # getting market data through Gamma API
    for page in get_category(mispricing_ids, max_pages=max_pages):

        # loop through each market of the page
        for market in page:

            # get market data
            market_id  = market[0] # get market id
            category = market[1] # get category
            market_data = {'market_id': market_id, 'category': category}

            # insert market data into market table from polymarket_db
            update_category(conn, market_data)

def main():

    # initialize conn for final guard
    conn = None
    
    try:
        # get db connection; create new connection every time script is ran
        conn = db.get_connection()

        # create cursor; execute query to only get unique market_id from mispricing events
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT market_id FROM mispricing_events;"
        )

        mispricing_ids = cursor.fetchall() # fetchall() returns list of tuples; tuple for each row of query result
        cursor.close() # close the cursor; new one will be opened later

        # flatten mispricing_ids as a set due to output structure of fetchall()
        mispricing_ids = {row[0] for row in mispricing_ids}

        # run the category backfill, log successful to ensure running properly
        category_backfill(conn, mispricing_ids)
        logging.info('Backfill category completed successfully')

    # log exception
    except Exception:
        logging.exception(f'Backfill category script error')
        
    finally:
        # guard in case db.get_connection() fails to create a connection
        # close connection to prevent memory leaks
        if conn is not None:
            conn.close()

# execute main function
if __name__ == '__main__':
    main()
