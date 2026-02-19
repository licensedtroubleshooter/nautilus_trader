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
from typing import TYPE_CHECKING, Any, Callable

from alpaca.data.live import CryptoDataStream
from alpaca.data.live import StockDataStream
from alpaca.trading.stream import TradingStream


class AlpacaMarketDataStream:
    """
    Manages Alpaca WebSocket market data streams for stocks and crypto.

    Parameters
    ----------
    api_key : str
        The Alpaca API key.
    api_secret : str
        The Alpaca API secret.
    feed : str
        The data feed: ``"iex"`` or ``"sip"``.

    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        feed: str = "iex",
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._feed = feed
        self._stock_stream: StockDataStream | None = None
        self._crypto_stream: CryptoDataStream | None = None
        self._stock_stream_task: asyncio.Task | None = None
        self._crypto_stream_task: asyncio.Task | None = None
        self._subscribed_stock_quotes: set[str] = set()
        self._subscribed_stock_trades: set[str] = set()
        self._subscribed_stock_bars: set[str] = set()
        self._subscribed_crypto_quotes: set[str] = set()
        self._subscribed_crypto_trades: set[str] = set()
        self._subscribed_crypto_bars: set[str] = set()

    def _ensure_stock_stream(self) -> StockDataStream:
        if self._stock_stream is None:
            self._stock_stream = StockDataStream(
                self._api_key,
                self._api_secret,
                feed=self._feed,
            )
        return self._stock_stream

    def _ensure_crypto_stream(self) -> CryptoDataStream:
        if self._crypto_stream is None:
            self._crypto_stream = CryptoDataStream(
                self._api_key,
                self._api_secret,
            )
        return self._crypto_stream

    async def start_stock_stream(self) -> None:
        """Start the stock data stream in a background task."""
        if self._stock_stream is not None and self._stock_stream_task is None:
            self._stock_stream_task = asyncio.get_event_loop().create_task(
                self._run_stock_stream(),
            )

    async def start_crypto_stream(self) -> None:
        """Start the crypto data stream in a background task."""
        if self._crypto_stream is not None and self._crypto_stream_task is None:
            self._crypto_stream_task = asyncio.get_event_loop().create_task(
                self._run_crypto_stream(),
            )

    async def _run_stock_stream(self) -> None:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._stock_stream.run,
            )
        except Exception:
            pass  # Stream disconnected

    async def _run_crypto_stream(self) -> None:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._crypto_stream.run,
            )
        except Exception:
            pass  # Stream disconnected

    def subscribe_stock_quotes(
        self,
        handler: Callable,
        *symbols: str,
    ) -> None:
        """Subscribe to stock quote updates."""
        stream = self._ensure_stock_stream()
        stream.subscribe_quotes(handler, *symbols)
        self._subscribed_stock_quotes.update(symbols)

    def subscribe_stock_trades(
        self,
        handler: Callable,
        *symbols: str,
    ) -> None:
        """Subscribe to stock trade updates."""
        stream = self._ensure_stock_stream()
        stream.subscribe_trades(handler, *symbols)
        self._subscribed_stock_trades.update(symbols)

    def subscribe_stock_bars(
        self,
        handler: Callable,
        *symbols: str,
    ) -> None:
        """Subscribe to stock bar updates."""
        stream = self._ensure_stock_stream()
        stream.subscribe_bars(handler, *symbols)
        self._subscribed_stock_bars.update(symbols)

    def subscribe_crypto_quotes(
        self,
        handler: Callable,
        *symbols: str,
    ) -> None:
        """Subscribe to crypto quote updates."""
        stream = self._ensure_crypto_stream()
        stream.subscribe_quotes(handler, *symbols)
        self._subscribed_crypto_quotes.update(symbols)

    def subscribe_crypto_trades(
        self,
        handler: Callable,
        *symbols: str,
    ) -> None:
        """Subscribe to crypto trade updates."""
        stream = self._ensure_crypto_stream()
        stream.subscribe_trades(handler, *symbols)
        self._subscribed_crypto_trades.update(symbols)

    def subscribe_crypto_bars(
        self,
        handler: Callable,
        *symbols: str,
    ) -> None:
        """Subscribe to crypto bar updates."""
        stream = self._ensure_crypto_stream()
        stream.subscribe_bars(handler, *symbols)
        self._subscribed_crypto_bars.update(symbols)

    async def close(self) -> None:
        """Close all streams."""
        if self._stock_stream_task is not None:
            self._stock_stream_task.cancel()
            self._stock_stream_task = None
        if self._crypto_stream_task is not None:
            self._crypto_stream_task.cancel()
            self._crypto_stream_task = None
        if self._stock_stream is not None:
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._stock_stream.stop,
                )
            except Exception:
                pass
            self._stock_stream = None
        if self._crypto_stream is not None:
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._crypto_stream.stop,
                )
            except Exception:
                pass
            self._crypto_stream = None


class AlpacaTradingStream:
    """
    Manages the Alpaca WebSocket trading/order updates stream.

    Parameters
    ----------
    api_key : str
        The Alpaca API key.
    api_secret : str
        The Alpaca API secret.
    paper : bool
        If ``True``, connect to the paper trading stream.

    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        paper: bool = True,
    ) -> None:
        self._stream = TradingStream(
            api_key,
            api_secret,
            paper=paper,
        )
        self._task: asyncio.Task | None = None

    def subscribe_trade_updates(self, handler: Callable) -> None:
        """Subscribe to trade/order update events."""
        self._stream.subscribe_trade_updates(handler)

    async def start(self) -> None:
        """Start the trading stream in a background task."""
        if self._task is None:
            self._task = asyncio.get_event_loop().create_task(
                self._run(),
            )

    async def _run(self) -> None:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._stream.run,
            )
        except Exception:
            pass  # Stream disconnected

    async def close(self) -> None:
        """Close the trading stream."""
        if self._task is not None:
            self._task.cancel()
            self._task = None
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._stream.stop,
            )
        except Exception:
            pass
