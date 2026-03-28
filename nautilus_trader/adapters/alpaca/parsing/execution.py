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

from decimal import Decimal
from typing import Any

from nautilus_trader.adapters.alpaca.enums import alpaca_liquidity_side
from nautilus_trader.adapters.alpaca.enums import alpaca_order_side_to_nautilus
from nautilus_trader.adapters.alpaca.enums import alpaca_order_status_to_nautilus
from nautilus_trader.adapters.alpaca.enums import alpaca_order_type_to_nautilus
from nautilus_trader.adapters.alpaca.enums import alpaca_tif_to_nautilus
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.execution.reports import FillReport
from nautilus_trader.execution.reports import OrderStatusReport
from nautilus_trader.execution.reports import PositionStatusReport
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.enums import ContingencyType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.enums import OrderStatus
from nautilus_trader.model.enums import OrderType
from nautilus_trader.model.enums import PositionSide
from nautilus_trader.model.enums import TimeInForce
from nautilus_trader.model.enums import TrailingOffsetType
from nautilus_trader.model.enums import TriggerType
from nautilus_trader.model.identifiers import AccountId
from nautilus_trader.model.identifiers import ClientOrderId
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import PositionId
from nautilus_trader.model.identifiers import TradeId
from nautilus_trader.model.identifiers import VenueOrderId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Money
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity


def _ts_to_nanos(dt: Any) -> int:
    """Convert a datetime object to UNIX nanoseconds."""
    if dt is None:
        return 0
    if hasattr(dt, "timestamp"):
        return int(dt.timestamp() * 1_000_000_000)
    return int(dt)


def parse_order_status_report(
    alpaca_order: Any,
    account_id: AccountId,
    instrument_id: InstrumentId,
    instrument: Instrument | None,
    ts_init: int,
) -> OrderStatusReport:
    """
    Parse an Alpaca order into a Nautilus ``OrderStatusReport``.

    Parameters
    ----------
    alpaca_order : alpaca.trading.models.Order
        The Alpaca order object.
    account_id : AccountId
        The Nautilus account ID.
    instrument_id : InstrumentId
        The Nautilus instrument ID.
    instrument : Instrument or None
        The Nautilus instrument for precision (if available).
    ts_init : int
        The UNIX timestamp (nanoseconds) for initialization.

    Returns
    -------
    OrderStatusReport

    """
    order_id = str(alpaca_order.id)
    client_order_id_str = getattr(alpaca_order, "client_order_id", None)
    order_side = alpaca_order_side_to_nautilus(str(alpaca_order.side))
    order_type = alpaca_order_type_to_nautilus(str(alpaca_order.type))
    tif = alpaca_tif_to_nautilus(str(alpaca_order.time_in_force))
    status = alpaca_order_status_to_nautilus(str(alpaca_order.status))

    qty_str = str(alpaca_order.qty) if alpaca_order.qty else "0"
    filled_str = str(alpaca_order.filled_qty) if alpaca_order.filled_qty else "0"

    if instrument is not None:
        quantity = instrument.make_qty(float(qty_str))
        filled_qty = instrument.make_qty(float(filled_str))
    else:
        quantity = Quantity.from_str(qty_str)
        filled_qty = Quantity.from_str(filled_str)

    # Price fields
    price = None
    trigger_price = None
    trailing_offset = None
    trailing_offset_type = None

    if order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT):
        limit_price = getattr(alpaca_order, "limit_price", None)
        if limit_price is not None:
            if instrument is not None:
                price = instrument.make_price(float(limit_price))
            else:
                price = Price.from_str(str(limit_price))

    if order_type in (OrderType.STOP_MARKET, OrderType.STOP_LIMIT):
        stop_price = getattr(alpaca_order, "stop_price", None)
        if stop_price is not None:
            if instrument is not None:
                trigger_price = instrument.make_price(float(stop_price))
            else:
                trigger_price = Price.from_str(str(stop_price))

    if order_type == OrderType.TRAILING_STOP_MARKET:
        trail_price = getattr(alpaca_order, "trail_price", None)
        trail_percent = getattr(alpaca_order, "trail_percent", None)
        if trail_price is not None:
            trailing_offset = Decimal(str(trail_price))
            trailing_offset_type = TrailingOffsetType.PRICE
        elif trail_percent is not None:
            trailing_offset = Decimal(str(trail_percent))
            trailing_offset_type = TrailingOffsetType.BASIS_POINTS

    # Average fill price
    avg_px = None
    avg_fill_price = getattr(alpaca_order, "filled_avg_price", None)
    if avg_fill_price is not None:
        avg_px = Decimal(str(avg_fill_price))

    # Timestamps
    ts_accepted = _ts_to_nanos(getattr(alpaca_order, "submitted_at", None)) or ts_init
    ts_last = _ts_to_nanos(getattr(alpaca_order, "updated_at", None)) or ts_init

    return OrderStatusReport(
        account_id=account_id,
        instrument_id=instrument_id,
        venue_order_id=VenueOrderId(order_id),
        order_side=order_side,
        order_type=order_type,
        time_in_force=tif,
        order_status=status,
        quantity=quantity,
        filled_qty=filled_qty,
        report_id=UUID4(),
        ts_accepted=ts_accepted,
        ts_last=ts_last,
        ts_init=ts_init,
        client_order_id=ClientOrderId(client_order_id_str) if client_order_id_str else None,
        price=price,
        trigger_price=trigger_price,
        trailing_offset=trailing_offset,
        trailing_offset_type=trailing_offset_type,
        avg_px=avg_px,
    )


def parse_fill_report(
    alpaca_order: Any,
    account_id: AccountId,
    instrument_id: InstrumentId,
    instrument: Instrument | None,
    ts_init: int,
) -> FillReport | None:
    """
    Parse an Alpaca order with fills into a Nautilus ``FillReport``.

    Returns ``None`` if the order has no fills.

    """
    filled_qty_raw = getattr(alpaca_order, "filled_qty", None)
    if filled_qty_raw is None or str(filled_qty_raw) == "0":
        return None

    filled_avg_price = getattr(alpaca_order, "filled_avg_price", None)
    if filled_avg_price is None:
        return None

    order_id = str(alpaca_order.id)
    order_side = alpaca_order_side_to_nautilus(str(alpaca_order.side))
    client_order_id_str = getattr(alpaca_order, "client_order_id", None)

    if instrument is not None:
        last_qty = instrument.make_qty(float(str(filled_qty_raw)))
        last_px = instrument.make_price(float(str(filled_avg_price)))
    else:
        last_qty = Quantity.from_str(str(filled_qty_raw))
        last_px = Price.from_str(str(filled_avg_price))

    ts_event = _ts_to_nanos(getattr(alpaca_order, "filled_at", None)) or ts_init

    return FillReport(
        account_id=account_id,
        instrument_id=instrument_id,
        venue_order_id=VenueOrderId(order_id),
        trade_id=TradeId(order_id),
        order_side=order_side,
        last_qty=last_qty,
        last_px=last_px,
        commission=Money(0, USD),
        liquidity_side=alpaca_liquidity_side(None),
        report_id=UUID4(),
        ts_event=ts_event,
        ts_init=ts_init,
        client_order_id=ClientOrderId(client_order_id_str) if client_order_id_str else None,
    )


def parse_position_status_report(
    alpaca_position: Any,
    account_id: AccountId,
    instrument_id: InstrumentId,
    instrument: Instrument | None,
    ts_init: int,
) -> PositionStatusReport:
    """
    Parse an Alpaca position into a Nautilus ``PositionStatusReport``.

    """
    qty_raw = getattr(alpaca_position, "qty", "0")
    qty_float = float(str(qty_raw))

    if qty_float > 0:
        position_side = PositionSide.LONG
    elif qty_float < 0:
        position_side = PositionSide.SHORT
    else:
        position_side = PositionSide.FLAT

    abs_qty = abs(qty_float)
    if instrument is not None:
        quantity = instrument.make_qty(abs_qty)
    else:
        quantity = Quantity.from_str(str(abs_qty))

    avg_entry = getattr(alpaca_position, "avg_entry_price", None)
    avg_px_open = Decimal(str(avg_entry)) if avg_entry is not None else None

    return PositionStatusReport(
        account_id=account_id,
        instrument_id=instrument_id,
        position_side=position_side,
        quantity=quantity,
        report_id=UUID4(),
        ts_last=ts_init,
        ts_init=ts_init,
        avg_px_open=avg_px_open,
    )
