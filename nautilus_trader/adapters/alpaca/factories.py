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
from functools import lru_cache
from typing import TYPE_CHECKING

from alpaca.trading.client import TradingClient

from nautilus_trader.adapters.alpaca.config import AlpacaDataClientConfig
from nautilus_trader.adapters.alpaca.config import AlpacaExecClientConfig
from nautilus_trader.adapters.alpaca.config import AlpacaInstrumentProviderConfig
from nautilus_trader.adapters.alpaca.constants import ALPACA_VENUE
from nautilus_trader.adapters.alpaca.credentials import get_alpaca_api_key
from nautilus_trader.adapters.alpaca.credentials import get_alpaca_api_secret
from nautilus_trader.adapters.alpaca.data import AlpacaDataClient
from nautilus_trader.adapters.alpaca.execution import AlpacaExecutionClient
from nautilus_trader.adapters.alpaca.providers import AlpacaInstrumentProvider
from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.clock import LiveClock
from nautilus_trader.live.factories import LiveDataClientFactory
from nautilus_trader.live.factories import LiveExecClientFactory
from nautilus_trader.model.identifiers import AccountId
from nautilus_trader.msgbus.bus import MessageBus


@lru_cache(1)
def get_cached_alpaca_trading_client(
    api_key: str,
    api_secret: str,
    paper: bool,
) -> TradingClient:
    """
    Return a cached Alpaca ``TradingClient`` instance.

    Parameters
    ----------
    api_key : str
        The Alpaca API key.
    api_secret : str
        The Alpaca API secret.
    paper : bool
        If ``True``, use the paper trading environment.

    Returns
    -------
    TradingClient

    """
    return TradingClient(
        api_key=api_key,
        secret_key=api_secret,
        paper=paper,
    )


@lru_cache(1)
def get_cached_alpaca_instrument_provider(
    client: TradingClient,
    clock: LiveClock,
    config: AlpacaInstrumentProviderConfig,
) -> AlpacaInstrumentProvider:
    """
    Return a cached ``AlpacaInstrumentProvider`` instance.

    Parameters
    ----------
    client : TradingClient
        The Alpaca trading client.
    clock : LiveClock
        The clock for the provider.
    config : AlpacaInstrumentProviderConfig
        The instrument provider configuration.

    Returns
    -------
    AlpacaInstrumentProvider

    """
    return AlpacaInstrumentProvider(
        client=client,
        clock=clock,
        config=config,
    )


def _resolve_credentials(
    api_key: str | None,
    api_secret: str | None,
) -> tuple[str, str]:
    """Resolve API credentials from config or environment variables."""
    key = api_key or get_alpaca_api_key()
    secret = api_secret or get_alpaca_api_secret()
    return key, secret


def _resolve_account_id(
    trading_client: TradingClient,
    config_account_id: str | None,
) -> AccountId:
    """Resolve the AccountId from config or by fetching from Alpaca API."""
    if config_account_id:
        return AccountId(f"{ALPACA_VENUE.value}-{config_account_id}")

    # Fetch from Alpaca API
    account = trading_client.get_account()
    alpaca_account_id = str(account.id)
    return AccountId(f"{ALPACA_VENUE.value}-{alpaca_account_id}")


class AlpacaLiveDataClientFactory(LiveDataClientFactory):
    """
    Provides a factory for creating Alpaca live data clients.
    """

    @staticmethod
    def create(  # type: ignore
        loop: asyncio.AbstractEventLoop,
        name: str,
        config: AlpacaDataClientConfig,
        msgbus: MessageBus,
        cache: Cache,
        clock: LiveClock,
    ) -> AlpacaDataClient:
        """
        Create a new Alpaca data client.

        Parameters
        ----------
        loop : asyncio.AbstractEventLoop
            The event loop for the client.
        name : str
            The custom client name.
        config : AlpacaDataClientConfig
            The client configuration.
        msgbus : MessageBus
            The message bus for the client.
        cache : Cache
            The cache for the client.
        clock : LiveClock
            The clock for the client.

        Returns
        -------
        AlpacaDataClient

        """
        api_key, api_secret = _resolve_credentials(config.api_key, config.api_secret)

        trading_client = get_cached_alpaca_trading_client(
            api_key=api_key,
            api_secret=api_secret,
            paper=config.paper,
        )

        provider = get_cached_alpaca_instrument_provider(
            client=trading_client,
            clock=clock,
            config=config.instrument_provider,
        )

        return AlpacaDataClient(
            loop=loop,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
            instrument_provider=provider,
            config=config,
            api_key=api_key,
            api_secret=api_secret,
            name=name,
        )


class AlpacaLiveExecClientFactory(LiveExecClientFactory):
    """
    Provides a factory for creating Alpaca live execution clients.
    """

    @staticmethod
    def create(  # type: ignore
        loop: asyncio.AbstractEventLoop,
        name: str,
        config: AlpacaExecClientConfig,
        msgbus: MessageBus,
        cache: Cache,
        clock: LiveClock,
    ) -> AlpacaExecutionClient:
        """
        Create a new Alpaca execution client.

        Parameters
        ----------
        loop : asyncio.AbstractEventLoop
            The event loop for the client.
        name : str
            The custom client name.
        config : AlpacaExecClientConfig
            The client configuration.
        msgbus : MessageBus
            The message bus for the client.
        cache : Cache
            The cache for the client.
        clock : LiveClock
            The clock for the client.

        Returns
        -------
        AlpacaExecutionClient

        """
        api_key, api_secret = _resolve_credentials(config.api_key, config.api_secret)

        trading_client = get_cached_alpaca_trading_client(
            api_key=api_key,
            api_secret=api_secret,
            paper=config.paper,
        )

        provider = get_cached_alpaca_instrument_provider(
            client=trading_client,
            clock=clock,
            config=config.instrument_provider,
        )

        account_id = _resolve_account_id(trading_client, config.account_id)

        return AlpacaExecutionClient(
            loop=loop,
            trading_client=trading_client,
            account_id=account_id,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
            instrument_provider=provider,
            config=config,
            api_key=api_key,
            api_secret=api_secret,
            name=name,
        )
