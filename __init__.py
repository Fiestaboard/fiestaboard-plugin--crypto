"""Crypto Prices plugin for FiestaBoard.

Displays live cryptocurrency prices and 24h changes from the CoinGecko API.
"""

import logging
import math
import re
from typing import Any, Dict, List, Optional

import requests

from src.plugins.base import PluginBase, PluginResult

logger = logging.getLogger(__name__)

API_URL = "https://api.coingecko.com/api/v3/simple/price"
USER_AGENT = "FiestaBoard (https://github.com/FiestaBoard/FiestaBoard)"
DEFAULT_COINS = "bitcoin,ethereum,solana"
DEFAULT_CURRENCY = "usd"
MAX_COINS = 10

# Well-known CoinGecko ids -> ticker symbols. Anything else falls back to the
# first four letters of the id, uppercased.
SYMBOLS = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "dogecoin": "DOGE",
    "cardano": "ADA",
    "ripple": "XRP",
    "litecoin": "LTC",
    "polkadot": "DOT",
    "chainlink": "LINK",
    "avalanche-2": "AVAX",
}


def parse_coins(value: Any) -> List[str]:
    """Split a comma-separated coin id string into a list of lowercase ids."""
    if not isinstance(value, str):
        return []
    return [c.strip().lower() for c in value.split(",") if c.strip()]


def coin_symbol(coin_id: str) -> str:
    """Return the ticker symbol for a CoinGecko id."""
    if coin_id in SYMBOLS:
        return SYMBOLS[coin_id]
    return re.sub(r"[^a-z]", "", coin_id)[:4].upper()


def coin_name(coin_id: str) -> str:
    """Derive a display name from a CoinGecko id (e.g. 'avalanche-2' -> 'Avalanche')."""
    return re.sub(r"-\d+$", "", coin_id).replace("-", " ").title()


def format_price(value: float) -> str:
    """Format a price: >=1000 no decimals with separators, >=1 two decimals,
    <1 four significant digits."""
    if value >= 1000:
        return f"{value:,.0f}"
    if value >= 1:
        return f"{value:.2f}"
    if value <= 0:
        return "0.00"
    decimals = min(3 - math.floor(math.log10(value)), 8)
    return f"{value:.{decimals}f}"


def format_change(value: float) -> str:
    """Format a percentage change with sign and one decimal, e.g. '+1.2'."""
    return f"{value:+.1f}"


class CryptoPlugin(PluginBase):
    """Crypto Prices plugin.

    Fetches current prices and 24h percentage changes from CoinGecko's
    free public API and exposes them as template variables.
    """

    @property
    def plugin_id(self) -> str:
        return "crypto"

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate crypto configuration."""
        errors = []

        coins = parse_coins(config.get("coins", DEFAULT_COINS))
        if not coins:
            errors.append("At least one coin id is required")
        elif len(coins) > MAX_COINS:
            errors.append(f"Maximum {MAX_COINS} coins allowed")

        currency = str(config.get("currency", DEFAULT_CURRENCY)).strip()
        if not re.fullmatch(r"[A-Za-z]{3}", currency):
            errors.append("Currency must be a 3-letter code (e.g. usd, eur)")

        return errors

    def fetch_data(self) -> PluginResult:
        """Fetch prices for all configured coins."""
        try:
            coins = parse_coins(self.config.get("coins", DEFAULT_COINS))[:MAX_COINS]
            if not coins:
                return PluginResult(available=False, error="No coins configured")

            currency = str(self.config.get("currency", DEFAULT_CURRENCY)).strip().lower() or DEFAULT_CURRENCY

            headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
            api_key = self.config.get("api_key")
            if api_key:
                headers["x-cg-demo-api-key"] = api_key

            response = requests.get(
                API_URL,
                params={
                    "ids": ",".join(coins),
                    "vs_currencies": currency,
                    "include_24hr_change": "true",
                },
                headers=headers,
                timeout=10,
            )
            if response.status_code == 429:
                return PluginResult(
                    available=False,
                    error="CoinGecko rate limit hit (HTTP 429) - increase refresh_seconds",
                )
            response.raise_for_status()

            payload = response.json()
            if not isinstance(payload, dict):
                return PluginResult(available=False, error="Malformed response from CoinGecko")

            items = []
            for coin_id in coins:
                entry = payload.get(coin_id)
                if not isinstance(entry, dict) or entry.get(currency) is None:
                    logger.warning(f"No {currency} price returned for coin id '{coin_id}', skipping")
                    continue
                items.append(self._build_item(coin_id, entry, currency))

            if not items:
                return PluginResult(available=False, error="No price data returned for configured coins")

            primary = items[0]
            data = {
                "symbol": primary["symbol"],
                "price": primary["price"],
                "change_24h": primary["change_24h"],
                "change_sign": primary["change_sign"],
                "formatted": primary["formatted"],
                "count": len(items),
                "coins": items,
            }
            return PluginResult(available=True, data=data)

        except Exception as e:
            logger.exception("Error fetching crypto prices")
            return PluginResult(available=False, error=str(e))

    def _build_item(self, coin_id: str, entry: Dict[str, Any], currency: str) -> Dict[str, Any]:
        """Build one array item from a CoinGecko price entry."""
        price = float(entry[currency])
        change = float(entry.get(f"{currency}_24h_change") or 0.0)
        symbol = coin_symbol(coin_id)
        price_str = format_price(price)
        change_str = format_change(change)
        return {
            "id": coin_id,
            "symbol": symbol,
            "name": coin_name(coin_id),
            "price": price_str,
            "change_24h": change_str,
            "change_sign": "+" if change >= 0 else "-",
            # 4 + 1 + 10 + 1 + 6 = 22 tiles: symbol left, price, change right
            "formatted": f"{symbol:<4} {price_str:>10} {change_str + '%':>6}",
        }

    def get_formatted_display(self) -> Optional[List[str]]:
        """Return default display: CRYPTO header then one line per coin."""
        result = self.get_data()
        if not result.available or not result.data:
            return None

        rows = self.board.rows if self.board else 6
        cols = self.board.cols if self.board else 22

        lines = ["CRYPTO".center(cols)]
        for coin in result.data["coins"][: rows - 1]:
            if cols >= 22:
                line = coin["formatted"]
            else:
                line = f"{coin['symbol']:<4} {coin['price']:>10}"
            lines.append(line[:cols])

        while len(lines) < rows:
            lines.append("")

        return lines[:rows]


# Export the plugin class
Plugin = CryptoPlugin
