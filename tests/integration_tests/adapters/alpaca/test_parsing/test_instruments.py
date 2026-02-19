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

from types import SimpleNamespace

from nautilus_trader.adapters.alpaca.constants import ALPACA_VENUE
from nautilus_trader.adapters.alpaca.parsing.instruments import parse_alpaca_crypto
from nautilus_trader.adapters.alpaca.parsing.instruments import parse_alpaca_equity
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import Symbol
from nautilus_trader.model.instruments.currency_pair import CurrencyPair
from nautilus_trader.model.instruments.equity import Equity


def _make_equity_asset(**kwargs) -> SimpleNamespace:
    defaults = {
        "id": "b0b6dd9d-8b9b-48a9-ba46-b9d54906e415",
        "asset_class": "us_equity",
        "exchange": "NASDAQ",
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "status": "active",
        "tradable": True,
        "fractionable": True,
        "marginable": True,
        "shortable": True,
        "easy_to_borrow": True,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_crypto_asset(**kwargs) -> SimpleNamespace:
    defaults = {
        "id": "276e2673-764b-4ab6-a611-caf665ca6340",
        "asset_class": "crypto",
        "exchange": "CRYPTO",
        "symbol": "BTC/USD",
        "name": "Bitcoin",
        "status": "active",
        "tradable": True,
        "fractionable": True,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestParseAlpacaEquity:
    def test_basic_equity(self) -> None:
        asset = _make_equity_asset()
        ts_init = 1_000_000_000

        result = parse_alpaca_equity(asset, ts_init)

        assert isinstance(result, Equity)
        assert result.id == InstrumentId(Symbol("AAPL"), ALPACA_VENUE)
        assert result.raw_symbol == Symbol("AAPL")
        assert result.currency == USD
        assert result.price_precision == 2
        assert result.ts_init == ts_init

    def test_equity_info_dict(self) -> None:
        asset = _make_equity_asset()
        result = parse_alpaca_equity(asset, 0)

        assert result.info["exchange"] == "NASDAQ"
        assert result.info["name"] == "Apple Inc."
        assert result.info["tradable"] is True
        assert result.info["fractionable"] is True

    def test_different_symbols(self) -> None:
        for sym in ["TSLA", "MSFT", "GOOG"]:
            asset = _make_equity_asset(symbol=sym)
            result = parse_alpaca_equity(asset, 0)
            assert result.id.symbol.value == sym


class TestParseAlpacaCrypto:
    def test_basic_crypto(self) -> None:
        asset = _make_crypto_asset()
        ts_init = 2_000_000_000

        result = parse_alpaca_crypto(asset, ts_init)

        assert isinstance(result, CurrencyPair)
        assert result.id == InstrumentId(Symbol("BTC/USD"), ALPACA_VENUE)
        assert result.quote_currency == USD
        assert result.base_currency.code == "BTC"
        assert result.ts_init == ts_init

    def test_crypto_precision(self) -> None:
        btc = _make_crypto_asset(symbol="BTC/USD")
        result = parse_alpaca_crypto(btc, 0)
        assert result.price_precision == 2
        assert result.size_precision == 8

    def test_low_value_crypto_precision(self) -> None:
        doge = _make_crypto_asset(symbol="DOGE/USD")
        result = parse_alpaca_crypto(doge, 0)
        assert result.price_precision == 4
        assert result.size_precision == 4

    def test_crypto_info_dict(self) -> None:
        asset = _make_crypto_asset()
        result = parse_alpaca_crypto(asset, 0)

        assert result.info["tradable"] is True
        assert result.info["fractionable"] is True
