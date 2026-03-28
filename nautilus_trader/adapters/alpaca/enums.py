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

from enum import Enum
from enum import unique

from nautilus_trader.model.enums import LiquiditySide
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.enums import OrderStatus
from nautilus_trader.model.enums import OrderType
from nautilus_trader.model.enums import TimeInForce


@unique
class AlpacaAssetClass(Enum):
    """Alpaca asset class types."""

    US_EQUITY = "us_equity"
    CRYPTO = "crypto"


@unique
class AlpacaOrderClass(Enum):
    """Alpaca advanced order class types."""

    SIMPLE = "simple"
    BRACKET = "bracket"
    OCO = "oco"
    OTO = "oto"


# ---------------------------------------------------------------------------
# Alpaca -> Nautilus mappings
# ---------------------------------------------------------------------------

ALPACA_ORDER_SIDE_TO_NAUTILUS: dict[str, OrderSide] = {
    "buy": OrderSide.BUY,
    "sell": OrderSide.SELL,
}

NAUTILUS_ORDER_SIDE_TO_ALPACA: dict[OrderSide, str] = {
    v: k for k, v in ALPACA_ORDER_SIDE_TO_NAUTILUS.items()
}

ALPACA_ORDER_TYPE_TO_NAUTILUS: dict[str, OrderType] = {
    "market": OrderType.MARKET,
    "limit": OrderType.LIMIT,
    "stop": OrderType.STOP_MARKET,
    "stop_limit": OrderType.STOP_LIMIT,
    "trailing_stop": OrderType.TRAILING_STOP_MARKET,
}

NAUTILUS_ORDER_TYPE_TO_ALPACA: dict[OrderType, str] = {
    v: k for k, v in ALPACA_ORDER_TYPE_TO_NAUTILUS.items()
}

ALPACA_TIF_TO_NAUTILUS: dict[str, TimeInForce] = {
    "day": TimeInForce.DAY,
    "gtc": TimeInForce.GTC,
    "opg": TimeInForce.AT_THE_OPEN,
    "cls": TimeInForce.AT_THE_CLOSE,
    "ioc": TimeInForce.IOC,
    "fok": TimeInForce.FOK,
}

NAUTILUS_TIF_TO_ALPACA: dict[TimeInForce, str] = {
    v: k for k, v in ALPACA_TIF_TO_NAUTILUS.items()
}

ALPACA_ORDER_STATUS_TO_NAUTILUS: dict[str, OrderStatus] = {
    "new": OrderStatus.ACCEPTED,
    "accepted": OrderStatus.ACCEPTED,
    "partially_filled": OrderStatus.PARTIALLY_FILLED,
    "filled": OrderStatus.FILLED,
    "done_for_day": OrderStatus.FILLED,
    "canceled": OrderStatus.CANCELED,
    "expired": OrderStatus.EXPIRED,
    "replaced": OrderStatus.ACCEPTED,
    "rejected": OrderStatus.REJECTED,
    "pending_new": OrderStatus.SUBMITTED,
    "pending_cancel": OrderStatus.PENDING_CANCEL,
    "pending_replace": OrderStatus.PENDING_UPDATE,
    "stopped": OrderStatus.ACCEPTED,
    "suspended": OrderStatus.ACCEPTED,
    "calculated": OrderStatus.ACCEPTED,
    "held": OrderStatus.ACCEPTED,
}

# Alpaca trade_update event types that map to Nautilus event generation
ALPACA_TRADE_EVENT_FILL = "fill"
ALPACA_TRADE_EVENT_PARTIAL_FILL = "partial_fill"
ALPACA_TRADE_EVENT_NEW = "new"
ALPACA_TRADE_EVENT_CANCELED = "canceled"
ALPACA_TRADE_EVENT_EXPIRED = "expired"
ALPACA_TRADE_EVENT_REJECTED = "rejected"
ALPACA_TRADE_EVENT_REPLACED = "replaced"
ALPACA_TRADE_EVENT_PENDING_NEW = "pending_new"
ALPACA_TRADE_EVENT_PENDING_CANCEL = "pending_cancel"
ALPACA_TRADE_EVENT_PENDING_REPLACE = "pending_replace"


def alpaca_order_side_to_nautilus(side: str) -> OrderSide:
    """Convert Alpaca order side string to Nautilus OrderSide."""
    try:
        return ALPACA_ORDER_SIDE_TO_NAUTILUS[side.lower()]
    except KeyError:
        raise ValueError(f"Unknown Alpaca order side: {side}")


def nautilus_order_side_to_alpaca(side: OrderSide) -> str:
    """Convert Nautilus OrderSide to Alpaca order side string."""
    try:
        return NAUTILUS_ORDER_SIDE_TO_ALPACA[side]
    except KeyError:
        raise ValueError(f"Cannot convert OrderSide to Alpaca: {side}")


def alpaca_order_type_to_nautilus(order_type: str) -> OrderType:
    """Convert Alpaca order type string to Nautilus OrderType."""
    try:
        return ALPACA_ORDER_TYPE_TO_NAUTILUS[order_type.lower()]
    except KeyError:
        raise ValueError(f"Unknown Alpaca order type: {order_type}")


def nautilus_order_type_to_alpaca(order_type: OrderType) -> str:
    """Convert Nautilus OrderType to Alpaca order type string."""
    try:
        return NAUTILUS_ORDER_TYPE_TO_ALPACA[order_type]
    except KeyError:
        raise ValueError(f"Cannot convert OrderType to Alpaca: {order_type}")


def alpaca_tif_to_nautilus(tif: str) -> TimeInForce:
    """Convert Alpaca time-in-force string to Nautilus TimeInForce."""
    try:
        return ALPACA_TIF_TO_NAUTILUS[tif.lower()]
    except KeyError:
        raise ValueError(f"Unknown Alpaca time in force: {tif}")


def nautilus_tif_to_alpaca(tif: TimeInForce) -> str:
    """Convert Nautilus TimeInForce to Alpaca time-in-force string."""
    try:
        return NAUTILUS_TIF_TO_ALPACA[tif]
    except KeyError:
        raise ValueError(f"Cannot convert TimeInForce to Alpaca: {tif}")


def alpaca_order_status_to_nautilus(status: str) -> OrderStatus:
    """Convert Alpaca order status string to Nautilus OrderStatus."""
    try:
        return ALPACA_ORDER_STATUS_TO_NAUTILUS[status.lower()]
    except KeyError:
        raise ValueError(f"Unknown Alpaca order status: {status}")


def alpaca_liquidity_side(liquidity: str | None) -> LiquiditySide:
    """Convert Alpaca liquidity indicator to Nautilus LiquiditySide."""
    if liquidity is None:
        return LiquiditySide.NO_LIQUIDITY_SIDE
    liquidity = liquidity.upper()
    if liquidity in ("T", "TAKER"):
        return LiquiditySide.TAKER
    if liquidity in ("M", "MAKER"):
        return LiquiditySide.MAKER
    return LiquiditySide.NO_LIQUIDITY_SIDE
