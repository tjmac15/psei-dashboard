# Daily Stock Signal Dashboard

A local Python tool that checks a small watchlist once a day, computes classic
technical indicators, and gives you a **BUY / SELL / HOLD** read on each stock
with the reasoning behind it — as a dashboard you open in your browser.

It does **not** place trades. It's read-only: you stay in control of every decision.

## What it does

For each ticker in your watchlist, it pulls ~1 year of daily price history and computes:

- **SMA 50 / SMA 200** — trend direction, golden cross / death cross
- **RSI (14)** — overbought (>70) / oversold (<30)
- **MACD (12, 26, 9)** — momentum shifts via signal-line crossovers

These are combined into a simple transparent score → BUY / SELL / HOLD, and
plotted on an interactive candlestick + indicator chart.

## Setup (one time)

```bash
pip install -r requirements.txt
```

## Usage

1. Open `trading_dashboard.py` and edit the `WATCHLIST` list near the top
   (keep it to ~5 tickers so it stays fast and readable):

   ```python
   WATCHLIST = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"]
   ```

2. Run it:

   ```bash
   python trading_dashboard.py
   ```

3. Open the generated `dashboard.html` in your browser.

The default watchlist tracks 5 individual large-cap stocks priced
roughly $50-150 a share, spread across different sectors: `WFC`
(Wells Fargo), `CSCO` (Cisco), `XOM` (ExxonMobil), `TGT` (Target),
and `SBUX` (Starbucks) — a mix of steadier names (banking, tech,
energy) and slightly more consumer-cycle-sensitive names (retail,
restaurants) for a bit more day-to-day movement, without straying
into speculative or small-cap territory.

## Automating the daily check (optional)

- **Mac/Linux (cron)** — run every weekday at 9am:
  ```
  0 9 * * 1-5 /usr/bin/python3 /path/to/trading_dashboard.py
  ```
- **Windows** — use Task Scheduler to run the script daily and reopen
  `dashboard.html` in your browser.

## Hosting it on GitHub (recommended — no computer needs to stay on)

This repo includes `.github/workflows/dashboard.yml`, which runs the
script automatically on GitHub's servers every weekday morning and
publishes the result as a website via GitHub Pages.

1. Create a new **public** GitHub repo (Pages' free tier requires public
   for personal accounts) and push these files to it:
   ```
   git init
   git add .
   git commit -m "Initial dashboard"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo>.git
   git push -u origin main
   ```
2. In the repo, go to **Settings → Pages** and set **Source** to
   **GitHub Actions**.
3. Go to the **Actions** tab, select "Daily Stock Dashboard", and click
   **Run workflow** once to trigger the first build manually (otherwise
   it waits for the next scheduled run).
4. After it finishes, your dashboard is live at:
   ```
   https://<your-username>.github.io/<your-repo>/
   ```
   It will then refresh automatically every weekday morning — just
   bookmark the link.

The cron schedule in the workflow runs at 13:00 UTC (~9am US/Eastern).
Edit the `cron:` line in `.github/workflows/dashboard.yml` if you want
a different time.

## Tuning the strategy

All the thresholds live at the top of `trading_dashboard.py`:
`SMA_FAST`, `SMA_SLOW`, `RSI_PERIOD`, `RSI_OVERBOUGHT`, `RSI_OVERSOLD`,
`MACD_FAST`, `MACD_SLOW`, `MACD_SIGNAL`. Adjust and re-run to see how
signals change. The `generate_signal()` function is short and readable —
it's meant to be a starting point you can tweak, not a black box.

## A note before you connect real money to this

- Technical indicators are **lagging** — they react to price moves that
  already happened, not predict future ones. False signals are common,
  especially in choppy or low-volume conditions.
- This tool only looks at price/volume history. It ignores fundamentals,
  news, earnings, and broader market context — all things worth checking
  before you act on a signal.
- Consider backtesting any strategy over historical data (and multiple
  market regimes — bull, bear, sideways) before trusting it with real capital.
- This is a personal research tool, not financial advice, and not a
  licensed trading system.
