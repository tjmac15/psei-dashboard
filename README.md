# PSEi Stock Signal Dashboard

A local Python tool that checks a small Philippine Stock Exchange (PSE)
watchlist once a day, computes classic technical indicators, and gives
you a **BUY / SELL / HOLD** read on each stock with the reasoning behind
it — as a dashboard you open in your browser.

It does **not** place trades. It's read-only: you stay in control of every decision.

Data comes from the [EODHD](https://eodhd.com) API. Yahoo Finance
(yfinance) has essentially no working historical data for individual PSE
stocks, and Twelve Data — despite listing PSE as a supported exchange —
actually gates individual PSE stock data behind their $329/month Ultra
plan. EODHD's free plan genuinely includes EOD historical data for any
ticker worldwide (capped at 1 year of history and 20 API calls/day),
which comfortably covers checking 5 stocks once a day.

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

**1. Get a free EODHD API key:**
- Go to [eodhd.com](https://eodhd.com) → sign up (no card needed)
- Your API key is on your account dashboard after signing in
- Free tier: 20 API calls/day, 1 year of history — this script uses 5
  calls per run, well within the limit

**2. Install dependencies:**
```bash
pip install -r requirements.txt
```

## Usage (running locally)

1. Set your API key as an environment variable:
   ```bash
   # Mac/Linux
   export EODHD_API_TOKEN="your_key_here"
   # Windows (PowerShell)
   $env:EODHD_API_TOKEN="your_key_here"
   ```
2. (Optional) Edit the `WATCHLIST` list in `trading_dashboard.py` — use
   plain PSE symbols like `"SM"`; the `.PSE` exchange suffix is added
   automatically.
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
   - Name: `EODHD_API_TOKEN`
   - Value: paste your EODHD API key
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
- The free EODHD tier caps history at 1 year, which means SMA200 (which
  needs 200 trading days) only has valid values for roughly the most
  recent 2-3 months of that window — plenty for today's signal, but not
  enough to backtest the strategy over a longer stretch without a paid
  plan.
- This tool only looks at price/volume history — it ignores company
  fundamentals, earnings, and PSE-specific news.
- Philippine small/mid-cap stocks can have lower trading volume than
  their US counterparts, which can make price swings choppier and
  technical signals noisier — the 2-day confirmation rule in this
  script exists specifically to cut down on that.
- This is a personal research tool, not financial advice, and not a
  licensed trading system.

