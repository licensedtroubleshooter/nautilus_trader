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

from nautilus_trader.model.identifiers import ClientId
from nautilus_trader.model.identifiers import Venue


ALPACA_VENUE = Venue("ALPACA")
ALPACA_CLIENT_ID = ClientId("ALPACA")

# REST API base URLs
ALPACA_PAPER_BASE_URL = "https://paper-api.alpaca.markets"
ALPACA_LIVE_BASE_URL = "https://api.alpaca.markets"

# Market data base URL (same for paper and live)
ALPACA_DATA_BASE_URL = "https://data.alpaca.markets"

# WebSocket streaming URLs - Market Data
ALPACA_STOCK_STREAM_SIP_URL = "wss://stream.data.alpaca.markets/v2/sip"
ALPACA_STOCK_STREAM_IEX_URL = "wss://stream.data.alpaca.markets/v2/iex"
ALPACA_CRYPTO_STREAM_URL = "wss://stream.data.alpaca.markets/v1beta3/crypto/us"

# WebSocket streaming URLs - Trade Updates
ALPACA_PAPER_TRADE_STREAM_URL = "wss://paper-api.alpaca.markets/stream"
ALPACA_LIVE_TRADE_STREAM_URL = "wss://api.alpaca.markets/stream"

# Rate limit: 200 requests per minute
ALPACA_RATE_LIMIT_PER_MINUTE = 200

# Environment variable names
ALPACA_API_KEY_ENV = "APCA_API_KEY_ID"
ALPACA_API_SECRET_ENV = "APCA_API_SECRET_KEY"
