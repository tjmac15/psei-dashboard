# PSEi Stock Signal Dashboard

A local Python tool that checks a small Philippine Stock Exchange (PSE)
watchlist once a day, computes classic technical indicators, and gives
you a **BUY / SELL / HOLD** read on each stock with the reasoning behind
it — as a dashboard you open in your browser.

It does **not** place trades. It's read-only: you stay in control of every decision.

## Watchlist

| Ticker | Company | Type |
|---|---|---|
| SM.PS | SM Investments Corp | Blue chip (conglomerate) |
| BDO.PS | BDO Unibank | Blue chip (banking) |
| AREIT.PS | AREIT (Ayala Land REIT) | REIT (office & retail) |
| RCR.PS | RL Commercial REIT | REIT (office, BPO tenants) |
| WLCON.PS | Wilcon Depot | Mid-cap (home improvement retail) |

PSE-listed stocks use a `.PS` suffix on Yahoo Finance (the data source
this script uses), so all tickers are written as e.g. `SM.PS` rather
than just `SM`.

## What it does

For each ticker, it pulls ~1 year of daily price history and computes:

- **SMA 50 / SMA 200** — trend direction, golden cross / death cross
- **RSI (14)** — overbought (>70) / oversold (<30)
- **MACD (12, 26, 9)** — momentum shifts via signal-line crossovers

These are combined into a simple transparent score → BUY / SELL / HOLD,
and plotted on an interactive candlestick + indicator chart. Prices are
shown in Philippine Pesos (₱).

## Setup (one time)

```bash
pip install -r requirements.txt
```

## Usage

1. Open `trading_dashboard.py` and edit the `WATCHLIST` list near the
   top if you want different stocks (keep the `.PS` suffix):

   ```python
   WATCHLIST = ["SM.PS", "BDO.PS", "AREIT.PS", "RCR.PS", "WLCON.PS"]
   ```

2. Run it:

   ```bash
   python trading_dashboard.py
   ```

3. Open the generated `dashboard.html` in your browser.

## Hosting it on GitHub (recommended)

This repo includes `.github/workflows/dashboard.yml`, which runs the
script automatically every weekday shortly after the PSE closes
(3:30pm Philippine Time) and publishes the result via GitHub Pages.

1. Create a new **public** GitHub repo and push these files to it:
   ```
   git init
   git add .
   git commit -m "Initial PSEi dashboard"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo>.git
   git push -u origin main
   ```
2. In the repo, go to **Settings → Pages** and set **Source** to
   **GitHub Actions**.
3. Go to the **Actions** tab, select "Daily PSEi Stock Dashboard", and
   click **Run workflow** to trigger the first build manually.
4. After it finishes, your dashboard is live at:
   ```
   https://<your-username>.github.io/<your-repo>/
   ```
   It refreshes automatically after each weekday's market close from
   then on.

## A note before you connect real money to this

- Technical indicators are **lagging** — they react to price moves that
  already happened, not predict future ones.
- REITs (AREIT, RCR) behave differently from regular stocks — their
  price often moves more on interest-rate expectations and dividend
  yield than on the same momentum patterns SMA/RSI/MACD are built to
  catch. Treat their signals here as a rough guide, not a full picture.
- This tool only looks at price/volume history — it ignores company
  fundamentals, earnings, and PSE-specific news.
- Philippine small/mid-cap stocks can have lower trading volume than
  their US counterparts, which can make price swings choppier and
  technical signals noisier.
- This is a personal research tool, not financial advice, and not a
  licensed trading system.
