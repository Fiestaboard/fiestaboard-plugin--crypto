# Crypto Prices Setup Guide

Show live cryptocurrency prices and 24-hour changes on your board, powered by CoinGecko's free API.

## Overview

The Crypto Prices plugin fetches current prices for the coins you choose (up to 10) and exposes them as template variables. It also provides a ready-made display: a `CRYPTO` header followed by one line per coin with the ticker, price, and 24h change.

**Prerequisites:**
- Internet access to `api.coingecko.com`
- No API key required

## Quick Setup

### 1. Enable the Plugin

In the FiestaBoard web UI, go to **Integrations**, find **Crypto Prices**, and click **Enable**.

Or via `.env`:

```bash
CRYPTO_ENABLED=true
```

### 2. Configure

Click **Configure** and fill in:

- **Coins** — Comma-separated CoinGecko coin ids, e.g. `bitcoin,ethereum,solana`. Up to 10. Find ids on any coin's CoinGecko page (the "API ID" field) — note that some differ from the ticker, e.g. `ripple` for XRP and `avalanche-2` for AVAX.
- **Currency** — 3-letter quote currency: `usd` (default), `eur`, `gbp`, `jpy`, etc.
- **Refresh Interval** — How often to fetch prices (default 300 seconds, minimum 60). See "Rate Limits" below.
- **CoinGecko Demo API Key** *(optional)* — Raises the request limit. Leave blank for the public tier.

### 3. Add a Template

Go to **Pages** and create a page using the Crypto Prices plugin. A simple template:

```
{center}CRYPTO
{{crypto.coins.0.formatted}}
{{crypto.coins.1.formatted}}
{{crypto.coins.2.formatted}}
```

Or leave the page template empty to use the built-in display.

### 4. View Your Board

```
        CRYPTO
BTC      77,679  +0.6%
ETH       2,513  -0.3%
SOL       84.10  +2.1%
```

---

## Template Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `{{crypto.symbol}}` | First coin ticker | `BTC` |
| `{{crypto.price}}` | First coin price | `77,679` |
| `{{crypto.change_24h}}` | First coin 24h change, signed (add `%` yourself) | `+0.6` |
| `{{crypto.change_sign}}` | `+` or `-` | `+` |
| `{{crypto.formatted}}` | First coin pre-formatted line | `BTC      77,679  +0.6%` |
| `{{crypto.count}}` | Coins with price data | `3` |
| `{{crypto.coins.N.id}}` | CoinGecko id of coin N (0-based) | `bitcoin` |
| `{{crypto.coins.N.symbol}}` | Ticker | `BTC` |
| `{{crypto.coins.N.name}}` | Name | `Bitcoin` |
| `{{crypto.coins.N.price}}` | Formatted price | `77,679` |
| `{{crypto.coins.N.change_24h}}` | Signed 24h change | `-0.3` |
| `{{crypto.coins.N.change_sign}}` | `+` or `-` | `-` |
| `{{crypto.coins.N.formatted}}` | Pre-formatted line | `ETH       2,513  -0.3%` |

`change_24h` is colored automatically: green for gains (>= 0), red for losses. You can change these rules per field in the web UI.

## Configuration Reference

| Setting | Description | Default | Range |
|---------|-------------|---------|-------|
| `enabled` | Enable the plugin | `false` | true / false |
| `coins` | Comma-separated CoinGecko ids | `bitcoin,ethereum,solana` | 1–10 ids |
| `currency` | Quote currency code | `usd` | any 3-letter code CoinGecko supports |
| `api_key` | CoinGecko demo API key | — | optional |
| `refresh_seconds` | Fetch interval in seconds | `300` | 60–3600 |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `CRYPTO_ENABLED` | Enable the plugin |
| `COINGECKO_API_KEY` | Optional demo API key |

## Rate Limits

CoinGecko's public (keyless) tier allows roughly **30 requests per minute**, shared with everyone on your IP. The plugin makes exactly one request per refresh regardless of how many coins you track, so the default 5-minute interval uses a tiny fraction of that. If you run several CoinGecko-backed tools on the same network and start seeing "rate limit hit (HTTP 429)" errors, increase the refresh interval or add a free demo API key from [coingecko.com/en/api/pricing](https://www.coingecko.com/en/api/pricing).

---

## Troubleshooting

**A coin is missing from the board**
- The id is probably wrong. Ids are lowercase CoinGecko slugs, not tickers: use `bitcoin` not `btc`, `ripple` not `xrp`, `avalanche-2` not `avax`
- Check the id on the coin's CoinGecko page under "API ID"
- Unknown ids are skipped silently so the rest of your list still shows

**"No price data returned for configured coins"**
- None of the ids were recognised — see above
- The currency code may not be supported for those coins; try `usd`

**"CoinGecko rate limit hit (HTTP 429)"**
- Increase **Refresh Interval** (minimum 60 seconds)
- Add a demo API key

**Ticker shows the wrong letters**
- Only well-known coins have a hand-mapped ticker; others show the first four letters of the id. Use `{{crypto.coins.N.name}}` if you prefer the full name

**Prices not updating**
- The plugin re-fetches based on **Refresh Interval** (default every 5 minutes)
- Check the FiestaBoard logs for CoinGecko errors
