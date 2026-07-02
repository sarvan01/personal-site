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

Pulls macro-index / macro-pulse / crypto-pulse from the **JSON endpoints your
browser calls** — the pages render client-side, so fetching the raw HTML gets
nothing. You find those endpoints once via DevTools; the script does the rest.

**Milk Road has no public API**; these pages are premium and behind your
login. Automated access to a paid product is a Terms-of-Service judgment call
— you're the account holder, and this pulls only your own subscription's data
for your own private dashboard, not for redistribution. If in doubt, Milk
Road's support can confirm whether personal-use automation is acceptable for
your account.

**Step 1 — find the JSON endpoint + cookie (one-time, per page, ~2 min each):**

1. Open Chrome or Edge, log into milkroad.com.
2. Go to `https://milkroad.com/data/macro-index/`.
3. Open DevTools (`F12`), click the **Network** tab, filter to **Fetch/XHR**.
4. Reload the page (`F5`).
5. Look through the request list for one whose **Response** (or Preview) tab
   shows JSON containing the index number/label — often named something with
   `api`, `index`, `pulse`, or `score` in the URL.
6. Right-click that request → **Copy → Copy link address** — this is the `url`.
7. In its **Response** tab, note which key holds the number and which holds
   any label, e.g. `{"data": {"score": 62, "label": "Risk-On"}}` →
   `value_path = "data.score"`, `label_path = "data.label"`.
8. On the **same** request, open the **Headers** tab → *Request Headers* →
   find `cookie:` → copy its entire value (long string). This is your
   `MILKROAD_COOKIE`.
9. Repeat steps 2–7 for `/data/macro-pulse/` and `/data/crypto-pulse/` (the
   cookie from step 8 is shared across all three — copy it once).

**Step 2 — configure and run:**

```powershell
copy scripts\feeds\milkroad_endpoints.sample.json scripts\feeds\milkroad_endpoints.json
notepad scripts\feeds\milkroad_endpoints.json
REM paste the 3 URLs + fix value_path/label_path if your JSON shape differs

set MILKROAD_COOKIE=paste_the_long_cookie_string_here
python scripts\feeds\fetch_milkroad_indicators.py --debug
```

`--debug` prints each endpoint's raw JSON — use it to confirm or fix
`value_path`/`label_path` in the config before relying on the output. Once it
reports real numbers, drop `--debug` for normal runs:

```powershell
python scripts\feeds\fetch_milkroad_indicators.py
python scripts\cockpit.py --config h1b
```

**Cookies expire** (typically days to weeks) — when the script starts
reporting HTTP errors, repeat steps 8–9 and update `MILKROAD_COOKIE`.
`scripts\feeds\milkroad_endpoints.json` is gitignored (it's your personal
config, not committed).

Both templates **merge** into `data/milkroad.json` without clobbering the other
section, so you can run Discord for trades and the indicators fetcher for
indicators independently.
