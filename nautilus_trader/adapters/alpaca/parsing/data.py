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

from typing import Any

from nautilus_trader.model.data import Bar
from nautilus_trader.model.data import BarType
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.data import TradeTick
from nautilus_trader.model.enums import AggressorSide
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import TradeId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity


def _ts_to_nanos(dt: Any) -> int:
    """Convert a datetime object to UNIX nanoseconds."""
    if dt is None:
        return 0
    if hasattr(dt, "timestamp"):
        return int(dt.timestamp() * 1_000_000_000)
    return int(dt)


def parse_quote_tick(
    alpaca_quote: Any,
    instrument: Instrument,
    ts_init: int,
) -> QuoteTick:
    """
    Parse an Alpaca quote into a Nautilus ``QuoteTick``.

    Parameters
    ----------
    alpaca_quote : alpaca.data.models.Quote
        The Alpaca quote object.
    instrument : Instrument
        The Nautilus instrument for precision.
    ts_init : int
        The UNIX timestamp (nanoseconds) for initialization.

    Returns
    -------
    QuoteTick

    """
    bid_price = getattr(alpaca_quote, "bid_price", 0) or 0
    ask_price = getattr(alpaca_quote, "ask_price", 0) or 0
    bid_size = getattr(alpaca_quote, "bid_size", 0) or 0
    ask_size = getattr(alpaca_quote, "ask_size", 0) or 0
    ts_event = _ts_to_nanos(getattr(alpaca_quote, "timestamp", None))

    return QuoteTick(
        instrument_id=instrument.id,
        bid_price=instrument.make_price(bid_price),
        ask_price=instrument.make_price(ask_price),
        bid_size=instrument.make_qty(bid_size),
        ask_size=instrument.make_qty(ask_size),
        ts_event=ts_event or ts_init,
        ts_init=ts_init,
    )


def parse_trade_tick(
    alpaca_trade: Any,
    instrument: Instrument,
    ts_init: int,
) -> TradeTick:
    """
    Parse an Alpaca trade into a Nautilus ``TradeTick``.

    Parameters
    ----------
    alpaca_trade : alpaca.data.models.Trade
        The Alpaca trade object.
    instrument : Instrument
        The Nautilus instrument for precision.
    ts_init : int
        The UNIX timestamp (nanoseconds) for initialization.

    Returns
    -------
    TradeTick

    """
    price = getattr(alpaca_trade, "price", 0) or 0
    size = getattr(alpaca_trade, "size", 0) or 0
    trade_id = str(getattr(alpaca_trade, "id", "")) or str(
        _ts_to_nanos(getattr(alpaca_trade, "timestamp", None)),
    )
    ts_event = _ts_to_nanos(getattr(alpaca_trade, "timestamp", None))

    return TradeTick(
        instrument_id=instrument.id,
        price=instrument.make_price(price),
        size=instrument.make_qty(max(size, instrument.size_increment)),
        aggressor_side=AggressorSide.NO_AGGRESSOR,
        trade_id=TradeId(trade_id),
        ts_event=ts_event or ts_init,
        ts_init=ts_init,
    )


def parse_bar(
    alpaca_bar: Any,
    instrument: Instrument,
    bar_type: BarType,
    ts_init: int,
) -> Bar:
    """
    Parse an Alpaca bar into a Nautilus ``Bar``.

    Parameters
    ----------
    alpaca_bar : alpaca.data.models.Bar
        The Alpaca bar object.
    instrument : Instrument
        The Nautilus instrument for precision.
    bar_type : BarType
        The Nautilus bar type.
    ts_init : int
        The UNIX timestamp (nanoseconds) for initialization.

    Returns
    -------
    Bar

    """
    open_price = getattr(alpaca_bar, "open", 0) or 0
    high_price = getattr(alpaca_bar, "high", 0) or 0
    low_price = getattr(alpaca_bar, "low", 0) or 0
    close_price = getattr(alpaca_bar, "close", 0) or 0
    volume = getattr(alpaca_bar, "volume", 0) or 0
    ts_event = _ts_to_nanos(getattr(alpaca_bar, "timestamp", None))

    return Bar(
        bar_type=bar_type,
        open=instrument.make_price(open_price),
        high=instrument.make_price(high_price),
        low=instrument.make_price(low_price),
        close=instrument.make_price(close_price),
        volume=instrument.make_qty(volume),
        ts_event=ts_event or ts_init,
        ts_init=ts_init,
    )
