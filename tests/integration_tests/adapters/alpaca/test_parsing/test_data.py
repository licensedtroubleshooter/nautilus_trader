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

from datetime import datetime, timezone
from types import SimpleNamespace

from nautilus_trader.adapters.alpaca.constants import ALPACA_VENUE
from nautilus_trader.adapters.alpaca.parsing.data import parse_bar
from nautilus_trader.adapters.alpaca.parsing.data import parse_quote_tick
from nautilus_trader.adapters.alpaca.parsing.data import parse_trade_tick
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import Bar
from nautilus_trader.model.data import BarType
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.data import TradeTick
from nautilus_trader.model.enums import AggressorSide
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import Symbol
from nautilus_trader.model.instruments.equity import Equity
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity


def _make_equity_instrument() -> Equity:
    return Equity(
        instrument_id=InstrumentId(Symbol("AAPL"), ALPACA_VENUE),
        raw_symbol=Symbol("AAPL"),
        currency=USD,
        price_precision=2,
        price_increment=Price.from_str("0.01"),
        lot_size=Quantity.from_int(1),
        ts_event=0,
        ts_init=0,
    )


class TestParseQuoteTick:
    def test_basic_quote(self) -> None:
        instrument = _make_equity_instrument()
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        quote = SimpleNamespace(
            bid_price=150.25,
            ask_price=150.30,
            bid_size=100,
            ask_size=200,
            timestamp=ts,
            symbol="AAPL",
        )

        result = parse_quote_tick(quote, instrument, 1_000_000_000)

        assert isinstance(result, QuoteTick)
        assert result.instrument_id == instrument.id
        assert float(result.bid_price) == 150.25
        assert float(result.ask_price) == 150.30
        assert float(result.bid_size) == 100.0
        assert float(result.ask_size) == 200.0

    def test_quote_with_none_values(self) -> None:
        instrument = _make_equity_instrument()
        quote = SimpleNamespace(
            bid_price=None,
            ask_price=None,
            bid_size=None,
            ask_size=None,
            timestamp=None,
            symbol="AAPL",
        )

        result = parse_quote_tick(quote, instrument, 1_000_000_000)
        assert isinstance(result, QuoteTick)


class TestParseTradeTick:
    def test_basic_trade(self) -> None:
        instrument = _make_equity_instrument()
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        trade = SimpleNamespace(
            price=150.50,
            size=50,
            id="12345",
            timestamp=ts,
            symbol="AAPL",
        )

        result = parse_trade_tick(trade, instrument, 1_000_000_000)

        assert isinstance(result, TradeTick)
        assert result.instrument_id == instrument.id
        assert float(result.price) == 150.50
        assert float(result.size) == 50.0
        assert result.aggressor_side == AggressorSide.NO_AGGRESSOR
        assert result.trade_id.value == "12345"


class TestParseBar:
    def test_basic_bar(self) -> None:
        instrument = _make_equity_instrument()
        bar_type = BarType.from_str(f"{instrument.id}-1-MINUTE-LAST-EXTERNAL")
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        alpaca_bar = SimpleNamespace(
            open=150.00,
            high=151.50,
            low=149.50,
            close=151.00,
            volume=10000,
            timestamp=ts,
            symbol="AAPL",
        )

        result = parse_bar(alpaca_bar, instrument, bar_type, 1_000_000_000)

        assert isinstance(result, Bar)
        assert result.bar_type == bar_type
        assert float(result.open) == 150.00
        assert float(result.high) == 151.50
        assert float(result.low) == 149.50
        assert float(result.close) == 151.00
        assert float(result.volume) == 10000.0
