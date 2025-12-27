import json
import os
import time
import requests
import pandas as pd
from collections import defaultdict

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType, PostOrdersArgs

POLL_INTERVAL = 15
SYNC_EPS = 4.99

HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": os.environ["CTH_KEY"],
}

POSITIONS_URL = "https://data-api.polymarket.com/positions"
COPY_URL = "https://api.copytradehorizon.com/polymarketcopy"

client = ClobClient(
    host=os.environ["HOST"],
    key=os.environ["PRIVATE_KEY"],
    chain_id=int(os.environ["CHAIN_ID"]),
    signature_type=2,
    funder=os.environ["FUNDER"]
)

creds = client.create_or_derive_api_creds()
client.set_api_creds(creds)

OWNER_ADDRESS = os.environ["FUNDER"]

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


def fetch_owner_positions(owner_address: str) -> dict[str, float]:
    try:
        params = {
            "user": owner_address,
            "limit": 1000,
            "sizeThreshold": 1,
            "redeemable": False,
        }
        response = requests.get(POSITIONS_URL, params=params)
        response.raise_for_status()
        positions = response.json()
    except Exception as e:
        return {}

    d = defaultdict(float)
    for p in positions:
        asset = p.get("asset")
        size = p.get("size")
        if asset is None or size is None:
            continue

        s = float(size)
        d[asset] += s

    return dict(d)


def apply_delta(base: dict[str, float], delta: dict[str, float]) -> dict[str, float]:
    out = dict(base)
    for asset, d in delta.items():
        new_val = out.get(asset, 0.0) + d
        if new_val < 0:
            new_val = 0.0
        out[asset] = new_val
    return out


# asset_id -> expected position after our outstanding trades settle
pending_targets: dict[str, float] = {}

# asset_id -> timestamp when we started waiting for this asset to sync
pending_since: dict[str, float] = {}


while True:
    try:
        now_ts = time.time()

        # 1) Always fetch current chain positions
        chain_now = fetch_owner_positions(OWNER_ADDRESS)

        # 2) Update per-asset pending state: mark assets as synced or timed-out
        for asset in list(pending_targets.keys()):
            target_val = pending_targets[asset]
            chain_val = chain_now.get(asset, 0.0)

            if abs(chain_val - target_val) <= SYNC_EPS:
                del pending_targets[asset]
                pending_since.pop(asset, None)

        blocked_assets = set(pending_targets.keys())

        # 3) Ask Lambda what net trades should be
        resp = requests.post(COPY_URL, json=payload, headers=HEADERS)
        resp.raise_for_status()
        records = resp.json()

        if records is None:
            time.sleep(POLL_INTERVAL)
            continue

        df = pd.DataFrame(records)

        if df.empty:
            time.sleep(POLL_INTERVAL)
            continue

        expiration = str(int(time.time()) + 70)

        # 4) Build orders for assets that are *not* currently blocked
        order_args_list = []
        for row in df.itertuples(index=False):
            asset_id = getattr(row, "asset_id")

            if asset_id in blocked_assets:
                continue

            try:
                sz = float(getattr(row, "size"))
                price = float(getattr(row, "target_price"))
            except Exception:
                continue

            if sz <= 0:
                continue

            side = getattr(row, "side")
            if side not in ("BUY", "SELL"):
                continue

            order_args_list.append(
                OrderArgs(
                    token_id=asset_id,
                    side=side,
                    price=price,
                    size=sz,
                    expiration=expiration,
                )
            )

        if not order_args_list:
            time.sleep(POLL_INTERVAL)
            continue

        # 5) Post orders in batches; compute EFFECTIVE deltas for non-blocked assets
        delta_effective = defaultdict(float)

        idx = 0
        while idx < len(order_args_list):
            batch_args = order_args_list[idx:idx + 5]
            idx += 5
            if not batch_args:
                continue

            signed_orders = [client.create_order(o) for o in batch_args]
            post_args = [
                PostOrdersArgs(order=so, orderType=OrderType.GTD)
                for so in signed_orders
            ]

            results = client.post_orders(post_args)
            if isinstance(results, dict):
                results = [results]

            for res_obj, o in zip(results, batch_args):
                success = bool(res_obj.get("success", False))
                if not success:
                    continue

                if o.side == "BUY":
                    delta_effective[o.token_id] += float(o.size)
                else:
                    delta_effective[o.token_id] -= float(o.size)

        if not delta_effective:
            time.sleep(POLL_INTERVAL)
            continue

        # 6) Compute new per-asset targets based on current chain snapshot
        target_full = apply_delta(chain_now, delta_effective)

        for asset, _delta in delta_effective.items():
            pending_targets[asset] = target_full.get(asset, 0.0)
            pending_since[asset] = now_ts

    except Exception as e:
        print("Error in loop:", e)

    time.sleep(POLL_INTERVAL)