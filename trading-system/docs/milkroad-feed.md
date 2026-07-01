# Milk Road context feed

A **display-only** side panel in the cockpit showing Milk Road indicators and
latest trades. **It is context, not a trading signal** — it never touches the
strategy, the risk engine, or the paper account. If you ever want Milk Road
data to influence trades, it must first become a pre-registered hypothesis,
tested through the same gate as H1b/H3.

## How it works

The cockpit reads `data/milkroad.json` (if present) and renders the panel.
No file → no panel (nothing else changes). Populate the JSON however you judge
ToS-compliant.

Quick start (manual):

```powershell
copy milkroad.sample.json data\milkroad.json
python scripts\cockpit.py --config h1b
```

Edit `data\milkroad.json` by hand whenever you want to update it.

## Schema (`data/milkroad.json`)

```json
{
  "updated_utc": "2026-06-13 20:00 UTC",
  "source": "manual | discord | milkroad.com",
  "indicators": {
    "macro_index":  { "value": 0-100, "label": "text", "as_of": "YYYY-MM-DD" },
    "macro_pulse":  { "value": 0-100, "label": "text", "as_of": "YYYY-MM-DD" },
    "crypto_pulse": { "value": 0-100, "label": "text", "as_of": "YYYY-MM-DD" }
  },
  "trades": [
    { "date": "YYYY-MM-DD", "action": "BUY|SELL|HOLD|WATCH|TRIM|ADD",
      "asset": "SOL", "note": "text", "source": "discord" }
  ]
}
```

All fields are optional and degrade gracefully — an empty `trades` list or a
missing indicator just renders less.

## Optional ingestion templates (`scripts/feeds/`)

These are **templates you complete and run locally** with your own
credentials. They were written but not verified in the authoring environment
(no network / no auth there); if one errors, paste it and it's a quick fix.

### Discord trades — `fetch_milkroad_discord.py`

Uses **your own Discord bot** to read a channel and write the latest trades.

```powershell
pip install discord.py
set DISCORD_BOT_TOKEN=your_bot_token
python scripts\feeds\fetch_milkroad_discord.py --channel <CHANNEL_ID> --limit 40
```

- Create a bot in the Discord Developer Portal, enable the **Message Content**
  intent, invite it to the server, and use **its** token.
- **Never** use a personal user token / self-bot — that violates Discord ToS.
- Adapt `parse_trade()` to Milk Road's actual message format.

### Indicators — `fetch_milkroad_indicators.py`

Skeleton to pull macro-index / macro-pulse / crypto-pulse.

```powershell
set MILKROAD_COOKIE=your_session_cookie
python scripts\feeds\fetch_milkroad_indicators.py
```

- **Milk Road has no public API**; these pages are premium and behind your
  login. Automated scraping may conflict with Milk Road's Terms — proceed only
  if you're comfortable it's allowed for your account.
- Fill in `scrape_value()` — the cleanest route is usually the underlying JSON
  endpoint (browser Network tab), not HTML parsing.

Both templates **merge** into `data/milkroad.json` without clobbering the other
section, so you can run Discord for trades and the indicators fetcher for
indicators independently.
