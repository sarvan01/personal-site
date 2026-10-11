# Trading Cockpit — Next.js dashboard (optional)

A premium dashboard for the two-sleeve system: KPI tiles, radial gauges
(regime exposure, drawdown-vs-breaker, funding, backtest gate), an equity
area chart, and signal cards. It reads `../out/status.json` (produced by
`scripts/cockpit.py`) — it runs **no** trading logic and places **no** orders.

> **This is a standalone app — NOT part of the portfolio site.** It lives
> under `trading-system/dashboard/` and is independent of the repo root.
>
> **You also don't need it.** The Python cockpit already produces a complete,
> premium single-file dashboard at `out/cockpit.html` (just double-click it,
> no Node required). This Next.js version is for when you want a live,
> component-based UI.

## Prerequisites

- Node.js 20+ and npm.

## Run it

```bash
cd trading-system/dashboard
npm install          # first time only
npm run dev          # starts http://localhost:4317
```

`npm run dev` first runs `npm run sync`, which copies the latest
`../out/status.json` into `public/`. So the flow each day is:

```bash
# from trading-system/
python scripts/cockpit.py --config h1b   # refresh status.json
cd dashboard && npm run dev               # view it (or just refresh the page)
```

A sample `public/status.json` is bundled so the app renders before you've run
the cockpit.

## Notes / troubleshooting

- Pinned to Next 16 / React 19 / Recharts 3. If `npm install` complains about
  peer versions, send me the error — versions move fast and may need a bump.
- The page is a client component that `fetch('/status.json')`s on load; press
  refresh after re-running the cockpit to see new data (or restart `npm run dev`
  to re-sync).
- Port 4317 is used to avoid clashing with the portfolio site's dev server.
- This scaffold was written but **not build-verified** in the authoring
  environment (no Node there). If anything fails to build, paste the error and
  it's a quick fix. The single-file `out/cockpit.html` is the verified primary.
