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

# Fallback geometry used only when no board is bound (self.board is None --
# legacy callers, unit tests). Every layout decision below reads self.board
# instead; a plugin instance is shared across every board a user owns, so
# nothing may assume a fixed size.
DEFAULT_BOARD_COLS = 22
DEFAULT_BOARD_ROWS = 6

# The tallest board FiestaBoard supports is an 8-tall note array (24 rows).
# One row always goes to the "CRYPTO" header, so 23 is the most price rows
# any board can ever show. Config is board-agnostic -- one config serves
# every board a user owns -- so the cap on how many coins can be configured
# has to cover the largest board, not whichever board happens to be bound
# when validate_config() runs.
MAX_BOARD_ROWS = 24
MAX_COINS = MAX_BOARD_ROWS - 1  # 23

# A wide-board row is built from three fields -- label, price, change -- with
# a single-space gap between each. Price and change keep the widths declared
# in the manifest; whatever width is left over goes to the label, which grows
# from a 4-character ticker into the coin's full name as the board widens.
# 4 + 1 + 10 + 1 + 6 = 22 is exactly a Flagship's width, which is also the
# minimum width that can show all three fields -- below it there is no room
# for "change" at all (see the narrow branch in format_row below).
MIN_LABEL_WIDTH = 4
PRICE_WIDTH = 10
CHANGE_WIDTH = 6
FIELD_GAP = 1
FULL_ROW_WIDTH = MIN_LABEL_WIDTH + FIELD_GAP + PRICE_WIDTH + FIELD_GAP + CHANGE_WIDTH

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


def format_row(symbol: str, name: str, price_str: str, change_str: str, cols: int) -> str:
    """Build one board row for a coin, deriving every field width from *cols*.

    ``cols`` is not a Flagship/panel classifier -- it is the exact width
    available, and every field is sized off it arithmetically:

    - Below ``FULL_ROW_WIDTH`` there isn't room for a change column at all
      (a Note is exactly a 4-wide symbol + 1 gap + a 10-wide price), so the
      row is just symbol + price, with price sized to fill what's left.
    - At or above ``FULL_ROW_WIDTH``, price and change keep their declared
      widths and the label gets whatever columns remain. At exactly
      ``FULL_ROW_WIDTH`` that is 4 (a ticker); on anything wider the label
      grows into the coin's full name instead of leaving the extra columns
      blank.
    """
    if cols < FULL_ROW_WIDTH:
        price_width = max(cols - MIN_LABEL_WIDTH - FIELD_GAP, 1)
        line = f"{symbol:<{MIN_LABEL_WIDTH}} {price_str:>{price_width}}"
        return line[:cols]

    label_width = cols - PRICE_WIDTH - CHANGE_WIDTH - 2 * FIELD_GAP
    label = symbol if label_width <= MIN_LABEL_WIDTH else name[:label_width]
    change_pct = f"{change_str}%"
    return f"{label:<{label_width}} {price_str:>{PRICE_WIDTH}} {change_pct:>{CHANGE_WIDTH}}"


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
            board = self.board
            cols = board.cols if board else DEFAULT_BOARD_COLS

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
                items.append(self._build_item(coin_id, entry, currency, cols))

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

    def _build_item(self, coin_id: str, entry: Dict[str, Any], currency: str, cols: int) -> Dict[str, Any]:
        """Build one array item from a CoinGecko price entry.

        ``formatted`` is sized to *cols*, the board currently bound via
        ``self.board`` (see :meth:`fetch_data`) -- never a fixed width.
        """
        price = float(entry[currency])
        change = float(entry.get(f"{currency}_24h_change") or 0.0)
        symbol = coin_symbol(coin_id)
        name = coin_name(coin_id)
        price_str = format_price(price)
        change_str = format_change(change)
        return {
            "id": coin_id,
            "symbol": symbol,
            "name": name,
            "price": price_str,
            "change_24h": change_str,
            "change_sign": "+" if change >= 0 else "-",
            "formatted": format_row(symbol, name, price_str, change_str, cols),
        }

    def get_formatted_display(self) -> Optional[List[str]]:
        """Return default display: CRYPTO header then one line per coin."""
        # Pass self.board through explicitly. Calling get_data() with no
        # argument would rebind self.board to None for the duration of the
        # fetch (get_data's own board=None default), so fetch_data would
        # build "formatted" for a flagship-sized board no matter what's
        # actually rendering, and every board would share get_data's single
        # board-agnostic cache slot instead of one keyed to its own geometry.
        board = self.board
        result = self.get_data(board)
        if not result.available or not result.data:
            return None

        rows = board.rows if board else DEFAULT_BOARD_ROWS
        cols = board.cols if board else DEFAULT_BOARD_COLS

        lines = ["CRYPTO".center(cols)]
        for coin in result.data["coins"][: rows - 1]:
            lines.append(coin["formatted"][:cols])

        while len(lines) < rows:
            lines.append("")

        return lines[:rows]


# Export the plugin class
Plugin = CryptoPlugin
