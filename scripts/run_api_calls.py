
'''
script to run the data pipeline
'''

import pandas as pd
import numpy as np
import json
import logging
from polymarket import api_calls
from polymarket import database_backend
# log to catch any errors when running script
logging.basicConfig(filename='collector.log', format= '%(asctime)s %(levelname)s %(message)s', level=logging.INFO)