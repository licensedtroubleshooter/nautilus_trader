# Alpaca Broker Integration Plan for NautilusTrader

## Overview

Build a full Alpaca adapter for NautilusTrader supporting **paper and live trading** of US equities (stocks/ETFs) and crypto. The integration uses the `alpaca-py` SDK as the underlying client (Python-only approach, no Rust core needed initially) and follows the same adapter patterns as Interactive Brokers, Binance, etc.

Paper vs. live trading differs only in the base URL and API keys—the adapter will handle this via a single `paper` boolean config flag.

---

## Target Directory Structure

```
nautilus_trader/adapters/alpaca/
├── __init__.py          # Public exports
├── config.py            # AlpacaDataClientConfig, AlpacaExecClientConfig, AlpacaInstrumentProviderConfig
├── constants.py         # Venue ID, URLs, enums
├── data.py              # AlpacaDataClient (LiveMarketDataClient)
├── execution.py         # AlpacaExecutionClient (LiveExecutionClient)
├── factories.py         # AlpacaLiveDataClientFactory, AlpacaLiveExecClientFactory
├── providers.py         # AlpacaInstrumentProvider (InstrumentProvider)
├── enums.py             # Alpaca-specific enums and mappings
├── parsing/
│   ├── __init__.py
│   ├── instruments.py   # Parse Alpaca assets -> Nautilus Equity/CryptoCurrency instruments
│   ├── data.py          # Parse quotes, trades, bars -> Nautilus QuoteTick, TradeTick, Bar
│   └── execution.py     # Parse Alpaca orders/fills -> Nautilus OrderStatusReport, FillReport, etc.
└── websocket.py         # Thin wrapper around alpaca-py streaming clients (StockDataStream, TradingStream)
```

Tests:
```
tests/integration_tests/adapters/alpaca/
├── test_config.py
├── test_data.py
├── test_execution.py
├── test_factories.py
├── test_providers.py
└── test_parsing/
    ├── test_instruments.py
    ├── test_data.py
    └── test_execution.py
```

---

## Phase 1: Foundation — Constants, Config, and Enums

### Step 1.1: `constants.py`
- Define `ALPACA_VENUE = Venue("ALPACA")`
- Base URLs for paper/live REST and WebSocket endpoints
- Rate limit constant (200 req/min)

### Step 1.2: `enums.py`
- Mapping tables between Alpaca and Nautilus enums:
  - `OrderSide` (buy/sell <-> BUY/SELL)
  - `OrderType` (market/limit/stop/stop_limit/trailing_stop <-> MARKET/LIMIT/STOP_MARKET/STOP_LIMIT/TRAILING_STOP_MARKET)
  - `TimeInForce` (day/gtc/opg/cls/ioc/fok <-> DAY/GTC/AT_THE_OPEN/AT_THE_CLOSE/IOC/FOK)
  - `OrderStatus` (new/fill/partial_fill/canceled/expired/rejected/etc. <-> Nautilus equivalents)
  - `OrderClass` (simple/bracket/oco/oto) for advanced order types

### Step 1.3: `config.py`
- **`AlpacaInstrumentProviderConfig`** (extends `InstrumentProviderConfig`)
  - `api_key: str` (env: `APCA_API_KEY_ID`)
  - `api_secret: str` (env: `APCA_API_SECRET_KEY`)
  - `paper: bool = True`
  - `asset_classes: frozenset[str] | None = None` (filter: "us_equity", "crypto")

- **`AlpacaDataClientConfig`** (extends `LiveDataClientConfig`)
  - `api_key: str`
  - `api_secret: str`
  - `paper: bool = True`
  - `feed: str = "iex"` (options: "iex", "sip" — SIP requires paid plan)
  - `instrument_provider: AlpacaInstrumentProviderConfig`

- **`AlpacaExecClientConfig`** (extends `LiveExecClientConfig`)
  - `api_key: str`
  - `api_secret: str`
  - `paper: bool = True`
  - `account_id: str | None = None` (auto-fetched if not set)
  - `instrument_provider: AlpacaInstrumentProviderConfig`

---

## Phase 2: Instrument Provider

### Step 2.1: `parsing/instruments.py`
- `parse_equity_instrument(alpaca_asset) -> Equity`
  - Map Alpaca asset fields (symbol, exchange, name, tradable, fractionable, easy_to_borrow, marginable) to Nautilus `Equity` instrument
  - Set `price_precision` and `size_precision` (Alpaca equities: 2 decimal price, fractional shares support)
  - Map exchange to appropriate venue (e.g., NYSE, NASDAQ, ARCA, or use ALPACA as default)
- `parse_crypto_instrument(alpaca_asset) -> CurrencyPair`
  - Map crypto trading pairs (e.g., BTC/USD) to Nautilus `CurrencyPair`
  - Set appropriate precision for crypto assets

### Step 2.2: `providers.py` — `AlpacaInstrumentProvider`
- Constructor: takes `AlpacaInstrumentProviderConfig`, creates `TradingClient` from alpaca-py
- `load_all_async(filters)`: call `trading_client.get_all_assets()`, filter by `tradable=True` and optional `asset_class`, parse each to Nautilus instrument, call `self.add()`
- `load_ids_async(instrument_ids, filters)`: for each ID, look up by symbol via `trading_client.get_asset(symbol)`, parse, add
- `load_async(instrument_id, filters)`: single instrument load
- Cache `alpaca_asset` objects for later reference (e.g., checking fractionable, easy_to_borrow)

---

## Phase 3: Market Data Client

### Step 3.1: `websocket.py` — Streaming wrapper
- Thin manager class around alpaca-py's `StockDataStream` and `CryptoDataStream`
- Handles lifecycle: connect, authenticate, subscribe, disconnect
- Callbacks forward raw data to the data client's parsing/publishing methods

### Step 3.2: `parsing/data.py`
- `parse_quote_tick(alpaca_quote, instrument_id) -> QuoteTick`
  - Map bid_price, ask_price, bid_size, ask_size, timestamp
- `parse_trade_tick(alpaca_trade, instrument_id) -> TradeTick`
  - Map price, size, timestamp, aggressor side (if available)
- `parse_bar(alpaca_bar, instrument_id, bar_type) -> Bar`
  - Map open, high, low, close, volume, timestamp

### Step 3.3: `data.py` — `AlpacaDataClient` (extends `LiveMarketDataClient`)
- **Constructor**: receives alpaca-py clients + instrument provider + config
- **`_connect()`**: initialize instrument provider, connect WebSocket streams
- **`_disconnect()`**: close WebSocket streams, cleanup
- **Subscriptions implemented**:
  - `_subscribe_quote_ticks(command)` — subscribe to Alpaca `quotes` channel
  - `_subscribe_trade_ticks(command)` — subscribe to Alpaca `trades` channel
  - `_subscribe_bars(command)` — subscribe to Alpaca `bars` (minute) or `dailyBars` channel
  - `_subscribe_instrument_status(command)` — subscribe to Alpaca `statuses` channel
  - `_subscribe_instrument(command)` — load instrument from provider
  - `_subscribe_instruments(command)` — load all instruments
  - Corresponding `_unsubscribe_*` methods
- **Historical data requests**:
  - `_request_bars(request)` — use `StockHistoricalDataClient.get_stock_bars()` or `CryptoHistoricalDataClient.get_crypto_bars()`
  - `_request_trade_ticks(request)` — use `get_stock_trades()` / `get_crypto_trades()`
  - `_request_quote_ticks(request)` — use `get_stock_quotes()`
  - `_request_instrument(request)` — load from provider
  - `_request_instruments(request)` — load all from provider

---

## Phase 4: Execution Client

### Step 4.1: `parsing/execution.py`
- `parse_order_status_report(alpaca_order, instrument_id) -> OrderStatusReport`
  - Map order_id, client_order_id, order_type, side, time_in_force, status, qty, filled_qty, avg_fill_price, timestamps
- `parse_fill_report(alpaca_order, instrument_id) -> FillReport`
  - Extract fill price, fill qty, commission, liquidity side, timestamps
- `parse_position_status_report(alpaca_position, instrument_id) -> PositionStatusReport`
  - Map qty, side, avg_entry_price, instrument
- `nautilus_order_to_alpaca_request(order, instrument) -> OrderRequest`
  - Convert Nautilus Order to alpaca-py `MarketOrderRequest` / `LimitOrderRequest` / `StopOrderRequest` / `StopLimitOrderRequest` / `TrailingStopOrderRequest`
  - Map order side, time_in_force, quantity, price, trigger price, trail percent/offset
  - Handle bracket/OCO/OTO via `order_class`, `take_profit`, `stop_loss` params

### Step 4.2: `websocket.py` — Trading updates stream (addition)
- Add `TradingStream` integration for real-time order/trade updates
- Subscribe to `trade_updates` channel
- Forward events to execution client handlers

### Step 4.3: `execution.py` — `AlpacaExecutionClient` (extends `LiveExecutionClient`)
- **Constructor**:
  - `oms_type = OmsType.NETTING` (Alpaca uses netting for equities)
  - `account_type = AccountType.MARGIN` (most Alpaca accounts are margin)
  - `base_currency = USD` (US broker, USD-denominated)
  - Creates `TradingClient` and `TradingStream` from alpaca-py

- **`_connect()`**:
  - Initialize instrument provider
  - Connect trading stream WebSocket
  - Subscribe to `trade_updates`
  - Fetch initial account state, generate `AccountState` event
  - Register event handlers for order updates

- **`_disconnect()`**: close trading stream, cleanup

- **Order submission**:
  - `_submit_order(command)` — convert to alpaca-py request, call `trading_client.submit_order()`, generate `OrderSubmitted` event
  - `_submit_order_list(command)` — handle bracket/OCO/OTO orders using Alpaca's `order_class` parameter
  - `_modify_order(command)` — call `trading_client.replace_order_by_id()` (Alpaca supports order replacement)
  - `_cancel_order(command)` — call `trading_client.cancel_order_by_id()`
  - `_cancel_all_orders(command)` — call `trading_client.cancel_orders()`

- **Order update handling** (from TradingStream):
  - `_handle_trade_update(event)` — dispatch based on event type:
    - `new` -> `generate_order_accepted()`
    - `fill` -> `generate_order_filled()`
    - `partial_fill` -> `generate_order_filled()` (with partial qty)
    - `canceled` -> `generate_order_canceled()`
    - `expired` -> `generate_order_expired()`
    - `rejected` -> `generate_order_rejected()`
    - `replaced` -> `generate_order_updated()`
    - `pending_new`, `pending_cancel`, `pending_replace` -> `generate_order_pending_*`

- **Report generation** (for reconciliation on connect):
  - `generate_order_status_reports()` — call `trading_client.get_orders(status="all")`, parse each
  - `generate_order_status_report()` — call `trading_client.get_order_by_id()`, parse
  - `generate_fill_reports()` — extract fills from closed orders
  - `generate_position_status_reports()` — call `trading_client.get_all_positions()`, parse each
  - `generate_mass_status()` — combine all above reports

- **Account query**:
  - `_query_account(command)` — call `trading_client.get_account()`, generate `AccountState` event with buying_power, equity, cash, etc.

---

## Phase 5: Factories and Package Init

### Step 5.1: `factories.py`
- **`get_cached_alpaca_trading_client(api_key, api_secret, paper)`** — `@lru_cache`, returns `TradingClient`
- **`get_cached_alpaca_instrument_provider(client, config)`** — `@lru_cache`, returns `AlpacaInstrumentProvider`
- **`AlpacaLiveDataClientFactory`** (implements `LiveDataClientFactory`)
  - `create(loop, name, config, msgbus, cache, clock)` -> `AlpacaDataClient`
  - Resolves credentials from config or environment variables
- **`AlpacaLiveExecClientFactory`** (implements `LiveExecClientFactory`)
  - `create(loop, name, config, msgbus, cache, clock)` -> `AlpacaExecutionClient`

### Step 5.2: `__init__.py`
- Export all public classes: configs, factories, providers, clients
- Define `__all__`

---

## Phase 6: Testing

### Step 6.1: Unit tests for parsing
- Test all parsing functions with sample Alpaca API response fixtures
- Test enum mapping tables for completeness
- Test edge cases: fractional shares, crypto precision, extended hours orders

### Step 6.2: Unit tests for instrument provider
- Mock `TradingClient.get_all_assets()` with sample data
- Verify correct Nautilus instrument creation for equities and crypto
- Test filtering by asset class

### Step 6.3: Integration tests for data client
- Mock alpaca-py streaming clients
- Verify subscription management, data parsing, and publishing to message bus
- Test historical data request flow

### Step 6.4: Integration tests for execution client
- Mock `TradingClient` order operations
- Verify order submission, modification, cancellation flows
- Test trade update event handling (fill, cancel, reject, etc.)
- Test report generation for reconciliation
- Test bracket/OCO/OTO order construction

### Step 6.5: End-to-end test
- Paper trading smoke test with real Alpaca paper credentials
- Submit market order, verify fill events
- Subscribe to quotes/trades, verify data flow

---

## Phase 7: Documentation and Example

### Step 7.1: Example script
- `examples/live/alpaca/` — minimal example showing:
  - Config setup with paper=True
  - TradingNode construction
  - Strategy that subscribes to bars and submits orders

---

## Supported Alpaca Features (Scope)

| Feature | Supported | Notes |
|---------|-----------|-------|
| US Equities (stocks/ETFs) | Yes | Primary asset class |
| Cryptocurrency | Yes | 20+ crypto assets via separate data stream |
| Options | No (future) | Would require separate data/execution paths |
| Market orders | Yes | |
| Limit orders | Yes | |
| Stop orders | Yes | |
| Stop-limit orders | Yes | |
| Trailing stop orders | Yes | trail_price or trail_percent |
| Bracket orders | Yes | Via order_class="bracket" |
| OCO orders | Yes | Via order_class="oco" |
| OTO orders | Yes | Via order_class="oto" |
| Order replacement | Yes | Alpaca supports replace_order |
| Fractional shares | Yes | When asset is fractionable |
| Extended hours trading | Yes | Via extended_hours=True on limit orders |
| Real-time quotes (WebSocket) | Yes | IEX (free) or SIP (paid) |
| Real-time trades (WebSocket) | Yes | |
| Real-time bars (WebSocket) | Yes | 1-min bars |
| Historical bars (REST) | Yes | Multiple timeframes |
| Historical trades (REST) | Yes | |
| Historical quotes (REST) | Yes | |
| Paper trading | Yes | paper=True config flag |
| Live trading | Yes | paper=False config flag |
| Account state | Yes | Buying power, equity, cash |
| Position tracking | Yes | Real-time via API |

---

## Dependencies

- `alpaca-py` >= 0.43 (pip install alpaca-py)
- No Rust crate needed initially (pure Python adapter using alpaca-py SDK)
- Future optimization: migrate HTTP/WebSocket to Rust core for lower latency

---

## Key Design Decisions

1. **Python-only (no Rust core)**: Use `alpaca-py` SDK directly. This is the fastest path to a working adapter. Rust core can be added later for performance.

2. **Single venue `ALPACA`**: Both equities and crypto route through the same venue. Instrument types distinguish them.

3. **Netting OMS**: Alpaca uses netting (not hedging) — you have one position per symbol, buys/sells net against each other.

4. **USD base currency**: Alpaca is a US broker; all accounts are USD-denominated.

5. **Paper/Live via config**: A single `paper: bool` flag switches between paper and live environments. The adapter code is identical for both.

6. **Credential resolution**: Check config first, then fall back to env vars (`APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`).
