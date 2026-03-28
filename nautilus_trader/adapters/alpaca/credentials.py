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

from nautilus_trader.adapters.alpaca.constants import ALPACA_API_KEY_ENV
from nautilus_trader.adapters.alpaca.constants import ALPACA_API_SECRET_ENV
from nautilus_trader.adapters.env import get_env_key


def get_alpaca_api_key() -> str:
    """Get Alpaca API key from environment variable ``APCA_API_KEY_ID``."""
    return get_env_key(ALPACA_API_KEY_ENV)


def get_alpaca_api_secret() -> str:
    """Get Alpaca API secret from environment variable ``APCA_API_SECRET_KEY``."""
    return get_env_key(ALPACA_API_SECRET_ENV)
