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
from typing import TYPE_CHECKING, Any

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest

from nautilus_trader.adapters.alpaca.config import AlpacaInstrumentProviderConfig
from nautilus_trader.adapters.alpaca.constants import ALPACA_VENUE
from nautilus_trader.adapters.alpaca.parsing.instruments import parse_alpaca_crypto
from nautilus_trader.adapters.alpaca.parsing.instruments import parse_alpaca_equity
from nautilus_trader.common.providers import InstrumentProvider
from nautilus_trader.model.identifiers import InstrumentId

if TYPE_CHECKING:
    from nautilus_trader.common.clock import Clock


class AlpacaInstrumentProvider(InstrumentProvider):
    """
    Provides instrument definitions from the Alpaca API.

    Parameters
    ----------
    client : TradingClient
        The Alpaca trading client.
    clock : Clock
        The clock for the provider.
    config : AlpacaInstrumentProviderConfig
        The configuration for the provider.

    """

    def __init__(
        self,
        client: TradingClient,
        clock: Clock,
        config: AlpacaInstrumentProviderConfig,
    ) -> None:
        super().__init__(config=config)
        self._client = client
        self._clock = clock
        self._config = config
        self._alpaca_assets: dict[InstrumentId, Any] = {}
        self._log_warnings = config.log_warnings

    async def load_all_async(
        self,
        filters: dict | None = None,
    ) -> None:
        """Load all tradable instruments from Alpaca."""
        asset_classes_to_load = self._config.asset_classes

        if asset_classes_to_load is None or "us_equity" in asset_classes_to_load:
            await self._load_equity_instruments()

        if asset_classes_to_load is None or "crypto" in asset_classes_to_load:
            await self._load_crypto_instruments()

    async def load_ids_async(
        self,
        instrument_ids: list[InstrumentId],
        filters: dict | None = None,
    ) -> None:
        """Load specific instruments by ID."""
        for instrument_id in instrument_ids:
            await self.load_async(instrument_id, filters)

    async def load_async(
        self,
        instrument_id: InstrumentId,
        filters: dict | None = None,
    ) -> None:
        """Load a single instrument by ID."""
        existing = self.find(instrument_id)
        if existing is not None:
            return

        symbol = instrument_id.symbol.value
        try:
            asset = await asyncio.get_event_loop().run_in_executor(
                None,
                self._client.get_asset,
                symbol,
            )
        except Exception as e:
            if self._log_warnings:
                self._log.warning(f"Failed to load instrument {instrument_id}: {e}")
            return

        self._parse_and_add_asset(asset)

    def get_alpaca_asset(self, instrument_id: InstrumentId) -> Any | None:
        """Return the raw Alpaca asset object for an instrument, or ``None``."""
        return self._alpaca_assets.get(instrument_id)

    async def _load_equity_instruments(self) -> None:
        """Load all tradable US equity instruments."""
        try:
            request = GetAssetsRequest(asset_class="us_equity", status="active")
            assets = await asyncio.get_event_loop().run_in_executor(
                None,
                self._client.get_all_assets,
                request,
            )
        except Exception as e:
            self._log.error(f"Failed to load equity instruments: {e}")
            return

        count = 0
        for asset in assets:
            if not getattr(asset, "tradable", False):
                continue
            try:
                self._parse_and_add_asset(asset)
                count += 1
            except Exception as e:
                if self._log_warnings:
                    self._log.warning(
                        f"Failed to parse equity {getattr(asset, 'symbol', '?')}: {e}",
                    )
        self._log.info(f"Loaded {count} Alpaca equity instruments")

    async def _load_crypto_instruments(self) -> None:
        """Load all tradable crypto instruments."""
        try:
            request = GetAssetsRequest(asset_class="crypto", status="active")
            assets = await asyncio.get_event_loop().run_in_executor(
                None,
                self._client.get_all_assets,
                request,
            )
        except Exception as e:
            self._log.error(f"Failed to load crypto instruments: {e}")
            return

        count = 0
        for asset in assets:
            if not getattr(asset, "tradable", False):
                continue
            try:
                self._parse_and_add_asset(asset)
                count += 1
            except Exception as e:
                if self._log_warnings:
                    self._log.warning(
                        f"Failed to parse crypto {getattr(asset, 'symbol', '?')}: {e}",
                    )
        self._log.info(f"Loaded {count} Alpaca crypto instruments")

    def _parse_and_add_asset(self, asset: Any) -> None:
        """Parse an Alpaca asset and add it to the provider."""
        ts_init = self._clock.timestamp_ns()
        asset_class = str(getattr(asset, "asset_class", "")).lower().replace(" ", "_")

        if asset_class == "us_equity":
            instrument = parse_alpaca_equity(asset, ts_init)
        elif asset_class == "crypto":
            instrument = parse_alpaca_crypto(asset, ts_init)
        else:
            raise ValueError(f"Unsupported Alpaca asset class: {asset_class}")

        self._alpaca_assets[instrument.id] = asset
        self.add(instrument)
