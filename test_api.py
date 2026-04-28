# importing libraries
import requests
import json

'''
Gamma API: contains all information regarding market data; markets, events, tags, comments etc. Markets most relevant ->
broken down into what we want like what markets exist, token Ids, dates, liquidity, spread, volume, outcome prices

CLOB (Central Order Book) API: orderbook data; most relevant real-time data via /midpoint endpoint; price history via /prices-history
'''

# Gamma API test
# from documentation: curl "https://gamma-api.polymarket.com/events?limit=5" (ran in terminal)
print("Gamma API Test ")

# call the api with /keyset endpoint since /markets endpoint being deprecated May 2026
# requets.get() opens url and returns json data
r = requests.get(
    "https://gamma-api.polymarket.com/markets/keyset",
    params={"active": "true", "closed": "false", "limit": "5"}
)

# print(r.text) # understand what the raw json file looks like and what can be extracted

# returns dict with 'markets' and 'next_cursor'; only markets list needed
markets = r.json()["markets"] #.json() converts raw data to a dict; access the 'markets' keyword to get cur market

# loop through the markets (total 5 since we limited to 5)
for m in markets:
    # .loads() further parses JSON data; clobTokenIds still a string but looks like list, .loads() converts into list
    token_ids = json.loads(m["clobTokenIds"]) # parse clubTokenIds to a list from a string
    prices = json.loads(m["outcomePrices"])  # parse yes and no price as list
    yes_price, no_price = prices[0], prices[1]

    # testing prints
    print(f"\nMarket:    {m['question']}")
    print(f"YES token: {token_ids[0]}")
    print(f"NO token:  {token_ids[1]}")
    print(f"YES price: {yes_price}\n NO price: {no_price}")
    print(f"YES + NO:  {float(yes_price) + float(no_price):.3f}")

# CLOB API test
print("\nCLOB API test")
# grab YES token from first market; toke_id required param for CLOB /midpoint call
first_token = json.loads(markets[0]["clobTokenIds"])[0]
r2 = requests.get(
    "https://clob.polymarket.com/midpoint",
    params={"token_id": first_token}
)
print(f"CLOB: {r2.json()}")