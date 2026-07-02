# Milk Road context feed

A **display-only** side panel in the cockpit showing Milk Road indicators and
latest trades. **It is context, not a trading signal** — it never touches the
strategy, the risk engine, or the paper account. If you ever want Milk Road
data to influence trades, it must first become a pre-registered hypothesis,
tested through the same gate as H1b/H3.

## How it works

The cockpit reads `data/milkroad.json` (if present) and renders the panel.
No file → no panel (nothing else changes). Three ways to populate it, in
order of effort:

1. **Zero-setup**: `fetch_fear_greed.py` — the Crypto Fear & Greed Index, via
   your CoinStats Premium key (already set up for the archived privacy
   study) or a free no-login fallback.
2. **Manual**: copy the sample and edit it by hand.
3. **Automated from Milk Road PRO**: `fetch_milkroad_indicators.py` — needs a
   short one-time DevTools setup (below).

```powershell
copy milkroad.sample.json data\milkroad.json
python scripts\cockpit.py --config h1b
```

## Schema (`data/milkroad.json`)

```json
{
  "updated_utc": "2026-07-02 13:00 UTC",
  "source": "manual | discord | milkroad.com | alternative.me",
  "indicators": {
    "macro_index":  { "value": 0.29, "label": "Risk On", "as_of": "YYYY-MM-DD",
                       "min": -3, "max": 3 },
    "macro_pulse":  { "value": 0-100, "label": "text", "as_of": "YYYY-MM-DD" },
    "crypto_pulse": { "value": 0-100, "label": "text", "as_of": "YYYY-MM-DD" },
    "fear_greed":   { "value": 0-100, "label": "text", "as_of": "YYYY-MM-DD" }
  },
  "trades": [
    { "date": "YYYY-MM-DD", "action": "BUY|SELL|HOLD|WATCH|TRIM|ADD",
      "asset": "SOL", "note": "text", "source": "discord",
      "analyst": "optional", "perf_pct": "optional number" }
  ]
}
```

All fields are optional and degrade gracefully. `min`/`max` default to 0/100
if omitted — set them when an indicator uses a different scale (Milk Road's
own Macro Index runs roughly **-3 to +3**, not 0-100; the dashboard meter
normalizes using whatever range you give it). `analyst` and `perf_pct` on a
trade are shown as extra table columns only when present on at least one
trade — plain manual/Discord entries without them render the same simple
table as before.

## Option 1 — Crypto Fear & Greed Index (no DevTools needed)

Fills the `fear_greed` indicator only; run Option 2 below for the other
three. Two sources, same underlying index (0-100, Extreme Fear..Extreme
Greed) — this is the same number Milk Road's Crypto Pulse page displays.

**CoinStats (recommended — you already have Premium set up):**

```powershell
set COINSTATS_API_KEY=your_key
python scripts\feeds\fetch_fear_greed.py
python scripts\cockpit.py --config h1b
```

Uses CoinStats' `/insights/fear-and-greed` endpoint — genuine key-based
access via the same `COINSTATS_API_KEY` already used for the archived H2
privacy-coin study, no scraping or cookies involved.

**Free fallback (no key at all):**

```powershell
python scripts\feeds\fetch_fear_greed.py --source alternative
python scripts\cockpit.py --config h1b
```

Uses `alternative.me`'s public API — no login, no cookie, no key.

## Option 2 — automated from your Milk Road PRO account

**Milk Road has no public API**, and these pages are premium/behind your
login. Automating access to a paid product for your own private dashboard
(not redistribution) is a Terms-of-Service judgment call you make as the
account holder — Milk Road's support can confirm what's acceptable if in
doubt.

The `/data/` pages render client-side (JavaScript fetches the numbers after
load), so scraping raw HTML gets nothing — you need the underlying JSON API
call, found once via DevTools.

### Finding the data (one-time, ~2 min per page)

1. Log into milkroad.com in Chrome or Edge.
2. Open the page you want (e.g. `https://milkroad.com/data/macro-index/`).
3. Press `F12` → **Network** tab → filter to **Fetch/XHR**.
4. Reload the page (`F5`).
5. **Fast way to find the right request**: press `Ctrl+Shift+F` to open
   DevTools' cross-resource **Search** panel, and search for a number you can
   see on the page — e.g. for the Macro Index page, search `0.29` (the
   headline MRMI value) or `3.83` (Macro Stress) or `0.73` (Market Momentum).
   This jumps straight to the response containing it instead of you checking
   requests one by one.
6. Click that request → right-click → **Copy → Copy link address** (the `url`).
7. In its **Response** tab, note the JSON key(s) holding the number and any
   label, e.g. `{"data": {"score": 0.29, "label": "Risk On"}}` →
   `value_path = "data.score"`, `label_path = "data.label"`.
8. On the same request, open **Headers** → *Request Headers* → copy the full
   `cookie:` value. This is shared across all Milk Road pages — copy it once.
9. Repeat for `/data/macro-pulse/` and `/data/crypto-pulse/`.

### Configure and run

```powershell
copy scripts\feeds\milkroad_endpoints.sample.json scripts\feeds\milkroad_endpoints.json
notepad scripts\feeds\milkroad_endpoints.json
REM paste your 3 URLs, fix value_path/label_path if your JSON shape differs

set MILKROAD_COOKIE=paste_the_long_cookie_string_here
python scripts\feeds\fetch_milkroad_indicators.py --debug
```

`--debug` prints each endpoint's raw JSON so you can confirm or fix the paths
before relying on it. Once it reports real numbers:

```powershell
python scripts\feeds\fetch_milkroad_indicators.py
python scripts\cockpit.py --config h1b
```

**Cookies expire** (days to weeks) — when it starts erroring, repeat step 8–9
and update `MILKROAD_COOKIE`. `scripts\feeds\milkroad_endpoints.json` is
gitignored (your personal config, not committed).

## Trades — two sources, pick one

### Recommended: Milk Road's own "Analyst Trade Log" page

If your account shows **Trades → Analyst Trade Log** with a structured table
(date, analyst, action, asset, shares, price, perf%, rationale), that's a
better source than Discord — same DevTools technique as above (search
network responses for a distinctive rationale phrase you can see on the page,
or an asset ticker like `CRWV`, to find the right request fast), no bot setup
required. This isn't built as a ready-made script yet since the exact JSON
shape varies by account — if you find the endpoint, paste me an example
response (redact the cookie) and I'll wire up a proper fetcher for it, mapped
to the richer `analyst`/`perf_pct` trade fields above.

### Alternative: your own Discord bot

`fetch_milkroad_discord.py` reads trade-call messages from a Discord channel
using **your own bot** (never a personal user token / self-bot — that
violates Discord's ToS).

```powershell
pip install discord.py
set DISCORD_BOT_TOKEN=your_bot_token
python scripts\feeds\fetch_milkroad_discord.py --channel <CHANNEL_ID> --limit 40
```

Create a bot in the Discord Developer Portal, enable the **Message Content**
intent, invite it to the server, and adapt `parse_trade()` to the channel's
actual message format.

---

All three scripts **merge** into `data/milkroad.json` without clobbering
other sections — run `fetch_fear_greed.py`, `fetch_milkroad_indicators.py`,
and a trades fetcher independently, in any order.
