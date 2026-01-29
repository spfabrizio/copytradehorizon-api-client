# CopyTradeHorizon API

Send a request to compare positions between your wallet address and the addresses of up to 5 traders you want to follow, and the API returns buy/sell instructions (asset id, size, side, limit price). You control risk with copy factors, min/max share size, event timing filters, and spread and price limits, to build an automated copy-trading bot for prediction markets.

* **Base URL:** `https://api.copytradehorizon.com`
* **Auth:** `X-API-Key` header
* **Docs:** OpenAPI spec in [`openapi/openapi.yaml`](openapi/openapi.yaml). Schemas in [`schemas/`](schemas/).
* **Examples:** Copytrading bot and sample request python code in [`client_example/`](client_example/).

## Table of Contents

* Authentication
* Quickstart
* Request Field Explanation
* Response Field Explanation
* Schemas
* OpenAPI
* Error Handling
* Rate Limits
* Security Notes
* Client Bot Tutorial
* License
* Legal / Compliance Notice

## Authentication

All requests require:

* Header: `X-API-Key: <your key>`
* Content-Type: `application/json`

## Quickstart

### 1) Get an API key

API access is issued manually for now. Email me to request an API key to receive pricing if required and include:

* Your name and what you're building/testing
* Expected usage
* Any timeline / deadline

After approval, you’ll receive:

* An API key to send as `X-API-Key`
* Your rate limit tier (if applicable)
* Any additional onboarding notes

**Contact:** `spfabrizio11@gmail.com`

### 2) Make your first request

**cURL**

```bash
curl -X POST "https://api.copytradehorizon.com/polymarketcopy" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{
    "owner": { "address": "0x...", "is_autoredeem_enabled": false },
    "price_configuration": {
      "spread": 0.03,
      "buffer": 0.03,
      "limits": { "buy": {"min": 0.01, "max": 0.98}, "sell": {"min": 0.01, "max": 0.98} }
    },
    "traders": [
      { "address": "0x...", "factor": 0.01, "excluded_tags": [], "min_share": 1, "max_share": 250 }
    ],
    "excluded_markets": [],
    "is_aggregated": true,
    "defer_execution": { "enabled": true, "hours_before_start": 5.0, "mode": "LIMIT_THEN_MARKET", "limit_offset_price": 0.01, "limit_window_hours": 120.0 }
  }'
```

**Example response**

```json
[
  { "asset_id": "123...", "event_id": "123456", "size": 5, "side": "BUY", "price": 0.49, "target_price": 0.46, "execution_style": "MARKET", "limit_price": 0.48, "limit_start_ts": 1769284800, "cutoff_ts": 1769716440, "event_time_ts": 1769716800 }
]
```

Owner and trader addresses are public EVM wallet addresses used on Polymarket: the owner address is the funded wallet that executes the copy trades, and the trader addresses are the wallets of the Polymarket accounts you want to mirror.

## Request Field Explanation

### `owner` (object)

**Who is placing the trades.** This section describes the wallet that will actually execute the copy-trades.

* **`owner.address`** (string)
    This is the public EVM wallet address that will place the copy-trade orders (your funded “execution wallet”). It must be a `0x...` address (42 characters total).

* **`owner.is_autoredeem_enabled`** (boolean)
    Set this to `true` if you want the system to automatically redeem positions when they become redeemable. Leave it `false` if you want to handle redemption manually. Currently, not supported so either value won't change output.

### `price_configuration` (object)

**How conservative or aggressive your copy orders should be.** This controls how pricing is selected and bounded.

* **`price_configuration.spread`** (number)
    This value filters out markets where the bid–ask spread is larger than the number you set. Polymarkets can vary a lot in liquidity, and some markets are “thin,” meaning the gap between the best bid and best ask can be wide. In thin markets, a trader you’re copying might get good fills using a carefully placed limit order, but copying that same trade can be inefficient for you because you may end up paying through the spread and losing the edge the original trader captured. Setting a spread limit helps avoid copying trades in markets where execution would likely be unfavorable. A larger spread threshold means you’ll copy trades more often and more quickly across more markets, but it can lead to worse fills. A reasonable recommended value for most users is `0.05`. Can be set between `0-1`.

* **`price_configuration.buffer`** (number)
    This value adjusts the limit price you send so your orders are more likely to fill when the market is moving or liquidity is thin. For buys, the buffer is added to the current price to allow you to pay slightly more (up to your limit) to get a fill. For sells, the buffer is subtracted to allow you to accept slightly less (down to your limit) to get a fill. The core idea is to avoid placing an order exactly at a price level that may not have enough size available, which can cause partial fills or no fill at all. If you set this too low, you may frequently miss fills and fall behind the trader you’re trying to copy. If you set it too high, you’ll get filled more reliably, but your execution can drift further from the intended price and reduce performance. Your buffer value should be greater than or equal to your spread value unless you want to place orders inside the spread that may not fill. If the sum of the current price and buffer is greater than 1 or the difference of the current price and buffer is less than 0, then the maximum and minimum target prices outputted are `0.99` and `0.01` respectively. Can be set between `0-1`.

* **`price_configuration.limits`** (object)
    Defines the hard bounds for the limit prices you allow for buys and sells filtering out markets to copy that have current prices outside these bounds. The filtering is not done using the target prices impacted by buffers.

  * **`price_configuration.limits.buy.min` / `buy.max`** (number)
    These define the minimum and maximum price your bot is allowed to use for BUY orders. Anything outside this range will not be used. Can be set between `0.01-0.99`.

  * **`price_configuration.limits.sell.min` / `sell.max`** (number)
    These define the minimum and maximum price your bot is allowed to use for SELL orders. Anything outside this range will not be used. Can be set between `0.01-0.99`.

### `traders` (array of objects)

**Which Polymarket wallets you want to follow, and how strongly.** Each entry represents one trader to mirror. You can currently copy up to 5 traders.

* **`traders[].address`** (string)
    This is the public EVM wallet address of the trader you want to mirror (the person you’re copying). It must be a `0x...` address.

* **`traders[].factor`** (number)
    This is the position scaling multiplier applied to that trader. For example, if a trader buys 100 shares and your `factor` is `0.10`, your target exposure would be about 10 shares (subject to your min/max rules). Shares are rounded to the nearest integer. The factor must be a non-negative value. Keep in mind, due to polymarket rules, limit orders for buying can only be placed if share count is greater than or equal to 5 worth greater than or equal $1. This means that you won't receive purchases less than $1 or less than 5 shares after factoring.

* **`traders[].excluded_tags`** (array of integers)
    These are category/tag IDs you want to block for this trader. If a market matches one of these tags, the system will ignore it for this trader. Find tags [`here`](https://docs.polymarket.com/api-reference/tags/list-tags).

* **`traders[].min_share`** (integer)
    This is the minimum trade size (in shares) that you are willing to place when copying this trader when they have a position. For example, if the minimum trade size is 5, all share counts, after applying the factor, are clipped to 5. A min share size of `1` is recommended.

* **`traders[].max_share`** (integer)
    This is the maximum trade size (in shares) you allow for any single market from this trader. This is a safety cap to prevent oversized orders.

### `excluded_markets` (array of strings)

**Markets you never want to trade.**
This is a list of Polymarket condition IDs (hash-style IDs). If a market appears here, it will be ignored entirely even if a copied trader trades it. Find markets and their condition IDs [`here`](https://docs.polymarket.com/api-reference/markets/list-markets).

### `is_aggregated` (boolean)

**Whether to combine trader signals into a single net instruction per market.**
If `true`, the API will merge/aggregate asset shares across traders (e.g., offsetting buys and sells) on a market before returning instructions. For example, lets say you want to start copying traders A and B currently trading on the same market. Trader A has the positions 2000 YES and 400 NO while trader B has the position 3000 NO. Then Trader B buys 5000 YES 30 minutes later. If your factor is `1` and `is_aggregated` is `false`, you will buy 2000 YES and 3400 NO. After 30 minutes, you will buy 5000 YES and have the final positions 7000 YES and 3400 NO. If `is_aggregated` is `true`, you will buy 1400 NO only. After 30 minutes, you will sell 1400 NO and buy 3600 YES and have the final position 3600 YES. Having the value be `true` is better if you have low capital.

### `defer_execution` (object)

**Optional timing + execution policy to avoid trading too early and to control how you enter.**
When enabled, the API can delay copying until closer to event start, and can optionally use a LIMIT-then-MARKET approach: LIMIT phase: start working the order with a resting post-only GTC limit (more price control). MARKET phase: near the cutoff, finish any remaining size to ensure you’re synced before the event. The API communicates the plan via `execution_style` and timestamps returned per instruction.

* **`defer_execution.enabled`** (boolean)  
    If `true`, the API may withhold instructions until the event is within the configured windows. If `false`, the API ignores the remaining fields and returns instructions immediately (subject to other filters).

* **`defer_execution.hours_before_start`** (number)  
    The “finalization window.” Once the event is within this many hours of start, the API can switch to returning `execution_style: "MARKET"` instructions (to finish remaining size before start).

* **`defer_execution.mode`** (string)  
    Execution strategy when deferral is enabled. Supported values: `LIMIT_THEN_MARKET`: return `LIMIT` instructions during the limit window, then `MARKET` instructions near cutoff to finish remainder.

* **`defer_execution.limit_window_hours`** (number)  
    How early the API is allowed to start returning `execution_style: "LIMIT"` instructions before event start.  Outside this window (too early), the API may return no instructions for that market.

* **`defer_execution.limit_offset_price`** (number)  
    A price offset applied by the server when computing `limit_price` during the LIMIT phase. The server returns the final `limit_price` in the response; clients should treat it as the authoritative limit level.

## Response Field Explanation

The response body is an array of trade instructions. It can be empty.

* `[]` means “no trades needed right now” (your current positions already match the target portfolio within tolerance, or all potential trades were filtered out by your settings).
* If the array is not empty, each element is a `CopyTradeInstruction` describing one action to take.
Depending on `defer_execution`, an instruction may be:
- `execution_style: "LIMIT"` — place/maintain a resting limit order (often post-only GTC).
- `execution_style: "MARKET"` — place an order intended to fill immediately (or as close as possible) to sync remaining exposure near cutoff.

### `CopyTradeInstruction` (object)

**Calculated trade to move your portfolio toward the target allocation.** Each instruction is independent and can be executed in order.

* **`asset_id`** (string)
    Outcome token id to trade.

* **`event_id`** (string)
    Polymarket event identifier for the market this instruction belongs to.

* **`side`** (`BUY` | `SELL`)
    Direction of the trade.

* **`size`** (integer)
    Total intended size for this instruction (in shares). Your client should typically treat this as the “desired” amount and may compute remaining based on fills/current positions.

* **`execution_style`** (`LIMIT` | `MARKET`)
    How the client should execute this instruction at the current time: `LIMIT`: use `limit_price` and maintain/cancel/reprice as needed until `cutoff_ts`. MARKET`: use `target_price` and finish remaining size (often after canceling any open limits).

* **`target_price`** (number)
    The server-computed execution price level for the instruction (used for MARKET-style execution, and may also serve as a reference anchor for LIMIT pricing).

* **`limit_price`** (number, optional)
    Present when `execution_style` is `LIMIT`. The exact limit price the client should place/maintain.

* **`price`** (number, optional)
    Informational price snapshot used during calculation (useful for debugging/logging).

* **`limit_start_ts`** (integer, unix seconds, optional)
    Earliest timestamp when the LIMIT phase is intended to begin for this instruction.

* **`cutoff_ts`** (integer, unix seconds, optional)
    Timestamp after which the client should stop maintaining LIMIT orders and switch to MARKET (finish remaining), if the server returns MARKET instructions.

* **`event_time_ts`** (integer, unix seconds, optional)
    The event start time used for defer-execution logic.


## Schemas

This repo includes JSON Schemas for validation/typing.

* Request schema: [`schemas/CopyTradeLambdaRequest.schema.json`](schemas/CopyTradeLambdaRequest.schema.json).
* Response schema: [`schemas/CopyTradeLambdaResponse.schema.json`](schemas/CopyTradeLambdaResponse.schema.json)

## OpenAPI

* Location: [`openapi/openapi.yaml`](openapi/openapi.yaml)
* Use it to generate:

  * client SDKs
  * docs pages
  * request/response models

## Error Handling

* `400` invalid request body / schema mismatch
* `401` missing/invalid API key
* `403` forbidden key
* `429` throttled / quota exceeded
* `500` internal error

## Rate Limits

API protected by AWS WAF. Current rate limit is 1 request / 10 seconds

## Security Notes

* Never commit real secrets (`.env`, private keys)
* `.env.example` is safe; `.env` should be gitignored
* API keys should be treated as secrets

## Client Bot Tutorial

### Python

Examples live in [`client_example/`](client_example/).

#### Minimal request example

This example sends **one request** to the CopyTradeHorizon API and prints the returned instructions as a table. It does **not** place any Polymarket orders, it only shows you what the API would recommend right now. This is good for testing what will be bought/sold and adjusting factors.

Run:

```bash
cd examples
cp .env.example .env
# fill in CTH_KEY and FUNDER at least
pip install -r requirements.txt
python client_request.py
```

What you need to set in `.env`:

* `CTH_KEY` - your CopyTradeHorizon API key (request by email).
* `FUNDER` - the EVM address that will be treated as your “owner” wallet in the request (your execution portfolio).
* `STATE_FILE` (optional) - path to persistent defer-execution state JSON (default `defer_state.json`).
* (Optional for the request-only example) `HOST`, `PRIVATE_KEY`, `CHAIN_ID` - only required for the full bot that actually places orders.

What the request script is doing:

* It builds `HEADERS` containing your API key (`X-API-Key`) so the request is authorized.
* It sets `OWNER_ADDRESS = os.environ["FUNDER"]` and uses it as `payload.owner.address`.
* It POSTs the `payload` to `https://api.copytradehorizon.com/polymarketcopy`.
* It converts the JSON response (an array of instructions) into a Pandas DataFrame, sorts by `size`, and prints it.

Review of the request (`payload`), look at other sections, schemas, and openapi documentation for better understanding:

* `owner.address` - the wallet you want the API to treat as the portfolio being managed (your execution wallet).
* `price_configuration.spread` - maximum allowed bid/ask spread for a market to be eligible for copying.
* `price_configuration.buffer` - how aggressively to push limit prices to improve fill probability (buys go slightly higher, sells go slightly lower).
* `price_configuration.limits` - hard min/max bounds on prices you’re willing to trade for buys and sells.
* `traders[]` - the Polymarket wallets you want to mirror, plus scaling and safety settings:

    * `address` - the trader’s wallet address to copy.
    * `factor` - how much to scale their position sizes (e.g., `0.10` copies at ~10% size).
    * `excluded_tags` - tag IDs you want to block for that trader.
    * `min_share` / `max_share` - per-market size clamps for safety.
* `excluded_markets[]` - condition IDs you never want to trade.
* `is_aggregated` - whether to merge multiple trader signals into a single net instruction per market.
* `defer_execution` - optional timing gate to avoid trading too early relative to market start time.

#### Full bot (places orders)

The bot example runs continuously: it polls the CopyTradeHorizon API for **execution-style instructions** and then manages Polymarket orders accordingly via `py-clob-client`. It supports a two-phase flow when `defer_execution.mode = "LIMIT_THEN_MARKET"`:

- **LIMIT phase:** place/maintain a post-only GTC limit order and reprice/resize as the server updates pricing or as fills occur.
- **MARKET phase:** near/after cutoff, cancel resting limits and finish any remaining size with short-lived (GTD) orders so your portfolio is synced before the event.

High-level flow:

1. Fetch your **current on-chain positions** from Polymarket (`data-api.polymarket.com/positions`) at the start of every poll.
2. Clear any assets that have **synced** after recent MARKET orders (if `abs(chain_position - pending_target) <= SYNC_EPS`), so they’re no longer blocked.
3. Call the CopyTradeHorizon API to get the **recommended instructions**, including `execution_style`, `limit_price`, `target_price`, and timing fields like `cutoff_ts`.
4. Drop stale intents: if an `asset_id` is no longer returned by the API, cancel any open orders for that asset and remove its entry from the persistent defer state.
5. Process **LIMIT instructions** (`execution_style == "LIMIT"`):
   - Skip assets currently blocked by the MARKET sync guard (`pending_targets`).
   - If the intent changed (side/desired size/cutoff changed), cancel existing open orders and reset an intent anchored to the **current chain position** (`base_pos`).
   - Compute **remaining size** using actual positions: progress is measured from `base_pos` (BUY: position increase; SELL: position decrease).
   - Cancel wrong-side orders, keep only one newest same-side order, and cancel extras.
   - Reprice/resize if needed (threshold-based) by canceling and re-posting a post-only GTC limit order.
   - Persist per-asset intent in `defer_state` (order id, side, desired size, base position, last limit price, cutoff timestamp).
6. Process **MARKET instructions** (`execution_style == "MARKET"`):
   - Skip assets blocked by the MARKET sync guard.
   - Cancel **all** open orders for the asset (covers restarts and prior LIMIT orders).
   - Compute **remaining size** using actual positions; if transitioning from LIMIT → MARKET for the same intent, reuse the stored `base_pos`.
   - Post short-lived GTD orders in small batches; record successful deltas and set a **pending target position** for each asset so the bot doesn’t repeat MARKET orders until positions update.
   - Remove any `defer_state` for the asset once it enters MARKET phase.
7. Save `defer_state` to disk every loop and on shutdown (SIGINT/SIGTERM/exit) so LIMIT intents survive restarts.

Key settings in the bot:

* `POLL_INTERVAL` - how often the bot checks for new instructions.
* `SYNC_EPS` - tolerance for considering a MARKET order “synced” (prevents repeating MARKET orders before positions update).
* `STATE_FILE` - path to the persistent defer-execution state JSON (default: `defer_state.json`).
* `LIMIT_REPRICE_THRESHOLD` - minimum price change needed to cancel/repost a LIMIT order.
* `SIZE_EPS` - tolerance for detecting meaningful size changes (used for intent changes and order resize decisions).

Environment variables required for the full bot:

* `CTH_KEY` - CopyTradeHorizon API key.
* `FUNDER` - your execution wallet address.
* `HOST` - Polymarket CLOB host (example: `https://clob.polymarket.com`).
* `PRIVATE_KEY` - private key for the wallet used to sign orders (keep this secret; never commit it).
* `CHAIN_ID` - chain id (e.g., 137 for Polygon).
* `STATE_FILE` (optional) - override the default location/name for the persistent defer-execution state file.

### Running the bot 24/7

A simple way to keep the bot running indefinitely is to deploy it on an Ubuntu instance (ex: AWS Lightsail) and run it as a Docker container with a restart policy.

1. SSH into your instance (or use VS Code Remote SSH).
2. Put your runtime secrets into a local env file (`runtime.env`) and lock down permissions.
3. Build the Docker image and run the container with `--restart unless-stopped`.
4. Use `docker ps` / `docker logs` to monitor.

Commands:

```bash
# connect to your instance, then:
cd /home/ubuntu/copytrade-bot
nano runtime.env
chmod 600 runtime.env

# build image
docker build -t copytrade-bot:latest .

# run continuously (background + auto-restart)
docker run -d \
  --name copytrade-bot \
  --restart unless-stopped \
  --env-file /home/ubuntu/copytrade-bot/runtime.env \
  copytrade-bot:latest

# check status
docker ps

# stop/start/restart
docker stop copytrade-bot
docker start copytrade-bot
docker restart copytrade-bot
```

Editing the bot and redeploying:

```bash
cd /home/ubuntu/copytrade-bot
docker build -t copytrade-bot:latest .
docker rm -f copytrade-bot
docker run -d --name copytrade-bot --restart unless-stopped --env-file /home/ubuntu/copytrade-bot/runtime.env copytrade-bot:latest
```

## License

This project is licensed under the terms in the [`LICENSE`](LICENSE.md) file.

## Legal / Compliance Notice

CopyTradeHorizon provides **software and API responses for informational purposes only**. It returns suggested trade instructions and market/position data, but it **does not** broker, execute, route, or custody funds on behalf of users.

You are responsible for complying with all applicable laws, regulations, and platform terms in your jurisdiction. Some jurisdictions restrict access to or use of Polymarket and/or related trading functionality. In particular, **users located in the United States may be restricted from placing trades** on Polymarket. This repository and API may be used to **retrieve and analyze public market data**, but it must not be used to violate any legal restrictions or platform rules.

By using this project, you agree that:

* You will only use this software in a manner that is lawful in your jurisdiction.
* You are solely responsible for any trades you place and any consequences of using third-party services.
* CopyTradeHorizon is not providing financial, legal, or tax advice.
* CopyTradeHorizon makes no guarantees about accuracy, performance, profitability, or availability.

If you are unsure whether you are permitted to place trades, use the project in **data-only mode** (requesting instructions and analyzing results).