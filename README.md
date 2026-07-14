# PSEi Stock Signal Dashboard

A local Python tool that checks a small Philippine Stock Exchange (PSE)
watchlist once a day, computes classic technical indicators, and gives
you a **BUY / SELL / HOLD** read on each stock with the reasoning behind
it — as a dashboard you open in your browser.

It does **not** place trades. It's read-only: you stay in control of every decision.

Data comes from the [Twelve Data](https://twelvedata.com) API, which has
real historical price coverage for individual PSE-listed stocks (Yahoo
Finance/yfinance does not — it only has good data for the PSEi index
itself, not individual PSE stocks, which is why this dashboard uses a
different data source than the US one).

## Watchlist

| Ticker | Company | Type |
|---|---|---|
| SM | SM Investments Corp | Blue chip (conglomerate) |
| BDO | BDO Unibank | Blue chip (banking) |
| AREIT | AREIT (Ayala Land REIT) | REIT (office & retail) |
| RCR | RL Commercial REIT | REIT (office, BPO tenants) |
| WLCON | Wilcon Depot | Mid-cap (home improvement retail) |

## What it does

For each ticker, it pulls ~1.5 years of daily price history and computes:

- **SMA 50 / SMA 200** — trend direction, golden cross / death cross
- **RSI (14)** — overbought (>70) / oversold (<30)
- **MACD (12, 26, 9)** — momentum shifts via signal-line crossovers

These are combined into a transparent score → BUY / SELL / HOLD. To
reduce false flips on lower-volume PH stocks, a signal only fires once
the score has cleared the threshold on 2 consecutive trading days (see
`SIGNAL_THRESHOLD` / `CONFIRMATION_DAYS` at the top of the script).
Everything is plotted on an interactive candlestick + indicator chart,
with prices in Philippine Pesos (₱).

## Setup (one time)

**1. Get a free Twelve Data API key:**
- Go to [twelvedata.com](https://twelvedata.com) → sign up (no card needed)
- Your API key is shown on your account dashboard after signing in
- Free tier: 800 requests/day — this script uses 5 requests per run, so
  daily use isn't close to the limit

**2. Install dependencies:**
```bash
pip install -r requirements.txt
```

## Usage (running locally)

1. Set your API key as an environment variable:
   ```bash
   # Mac/Linux
   export TWELVEDATA_API_KEY="your_key_here"
   # Windows (PowerShell)
   $env:TWELVEDATA_API_KEY="your_key_here"
   ```
2. (Optional) Edit the `WATCHLIST` list in `trading_dashboard.py` — use
   plain PSE symbols like `"SM"`, no suffix needed.
3. Run it:
   ```bash
   python trading_dashboard.py
   ```
4. Open the generated `dashboard.html` in your browser.

## Hosting it on GitHub (recommended)

This repo includes `.github/workflows/dashboard.yml`, which runs the
script automatically every weekday shortly after the PSE closes
(3:30pm Philippine Time) and publishes the result via GitHub Pages.
Your API key is stored as a GitHub secret — never committed to the repo,
never visible in the code.

1. Create a new **public** GitHub repo and push these files to it:
   ```
   git init
   git add .
   git commit -m "Initial PSEi dashboard"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo>.git
   git push -u origin main
   ```
2. **Add your API key as a repo secret:**
   - In the repo: **Settings → Secrets and variables → Actions**
   - Click **New repository secret**
   - Name: `TWELVEDATA_API_KEY`
   - Value: paste your Twelve Data API key
   - Click **Add secret**
3. In the repo, go to **Settings → Pages** and set **Source** to
   **GitHub Actions**.
4. Go to the **Actions** tab, select "Daily PSEi Stock Dashboard", and
   click **Run workflow** to trigger the first build manually.
5. After it finishes, your dashboard is live at:
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
  technical signals noisier — the 2-day confirmation rule in this
  script exists specifically to cut down on that.
- This is a personal research tool, not financial advice, and not a
  licensed trading system.

