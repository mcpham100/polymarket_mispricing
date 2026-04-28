CREATE TABLE IF NOT EXISTS markets( --IF NOT EXISTS allows for running file multiple times without issues
    market_id TEXT PRIMARY KEY, --API treats market_id as a string despite storing only ints
    question VARCHAR,
    category VARCHAR,
    end_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP 
);

CREATE TABLE IF NOT EXISTS snapshots(
    id SERIAL PRIMARY KEY, --serial datatype increments each row
    market_id TEXT REFERENCES markets(market_id), --foreign key attribute(s) that link two tables
    yes_price FLOAT,
    no_price FLOAT,
    volume FLOAT,
    liquidity FLOAT,
    spread FLOAT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP --default now; no need to pass param everytime
);

CREATE TABLE IF NOT EXISTS mispricing_events(
    event_id SERIAL PRIMARY KEY,
    market_id TEXT REFERENCES markets(market_id),
    snapshot_id INTEGER REFERENCES snapshots(id),
    start_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, --
    deviation FLOAT
    --consider end_time in the future; end_time will come from API call not DEFAULT
);

-- to run: psql -U postgres -d polymarket_db -f data/schema.sql
--Open postgresql, login as postgres, connect to polymarket_db, runs this file