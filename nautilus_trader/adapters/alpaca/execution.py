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
from decimal import Decimal
from typing import Any

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide as AlpacaOrderSide
from alpaca.trading.enums import TimeInForce as AlpacaTIF
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.requests import LimitOrderRequest
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.requests import ReplaceOrderRequest
from alpaca.trading.requests import StopLimitOrderRequest
from alpaca.trading.requests import StopOrderRequest
from alpaca.trading.requests import TrailingStopOrderRequest

from nautilus_trader.adapters.alpaca.config import AlpacaExecClientConfig
from nautilus_trader.adapters.alpaca.constants import ALPACA_VENUE
from nautilus_trader.adapters.alpaca.enums import ALPACA_TRADE_EVENT_CANCELED
from nautilus_trader.adapters.alpaca.enums import ALPACA_TRADE_EVENT_EXPIRED
from nautilus_trader.adapters.alpaca.enums import ALPACA_TRADE_EVENT_FILL
from nautilus_trader.adapters.alpaca.enums import ALPACA_TRADE_EVENT_NEW
from nautilus_trader.adapters.alpaca.enums import ALPACA_TRADE_EVENT_PARTIAL_FILL
from nautilus_trader.adapters.alpaca.enums import ALPACA_TRADE_EVENT_REJECTED
from nautilus_trader.adapters.alpaca.enums import ALPACA_TRADE_EVENT_REPLACED
from nautilus_trader.adapters.alpaca.enums import nautilus_order_side_to_alpaca
from nautilus_trader.adapters.alpaca.enums import nautilus_tif_to_alpaca
from nautilus_trader.adapters.alpaca.parsing.execution import parse_fill_report
from nautilus_trader.adapters.alpaca.parsing.execution import parse_order_status_report
from nautilus_trader.adapters.alpaca.parsing.execution import parse_position_status_report
from nautilus_trader.adapters.alpaca.providers import AlpacaInstrumentProvider
from nautilus_trader.adapters.alpaca.websocket import AlpacaTradingStream
from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.clock import LiveClock
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.execution.messages import BatchCancelOrders
from nautilus_trader.execution.messages import CancelAllOrders
from nautilus_trader.execution.messages import CancelOrder
from nautilus_trader.execution.messages import GenerateFillReports
from nautilus_trader.execution.messages import GenerateOrderStatusReport
from nautilus_trader.execution.messages import GenerateOrderStatusReports
from nautilus_trader.execution.messages import GeneratePositionStatusReports
from nautilus_trader.execution.messages import ModifyOrder
from nautilus_trader.execution.messages import QueryAccount
from nautilus_trader.execution.messages import SubmitOrder
from nautilus_trader.execution.messages import SubmitOrderList
from nautilus_trader.execution.reports import ExecutionMassStatus
from nautilus_trader.execution.reports import FillReport
from nautilus_trader.execution.reports import OrderStatusReport
from nautilus_trader.execution.reports import PositionStatusReport
from nautilus_trader.live.execution_client import LiveExecutionClient
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.enums import LiquiditySide
from nautilus_trader.model.enums import OmsType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.enums import OrderType
from nautilus_trader.model.identifiers import AccountId
from nautilus_trader.model.identifiers import ClientId
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import TradeId
from nautilus_trader.model.identifiers import VenueOrderId
from nautilus_trader.model.objects import AccountBalance
from nautilus_trader.model.objects import MarginBalance
from nautilus_trader.model.objects import Money
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity
from nautilus_trader.model.orders import Order
from nautilus_trader.msgbus.bus import MessageBus


class AlpacaExecutionClient(LiveExecutionClient):
    """
    Provides an execution client for the Alpaca broker API.

    Parameters
    ----------
    loop : asyncio.AbstractEventLoop
        The event loop for the client.
    trading_client : TradingClient
        The Alpaca trading client (from alpaca-py).
    account_id : AccountId
        The Nautilus account ID.
    msgbus : MessageBus
        The message bus for the client.
    cache : Cache
        The cache for the client.
    clock : LiveClock
        The clock for the client.
    instrument_provider : AlpacaInstrumentProvider
        The instrument provider.
    config : AlpacaExecClientConfig
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
        trading_client: TradingClient,
        account_id: AccountId,
        msgbus: MessageBus,
        cache: Cache,
        clock: LiveClock,
        instrument_provider: AlpacaInstrumentProvider,
        config: AlpacaExecClientConfig,
        api_key: str,
        api_secret: str,
        name: str | None = None,
    ) -> None:
        client_id_str = name or ALPACA_VENUE.value
        super().__init__(
            loop=loop,
            client_id=ClientId(client_id_str),
            venue=ALPACA_VENUE,
            oms_type=OmsType.NETTING,
            instrument_provider=instrument_provider,
            account_type=AccountType.MARGIN,
            base_currency=USD,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
            config=config,
        )
        self._set_account_id(account_id)

        self._trading_client = trading_client
        self._api_key = api_key
        self._api_secret = api_secret
        self._config = config

        # Trading stream for order updates
        self._trading_stream = AlpacaTradingStream(
            api_key=api_key,
            api_secret=api_secret,
            paper=config.paper,
        )

    @property
    def instrument_provider(self) -> AlpacaInstrumentProvider:
        return self._instrument_provider  # type: ignore

    # -- CONNECTION ---------------------------------------------------------------------------------

    async def _connect(self) -> None:
        await self.instrument_provider.initialize()

        # Subscribe to trade updates
        self._trading_stream.subscribe_trade_updates(self._on_trade_update)
        await self._trading_stream.start()

        # Load initial account state
        await self._update_account_state()

        self._log.info("AlpacaExecutionClient connected")

    async def _disconnect(self) -> None:
        await self._trading_stream.close()
        self._log.info("AlpacaExecutionClient disconnected")

    # -- ACCOUNT ------------------------------------------------------------------------------------

    async def _update_account_state(self) -> None:
        """Fetch account state from Alpaca and generate AccountState event."""
        try:
            account = await asyncio.get_event_loop().run_in_executor(
                None,
                self._trading_client.get_account,
            )

            equity = float(str(account.equity))
            cash = float(str(account.cash))
            buying_power = float(str(account.buying_power))
            init_margin = float(str(getattr(account, "initial_margin", "0") or "0"))
            maint_margin = float(str(getattr(account, "maintenance_margin", "0") or "0"))

            total = Money(equity, USD)
            free = Money(buying_power, USD)
            locked = Money(max(equity - buying_power, 0), USD)

            balance = AccountBalance(
                total=total,
                free=free,
                locked=locked,
            )
            margin = MarginBalance(
                initial=Money(init_margin, USD),
                maintenance=Money(maint_margin, USD),
            )

            self.generate_account_state(
                balances=[balance],
                margins=[margin],
                reported=True,
                ts_event=self._clock.timestamp_ns(),
                info={
                    "equity": str(account.equity),
                    "cash": str(account.cash),
                    "buying_power": str(account.buying_power),
                    "portfolio_value": str(getattr(account, "portfolio_value", "")),
                    "pattern_day_trader": str(getattr(account, "pattern_day_trader", "")),
                },
            )
        except Exception as e:
            self._log.error(f"Failed to update account state: {e}")

    async def _query_account(self, command: QueryAccount) -> None:
        await self._update_account_state()

    # -- EXECUTION REPORTS --------------------------------------------------------------------------

    async def generate_order_status_report(
        self,
        command: GenerateOrderStatusReport,
    ) -> OrderStatusReport | None:
        try:
            order_id = str(command.venue_order_id) if command.venue_order_id else None
            if order_id is None:
                return None

            alpaca_order = await asyncio.get_event_loop().run_in_executor(
                None,
                self._trading_client.get_order_by_id,
                order_id,
            )

            instrument_id = self._resolve_instrument_id(alpaca_order)
            instrument = self.instrument_provider.find(instrument_id)

            return parse_order_status_report(
                alpaca_order=alpaca_order,
                account_id=self.account_id,
                instrument_id=instrument_id,
                instrument=instrument,
                ts_init=self._clock.timestamp_ns(),
            )
        except Exception as e:
            self._log.error(f"Failed to generate order status report: {e}")
            return None

    async def generate_order_status_reports(
        self,
        command: GenerateOrderStatusReports,
    ) -> list[OrderStatusReport]:
        reports: list[OrderStatusReport] = []
        try:
            status_filter = "open" if command.open_only else "all"
            request = GetOrdersRequest(status=status_filter)

            alpaca_orders = await asyncio.get_event_loop().run_in_executor(
                None,
                self._trading_client.get_orders,
                request,
            )

            ts_init = self._clock.timestamp_ns()
            for order in alpaca_orders:
                instrument_id = self._resolve_instrument_id(order)

                if command.instrument_id and instrument_id != command.instrument_id:
                    continue

                instrument = self.instrument_provider.find(instrument_id)
                report = parse_order_status_report(
                    alpaca_order=order,
                    account_id=self.account_id,
                    instrument_id=instrument_id,
                    instrument=instrument,
                    ts_init=ts_init,
                )
                reports.append(report)
        except Exception as e:
            self._log.error(f"Failed to generate order status reports: {e}")

        return reports

    async def generate_fill_reports(
        self,
        command: GenerateFillReports,
    ) -> list[FillReport]:
        reports: list[FillReport] = []
        try:
            request = GetOrdersRequest(status="closed")
            alpaca_orders = await asyncio.get_event_loop().run_in_executor(
                None,
                self._trading_client.get_orders,
                request,
            )

            ts_init = self._clock.timestamp_ns()
            for order in alpaca_orders:
                instrument_id = self._resolve_instrument_id(order)

                if command.instrument_id and instrument_id != command.instrument_id:
                    continue

                instrument = self.instrument_provider.find(instrument_id)
                report = parse_fill_report(
                    alpaca_order=order,
                    account_id=self.account_id,
                    instrument_id=instrument_id,
                    instrument=instrument,
                    ts_init=ts_init,
                )
                if report is not None:
                    reports.append(report)
        except Exception as e:
            self._log.error(f"Failed to generate fill reports: {e}")

        return reports

    async def generate_position_status_reports(
        self,
        command: GeneratePositionStatusReports,
    ) -> list[PositionStatusReport]:
        reports: list[PositionStatusReport] = []
        try:
            positions = await asyncio.get_event_loop().run_in_executor(
                None,
                self._trading_client.get_all_positions,
            )

            ts_init = self._clock.timestamp_ns()
            for pos in positions:
                instrument_id = self._resolve_position_instrument_id(pos)

                if command.instrument_id and instrument_id != command.instrument_id:
                    continue

                instrument = self.instrument_provider.find(instrument_id)
                report = parse_position_status_report(
                    alpaca_position=pos,
                    account_id=self.account_id,
                    instrument_id=instrument_id,
                    instrument=instrument,
                    ts_init=ts_init,
                )
                reports.append(report)
        except Exception as e:
            self._log.error(f"Failed to generate position status reports: {e}")

        return reports

    async def generate_mass_status(
        self,
        lookback_mins: int | None = None,
    ) -> ExecutionMassStatus | None:
        mass_status = ExecutionMassStatus(
            client_id=self.id,
            account_id=self.account_id,
            venue=ALPACA_VENUE,
            report_id=UUID4(),
            ts_init=self._clock.timestamp_ns(),
        )

        order_reports_cmd = GenerateOrderStatusReports(
            client_id=self.id,
            venue=ALPACA_VENUE,
            instrument_id=None,
            start=None,
            end=None,
            open_only=False,
        )
        fill_reports_cmd = GenerateFillReports(
            client_id=self.id,
            venue=ALPACA_VENUE,
            instrument_id=None,
            start=None,
            end=None,
        )
        position_reports_cmd = GeneratePositionStatusReports(
            client_id=self.id,
            venue=ALPACA_VENUE,
            instrument_id=None,
            start=None,
            end=None,
        )

        results = await asyncio.gather(
            self.generate_order_status_reports(order_reports_cmd),
            self.generate_fill_reports(fill_reports_cmd),
            self.generate_position_status_reports(position_reports_cmd),
        )

        mass_status.add_order_reports(reports=results[0])
        mass_status.add_fill_reports(reports=results[1])
        mass_status.add_position_reports(reports=results[2])

        return mass_status

    # -- ORDER SUBMISSION ---------------------------------------------------------------------------

    async def _submit_order(self, command: SubmitOrder) -> None:
        order = command.order

        try:
            alpaca_request = self._build_order_request(order)

            alpaca_order = await asyncio.get_event_loop().run_in_executor(
                None,
                self._trading_client.submit_order,
                alpaca_request,
            )

            self.generate_order_submitted(
                strategy_id=order.strategy_id,
                instrument_id=order.instrument_id,
                client_order_id=order.client_order_id,
                ts_event=self._clock.timestamp_ns(),
            )

            venue_order_id = VenueOrderId(str(alpaca_order.id))
            self.generate_order_accepted(
                strategy_id=order.strategy_id,
                instrument_id=order.instrument_id,
                client_order_id=order.client_order_id,
                venue_order_id=venue_order_id,
                ts_event=self._clock.timestamp_ns(),
            )

        except Exception as e:
            self.generate_order_rejected(
                strategy_id=order.strategy_id,
                instrument_id=order.instrument_id,
                client_order_id=order.client_order_id,
                reason=str(e),
                ts_event=self._clock.timestamp_ns(),
            )

    async def _submit_order_list(self, command: SubmitOrderList) -> None:
        for order in command.order_list.orders:
            submit = SubmitOrder(
                trader_id=command.trader_id,
                strategy_id=command.strategy_id,
                order=order,
                position_id=command.position_id,
                command_id=UUID4(),
                ts_init=self._clock.timestamp_ns(),
            )
            await self._submit_order(submit)

    async def _modify_order(self, command: ModifyOrder) -> None:
        try:
            venue_order_id = command.venue_order_id
            if venue_order_id is None:
                self._log.error("Cannot modify order: no venue_order_id")
                return

            replace_request = ReplaceOrderRequest(
                qty=float(command.quantity) if command.quantity else None,
                limit_price=float(command.price) if command.price else None,
            )

            alpaca_order = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._trading_client.replace_order_by_id(
                    str(venue_order_id),
                    replace_request,
                ),
            )

            new_venue_order_id = VenueOrderId(str(alpaca_order.id))

            self.generate_order_updated(
                strategy_id=command.strategy_id,
                instrument_id=command.instrument_id,
                client_order_id=command.client_order_id,
                venue_order_id=new_venue_order_id,
                quantity=command.quantity or Quantity.from_int(0),
                price=command.price,
                trigger_price=command.trigger_price,
                ts_event=self._clock.timestamp_ns(),
                venue_order_id_modified=True,
            )
        except Exception as e:
            self.generate_order_modify_rejected(
                strategy_id=command.strategy_id,
                instrument_id=command.instrument_id,
                client_order_id=command.client_order_id,
                venue_order_id=command.venue_order_id,
                reason=str(e),
                ts_event=self._clock.timestamp_ns(),
            )

    async def _cancel_order(self, command: CancelOrder) -> None:
        try:
            venue_order_id = command.venue_order_id
            if venue_order_id is None:
                self._log.error("Cannot cancel order: no venue_order_id")
                return

            await asyncio.get_event_loop().run_in_executor(
                None,
                self._trading_client.cancel_order_by_id,
                str(venue_order_id),
            )

        except Exception as e:
            self.generate_order_cancel_rejected(
                strategy_id=command.strategy_id,
                instrument_id=command.instrument_id,
                client_order_id=command.client_order_id,
                venue_order_id=command.venue_order_id,
                reason=str(e),
                ts_event=self._clock.timestamp_ns(),
            )

    async def _cancel_all_orders(self, command: CancelAllOrders) -> None:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._trading_client.cancel_orders,
            )
        except Exception as e:
            self._log.error(f"Failed to cancel all orders: {e}")

    async def _batch_cancel_orders(self, command: BatchCancelOrders) -> None:
        for cancel in command.cancels:
            await self._cancel_order(cancel)

    # -- TRADE UPDATE STREAM HANDLER ----------------------------------------------------------------

    def _on_trade_update(self, data: Any) -> None:
        """Handle trade update events from the Alpaca WebSocket stream."""
        try:
            event_type = str(getattr(data, "event", "")).lower()
            order_data = getattr(data, "order", data)

            alpaca_order_id = str(getattr(order_data, "id", ""))
            client_order_id_str = getattr(order_data, "client_order_id", None)
            symbol = str(getattr(order_data, "symbol", "")).upper()

            instrument_id = InstrumentId.from_str(f"{symbol}.{ALPACA_VENUE}")
            venue_order_id = VenueOrderId(alpaca_order_id)

            # Try to find the Nautilus order in the cache
            nautilus_order = None
            if client_order_id_str:
                from nautilus_trader.model.identifiers import ClientOrderId
                client_order_id = ClientOrderId(client_order_id_str)
                nautilus_order = self._cache.order(client_order_id)

            if nautilus_order is None:
                nautilus_order = self._cache.order(venue_order_id=venue_order_id)

            if nautilus_order is None:
                self._log.warning(
                    f"Received trade update for unknown order {alpaca_order_id} ({event_type})",
                )
                return

            strategy_id = nautilus_order.strategy_id
            instrument_id = nautilus_order.instrument_id
            client_order_id = nautilus_order.client_order_id
            ts_event = self._clock.timestamp_ns()

            if event_type == ALPACA_TRADE_EVENT_NEW:
                self.generate_order_accepted(
                    strategy_id=strategy_id,
                    instrument_id=instrument_id,
                    client_order_id=client_order_id,
                    venue_order_id=venue_order_id,
                    ts_event=ts_event,
                )

            elif event_type in (ALPACA_TRADE_EVENT_FILL, ALPACA_TRADE_EVENT_PARTIAL_FILL):
                self._handle_fill_event(
                    order_data=order_data,
                    strategy_id=strategy_id,
                    instrument_id=instrument_id,
                    client_order_id=client_order_id,
                    venue_order_id=venue_order_id,
                    ts_event=ts_event,
                )

            elif event_type == ALPACA_TRADE_EVENT_CANCELED:
                self.generate_order_canceled(
                    strategy_id=strategy_id,
                    instrument_id=instrument_id,
                    client_order_id=client_order_id,
                    venue_order_id=venue_order_id,
                    ts_event=ts_event,
                )

            elif event_type == ALPACA_TRADE_EVENT_EXPIRED:
                self.generate_order_expired(
                    strategy_id=strategy_id,
                    instrument_id=instrument_id,
                    client_order_id=client_order_id,
                    venue_order_id=venue_order_id,
                    ts_event=ts_event,
                )

            elif event_type == ALPACA_TRADE_EVENT_REJECTED:
                reason = str(getattr(order_data, "status", "rejected"))
                self.generate_order_rejected(
                    strategy_id=strategy_id,
                    instrument_id=instrument_id,
                    client_order_id=client_order_id,
                    reason=reason,
                    ts_event=ts_event,
                )

            elif event_type == ALPACA_TRADE_EVENT_REPLACED:
                qty_str = str(getattr(order_data, "qty", "0"))
                instrument = self.instrument_provider.find(instrument_id)
                quantity = instrument.make_qty(float(qty_str)) if instrument else Quantity.from_str(qty_str)

                limit_price = getattr(order_data, "limit_price", None)
                price = None
                if limit_price is not None:
                    price = instrument.make_price(float(str(limit_price))) if instrument else Price.from_str(str(limit_price))

                stop_price = getattr(order_data, "stop_price", None)
                trigger_price = None
                if stop_price is not None:
                    trigger_price = instrument.make_price(float(str(stop_price))) if instrument else Price.from_str(str(stop_price))

                self.generate_order_updated(
                    strategy_id=strategy_id,
                    instrument_id=instrument_id,
                    client_order_id=client_order_id,
                    venue_order_id=venue_order_id,
                    quantity=quantity,
                    price=price,
                    trigger_price=trigger_price,
                    ts_event=ts_event,
                    venue_order_id_modified=False,
                )

            else:
                self._log.debug(f"Unhandled trade update event: {event_type}")

        except Exception as e:
            self._log.error(f"Error handling trade update: {e}")

    def _handle_fill_event(
        self,
        order_data: Any,
        strategy_id: Any,
        instrument_id: InstrumentId,
        client_order_id: Any,
        venue_order_id: VenueOrderId,
        ts_event: int,
    ) -> None:
        """Handle a fill or partial fill trade update event."""
        instrument = self.instrument_provider.find(instrument_id)

        filled_qty_raw = str(getattr(order_data, "filled_qty", "0"))
        filled_avg_price = str(getattr(order_data, "filled_avg_price", "0"))

        # Determine the last fill quantity
        order_in_cache = self._cache.order(client_order_id)
        if order_in_cache is not None:
            already_filled = float(str(order_in_cache.filled_qty))
            total_filled = float(filled_qty_raw)
            last_fill_qty = total_filled - already_filled
        else:
            last_fill_qty = float(filled_qty_raw)

        if last_fill_qty <= 0:
            return

        if instrument is not None:
            last_qty = instrument.make_qty(last_fill_qty)
            last_px = instrument.make_price(float(filled_avg_price))
        else:
            last_qty = Quantity.from_str(str(last_fill_qty))
            last_px = Price.from_str(filled_avg_price)

        order_side_str = str(getattr(order_data, "side", "buy"))
        order_type_str = str(getattr(order_data, "type", "market"))

        from nautilus_trader.adapters.alpaca.enums import alpaca_order_side_to_nautilus
        from nautilus_trader.adapters.alpaca.enums import alpaca_order_type_to_nautilus

        self.generate_order_filled(
            strategy_id=strategy_id,
            instrument_id=instrument_id,
            client_order_id=client_order_id,
            venue_order_id=venue_order_id,
            venue_position_id=None,
            trade_id=TradeId(str(getattr(order_data, "id", venue_order_id.value))),
            order_side=alpaca_order_side_to_nautilus(order_side_str),
            order_type=alpaca_order_type_to_nautilus(order_type_str),
            last_qty=last_qty,
            last_px=last_px,
            quote_currency=USD,
            commission=Money(0, USD),
            liquidity_side=LiquiditySide.NO_LIQUIDITY_SIDE,
            ts_event=ts_event,
        )

    # -- HELPERS ------------------------------------------------------------------------------------

    def _build_order_request(self, order: Order) -> Any:
        """Build an alpaca-py order request from a Nautilus Order."""
        symbol = order.instrument_id.symbol.value
        side_str = nautilus_order_side_to_alpaca(order.side)
        side = AlpacaOrderSide.BUY if side_str == "buy" else AlpacaOrderSide.SELL
        tif_str = nautilus_tif_to_alpaca(order.time_in_force)
        tif = AlpacaTIF(tif_str)
        qty = float(order.quantity)

        if order.order_type == OrderType.MARKET:
            return MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                time_in_force=tif,
                client_order_id=str(order.client_order_id),
            )

        elif order.order_type == OrderType.LIMIT:
            return LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                time_in_force=tif,
                limit_price=float(order.price),
                client_order_id=str(order.client_order_id),
            )

        elif order.order_type == OrderType.STOP_MARKET:
            return StopOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                time_in_force=tif,
                stop_price=float(order.trigger_price),
                client_order_id=str(order.client_order_id),
            )

        elif order.order_type == OrderType.STOP_LIMIT:
            return StopLimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                time_in_force=tif,
                limit_price=float(order.price),
                stop_price=float(order.trigger_price),
                client_order_id=str(order.client_order_id),
            )

        elif order.order_type == OrderType.TRAILING_STOP_MARKET:
            trail_percent = getattr(order, "trailing_offset", None)
            return TrailingStopOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                time_in_force=tif,
                trail_percent=float(trail_percent) if trail_percent else None,
                client_order_id=str(order.client_order_id),
            )

        else:
            raise ValueError(f"Unsupported order type for Alpaca: {order.order_type}")

    def _resolve_instrument_id(self, alpaca_order: Any) -> InstrumentId:
        """Resolve the InstrumentId from an Alpaca order."""
        symbol = str(getattr(alpaca_order, "symbol", "")).upper()
        return InstrumentId.from_str(f"{symbol}.{ALPACA_VENUE}")

    def _resolve_position_instrument_id(self, alpaca_position: Any) -> InstrumentId:
        """Resolve the InstrumentId from an Alpaca position."""
        symbol = str(getattr(alpaca_position, "symbol", "")).upper()
        return InstrumentId.from_str(f"{symbol}.{ALPACA_VENUE}")
