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

import pytest

from nautilus_trader.adapters.alpaca.enums import alpaca_liquidity_side
from nautilus_trader.adapters.alpaca.enums import alpaca_order_side_to_nautilus
from nautilus_trader.adapters.alpaca.enums import alpaca_order_status_to_nautilus
from nautilus_trader.adapters.alpaca.enums import alpaca_order_type_to_nautilus
from nautilus_trader.adapters.alpaca.enums import alpaca_tif_to_nautilus
from nautilus_trader.adapters.alpaca.enums import nautilus_order_side_to_alpaca
from nautilus_trader.adapters.alpaca.enums import nautilus_order_type_to_alpaca
from nautilus_trader.adapters.alpaca.enums import nautilus_tif_to_alpaca
from nautilus_trader.model.enums import LiquiditySide
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.enums import OrderStatus
from nautilus_trader.model.enums import OrderType
from nautilus_trader.model.enums import TimeInForce


class TestOrderSideMapping:
    def test_buy(self) -> None:
        assert alpaca_order_side_to_nautilus("buy") == OrderSide.BUY
        assert nautilus_order_side_to_alpaca(OrderSide.BUY) == "buy"

    def test_sell(self) -> None:
        assert alpaca_order_side_to_nautilus("sell") == OrderSide.SELL
        assert nautilus_order_side_to_alpaca(OrderSide.SELL) == "sell"

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            alpaca_order_side_to_nautilus("invalid")


class TestOrderTypeMapping:
    def test_market(self) -> None:
        assert alpaca_order_type_to_nautilus("market") == OrderType.MARKET
        assert nautilus_order_type_to_alpaca(OrderType.MARKET) == "market"

    def test_limit(self) -> None:
        assert alpaca_order_type_to_nautilus("limit") == OrderType.LIMIT
        assert nautilus_order_type_to_alpaca(OrderType.LIMIT) == "limit"

    def test_stop(self) -> None:
        assert alpaca_order_type_to_nautilus("stop") == OrderType.STOP_MARKET
        assert nautilus_order_type_to_alpaca(OrderType.STOP_MARKET) == "stop"

    def test_stop_limit(self) -> None:
        assert alpaca_order_type_to_nautilus("stop_limit") == OrderType.STOP_LIMIT
        assert nautilus_order_type_to_alpaca(OrderType.STOP_LIMIT) == "stop_limit"

    def test_trailing_stop(self) -> None:
        assert alpaca_order_type_to_nautilus("trailing_stop") == OrderType.TRAILING_STOP_MARKET
        assert nautilus_order_type_to_alpaca(OrderType.TRAILING_STOP_MARKET) == "trailing_stop"

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            alpaca_order_type_to_nautilus("invalid")


class TestTimeInForceMapping:
    def test_day(self) -> None:
        assert alpaca_tif_to_nautilus("day") == TimeInForce.DAY
        assert nautilus_tif_to_alpaca(TimeInForce.DAY) == "day"

    def test_gtc(self) -> None:
        assert alpaca_tif_to_nautilus("gtc") == TimeInForce.GTC
        assert nautilus_tif_to_alpaca(TimeInForce.GTC) == "gtc"

    def test_ioc(self) -> None:
        assert alpaca_tif_to_nautilus("ioc") == TimeInForce.IOC
        assert nautilus_tif_to_alpaca(TimeInForce.IOC) == "ioc"

    def test_fok(self) -> None:
        assert alpaca_tif_to_nautilus("fok") == TimeInForce.FOK
        assert nautilus_tif_to_alpaca(TimeInForce.FOK) == "fok"

    def test_opg(self) -> None:
        assert alpaca_tif_to_nautilus("opg") == TimeInForce.AT_THE_OPEN
        assert nautilus_tif_to_alpaca(TimeInForce.AT_THE_OPEN) == "opg"

    def test_cls(self) -> None:
        assert alpaca_tif_to_nautilus("cls") == TimeInForce.AT_THE_CLOSE
        assert nautilus_tif_to_alpaca(TimeInForce.AT_THE_CLOSE) == "cls"

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            alpaca_tif_to_nautilus("invalid")


class TestOrderStatusMapping:
    def test_new(self) -> None:
        assert alpaca_order_status_to_nautilus("new") == OrderStatus.ACCEPTED

    def test_filled(self) -> None:
        assert alpaca_order_status_to_nautilus("filled") == OrderStatus.FILLED

    def test_partially_filled(self) -> None:
        assert alpaca_order_status_to_nautilus("partially_filled") == OrderStatus.PARTIALLY_FILLED

    def test_canceled(self) -> None:
        assert alpaca_order_status_to_nautilus("canceled") == OrderStatus.CANCELED

    def test_expired(self) -> None:
        assert alpaca_order_status_to_nautilus("expired") == OrderStatus.EXPIRED

    def test_rejected(self) -> None:
        assert alpaca_order_status_to_nautilus("rejected") == OrderStatus.REJECTED

    def test_pending_new(self) -> None:
        assert alpaca_order_status_to_nautilus("pending_new") == OrderStatus.SUBMITTED

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            alpaca_order_status_to_nautilus("invalid")


class TestLiquiditySide:
    def test_taker(self) -> None:
        assert alpaca_liquidity_side("T") == LiquiditySide.TAKER
        assert alpaca_liquidity_side("TAKER") == LiquiditySide.TAKER

    def test_maker(self) -> None:
        assert alpaca_liquidity_side("M") == LiquiditySide.MAKER
        assert alpaca_liquidity_side("MAKER") == LiquiditySide.MAKER

    def test_none(self) -> None:
        assert alpaca_liquidity_side(None) == LiquiditySide.NO_LIQUIDITY_SIDE

    def test_unknown(self) -> None:
        assert alpaca_liquidity_side("unknown") == LiquiditySide.NO_LIQUIDITY_SIDE
