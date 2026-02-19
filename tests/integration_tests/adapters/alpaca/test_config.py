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

from nautilus_trader.adapters.alpaca.config import AlpacaDataClientConfig
from nautilus_trader.adapters.alpaca.config import AlpacaExecClientConfig
from nautilus_trader.adapters.alpaca.config import AlpacaInstrumentProviderConfig


class TestAlpacaInstrumentProviderConfig:
    def test_default_values(self) -> None:
        config = AlpacaInstrumentProviderConfig()
        assert config.api_key is None
        assert config.api_secret is None
        assert config.paper is True
        assert config.asset_classes is None
        assert config.load_all is False

    def test_with_custom_values(self) -> None:
        config = AlpacaInstrumentProviderConfig(
            api_key="test-key",
            api_secret="test-secret",
            paper=False,
            asset_classes=frozenset({"us_equity"}),
            load_all=True,
        )
        assert config.api_key == "test-key"
        assert config.api_secret == "test-secret"
        assert config.paper is False
        assert config.asset_classes == frozenset({"us_equity"})
        assert config.load_all is True

    def test_frozen(self) -> None:
        config = AlpacaInstrumentProviderConfig()
        try:
            config.paper = False  # type: ignore
            assert False, "Should have raised"
        except AttributeError:
            pass

    def test_equality(self) -> None:
        config1 = AlpacaInstrumentProviderConfig(paper=True, load_all=True)
        config2 = AlpacaInstrumentProviderConfig(paper=True, load_all=True)
        config3 = AlpacaInstrumentProviderConfig(paper=False, load_all=True)
        assert config1 == config2
        assert config1 != config3

    def test_hash(self) -> None:
        config1 = AlpacaInstrumentProviderConfig(paper=True)
        config2 = AlpacaInstrumentProviderConfig(paper=True)
        assert hash(config1) == hash(config2)


class TestAlpacaDataClientConfig:
    def test_default_values(self) -> None:
        config = AlpacaDataClientConfig()
        assert config.api_key is None
        assert config.api_secret is None
        assert config.paper is True
        assert config.feed == "iex"
        assert isinstance(config.instrument_provider, AlpacaInstrumentProviderConfig)

    def test_with_custom_values(self) -> None:
        config = AlpacaDataClientConfig(
            api_key="test-key",
            api_secret="test-secret",
            paper=False,
            feed="sip",
        )
        assert config.api_key == "test-key"
        assert config.paper is False
        assert config.feed == "sip"


class TestAlpacaExecClientConfig:
    def test_default_values(self) -> None:
        config = AlpacaExecClientConfig()
        assert config.api_key is None
        assert config.api_secret is None
        assert config.paper is True
        assert config.account_id is None

    def test_with_custom_values(self) -> None:
        config = AlpacaExecClientConfig(
            api_key="test-key",
            api_secret="test-secret",
            paper=False,
            account_id="abc123",
        )
        assert config.api_key == "test-key"
        assert config.paper is False
        assert config.account_id == "abc123"
