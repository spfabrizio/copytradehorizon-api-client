import json
import os
import time
import requests
import pandas as pd
from collections import defaultdict

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType, PostOrdersArgs, OpenOrderParams

POLL_INTERVAL = 10
SYNC_EPS = 4.99

STATE_FILE = os.environ.get("STATE_FILE", "defer_state.json")

state_dir = os.path.dirname(STATE_FILE)
if state_dir:
    os.makedirs(state_dir, exist_ok=True)

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
    funder=os.environ["FUNDER"],
)

client.set_api_creds(client.create_or_derive_api_creds())

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
        "mode": "LIMIT_THEN_MARKET",
        "limit_offset_price": 0.01,
        "limit_window_hours": 24.0, 
    },
}


def load_state() -> dict:
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state: dict) -> None:
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, STATE_FILE)


def fetch_owner_positions(owner_address: str) -> dict[str, float]:
    try:
        params = {
            "user": owner_address,
            "limit": 1000,
            "sizeThreshold": 1,
            "redeemable": False,
        }
        r = requests.get(POSITIONS_URL, params=params, timeout=15)
        r.raise_for_status()
        positions = r.json()
    except Exception:
        return {}

    d = defaultdict(float)
    for p in positions:
        asset = p.get("asset")
        size = p.get("size")
        if asset is None or size is None:
            continue
        try:
            d[str(asset)] += float(size)
        except Exception:
            continue
    return dict(d)


def apply_delta(base: dict[str, float], delta: dict[str, float]) -> dict[str, float]:
    out = dict(base)
    for asset, d in delta.items():
        new_val = out.get(asset, 0.0) + d
        if new_val < 0:
            new_val = 0.0
        out[asset] = new_val
    return out


def extract_order_id(res_obj: dict) -> str | None:
    for k in ("orderId", "orderID", "id", "order_id"):
        v = res_obj.get(k)
        if isinstance(v, str) and v:
            return v
    return None


def safe_cancel_one(order_id: str) -> None:
    if not order_id:
        return
    try:
        client.cancel(order_id=order_id)
    except Exception:
        pass


def safe_cancel_many(order_ids: list[str]) -> None:
    ids = [oid for oid in order_ids if oid]
    if not ids:
        return
    try:
        client.cancel_orders(ids)
    except Exception:
        for oid in ids:
            safe_cancel_one(oid)


def get_order(order_id: str) -> dict:
    try:
        resp = client.get_order(order_id)
        if isinstance(resp, dict) and "order" in resp:
            return resp["order"] or {}
        if isinstance(resp, dict):
            return resp
    except Exception:
        return {}
    return {}


def get_open_orders_for_asset(asset_id: str) -> list[dict]:
    try:
        resp = client.get_orders(OpenOrderParams(asset_id=asset_id))
        if isinstance(resp, list):
            return resp
        if isinstance(resp, dict):
            for k in ("orders", "data", "result"):
                v = resp.get(k)
                if isinstance(v, list):
                    return v
    except Exception:
        return []
    return []


def order_status(order: dict) -> str:
    return str(order.get("status", "") or "").lower()


def order_price(order: dict) -> float:
    try:
        return float(order.get("price", 0) or 0)
    except Exception:
        return 0.0


def order_filled(order: dict) -> float:
    try:
        return float(order.get("size_matched", "0") or 0)
    except Exception:
        return 0.0


def order_original_size(order: dict) -> float:
    for k in ("original_size", "size"):
        try:
            v = order.get(k)
            if v is None:
                continue
            return float(v)
        except Exception:
            continue
    return 0.0


def order_remaining_size(order: dict) -> float:
    return max(0.0, order_original_size(order) - order_filled(order))


def progress_from_positions(chain_pos: float, base_pos: float, side: str) -> float:
    side_u = str(side).upper()
    if side_u == "BUY":
        return max(0.0, float(chain_pos) - float(base_pos))
    else:
        # SELL: progress is how much position decreased
        return max(0.0, float(base_pos) - float(chain_pos))


def signed_delta(side: str, size: float) -> float:
    return float(size) if str(side).upper() == "BUY" else -float(size)


def place_limit_gtc_postonly(asset_id: str, side: str, price: float, size: float) -> str | None:
    if size <= 0:
        return None
    oargs = OrderArgs(
        token_id=str(asset_id),
        side=str(side).upper(),
        price=float(price),
        size=float(size),
    )
    signed = client.create_order(oargs)
    res = client.post_orders([
        PostOrdersArgs(
            order=signed,
            orderType=OrderType.GTC,
            postOnly=True,
        )
    ])
    if isinstance(res, dict):
        res = [res]
    if not res or not bool(res[0].get("success", False)):
        return None
    return extract_order_id(res[0])



defer_state = load_state()

import signal, sys, atexit

def _shutdown_handler(signum, frame):
    try:
        save_state(defer_state)
    except Exception:
        pass
    sys.exit(0)

signal.signal(signal.SIGTERM, _shutdown_handler)
signal.signal(signal.SIGINT, _shutdown_handler)

@atexit.register
def _atexit_save():
    try:
        save_state(defer_state)
    except Exception:
        pass

save_state(defer_state)

pending_targets: dict[str, float] = {}
pending_since: dict[str, float] = {}

LIMIT_REPRICE_THRESHOLD = 0.0099   # 1 cent
SIZE_EPS = 0.50                  # rounding tolerance for share sizes


while True:
    try:
        now_ts = time.time()

        chain_now = fetch_owner_positions(OWNER_ADDRESS)

        for asset in list(pending_targets.keys()):
            target_val = pending_targets[asset]
            chain_val = chain_now.get(asset, 0.0)
            if abs(chain_val - target_val) <= SYNC_EPS:
                del pending_targets[asset]
                pending_since.pop(asset, None)

        blocked_assets = set(pending_targets.keys())

        resp = requests.post(COPY_URL, json=payload, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        records = resp.json()

        df = pd.DataFrame(records or [])
        if df.empty:
            save_state(defer_state)
            time.sleep(POLL_INTERVAL)
            continue

        # Normalize
        df["asset_id"] = df["asset_id"].astype(str)
        df["side"] = df["side"].astype(str).str.upper()
        df["execution_style"] = df.get("execution_style", "MARKET").astype(str).str.upper()

        desired_assets = set(df["asset_id"].tolist())

        for asset_id in list(defer_state.keys()):
            if asset_id not in desired_assets:
                # cancel any open orders for this asset (robust to restarts)
                open_orders = get_open_orders_for_asset(asset_id)
                safe_cancel_many([o.get("id") for o in open_orders if isinstance(o.get("id"), str)])
                defer_state.pop(asset_id, None)

        for row in df.itertuples(index=False):
            asset_id = getattr(row, "asset_id")
            if getattr(row, "execution_style", "MARKET") != "LIMIT":
                continue

            if asset_id in blocked_assets:
                continue

            side = str(getattr(row, "side")).upper()
            desired_size = float(getattr(row, "size"))
            limit_price = float(getattr(row, "limit_price"))
            cutoff_ts = int(getattr(row, "cutoff_ts") or 0)

            if cutoff_ts and now_ts >= cutoff_ts:
                continue

            chain_pos = float(chain_now.get(asset_id, 0.0))

            st = defer_state.get(asset_id)
            intent_changed = (
                (st is None)
                or (str(st.get("side", "")).upper() != side)
                or (abs(float(st.get("desired_size", -1.0)) - desired_size) >= SIZE_EPS)
                or (int(st.get("cutoff_ts", 0) or 0) != cutoff_ts)
            )

            if intent_changed:
                # Reset to a fresh intent anchored to CURRENT chain positions
                open_orders = get_open_orders_for_asset(asset_id)
                safe_cancel_many([o.get("id") for o in open_orders if isinstance(o.get("id"), str)])
                st = {
                    "order_id": None,
                    "side": side,
                    "desired_size": desired_size,
                    "base_pos": chain_pos,
                    "last_limit_price": -1.0,
                    "cutoff_ts": cutoff_ts,
                }

            base_pos = float(st.get("base_pos", chain_pos))
            prog = progress_from_positions(chain_pos, base_pos, side)
            desired_remaining = max(0.0, desired_size - prog)

            if desired_remaining <= 0:
                # We already reached/exceeded the intent using ACTUAL positions; cancel any resting orders.
                open_orders = get_open_orders_for_asset(asset_id)
                safe_cancel_many([o.get("id") for o in open_orders if isinstance(o.get("id"), str)])
                defer_state.pop(asset_id, None)
                continue

            open_orders = get_open_orders_for_asset(asset_id)
            wrong_side_ids = [
                o.get("id") for o in open_orders
                if isinstance(o.get("id"), str) and str(o.get("side", "")).upper() != side
            ]
            safe_cancel_many(wrong_side_ids)

            open_orders = get_open_orders_for_asset(asset_id)
            open_orders = [
                o for o in open_orders
                if isinstance(o.get("id"), str) and str(o.get("side", "")).upper() == side
            ]

            keep_order = None
            if open_orders:
                def _created_at(o: dict) -> int:
                    try:
                        return int(float(o.get("created_at", 0) or 0))
                    except Exception:
                        return 0
                open_orders_sorted = sorted(open_orders, key=_created_at, reverse=True)
                keep_order = open_orders_sorted[0]
                extras = open_orders_sorted[1:]
                safe_cancel_many([e.get("id") for e in extras if isinstance(e.get("id"), str)])

            order_id = keep_order.get("id") if (keep_order and isinstance(keep_order.get("id"), str)) else None
            current_order = {}
            if order_id:
                current_order = get_order(order_id) or keep_order
                stat = order_status(current_order)
                if stat and stat not in ("live", "open", "pending", "delayed", "unmatched"):
                    order_id = None
                    current_order = {}

            open_remaining = order_remaining_size(current_order) if current_order else 0.0
            existing_px = order_price(current_order) if current_order else -1.0

            size_mismatch = (order_id is None) or (abs(open_remaining - desired_remaining) >= SIZE_EPS)
            price_mismatch = (order_id is None) or (existing_px < 0) or (abs(limit_price - existing_px) >= LIMIT_REPRICE_THRESHOLD)

            if size_mismatch or price_mismatch:
                if order_id:
                    safe_cancel_one(order_id)
                new_id = place_limit_gtc_postonly(
                    asset_id=asset_id,
                    side=side,
                    price=limit_price,
                    size=desired_remaining,
                )
                st["order_id"] = new_id
                st["last_limit_price"] = limit_price
            else:
                st["order_id"] = order_id
                st["last_limit_price"] = existing_px

            defer_state[asset_id] = st

        market_batch: list[OrderArgs] = []
        delta_effective = defaultdict(float)

        expiration_market = int(time.time()) + 70

        for row in df.itertuples(index=False):
            asset_id = getattr(row, "asset_id")
            if getattr(row, "execution_style", "MARKET") != "MARKET":
                continue

            if asset_id in blocked_assets:
                continue

            side = str(getattr(row, "side")).upper()
            desired_size = float(getattr(row, "size"))
            target_price = float(getattr(row, "target_price"))

            chain_pos = float(chain_now.get(asset_id, 0.0))

            # Cancel ALL open orders for this asset (covers missing state / restarts)
            open_orders = get_open_orders_for_asset(asset_id)
            safe_cancel_many([o.get("id") for o in open_orders if isinstance(o.get("id"), str)])

            # If we are transitioning from LIMIT -> MARKET for the same intent, use stored base_pos.
            st = defer_state.get(asset_id)
            use_state_intent = (
                st is not None
                and str(st.get("side", "")).upper() == side
                and abs(float(st.get("desired_size", -1.0)) - desired_size) < SIZE_EPS
            )
            base_pos = float(st.get("base_pos", chain_pos)) if use_state_intent else chain_pos

            prog = progress_from_positions(chain_pos, base_pos, side)
            remaining = max(0.0, desired_size - prog)

            defer_state.pop(asset_id, None)

            if remaining <= 0:
                continue

            market_batch.append(
                OrderArgs(
                    token_id=asset_id,
                    side=side,
                    price=target_price,
                    size=remaining,
                    expiration=str(expiration_market),
                )
            )

        idx = 0
        while idx < len(market_batch):
            batch = market_batch[idx:idx + 5]
            idx += 5
            if not batch:
                continue

            signed_orders = [client.create_order(o) for o in batch]
            post_args = [PostOrdersArgs(order=so, orderType=OrderType.GTD) for so in signed_orders]

            results = client.post_orders(post_args)
            if isinstance(results, dict):
                results = [results]

            for res_obj, o in zip(results, batch):
                if not bool(res_obj.get("success", False)):
                    continue
                delta_effective[o.token_id] += signed_delta(o.side, float(o.size))

        if delta_effective:
            target_full = apply_delta(chain_now, delta_effective)
            for asset in delta_effective.keys():
                pending_targets[asset] = target_full.get(asset, 0.0)
                pending_since[asset] = now_ts

        save_state(defer_state)

    except Exception as e:
        print("Error in loop:", e)

    time.sleep(POLL_INTERVAL)