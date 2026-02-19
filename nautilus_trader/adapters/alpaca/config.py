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

from nautilus_trader.config import InstrumentProviderConfig
from nautilus_trader.config import LiveDataClientConfig
from nautilus_trader.config import LiveExecClientConfig


class AlpacaInstrumentProviderConfig(InstrumentProviderConfig, frozen=True):
    """
    Configuration for ``AlpacaInstrumentProvider`` instances.

    Parameters
    ----------
    load_all : bool, default False
        If all venue instruments should be loaded on start.
    load_ids : frozenset[InstrumentId], optional
        The list of instrument IDs to be loaded on start (if ``load_all`` is False).
    filters : dict[str, Any], optional
        The venue specific instrument loading filters to apply.
    filter_callable : str, optional
        A fully qualified path to a callable that filters instruments.
    log_warnings : bool, default True
        If parser warnings should be logged.
    api_key : str, optional
        The Alpaca API key. If ``None``, falls back to the ``APCA_API_KEY_ID``
        environment variable.
    api_secret : str, optional
        The Alpaca API secret. If ``None``, falls back to the ``APCA_API_SECRET_KEY``
        environment variable.
    paper : bool, default True
        If ``True``, use the Alpaca paper trading environment.
        If ``False``, use the live trading environment.
    asset_classes : frozenset[str], optional
        Filter to only load instruments of the specified Alpaca asset classes.
        Valid values: ``"us_equity"``, ``"crypto"``. If ``None``, loads all.

    """

    api_key: str | None = None
    api_secret: str | None = None
    paper: bool = True
    asset_classes: frozenset[str] | None = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AlpacaInstrumentProviderConfig):
            return NotImplemented
        return (
            self.load_all == other.load_all
            and self.load_ids == other.load_ids
            and self.filters == other.filters
            and self.paper == other.paper
            and self.asset_classes == other.asset_classes
        )

    def __hash__(self) -> int:
        return hash((
            self.load_all,
            self.load_ids,
            self.filters,
            self.paper,
            self.asset_classes,
        ))


class AlpacaDataClientConfig(LiveDataClientConfig, frozen=True):
    """
    Configuration for ``AlpacaDataClient`` instances.

    Parameters
    ----------
    instrument_provider : AlpacaInstrumentProviderConfig
        The instrument provider configuration.
    api_key : str, optional
        The Alpaca API key. If ``None``, falls back to the ``APCA_API_KEY_ID``
        environment variable.
    api_secret : str, optional
        The Alpaca API secret. If ``None``, falls back to the ``APCA_API_SECRET_KEY``
        environment variable.
    paper : bool, default True
        If ``True``, use the Alpaca paper trading environment.
    feed : str, default "iex"
        The market data feed: ``"iex"`` (free) or ``"sip"`` (paid).

    """

    instrument_provider: AlpacaInstrumentProviderConfig = AlpacaInstrumentProviderConfig()
    api_key: str | None = None
    api_secret: str | None = None
    paper: bool = True
    feed: str = "iex"


class AlpacaExecClientConfig(LiveExecClientConfig, frozen=True):
    """
    Configuration for ``AlpacaExecutionClient`` instances.

    Parameters
    ----------
    instrument_provider : AlpacaInstrumentProviderConfig
        The instrument provider configuration.
    api_key : str, optional
        The Alpaca API key. If ``None``, falls back to the ``APCA_API_KEY_ID``
        environment variable.
    api_secret : str, optional
        The Alpaca API secret. If ``None``, falls back to the ``APCA_API_SECRET_KEY``
        environment variable.
    paper : bool, default True
        If ``True``, use the Alpaca paper trading environment.
    account_id : str, optional
        The Alpaca account ID. If ``None``, fetched automatically from the API.

    """

    instrument_provider: AlpacaInstrumentProviderConfig = AlpacaInstrumentProviderConfig()
    api_key: str | None = None
    api_secret: str | None = None
    paper: bool = True
    account_id: str | None = None
