
'''
API calls to Polymarket's Gamma API and CLOB API

Gamma API: contains all information regarding market data; markets, events, tags, comments etc. Markets most relevant ->
broken down into what we want like what markets exist, token Ids, dates, liquidity, spread, volume, outcome prices

CLOB (Central Order Book) API: orderbook data; most relevant real-time data via /midpoint endpoint; price history via /prices-history

Builds the logic to also store the API calls into the database.
'''

# importing libraries
import requests
import json
import logging
import database_backend as db

# log to catch any errors when running script
logging.basicConfig(filename='collector.log', format= '%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

def gamma_markets():
    
    # define next_cursor (part of Gamma API to be used to load next page)
    next_cursor = None

    # loop through all pages 
    while True:
        # buld market_data
        market_data = list()

        # additional parameters per Polymarket's API documentation
        params={"active": "true", "closed": "false", "limit": "100"}
        
        # updates params if it's not the first call
        if next_cursor is not None:
            params['after_cursor'] = next_cursor

        try:
            # call gamma api with necessary parameters
            response = requests.get("https://gamma-api.polymarket.com/markets/keyset",
            params = params
            )

            response.raise_for_status() # error if 4xx or 5xx from response status code (ex: 404 or 429 rate limit)

            # break down response into markets and next_cursor components
            response_json = response.json()
            markets = response_json['markets']
            next_cursor = response_json['next_cursor']

            # loop through the markets of the page
            for m in markets:
                try:
                    # buld market_data
                    market_id = m['id']
                    question = m['question']
                    category = None
                    liquidity = m['liquidity']
                    volume = m['volume']
                    spread = m['spread']
                    end_date = m['endDate']
                    tokens = json.loads(m['clobTokenIds'])
                    market_data.append((market_id, question, category, liquidity, volume, spread, end_date, tokens)) # tokens is a tuple
                
                # error if data not found or can't be decoded (not proper JSON format) or found, log error
                except (KeyError, TypeError, json.JSONDecodeError) as e:
                    logging.error(f'Error appending market: {e}')

            # create generator; returns market_data then re-runs
            yield market_data # dict of {attribute:value}

            # break out of loop once reaching the last page
            if not next_cursor:
                break
        
        # error if API call fails, log error
        except requests.exceptions.RequestException as e:
            logging.error(f'Gamma API request failed: {e}')
            break
        
    

def clob_midpoints(tokens):
 
    # flatten tokens into a string to be passed as a param of a single string in CLOB api call
    tokens_str = [token for pair in tokens for token in pair]

    try:
        # call CLOB api
        response = requests.post(
                "https://clob.polymarket.com/midpoints",
                json=[{"token_id": token} for token in tokens_str]) # token_ids takes in a list of strings
        
        response.raise_for_status()
        return response.json() # return dict of {token_id:token_price} if no exceptions

    # raise error if CLOB api call fails, log error
    except requests.exceptions.RequestException as e:
        logging.error(f'CLOB API request failed: {e}')
        return dict()
    

def collect():

    # get db connection
    conn = db.get_connection()

    # call Gamma API to get market data
    for page in gamma_markets():

        tokens = [] # batch of tokens for each page
        # loop through each market of the page
        for market in page:

            # build market_data
            market_id  = market[0] # get market_id
            q = market[1] # get question
            cat = market[2] # get category
            end = market[6] # get end_date
            market_data = {'market_id': market_id, 'question': q, 'category': cat, 'end_date': end}

            # insert market data into the market table from the polymarket_db
            db.insert_market(conn, market_data)

            # build list of tokens for the entire page
            tokens.append(market[7])

        token_prices = clob_midpoints(tokens) # batch of yes, no prices for each page

        for market in page:
            yes_price = token_prices.get(market[7][0]) # look up from CLOB using yes_token id
            no_price = token_prices.get(market[7][1])
            
            # build snapshot data
            market_id  = market[0]
            liquidity = market[3]
            volume = market[4]
            spread = market[5]
            snapshot_data = {'market_id': market_id, 'yes_price': yes_price, 'no_price': no_price, 
                             'liquidity': liquidity, 'volume': volume, 'spread': spread}

            db.insert_snapshot(conn, snapshot_data)

    # close connection to prevent data leaks
    conn.close()