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
from nautilus_trader.adapters.alpaca.parsing.execution import parse_fill_report
from nautilus_trader.adapters.alpaca.parsing.execution import parse_order_status_report
from nautilus_trader.adapters.alpaca.parsing.execution import parse_position_status_report
from nautilus_trader.execution.reports import FillReport
from nautilus_trader.execution.reports import OrderStatusReport
from nautilus_trader.execution.reports import PositionStatusReport
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.enums import OrderStatus
from nautilus_trader.model.enums import OrderType
from nautilus_trader.model.enums import PositionSide
from nautilus_trader.model.enums import TimeInForce
from nautilus_trader.model.identifiers import AccountId
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import Symbol
from nautilus_trader.model.instruments.equity import Equity
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity


def _make_instrument() -> Equity:
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


ACCOUNT_ID = AccountId("ALPACA-test-account")


def _make_alpaca_order(**kwargs) -> SimpleNamespace:
    defaults = {
        "id": "order-123-abc",
        "client_order_id": "O-20240115-001",
        "symbol": "AAPL",
        "side": "buy",
        "type": "limit",
        "time_in_force": "day",
        "status": "new",
        "qty": "100",
        "filled_qty": "0",
        "limit_price": "150.50",
        "stop_price": None,
        "trail_price": None,
        "trail_percent": None,
        "filled_avg_price": None,
        "submitted_at": datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 15, 10, 0, 1, tzinfo=timezone.utc),
        "filled_at": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestParseOrderStatusReport:
    def test_new_limit_order(self) -> None:
        instrument = _make_instrument()
        order = _make_alpaca_order()
        instrument_id = InstrumentId(Symbol("AAPL"), ALPACA_VENUE)

        report = parse_order_status_report(
            alpaca_order=order,
            account_id=ACCOUNT_ID,
            instrument_id=instrument_id,
            instrument=instrument,
            ts_init=1_000_000_000,
        )

        assert isinstance(report, OrderStatusReport)
        assert report.account_id == ACCOUNT_ID
        assert report.instrument_id == instrument_id
        assert report.venue_order_id.value == "order-123-abc"
        assert report.order_side == OrderSide.BUY
        assert report.order_type == OrderType.LIMIT
        assert report.time_in_force == TimeInForce.DAY
        assert report.order_status == OrderStatus.ACCEPTED

    def test_filled_market_order(self) -> None:
        instrument = _make_instrument()
        order = _make_alpaca_order(
            type="market",
            status="filled",
            filled_qty="100",
            filled_avg_price="150.75",
            limit_price=None,
            filled_at=datetime(2024, 1, 15, 10, 0, 2, tzinfo=timezone.utc),
        )
        instrument_id = InstrumentId(Symbol("AAPL"), ALPACA_VENUE)

        report = parse_order_status_report(
            alpaca_order=order,
            account_id=ACCOUNT_ID,
            instrument_id=instrument_id,
            instrument=instrument,
            ts_init=1_000_000_000,
        )

        assert report.order_type == OrderType.MARKET
        assert report.order_status == OrderStatus.FILLED
        assert float(report.filled_qty) == 100.0

    def test_sell_stop_order(self) -> None:
        instrument = _make_instrument()
        order = _make_alpaca_order(
            side="sell",
            type="stop",
            status="new",
            limit_price=None,
            stop_price="148.00",
        )
        instrument_id = InstrumentId(Symbol("AAPL"), ALPACA_VENUE)

        report = parse_order_status_report(
            alpaca_order=order,
            account_id=ACCOUNT_ID,
            instrument_id=instrument_id,
            instrument=instrument,
            ts_init=1_000_000_000,
        )

        assert report.order_side == OrderSide.SELL
        assert report.order_type == OrderType.STOP_MARKET
        assert float(report.trigger_price) == 148.00


class TestParseFillReport:
    def test_filled_order(self) -> None:
        instrument = _make_instrument()
        order = _make_alpaca_order(
            status="filled",
            filled_qty="100",
            filled_avg_price="150.75",
            filled_at=datetime(2024, 1, 15, 10, 0, 2, tzinfo=timezone.utc),
        )
        instrument_id = InstrumentId(Symbol("AAPL"), ALPACA_VENUE)

        report = parse_fill_report(
            alpaca_order=order,
            account_id=ACCOUNT_ID,
            instrument_id=instrument_id,
            instrument=instrument,
            ts_init=1_000_000_000,
        )

        assert isinstance(report, FillReport)
        assert report.account_id == ACCOUNT_ID
        assert report.order_side == OrderSide.BUY
        assert float(report.last_qty) == 100.0
        assert float(report.last_px) == 150.75

    def test_unfilled_order_returns_none(self) -> None:
        order = _make_alpaca_order(filled_qty="0", filled_avg_price=None)
        instrument_id = InstrumentId(Symbol("AAPL"), ALPACA_VENUE)

        report = parse_fill_report(
            alpaca_order=order,
            account_id=ACCOUNT_ID,
            instrument_id=instrument_id,
            instrument=None,
            ts_init=1_000_000_000,
        )

        assert report is None


class TestParsePositionStatusReport:
    def test_long_position(self) -> None:
        instrument = _make_instrument()
        position = SimpleNamespace(
            symbol="AAPL",
            qty="100",
            avg_entry_price="150.00",
            side="long",
            market_value="15100.00",
            unrealized_pl="100.00",
        )
        instrument_id = InstrumentId(Symbol("AAPL"), ALPACA_VENUE)

        report = parse_position_status_report(
            alpaca_position=position,
            account_id=ACCOUNT_ID,
            instrument_id=instrument_id,
            instrument=instrument,
            ts_init=1_000_000_000,
        )

        assert isinstance(report, PositionStatusReport)
        assert report.position_side == PositionSide.LONG
        assert float(report.quantity) == 100.0

    def test_short_position(self) -> None:
        instrument = _make_instrument()
        position = SimpleNamespace(
            symbol="AAPL",
            qty="-50",
            avg_entry_price="155.00",
            side="short",
        )
        instrument_id = InstrumentId(Symbol("AAPL"), ALPACA_VENUE)

        report = parse_position_status_report(
            alpaca_position=position,
            account_id=ACCOUNT_ID,
            instrument_id=instrument_id,
            instrument=instrument,
            ts_init=1_000_000_000,
        )

        assert report.position_side == PositionSide.SHORT
        assert float(report.quantity) == 50.0

    def test_flat_position(self) -> None:
        instrument = _make_instrument()
        position = SimpleNamespace(
            symbol="AAPL",
            qty="0",
            avg_entry_price="0",
        )
        instrument_id = InstrumentId(Symbol("AAPL"), ALPACA_VENUE)

        report = parse_position_status_report(
            alpaca_position=position,
            account_id=ACCOUNT_ID,
            instrument_id=instrument_id,
            instrument=instrument,
            ts_init=1_000_000_000,
        )

        assert report.position_side == PositionSide.FLAT
