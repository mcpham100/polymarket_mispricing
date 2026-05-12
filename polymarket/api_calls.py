
'''
API calls to Polymarket's Gamma API and CLOB API

Gamma API: contains all information about market data (markets, events, tags, comments, etc). We break down most relevant
markets into what we want (ex: what markets exist, token ids, dates, liquidity, spread, volume, outcome prices)

CLOB (Central Order Book) API: orderbook data; most relevant real-time data from /midpoint endpoint; price history from /prices-history

Builds the logic to store the API calls into the database.
'''

# importing libraries
import requests
import json
import logging
import time

# import database_backend
from polymarket import database_backend as db

# log to catch any errors when running script
logging.basicConfig(filename='collector.log', format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)


# max_pages paramater used in testing; not actually used in deployment
def gamma_markets(max_pages=None):
    """
    A generator that grabs active market metadata from Polymarket Gamma API.

    Numbers pages through the /markets/keyset endpoint to get info 
    like questions, token ids, and current volume or liquidity.

    Args:
        max_pages (int, optional): the max number of pages to retrieve.
            used to limit data during testing. Defaults to None (all pages)

    Yields:
        list[tuple]: a list of tuples with market data:
            (market_id, question, category, liquidity, volume, spread, end_date, tokens)
    """
    # define next_cursor (part of Gamma API to be used to load next page)
    next_cursor = None
    page_count = 0

    # loop through all pages 
    while True:
        # buld market_data
        market_data = list()

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
                    # buld market_data; default values for floats if not found
                    # keep market_id, question, and tokens indexing so it can trigger the except error
                    market_id = m['id']
                    question = m['question']
                    category = None
                    liquidity = m.get('liquidity', 0.0)
                    volume = m.get('volume', 0.0)
                    spread = m.get('spread', 0.0)
                    end_date = m.get('endDate', None)
                    tokens = json.loads(m['clobTokenIds']) # convert tokens to list

                    market_data.append((market_id, question, category, liquidity, volume, spread, end_date, tokens))
                
                # error if data not found or can't be decoded (improper JSON format) or found, log error
                except (KeyError, TypeError, json.JSONDecodeError) as e:
                    logging.error(f'Error appending market: {e}')

            # create generator; returns market_data then re-runs
            yield market_data # returns a list of tuples [(market1), (market2)]

            page_count += 1
            if max_pages is not None and page_count >= max_pages:
                break

            # break out of loop once it reaches the last page
            if not next_cursor:
                break
        
        # error if API call fails, log error
        except requests.exceptions.RequestException as e:
            logging.error(f'Gamma API request failed: {e}')
            break
        
    

def clob_midpoints(tokens):
    """
    Gets real-time midpoint prices for a list of token ids from CLOB API.

    The function flattens the input tokens and processes them in groups of 50 
    to follow API's payload limits.

    Args:
        tokens (list[list[str]]): a nested list of token ids

    Returns:
        dict: a dictionary mapping token_id strings to their float midpoint prices.
            returns an empty dictionary if request fails
    """
    # flatten tokens into a string to be passed as a param of a single string in CLOB api call
    tokens_str = [token for pair in tokens for token in pair]
    token_chunk = [tokens_str[i : i+ 50] for i in range(0, len(tokens_str), 50)] # split into chunks to prevent too large of a call
    token_prices = dict()

    try:
        # call CLOB api
        for chunks in token_chunk:
            response = requests.post(
                    "https://clob.polymarket.com/midpoints",
                    json=[{"token_id": token} for token in chunks], # token_id takes in a list of strings
                    timeout=10) # add a timeout to prevent connections waiting indefinitely
            
            # check for response issues
            response.raise_for_status()

            # merging dictionary with recent calls
            token_prices |= response.json()
            time.sleep(0.5) # prevent connection resets
            
        return token_prices # return dict of {token_id:token_price} if no exceptions

    # raise error if CLOB api call fails, log error
    except requests.exceptions.RequestException as e:
        return dict()
    
# max_pages paramater used in testing; not actually used in deployment
def collect(conn, max_pages=None):
    """
    Organizes the full data collection process for both Gamma and CLOB APIs.

    Grabs market metadata, updates the market registry in the 
    database, retrieves real-time pricing, and saves a point-in-time snapshot 
    of market liquidity and volume.

    Args:
        conn (sqlite3.Connection): the database connection object
        max_pages (int, optional): the max number of Gamma API pages to process

    Returns:
        None
    """
    # getting market data through Gamma API
    for page in gamma_markets(max_pages=max_pages):

        tokens = [] # list of tokens for each page
        # loop through each market of the page
        for market in page:

            # get market data
            market_id  = market[0] # get market id
            q = market[1] # get question
            cat = market[2] # get category
            end = market[6] # get end date
            market_data = {'market_id': market_id, 'question': q, 'category': cat, 'end_date': end}

            # insert market data into market table from polymarket_db
            db.insert_market(conn, market_data)

            # build list of tokens for the entire page
            tokens.append(market[7])

        token_prices = clob_midpoints(tokens) # batch of yes, no prices for each page

        for market in page:
            try:
                yes_price = float(token_prices.get(market[7][0])) # look up from CLOB using yes_token id
                no_price = float(token_prices.get(market[7][1]))
            except TypeError as e:
                logging.error(f'Casting prices error after CLOB api call: {e}')
                continue
            
            # creating snapshot data
            market_id  = market[0]
            liquidity = market[3]
            volume = market[4]
            spread = market[5]
            snapshot_data = {'market_id': market_id, 'yes_price': yes_price, 'no_price': no_price, 
                             'liquidity': liquidity, 'volume': volume, 'spread': spread}

            db.insert_snapshot(conn, snapshot_data)
