import json
import os
import time
import requests
import pandas as pd
from collections import defaultdict

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType, PostOrdersArgs

HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": os.environ["CTH_KEY"],
}

OWNER_ADDRESS = os.environ["FUNDER"]
COPY_URL = "https://api.copytradehorizon.com/polymarketcopy"

payload = {
    "owner": {
        "address": OWNER_ADDRESS,
        "is_autoredeem_enabled": False,
    },
    "price_configuration": {
        "spread": 0.05,
        "buffer": 0.05,
        "limits": {
            "buy":  {"min": 0.01, "max": 0.98},
            "sell": {"min": 0.01, "max": 0.98},
        },
    },
    "traders": [
        {
            "address": "0x7c3db723f1d4d8cb9c550095203b686cb11e5c6b", # @Car
            "factor": 0.01,
            "excluded_tags": [],
            "min_share": 1,
            "max_share": 250,
        },
        {
            "address": "0xee00ba338c59557141789b127927a55f5cc5cea1", # @S-Works
            "factor": 0.001,
            "excluded_tags": [],
            "min_share": 1,
            "max_share": 500,
        }
    ],
    "excluded_markets": [],
    "is_aggregated": True,
    "defer_execution": {
        "enabled": True,
        "hours_before_start": 5.0,
    },
}

response = requests.post(COPY_URL, json=payload, headers=HEADERS)
records = response.json()
print(response.status_code)
df = pd.DataFrame(records)
if not df.empty:
    df = df.sort_values(by="size", ascending=False).reset_index(drop=True)
    print(df)