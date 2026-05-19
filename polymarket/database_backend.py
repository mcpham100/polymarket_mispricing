'''
Backend that connects the PostgreSQL databse to the data collection pipeline.
Creates functions to establish connections and perform psql operations on polymarket_db database.
''' 

# importing libraries
import psycopg2 # adapter to connect python to psql
import sys
from dotenv import load_dotenv
import os
import logging


def get_connection():
    '''
    Makes and returns a connection to the PostgreSQL database.
    
    Loads credentials from a .env file to avoid hardcoding sensitive information.
    If a connection cannot be established, it exits the program
    
    Args:
        None
    
    Returns:
        conn (psycopg2.connection): active database connection object to be 
        passed into insert and query functions
    '''
    # load .env file; accesses secret/information not wanted to be pushed into repo
    load_dotenv()

    # obtain .env info
    host = os.getenv("HOST")
    dbname = os.getenv("DBNAME")
    dbuser = os.getenv("DBUSER")
    password = os.getenv("PASSWORD")
    port = os.getenv("PORT")

	# get a connection, if a connect cannot be made an exception will be raised here
    try:
        conn = psycopg2.connect(
            host=host,
            dbname=dbname,
            user=dbuser, # renamed due to issues with vm
            password=password,
            port=port
        )

    # raise error and exit
    # use except with OperationalError from psycopg2 documentation
    except psycopg2.OperationalError as e:
        logging.error(f'Connection to Postgre failed: {e}')
        sys.exit(1) # exits; prevents further execution

    # return connection to be used in other functions that write into the DB
    return conn


def insert_market(conn, market_data):
    '''
    Inserts a single market record into the markets table.
    
    Silently skips insertion if the market_id already exists, preventing duplicates
    in collection runs.

    Args:
        conn (psycopg2.connection): active database connection from get_connection()
        market_data (dict): market metadata with keys:
            - market_id (str): unique Polymarket market identifier
            - question (str): the market's question text
            - category (str or None): market category, currently None; needs to be backfilled via /tags from Gamma API
            - end_date (str): market resolution date from Polymarket
    '''
    # conn.cursor will return a cursor object, you can use this query to perform queries
    cursor = conn.cursor()

    try:
    # cursor.execute(SQL) allows for SQL queries within Python
    # query to add a row with given attributes
        cursor.execute("""
                    INSERT INTO markets (market_id, question, category, end_date)
                    VALUES (%(market_id)s, %(question)s, %(category)s, %(end_date)s)
                    ON CONFLICT (market_id) DO NOTHING
                    """,
                    {'market_id': market_data["market_id"], 'question': market_data["question"], 
                     'category': market_data["category"], 'end_date': market_data["end_date"]})
        
        # %s serves as placeholders value; pass in a dict as second arg to pass in actual value from python
        
        conn.commit() # no need to check for conflicts as only one write at a time (no concurrency occuring)

    # raise error and exit
    except psycopg2.Error as e:
        logging.error(f'Inserting into market failure: {e}')
        conn.rollback() # rollback changes (does not commit them)

    finally:
        # close to prevent memory leaks (deletes cursor object)
        cursor.close()


def insert_snapshot(conn, snapshot_data):
    '''
    Inserts a single price snapshot into the snapshots table.
    
    Called every collection run (~ every 5 min) for each market.

    Args:
        conn (psycopg2.connection): active database connection from get_connection()
        snapshot_data (dict): snapshot data with keys:
            - market_id (str): foreign key referencing markets table
            - yes_price (float): midpoint price of the YES outcome token from CLOB API
            - no_price (float): midpoint price of the NO outcome token from CLOB API
            - volume (float): total trading volume of the market
            - liquidity (float): current liquidity of the market
            - spread (float): bid-ask spread of the market
    
    Return:
        None
    '''
    # conn.cursor will return a cursor object, you can use this query to perform queries
    cursor = conn.cursor()

    try:
    # cursor.execute(SQL) allows for SQL queries within Python
    # query to add a row with given attributes
        cursor.execute("""
                    INSERT INTO snapshots (market_id, yes_price, no_price, volume, liquidity, spread)
                    VALUES (%(m_id)s, %(yes)s, %(no)s, %(vol)s, %(liq)s, %(spread)s)
                    """,
                    {'m_id': snapshot_data["market_id"], 'yes': snapshot_data["yes_price"], 'no': snapshot_data["no_price"], 
                     'vol': snapshot_data["volume"], 'liq': snapshot_data["liquidity"], 'spread': snapshot_data["spread"]})
        
        # %s serves as placeholders value; pass in a dict as second arg to pass in actual value from python
        
        conn.commit() # no need to check for conflicts as only one write at a time (no concurrency occuring)

    # raise error and rollback
    except psycopg2.Error as e:
        logging.error(f'Inserting into snapshot failure: {e}')
        conn.rollback()

    finally:
        # close to prevent memory leaks (deletes cursor object)
        cursor.close()

def insert_event(conn, event):
    '''
    Inserts an event into the mispricing_events table.

    Args:
        conn (psycopg2.connection): active database connection from get_connection()
        event (Pd.Series): event data for a detected mispricing:
            - market_id (str): foreign key referencing markets table
            - start_time (float): the snapshot time at which the deviation was first detected
            - end_time (float): the last snapshot of the event with a deviation
            - peak_deviation (float): max deviation throughout the event
            - initial_deviation (float): deviation first captured in the initial snapshot detecting the mispricing
            - duration (float): how long the mispricing event lasted; end_time - smart_time
    
    Return:
        None
    '''
    # create connection
    cursor = conn.cursor()

    try:
    # cursor.execute(SQL) allows for SQL queries within Python
    # query to add a row with given attributes
        cursor.execute("""
                    INSERT INTO mispricing_events (market_id, start_time, end_time, peak_deviation, 
                       initial_deviation, duration)
                    VALUES (%(m_id)s, %(start)s, %(end)s, %(peak)s, %(init)s, %(duration)s)
                    """,
                    {'m_id': event["market_id"], 'start': event["start_time"], 'end': event["end_time"], 
                     'peak': event["peak_deviation"], 'init': event["initial_deviation"], 'duration': event["duration"]})
        
        # %s serves as placeholders value; pass in a dict as second arg to pass in actual value from python
        
        conn.commit() # no need to check for conflicts as only one write at a time (no concurrency occuring)

    # raise error and rollback
    except psycopg2.Error as e:
        logging.error(f'Inserting into mispricing_events failure: {e}')
        conn.rollback()

    finally:
        # close to prevent memory leaks (deletes cursor object)
        cursor.close()