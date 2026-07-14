"""
PSEi Stock Signal Dashboard
=============================
Pulls daily price history for a small watchlist of Philippine Stock
Exchange (PSE) listed stocks, computes classic technical indicators
(SMA, RSI, MACD), derives a simple BUY / SELL / HOLD signal for each
stock, and writes everything to a single self-contained HTML dashboard
you can open in your browser.

This tool does NOT place trades. It only surfaces signals for you to review.

HOW TO RUN
----------
1. Install dependencies (one time):
       pip install yfinance pandas plotly

2. Edit the WATCHLIST list below (max ~5 tickers keeps it fast and readable).
   PSE tickers on Yahoo Finance use a ".PS" suffix, e.g. "SM.PS".

3. Run it:
       python trading_dashboard.py

4. Open the generated file:
       dashboard.html

5. (Optional) Automate the daily check:
   - Mac/Linux: add a cron job, e.g. run at 5pm every weekday (after PSE close):
       0 17 * * 1-5 /usr/bin/python3 /path/to/trading_dashboard.py
   - Windows: use Task Scheduler to run this script daily.

DISCLAIMER
----------
This is a technical-analysis educational tool, not financial advice.
Indicators are lagging by nature and can produce false signals, especially
in choppy or low-volume markets. Always do your own research and consider
your own risk tolerance before trading.
"""

import sys
from datetime import datetime

import pandas as pd

# ---------------------------------------------------------------------------
# CONFIG — edit this section
# ---------------------------------------------------------------------------
# 2 blue chips (SM Investments, BDO Unibank) + 3 non-blue-chip / REITs
# (AREIT, RCR — real estate income plays; WLCON — mid-cap growth retailer)
WATCHLIST = ["SM.PS", "BDO.PS", "AREIT.PS", "RCR.PS", "WLCON.PS"]
LOOKBACK_PERIOD = "1y"      # how much history to pull (e.g. "6mo", "1y", "2y")
SMA_FAST = 50
SMA_SLOW = 200
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
OUTPUT_FILE = "dashboard.html"
# ---------------------------------------------------------------------------


def fetch_data(ticker: str, period: str) -> pd.DataFrame:
    """Download daily OHLCV data for a ticker."""
    import yfinance as yf
    df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
    if df.empty:
        raise ValueError(f"No data returned for {ticker}. Check the ticker symbol.")
    # yfinance sometimes returns MultiIndex columns for a single ticker — flatten them
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add SMA, RSI, MACD columns to the dataframe."""
    df = df.copy()

    # Simple Moving Averages
    df[f"SMA{SMA_FAST}"] = df["Close"].rolling(SMA_FAST).mean()
    df[f"SMA{SMA_SLOW}"] = df["Close"].rolling(SMA_SLOW).mean()

    # RSI (Wilder's smoothing)
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / RSI_PERIOD, min_periods=RSI_PERIOD, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / RSI_PERIOD, min_periods=RSI_PERIOD, adjust=False).mean()
    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # MACD
    ema_fast = df["Close"].ewm(span=MACD_FAST, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=MACD_SLOW, adjust=False).mean()
    df["MACD"] = ema_fast - ema_slow
    df["MACD_signal"] = df["MACD"].ewm(span=MACD_SIGNAL, adjust=False).mean()
    df["MACD_hist"] = df["MACD"] - df["MACD_signal"]

    return df


def generate_signal(df: pd.DataFrame) -> dict:
    """
    Look at the most recent bar(s) and derive a simple BUY / SELL / HOLD
    signal plus the reasons behind it. This is intentionally simple and
    transparent so you can see exactly why it fired.
    """
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    reasons = []
    score = 0  # positive = bullish, negative = bearish

    # 1. Trend: price vs long SMA
    if pd.notna(latest[f"SMA{SMA_SLOW}"]):
        if latest["Close"] > latest[f"SMA{SMA_SLOW}"]:
            score += 1
            reasons.append(f"Price above SMA{SMA_SLOW} (long-term uptrend)")
        else:
            score -= 1
            reasons.append(f"Price below SMA{SMA_SLOW} (long-term downtrend)")

    # 2. Golden cross / death cross (SMA_FAST vs SMA_SLOW)
    if pd.notna(latest[f"SMA{SMA_FAST}"]) and pd.notna(latest[f"SMA{SMA_SLOW}"]):
        fast_now, slow_now = latest[f"SMA{SMA_FAST}"], latest[f"SMA{SMA_SLOW}"]
        fast_prev, slow_prev = prev[f"SMA{SMA_FAST}"], prev[f"SMA{SMA_SLOW}"]
        if fast_prev <= slow_prev and fast_now > slow_now:
            score += 2
            reasons.append(f"Golden cross: SMA{SMA_FAST} just crossed above SMA{SMA_SLOW}")
        elif fast_prev >= slow_prev and fast_now < slow_now:
            score -= 2
            reasons.append(f"Death cross: SMA{SMA_FAST} just crossed below SMA{SMA_SLOW}")

    # 3. MACD crossover
    if pd.notna(latest["MACD"]) and pd.notna(latest["MACD_signal"]):
        if prev["MACD"] <= prev["MACD_signal"] and latest["MACD"] > latest["MACD_signal"]:
            score += 2
            reasons.append("MACD crossed above its signal line (bullish momentum shift)")
        elif prev["MACD"] >= prev["MACD_signal"] and latest["MACD"] < latest["MACD_signal"]:
            score -= 2
            reasons.append("MACD crossed below its signal line (bearish momentum shift)")
        elif latest["MACD"] > latest["MACD_signal"]:
            score += 1
            reasons.append("MACD above signal line (momentum still positive)")
        else:
            score -= 1
            reasons.append("MACD below signal line (momentum still negative)")

    # 4. RSI — overbought / oversold
    if pd.notna(latest["RSI"]):
        if latest["RSI"] < RSI_OVERSOLD:
            score += 1
            reasons.append(f"RSI at {latest['RSI']:.1f} — oversold, watch for a bounce")
        elif latest["RSI"] > RSI_OVERBOUGHT:
            score -= 1
            reasons.append(f"RSI at {latest['RSI']:.1f} — overbought, watch for a pullback")
        else:
            reasons.append(f"RSI at {latest['RSI']:.1f} — neutral zone")

    # Translate score to a signal label
    if score >= 3:
        label = "BUY"
    elif score <= -3:
        label = "SELL"
    else:
        label = "HOLD"

    return {
        "signal": label,
        "score": score,
        "reasons": reasons,
        "close": latest["Close"],
        "date": df.index[-1].strftime("%Y-%m-%d"),
    }


def build_chart_html(ticker: str, df: pd.DataFrame) -> str:
    """Build a Plotly price+indicator chart for one ticker, return as HTML div."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.55, 0.2, 0.25], vertical_spacing=0.03,
        subplot_titles=(f"{ticker} — Price & Moving Averages", "RSI", "MACD"),
    )

    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name="Price", showlegend=False,
    ), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df[f"SMA{SMA_FAST}"], name=f"SMA{SMA_FAST}",
                              line=dict(width=1.3)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df[f"SMA{SMA_SLOW}"], name=f"SMA{SMA_SLOW}",
                              line=dict(width=1.3)), row=1, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI",
                              line=dict(width=1.3, color="#8e44ad")), row=2, col=1)
    fig.add_hline(y=RSI_OVERBOUGHT, line_dash="dot", line_color="red", row=2, col=1)
    fig.add_hline(y=RSI_OVERSOLD, line_dash="dot", line_color="green", row=2, col=1)

    fig.add_trace(go.Bar(x=df.index, y=df["MACD_hist"], name="MACD Hist",
                          marker_color="#95a5a6"), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD",
                              line=dict(width=1.3, color="#2980b9")), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD_signal"], name="Signal",
                              line=dict(width=1.3, color="#e67e22")), row=3, col=1)

    fig.update_layout(
        height=700, margin=dict(l=40, r=20, t=40, b=20),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.08),
        template="plotly_white",
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def build_dashboard(results: list[dict]) -> str:
    """Assemble the full HTML dashboard page from per-ticker results."""
    signal_colors = {"BUY": "#1e8e3e", "SELL": "#d93025", "HOLD": "#e8a33d"}

    summary_rows = ""
    for r in results:
        color = signal_colors[r["signal"]]
        summary_rows += f"""
        <tr>
          <td><strong>{r['ticker']}</strong></td>
          <td>₱{r['close']:.2f}</td>
          <td><span style="background:{color};color:white;padding:4px 10px;
              border-radius:12px;font-weight:600;">{r['signal']}</span></td>
          <td style="font-size:0.85em;color:#555;">{'; '.join(r['reasons'])}</td>
        </tr>"""

    chart_sections = ""
    for r in results:
        chart_sections += f"""
        <div class="chart-card">
          {r['chart_html']}
        </div>"""

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>PSEi Stock Signal Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif;
         background:#f5f6f8; margin:0; padding:24px; color:#1a1a1a; }}
  h1 {{ margin-bottom:4px; }}
  .timestamp {{ color:#777; margin-bottom:24px; font-size:0.9em; }}
  table {{ width:100%; border-collapse:collapse; background:white;
          box-shadow:0 1px 3px rgba(0,0,0,0.1); border-radius:8px; overflow:hidden; }}
  th, td {{ text-align:left; padding:12px 16px; border-bottom:1px solid #eee; }}
  th {{ background:#fafafa; font-size:0.8em; text-transform:uppercase; color:#666; }}
  .chart-card {{ background:white; border-radius:8px; padding:16px; margin-top:24px;
                box-shadow:0 1px 3px rgba(0,0,0,0.1); }}
  .disclaimer {{ margin-top:32px; padding:16px; background:#fff8e1; border-left:4px solid #e8a33d;
                font-size:0.85em; color:#555; border-radius:4px; }}
</style>
</head>
<body>
  <h1>📊 PSEi Stock Signal Dashboard</h1>
  <div class="timestamp">Generated {now}</div>

  <table>
    <tr><th>Ticker</th><th>Last Close</th><th>Signal</th><th>Why</th></tr>
    {summary_rows}
  </table>

  {chart_sections}

  <div class="disclaimer">
    <strong>Not financial advice.</strong> These signals come from lagging technical
    indicators (SMA crossovers, RSI, MACD) applied mechanically to recent price
    history. They can and do produce false signals. Use this as one input among many,
    do your own research, and only invest what you can afford to lose.
  </div>
</body>
</html>"""


def main():
    results = []
    for ticker in WATCHLIST:
        print(f"Fetching {ticker}...")
        try:
            df = fetch_data(ticker, LOOKBACK_PERIOD)
            df = compute_indicators(df)
            sig = generate_signal(df)
            sig["ticker"] = ticker
            sig["chart_html"] = build_chart_html(ticker, df)
            results.append(sig)
            print(f"  -> {sig['signal']} at ₱{sig['close']:.2f}")
        except Exception as e:
            print(f"  !! Failed to process {ticker}: {e}", file=sys.stderr)

    if not results:
        print("No results generated — check your internet connection and ticker symbols.")
        sys.exit(1)

    html = build_dashboard(results)
    with open(OUTPUT_FILE, "w") as f:
        f.write(html)
    print(f"\nDashboard written to {OUTPUT_FILE} — open it in your browser.")


if __name__ == "__main__":
    main()
