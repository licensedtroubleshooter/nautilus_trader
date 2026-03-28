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

from nautilus_trader.adapters.alpaca.constants import ALPACA_VENUE
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.currencies import USDC
from nautilus_trader.model.currencies import USDT
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import Symbol
from nautilus_trader.model.instruments.currency_pair import CurrencyPair
from nautilus_trader.model.instruments.equity import Equity
from nautilus_trader.model.objects import Currency
from nautilus_trader.model.objects import Money
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity


def parse_alpaca_equity(
    asset: Any,
    ts_init: int,
) -> Equity:
    """
    Parse an Alpaca asset object into a Nautilus ``Equity`` instrument.

    Parameters
    ----------
    asset : alpaca.trading.models.Asset
        The Alpaca asset object.
    ts_init : int
        The UNIX timestamp (nanoseconds) for initialization.

    Returns
    -------
    Equity

    """
    symbol_str = str(asset.symbol).upper()
    instrument_id = InstrumentId(Symbol(symbol_str), ALPACA_VENUE)

    price_precision = 2
    price_increment = Price.from_str("0.01")

    info: dict[str, Any] = {
        "alpaca_id": str(asset.id) if asset.id else None,
        "exchange": str(asset.exchange) if asset.exchange else None,
        "name": str(asset.name) if asset.name else None,
        "tradable": bool(asset.tradable) if asset.tradable is not None else False,
        "fractionable": bool(asset.fractionable) if asset.fractionable is not None else False,
        "marginable": bool(asset.marginable) if asset.marginable is not None else False,
        "shortable": bool(asset.shortable) if asset.shortable is not None else False,
        "easy_to_borrow": bool(asset.easy_to_borrow) if asset.easy_to_borrow is not None else False,
    }

    return Equity(
        instrument_id=instrument_id,
        raw_symbol=Symbol(symbol_str),
        currency=USD,
        price_precision=price_precision,
        price_increment=price_increment,
        lot_size=Quantity.from_int(1),
        ts_event=ts_init,
        ts_init=ts_init,
        info=info,
    )


def parse_alpaca_crypto(
    asset: Any,
    ts_init: int,
) -> CurrencyPair:
    """
    Parse an Alpaca crypto asset object into a Nautilus ``CurrencyPair`` instrument.

    Parameters
    ----------
    asset : alpaca.trading.models.Asset
        The Alpaca crypto asset object.
    ts_init : int
        The UNIX timestamp (nanoseconds) for initialization.

    Returns
    -------
    CurrencyPair

    """
    symbol_str = str(asset.symbol).upper()
    instrument_id = InstrumentId(Symbol(symbol_str), ALPACA_VENUE)

    base_str, quote_str = _parse_crypto_symbol(symbol_str)
    base_currency = Currency.from_str(base_str)
    quote_currency = _resolve_quote_currency(quote_str)

    price_precision = _crypto_price_precision(base_str)
    size_precision = _crypto_size_precision(base_str)

    info: dict[str, Any] = {
        "alpaca_id": str(asset.id) if asset.id else None,
        "tradable": bool(asset.tradable) if asset.tradable is not None else False,
        "fractionable": bool(asset.fractionable) if asset.fractionable is not None else False,
    }

    return CurrencyPair(
        instrument_id=instrument_id,
        raw_symbol=Symbol(symbol_str),
        base_currency=base_currency,
        quote_currency=quote_currency,
        price_precision=price_precision,
        size_precision=size_precision,
        price_increment=Price(10 ** -price_precision, price_precision),
        size_increment=Quantity(10 ** -size_precision, size_precision),
        lot_size=None,
        max_quantity=None,
        min_quantity=Quantity(10 ** -size_precision, size_precision),
        max_notional=None,
        min_notional=None,
        max_price=None,
        min_price=None,
        margin_init=Decimal(0),
        margin_maint=Decimal(0),
        maker_fee=Decimal("0.0015"),
        taker_fee=Decimal("0.0025"),
        ts_event=ts_init,
        ts_init=ts_init,
        info=info,
    )


def _parse_crypto_symbol(symbol: str) -> tuple[str, str]:
    """Parse a crypto symbol like 'BTC/USD' or 'BTCUSD' into (base, quote)."""
    if "/" in symbol:
        parts = symbol.split("/")
        return parts[0], parts[1]
    # Common quote currencies in order of length (longest first)
    for quote in ("USDT", "USDC", "USD", "BTC", "ETH"):
        if symbol.endswith(quote) and len(symbol) > len(quote):
            return symbol[: -len(quote)], quote
    raise ValueError(f"Cannot parse crypto symbol: {symbol}")


def _resolve_quote_currency(quote_str: str) -> Currency:
    """Resolve a quote currency string to a Nautilus Currency."""
    mapping = {
        "USD": USD,
        "USDT": USDT,
        "USDC": USDC,
    }
    if quote_str in mapping:
        return mapping[quote_str]
    return Currency.from_str(quote_str)


def _crypto_price_precision(base: str) -> int:
    """Return the price precision for a crypto asset."""
    high_precision = {"BTC", "ETH", "AVAX", "LINK", "UNI", "AAVE", "MKR", "SOL", "DOT"}
    if base in high_precision:
        return 2
    return 4


def _crypto_size_precision(base: str) -> int:
    """Return the size precision for a crypto asset."""
    high_value = {"BTC"}
    medium_value = {"ETH"}
    if base in high_value:
        return 8
    if base in medium_value:
        return 6
    return 4
