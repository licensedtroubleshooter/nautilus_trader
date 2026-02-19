# -------------------------------------------------------------------------------------------------
#  Copyright (C) 2015-2026 Nautech Systems Pty Ltd. All rights reserved.
#  https://nautechsystems.io
#
#  Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
#  You may not use this file except in compliance with the License.
#  You may obtain a copy of the License at https://www.gnu.org/licenses/lgpl-3.0.en.html
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# -------------------------------------------------------------------------------------------------

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.requests import CryptoTradesRequest
from alpaca.data.requests import StockBarsRequest
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.data.requests import StockQuotesRequest
from alpaca.data.requests import StockTradesRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.timeframe import TimeFrameUnit

from nautilus_trader.adapters.alpaca.config import AlpacaDataClientConfig
from nautilus_trader.adapters.alpaca.constants import ALPACA_VENUE
from nautilus_trader.adapters.alpaca.parsing.data import parse_bar
from nautilus_trader.adapters.alpaca.parsing.data import parse_quote_tick
from nautilus_trader.adapters.alpaca.parsing.data import parse_trade_tick
from nautilus_trader.adapters.alpaca.providers import AlpacaInstrumentProvider
from nautilus_trader.adapters.alpaca.websocket import AlpacaMarketDataStream
from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.clock import LiveClock
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.data.messages import RequestBars
from nautilus_trader.data.messages import RequestInstrument
from nautilus_trader.data.messages import RequestInstruments
from nautilus_trader.data.messages import RequestQuoteTicks
from nautilus_trader.data.messages import RequestTradeTicks
from nautilus_trader.data.messages import SubscribeBars
from nautilus_trader.data.messages import SubscribeInstrument
from nautilus_trader.data.messages import SubscribeInstruments
from nautilus_trader.data.messages import SubscribeQuoteTicks
from nautilus_trader.data.messages import SubscribeTradeTicks
from nautilus_trader.data.messages import UnsubscribeBars
from nautilus_trader.data.messages import UnsubscribeQuoteTicks
from nautilus_trader.data.messages import UnsubscribeTradeTicks
from nautilus_trader.live.data_client import LiveMarketDataClient
from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import BarAggregation
from nautilus_trader.model.identifiers import ClientId
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.msgbus.bus import MessageBus


class AlpacaDataClient(LiveMarketDataClient):
    """
    Provides a data client for the Alpaca broker API.

    Parameters
    ----------
    loop : asyncio.AbstractEventLoop
        The event loop for the client.
    msgbus : MessageBus
        The message bus for the client.
    cache : Cache
        The cache for the client.
    clock : LiveClock
        The clock for the client.
    instrument_provider : AlpacaInstrumentProvider
        The instrument provider.
    config : AlpacaDataClientConfig
        The configuration for the client.
    api_key : str
        The Alpaca API key.
    api_secret : str
        The Alpaca API secret.
    name : str, optional
        The custom client name.

    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        msgbus: MessageBus,
        cache: Cache,
        clock: LiveClock,
        instrument_provider: AlpacaInstrumentProvider,
        config: AlpacaDataClientConfig,
        api_key: str,
        api_secret: str,
        name: str | None = None,
    ) -> None:
        super().__init__(
            loop=loop,
            client_id=ClientId(name or ALPACA_VENUE.value),
            venue=ALPACA_VENUE,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
            instrument_provider=instrument_provider,
            config=config,
        )
        self._api_key = api_key
        self._api_secret = api_secret
        self._config = config
        self._feed = config.feed

        # Historical data clients (alpaca-py SDK)
        self._stock_hist_client = StockHistoricalDataClient(
            api_key=api_key,
            secret_key=api_secret,
        )
        self._crypto_hist_client = CryptoHistoricalDataClient(
            api_key=api_key,
            secret_key=api_secret,
        )

        # Market data streaming
        self._market_stream = AlpacaMarketDataStream(
            api_key=api_key,
            api_secret=api_secret,
            feed=self._feed,
        )

    @property
    def instrument_provider(self) -> AlpacaInstrumentProvider:
        return self._instrument_provider  # type: ignore

    # -- CONNECTION ---------------------------------------------------------------------------------

    async def _connect(self) -> None:
        await self.instrument_provider.initialize()

        for instrument in self.instrument_provider.list_all():
            self._handle_data(instrument)

        self._log.info("AlpacaDataClient connected")

    async def _disconnect(self) -> None:
        await self._market_stream.close()
        self._log.info("AlpacaDataClient disconnected")

    # -- SUBSCRIPTIONS (INSTRUMENTS) ----------------------------------------------------------------

    async def _subscribe_instrument(self, command: SubscribeInstrument) -> None:
        instrument = self.instrument_provider.find(command.instrument_id)
        if instrument is None:
            await self.instrument_provider.load_async(command.instrument_id)
            instrument = self.instrument_provider.find(command.instrument_id)
        if instrument is not None:
            self._handle_data(instrument)

    async def _subscribe_instruments(self, command: SubscribeInstruments) -> None:
        for instrument in self.instrument_provider.list_all():
            self._handle_data(instrument)

    # -- SUBSCRIPTIONS (QUOTES) ---------------------------------------------------------------------

    async def _subscribe_quote_ticks(self, command: SubscribeQuoteTicks) -> None:
        instrument_id = command.instrument_id
        instrument = self.instrument_provider.find(instrument_id)
        if instrument is None:
            self._log.error(f"Cannot subscribe quotes: instrument {instrument_id} not found")
            return

        symbol = instrument_id.symbol.value
        is_crypto = self._is_crypto(instrument_id)

        if is_crypto:
            self._market_stream.subscribe_crypto_quotes(
                self._on_crypto_quote,
                symbol,
            )
            await self._market_stream.start_crypto_stream()
        else:
            self._market_stream.subscribe_stock_quotes(
                self._on_stock_quote,
                symbol,
            )
            await self._market_stream.start_stock_stream()

    async def _unsubscribe_quote_ticks(self, command: UnsubscribeQuoteTicks) -> None:
        pass  # alpaca-py SDK doesn't support granular unsubscribe easily

    # -- SUBSCRIPTIONS (TRADES) ---------------------------------------------------------------------

    async def _subscribe_trade_ticks(self, command: SubscribeTradeTicks) -> None:
        instrument_id = command.instrument_id
        instrument = self.instrument_provider.find(instrument_id)
        if instrument is None:
            self._log.error(f"Cannot subscribe trades: instrument {instrument_id} not found")
            return

        symbol = instrument_id.symbol.value
        is_crypto = self._is_crypto(instrument_id)

        if is_crypto:
            self._market_stream.subscribe_crypto_trades(
                self._on_crypto_trade,
                symbol,
            )
            await self._market_stream.start_crypto_stream()
        else:
            self._market_stream.subscribe_stock_trades(
                self._on_stock_trade,
                symbol,
            )
            await self._market_stream.start_stock_stream()

    async def _unsubscribe_trade_ticks(self, command: UnsubscribeTradeTicks) -> None:
        pass  # alpaca-py SDK doesn't support granular unsubscribe easily

    # -- SUBSCRIPTIONS (BARS) -----------------------------------------------------------------------

    async def _subscribe_bars(self, command: SubscribeBars) -> None:
        bar_type = command.bar_type
        instrument_id = bar_type.instrument_id
        instrument = self.instrument_provider.find(instrument_id)
        if instrument is None:
            self._log.error(f"Cannot subscribe bars: instrument {instrument_id} not found")
            return

        symbol = instrument_id.symbol.value
        is_crypto = self._is_crypto(instrument_id)

        if is_crypto:
            self._market_stream.subscribe_crypto_bars(
                self._on_crypto_bar,
                symbol,
            )
            await self._market_stream.start_crypto_stream()
        else:
            self._market_stream.subscribe_stock_bars(
                self._on_stock_bar,
                symbol,
            )
            await self._market_stream.start_stock_stream()

    async def _unsubscribe_bars(self, command: UnsubscribeBars) -> None:
        pass

    # -- REQUESTS -----------------------------------------------------------------------------------

    async def _request_instrument(self, request: RequestInstrument) -> None:
        await self.instrument_provider.load_async(request.instrument_id)
        instrument = self.instrument_provider.find(request.instrument_id)
        if instrument is not None:
            self._handle_data(instrument)
            self._handle_instrument(
                instrument,
                request.id,
                request.start,
                request.end,
                request.params,
            )
        else:
            self._log.warning(f"Instrument {request.instrument_id} not available")

    async def _request_instruments(self, request: RequestInstruments) -> None:
        instruments = self.instrument_provider.list_all()
        self._handle_instruments(
            venue=request.venue,
            instruments=instruments,
            correlation_id=request.id,
            start=request.start,
            end=request.end,
            params=request.params,
        )

    async def _request_quote_ticks(self, request: RequestQuoteTicks) -> None:
        instrument_id = request.instrument_id
        instrument = self.instrument_provider.find(instrument_id)
        if instrument is None:
            self._log.error(f"Cannot request quotes: instrument {instrument_id} not found")
            return

        symbol = instrument_id.symbol.value
        start = request.start.to_pydatetime() if request.start else None
        end = request.end.to_pydatetime() if request.end else None

        try:
            quotes_request = StockQuotesRequest(
                symbol_or_symbols=symbol,
                start=start,
                end=end,
                limit=request.limit if hasattr(request, "limit") else None,
            )
            raw_quotes = await asyncio.get_event_loop().run_in_executor(
                None,
                self._stock_hist_client.get_stock_quotes,
                quotes_request,
            )

            ticks = []
            ts_init = self._clock.timestamp_ns()
            quote_set = raw_quotes.get(symbol, []) if isinstance(raw_quotes, dict) else raw_quotes
            if hasattr(quote_set, "data"):
                quote_set = quote_set.data.get(symbol, [])
            elif hasattr(quote_set, "__getitem__") and symbol in quote_set:
                quote_set = quote_set[symbol]

            for q in quote_set:
                ticks.append(parse_quote_tick(q, instrument, ts_init))

            self._handle_quote_ticks(
                instrument_id,
                ticks,
                request.id,
                request.start,
                request.end,
                request.params,
            )
        except Exception as e:
            self._log.error(f"Failed to request quotes for {symbol}: {e}")

    async def _request_trade_ticks(self, request: RequestTradeTicks) -> None:
        instrument_id = request.instrument_id
        instrument = self.instrument_provider.find(instrument_id)
        if instrument is None:
            self._log.error(f"Cannot request trades: instrument {instrument_id} not found")
            return

        symbol = instrument_id.symbol.value
        start = request.start.to_pydatetime() if request.start else None
        end = request.end.to_pydatetime() if request.end else None
        is_crypto = self._is_crypto(instrument_id)

        try:
            if is_crypto:
                trades_request = CryptoTradesRequest(
                    symbol_or_symbols=symbol,
                    start=start,
                    end=end,
                )
                raw_trades = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._crypto_hist_client.get_crypto_trades,
                    trades_request,
                )
            else:
                trades_request = StockTradesRequest(
                    symbol_or_symbols=symbol,
                    start=start,
                    end=end,
                )
                raw_trades = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._stock_hist_client.get_stock_trades,
                    trades_request,
                )

            ticks = []
            ts_init = self._clock.timestamp_ns()
            trade_set = raw_trades.get(symbol, []) if isinstance(raw_trades, dict) else raw_trades
            if hasattr(trade_set, "data"):
                trade_set = trade_set.data.get(symbol, [])
            elif hasattr(trade_set, "__getitem__") and symbol in trade_set:
                trade_set = trade_set[symbol]

            for t in trade_set:
                ticks.append(parse_trade_tick(t, instrument, ts_init))

            self._handle_trade_ticks(
                instrument_id,
                ticks,
                request.id,
                request.start,
                request.end,
                request.params,
            )
        except Exception as e:
            self._log.error(f"Failed to request trades for {symbol}: {e}")

    async def _request_bars(self, request: RequestBars) -> None:
        bar_type = request.bar_type
        instrument_id = bar_type.instrument_id
        instrument = self.instrument_provider.find(instrument_id)
        if instrument is None:
            self._log.error(f"Cannot request bars: instrument {instrument_id} not found")
            return

        symbol = instrument_id.symbol.value
        start = request.start.to_pydatetime() if request.start else None
        end = request.end.to_pydatetime() if request.end else None
        is_crypto = self._is_crypto(instrument_id)
        timeframe = self._bar_type_to_timeframe(bar_type)

        try:
            if is_crypto:
                bars_request = CryptoBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=timeframe,
                    start=start,
                    end=end,
                )
                raw_bars = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._crypto_hist_client.get_crypto_bars,
                    bars_request,
                )
            else:
                bars_request = StockBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=timeframe,
                    start=start,
                    end=end,
                )
                raw_bars = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._stock_hist_client.get_stock_bars,
                    bars_request,
                )

            bars = []
            ts_init = self._clock.timestamp_ns()
            bar_set = raw_bars.get(symbol, []) if isinstance(raw_bars, dict) else raw_bars
            if hasattr(bar_set, "data"):
                bar_set = bar_set.data.get(symbol, [])
            elif hasattr(bar_set, "__getitem__") and symbol in bar_set:
                bar_set = bar_set[symbol]

            for b in bar_set:
                bars.append(parse_bar(b, instrument, bar_type, ts_init))

            self._handle_bars(
                bar_type,
                bars,
                request.id,
                request.start,
                request.end,
                request.params,
            )
        except Exception as e:
            self._log.error(f"Failed to request bars for {symbol}: {e}")

    # -- STREAM CALLBACKS ---------------------------------------------------------------------------

    def _on_stock_quote(self, quote: Any) -> None:
        symbol = str(getattr(quote, "symbol", "")).upper()
        instrument_id = InstrumentId.from_str(f"{symbol}.{ALPACA_VENUE}")
        instrument = self.instrument_provider.find(instrument_id)
        if instrument is None:
            return
        ts_init = self._clock.timestamp_ns()
        tick = parse_quote_tick(quote, instrument, ts_init)
        self._handle_data(tick)

    def _on_crypto_quote(self, quote: Any) -> None:
        self._on_stock_quote(quote)  # same parsing logic

    def _on_stock_trade(self, trade: Any) -> None:
        symbol = str(getattr(trade, "symbol", "")).upper()
        instrument_id = InstrumentId.from_str(f"{symbol}.{ALPACA_VENUE}")
        instrument = self.instrument_provider.find(instrument_id)
        if instrument is None:
            return
        ts_init = self._clock.timestamp_ns()
        tick = parse_trade_tick(trade, instrument, ts_init)
        self._handle_data(tick)

    def _on_crypto_trade(self, trade: Any) -> None:
        self._on_stock_trade(trade)

    def _on_stock_bar(self, bar: Any) -> None:
        symbol = str(getattr(bar, "symbol", "")).upper()
        instrument_id = InstrumentId.from_str(f"{symbol}.{ALPACA_VENUE}")
        instrument = self.instrument_provider.find(instrument_id)
        if instrument is None:
            return
        # Default bar type for streaming: 1-min bars
        bar_type = BarType.from_str(f"{instrument_id}-1-MINUTE-LAST-EXTERNAL")
        ts_init = self._clock.timestamp_ns()
        nautilus_bar = parse_bar(bar, instrument, bar_type, ts_init)
        self._handle_data(nautilus_bar)

    def _on_crypto_bar(self, bar: Any) -> None:
        self._on_stock_bar(bar)

    # -- HELPERS ------------------------------------------------------------------------------------

    def _is_crypto(self, instrument_id: InstrumentId) -> bool:
        """Check if an instrument is a crypto asset."""
        alpaca_asset = self.instrument_provider.get_alpaca_asset(instrument_id)
        if alpaca_asset is not None:
            asset_class = str(getattr(alpaca_asset, "asset_class", "")).lower().replace(" ", "_")
            return asset_class == "crypto"
        # Fallback: check symbol pattern (contains /)
        return "/" in instrument_id.symbol.value

    @staticmethod
    def _bar_type_to_timeframe(bar_type: BarType) -> TimeFrame:
        """Convert a Nautilus BarType aggregation to an Alpaca TimeFrame."""
        spec = bar_type.spec
        step = spec.step

        if spec.aggregation == BarAggregation.MINUTE:
            return TimeFrame(step, TimeFrameUnit.Minute)
        elif spec.aggregation == BarAggregation.HOUR:
            return TimeFrame(step, TimeFrameUnit.Hour)
        elif spec.aggregation == BarAggregation.DAY:
            return TimeFrame(step, TimeFrameUnit.Day)
        elif spec.aggregation == BarAggregation.WEEK:
            return TimeFrame(step, TimeFrameUnit.Week)
        elif spec.aggregation == BarAggregation.MONTH:
            return TimeFrame(step, TimeFrameUnit.Month)
        else:
            raise ValueError(
                f"Unsupported bar aggregation for Alpaca: {spec.aggregation}",
            )
