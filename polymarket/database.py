
'''
essentially the backend connecting the db to the collection scripts
connecting a PostgreSQL database in Python

REMINDER TO PUT .ENV IN .GITIGNORE TO NOT PUSH PASSWORDS INTO REPO

''' 
# importing libraries
import psycopg2
import sys
from dotenv import load_dotenv
import os

def get_connection():
    # load .env file; accesses secret/information not wanted to be pushed into repo
    load_dotenv()

    # obtain .env info
    host = os.getenv("HOST")
    dbname = os.getenv("DBNAME")
    user = os.getenv("USER")
    password = os.getenv("PASSWORD")
    port = os.getenv("PORT")

	# get a connection, if a connect cannot be made an exception will be raised here
    try:
        conn = psycopg2.connect(
            host=host,
            dbname=dbname,
            user=user,
            password=password,
            port=port
        )

    # raise error and exit
    except psycopg2.OperationalError as e:
        print(f'Connection failed: {e}')
        sys.exit(1) # exits; prevents further execution

    return conn

def insert_market(conn, market_data):
    # conn.cursor will return a cursor object, you can use this query to perform queries
    cursor = conn.cursor()

    try:
    # cursor.execute(SQL) allows for SQL queries within Python
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
        print(f"Insert market failed: {e}")
        conn.rollback()
        sys.exit(1)

    finally:
        # close to prevent memory leaks (deletes cursor object)
        cursor.close()

def insert_snapshot(conn, snapshot_data):
    # conn.cursor will return a cursor object, you can use this query to perform queries
    cursor = conn.cursor()

    try:
    # cursor.execute(SQL) allows for SQL queries within Python
        cursor.execute("""
                    INSERT INTO snapshots (market_id, yes_price, no_price, volume, liquidity, spread)
                    VALUES (%(m_id)s, %(yes)s, %(no)s, %(vol)s, %(liq)s, %(spread)s)
                    """,
                    {'m_id': snapshot_data["market_id"], 'yes': snapshot_data["yes_price"], 'no': snapshot_data["no_price"], 
                     'vol': snapshot_data["volume"], 'liq': snapshot_data["liquidity"], 'spread': snapshot_data["spread"]})
        
        # %s serves as placeholders value; pass in a dict as second arg to pass in actual value from python
        
        conn.commit() # no need to check for conflicts as only one write at a time (no concurrency occuring)

    # raise error and exit
    except psycopg2.Error as e:
        print(f"Insert market failed: {e}")
        conn.rollback()
        sys.exit(1)

    finally:
        # close to prevent memory leaks (deletes cursor object)
        cursor.close()

def get_recent_snapshots(conn, market_id):

    cursor = conn.cursor()

    try:
        cursor.execute("""
                       SELECT * 
                       FROM snapshots 
                       WHERE market_id = %s 
                       ORDER BY timestamp DESC
                       LIMIT 100
                        """,
                        (market_id, )) # pass as a tuple
        
        return cursor.fetchall()
    
    except psycopg2.Error as e:
        print(f"Insert market failed: {e}")
        conn.rollback()
        sys.exit(1)

    finally:
        cursor.close()

# testing

# conn1 = get_connection()
# get_recent_snapshots(conn1, 'test123')
# print('success')