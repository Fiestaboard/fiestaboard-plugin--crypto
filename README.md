# Crypto Prices Plugin

Display live cryptocurrency prices and 24-hour changes from the [CoinGecko](https://www.coingecko.com/) API.

**→ [Setup Guide](./docs/SETUP.md)** - Configuration instructions

## Overview

The Crypto Prices plugin fetches current prices and 24h percentage changes for up to 10 coins from CoinGecko's free public API and displays them on your board. No API key is required.

Default display:

```
        CRYPTO
BTC      77,679  +0.6%
ETH       2,513  -0.3%
SOL       84.10  +2.1%
```

## Template Variables

### Primary Coin (First Configured)

```
{{crypto.symbol}}        # Ticker symbol (e.g. "BTC")
{{crypto.price}}         # Formatted price (e.g. "77,679")
{{crypto.change_24h}}    # Signed 24h change, no % sign (e.g. "+0.6")
{{crypto.change_sign}}   # "+" or "-"
{{crypto.formatted}}     # Pre-formatted 22-char line
{{crypto.count}}         # Number of coins with price data
```

### Individual Coins (Array)

```
{{crypto.coins.0.id}}           # CoinGecko id (e.g. "bitcoin")
{{crypto.coins.0.symbol}}       # Ticker (e.g. "BTC")
{{crypto.coins.0.name}}         # Name (e.g. "Bitcoin")
{{crypto.coins.0.price}}        # Formatted price
{{crypto.coins.0.change_24h}}   # Signed 24h change (e.g. "-0.3")
{{crypto.coins.0.change_sign}}  # "+" or "-"
{{crypto.coins.0.formatted}}    # "BTC      77,679  +0.6%"
```

Coins appear in the order you configured them; ids CoinGecko doesn't recognise are skipped.

### Price formatting

| Price | Shown as |
|-------|----------|
| >= 1000 | no decimals, thousands separator (`77,679`) |
| >= 1 | two decimals (`84.10`) |
| < 1 | four significant digits (`0.1234`, `0.00001234`) |

### Color rules

`change_24h` has default color rules: green when >= 0, red when < 0. The template engine prepends the color tile automatically when you reference `{{crypto.change_24h}}`.

## Example Templates

### Coin List

```
{center}CRYPTO
{{crypto.coins.0.formatted}}
{{crypto.coins.1.formatted}}
{{crypto.coins.2.formatted}}
{{crypto.coins.3.formatted}}
{{crypto.coins.4.formatted}}
```

### Single Coin

```
{center}{{crypto.coins.0.name}}
{center}{{crypto.price}}
{center}{{crypto.change_24h}}%
```

## Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| enabled | boolean | false | Enable/disable the plugin |
| coins | string | "bitcoin,ethereum,solana" | Comma-separated CoinGecko coin ids (max 10) |
| currency | string | "usd" | 3-letter quote currency (usd, eur, gbp, ...) |
| api_key | string | - | Optional CoinGecko demo API key |
| refresh_seconds | integer | 300 | Update interval (minimum 60) |

Known ids map to tickers (bitcoin→BTC, ethereum→ETH, solana→SOL, dogecoin→DOGE, cardano→ADA, ripple→XRP, litecoin→LTC, polkadot→DOT, chainlink→LINK, avalanche-2→AVAX). Other ids use their first four letters uppercased.

## API

This plugin uses the free [CoinGecko API](https://docs.coingecko.com/reference/simple-price):

```
GET https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true
```

No API key is required. The public tier allows roughly 30 requests per minute; the plugin makes one request per refresh, so the default 300-second interval is well within limits. A [demo API key](https://www.coingecko.com/en/api/pricing) can be set to raise the limit; it is sent as the `x-cg-demo-api-key` header. On HTTP 429 the plugin reports unavailable until the next refresh.

## Development

```bash
pip install -r requirements-dev.txt
pytest tests/ -v --cov=.
```

See `.github/workflows/ci.yml` for the full test setup (the plugin is tested against the FiestaBoard core checkout).

## Author

FiestaBoard Team
