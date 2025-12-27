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
      "spread": 0.05,
      "buffer": 0.05,
      "limits": { "buy": {"min": 0.01, "max": 0.98}, "sell": {"min": 0.01, "max": 0.98} }
    },
    "traders": [
      { "address": "0x...", "factor": 0.01, "excluded_tags": [], "min_share": 1, "max_share": 250 }
    ],
    "excluded_markets": [],
    "is_aggregated": true,
    "defer_execution": { "enabled": true, "hours_before_start": 5.0 }
  }'
```

**Example response**

```json
[
  { "asset_id": "123...", "size": 10, "side": "BUY", "target_price": 0.42 }
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

**A timing gate to avoid trading too early.** This lets you delay execution until closer to a market’s start time. This is very useful to avoid locking up capital. Best to use for sports markets. If the person you are copying purchases lots of shares for an event happening in 3 days, you have extra capital for trading until the date arrives when you defer execution. Does not work well for Esports markets based on how Polymarket notes their start time and will copy earlier for these markets than inputted.

* **`defer_execution.enabled`** (boolean)
    If `true`, the system will not generate trades for markets that are still too far from their start time (based on the setting below). If `false`, the system will copy all events irrespective of their start time and ignore values in `hours_before_start` field.

* **`defer_execution.hours_before_start`** (number)
    If deferral is enabled, trades are only allowed when the market is within this many hours of starting. Example: if `hours_before_start` is `5`, the system waits until the market is less than or equal to 5 hours from start before allowing copy-trade instructions.

## Response Field Explanation

The response body is an array of trade instructions. It can be empty.

* `[]` means “no trades needed right now” (your current positions already match the target portfolio within tolerance, or all potential trades were filtered out by your settings).
* If the array is not empty, each element is a `CopyTradeInstruction` object describing one limit order you should place. This object is represented as `CopyTradeLambdaResponse` object in the schemas folder.

### `CopyTradeInstruction` (object)

**Calculated trade to move your portfolio toward the target allocation.** Each instruction is independent and can be executed in order.

* **`asset_id`** (string)
    The Polymarket asset/token ID to trade. This identifies the specific outcome token (e.g., a YES token or NO token to a particular market) that the instruction applies to.

* **`size`** (integer)
    The number of shares to buy or sell for this instruction. This is always a whole number of shares and represents the suggested trade size after applying your scaling rules (factor, min/max shares) and any aggregation logic.

* **`side`** (`BUY` | `SELL`)
    Whether you should buy shares (`BUY`) or sell shares (`SELL`) for the given `asset_id`. This is the action needed to move your current position toward the target position.

* **`target_price`** (number)
    he limit price you should use for the order. This will always be bounded to valid probability-style prices and is influenced by your `price_configuration` rules (buffer and limits). A higher buy price or lower sell price generally increases fill probability, but can worsen execution quality.

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

The bot example runs continuously: it polls the CopyTradeHorizon API for instructions, then places limit orders on Polymarket via `py-clob-client`.

High-level flow:

1. Fetch your **current on-chain positions** from Polymarket (`data-api.polymarket.com/positions`).
2. Call the CopyTradeHorizon API to get the **recommended instructions**.
3. Convert instructions into `OrderArgs` (token, side, size, limit price).
4. Post orders to the Polymarket CLOB.
5. Track “pending targets” so the bot does not spam repeat orders for the same asset while fills/settlement catch up.

Key settings in the bot:

* `POLL_INTERVAL` - how often the bot checks for new instructions.
* `SYNC_EPS` - tolerance used to decide when your current position is “close enough” to the expected target after recent orders, so the bot doesn’t re-issue trades too aggressively.

Environment variables required for the full bot:

* `CTH_KEY` - CopyTradeHorizon API key.
* `FUNDER` - your execution wallet address.
* `HOST` - Polymarket CLOB host (example: `https://clob.polymarket.com`).
* `PRIVATE_KEY` - private key for the wallet used to sign orders (keep this secret; never commit it).
* `CHAIN_ID` - chain id (e.g., 137 for Polygon).

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