"""
DISCLAIMER
----------
This is a technical-analysis educational tool, not financial advice.
Indicators are lagging by nature and can produce false signals, especially
in choppy or low-volume markets. Always do your own research and consider
your own risk tolerance before trading.
"""

import os
import sys
import time
from datetime import datetime

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# CONFIG — edit this section
# ---------------------------------------------------------------------------
# 2 blue chips (SM Investments, BDO Unibank) + 3 non-blue-chip / REITs
# (AREIT, RCR — real estate income plays; WLCON — mid-cap growth retailer)
# Plain PSE symbols — the ".PSE" exchange suffix EODHD expects is added
# automatically in fetch_data().
WATCHLIST = ["SM", "BDO", "AREIT", "RCR", "WLCON"]
EXCHANGE_SUFFIX = "PSE"     # EODHD's exchange code for the Philippine Stock Exchange
SMA_FAST = 50
SMA_SLOW = 200
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
SIGNAL_THRESHOLD = 4         # score must reach +/- this to trigger BUY/SELL (was 3 — raised to reduce whipsaws on lower-volume PH stocks)
CONFIRMATION_DAYS = 2        # score must clear the threshold on this many consecutive days before the signal actually flips
OUTPUT_FILE = "dashboard.html"
CURRENCY_SYMBOL = "₱"
STOP_LOSS_PCT = -8      # if your position is down at least this % and the signal is still HOLD, flag your stop-loss
TAKE_PROFIT_PCT = 20    # if your position is up at least this % and the signal is still HOLD, flag taking some profit

# Optional: AI-written analysis per stock, based on the technical signal only
# (no fundamentals here — those are paywalled for PSE stocks, see README.md).
# Uses Google's Gemini API, which has a genuinely free tier (no credit card,
# no minimum spend) — needs a free API key from https://aistudio.google.com
# set as the GEMINI_API_KEY environment variable. If it's not set, this is
# skipped entirely — the dashboard works exactly as before, no AI section shown.
ENABLE_AI_ANALYSIS = True
GEMINI_MODEL = "gemini-2.5-flash-lite"   # most generous free tier: 15 requests/min, 1,000/day

# Optional: Google sign-in + cloud sync for your buy price/qty entries, so
# they survive across devices and browser data clears instead of relying on
# browser local storage. Leave these as-is to skip cloud sync (the dashboard
# still works fine — entries just stay local-only). To enable it, create a
# free Firebase project (see README.md for exact steps) and paste your web
# app's config values in below.
FIREBASE_CONFIG = {
    "apiKey": "AIzaSyCgkyb5CflgDuEHpeIf_I-64eDqIYlKebs",
    "authDomain": "stock-dashboard-1a7bd.firebaseapp.com",
    "projectId": "stock-dashboard-1a7bd",
    "storageBucket": "stock-dashboard-1a7bd.firebasestorage.app",
    "messagingSenderId": "466011958430",
    "appId": "1:466011958430:web:434377d05c4ba90f691f8f",
}
# ---------------------------------------------------------------------------


def fetch_data(ticker: str, exchange_suffix: str = EXCHANGE_SUFFIX) -> pd.DataFrame:
    """Download daily OHLCV data for a ticker from the EODHD API."""
    api_key = os.environ.get("EODHD_API_TOKEN")
    if not api_key:
        raise EnvironmentError(
            "EODHD_API_TOKEN environment variable is not set. "
            "Get a free key at https://eodhd.com and set it before running."
        )

    full_symbol = f"{ticker}.{exchange_suffix}"
    url = f"https://eodhd.com/api/eod/{full_symbol}"
    params = {
        "api_token": api_key,
        "fmt": "json",
        "period": "d",   # daily
        "order": "a",    # ascending dates (oldest first) — matches what compute_indicators expects
    }
    resp = requests.get(url, params=params, timeout=30)

    if resp.status_code != 200:
        raise ValueError(f"EODHD error for {full_symbol}: HTTP {resp.status_code} — {resp.text[:200]}")

    data = resp.json()
    if not isinstance(data, list) or len(data) == 0:
        raise ValueError(f"EODHD returned no data for {full_symbol}: {data}")

    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    df = df.rename(columns={
        "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume",
    })

    # Small delay to stay comfortably under the free-tier rate limit
    time.sleep(1)

    # Defensive: drop any incomplete rows (missing OHLC) so "latest" always
    # means the last fully-reported trading day, same safeguard as the US script.
    result = df[["Open", "High", "Low", "Close", "Volume"]]
    result = result.dropna(subset=["Open", "High", "Low", "Close"])
    if result.empty:
        raise ValueError(f"No complete trading data available for {full_symbol} after filtering.")
    return result


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


def _score_at(df: pd.DataFrame, i: int) -> tuple[int, list[str]]:
    """
    Compute the bullish/bearish score and reasons for the bar at index i,
    comparing it against the bar at i-1. This is the same logic used for
    every day we check — factored out so generate_signal() can look at
    more than just the single latest day.
    """
    latest = df.iloc[i]
    prev = df.iloc[i - 1]

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

    return score, reasons


def generate_signal(df: pd.DataFrame) -> dict:
    """
    Derive a BUY / SELL / HOLD signal from the recent bars.

    To cut down on whipsaws (especially on lower-volume stocks where a
    single noisy day can flip the score), a BUY or SELL only fires once
    the score has cleared SIGNAL_THRESHOLD on CONFIRMATION_DAYS
    consecutive days in a row. A one-day spike that reverses the next
    day is treated as noise and reported as HOLD.
    """
    latest_score, reasons = _score_at(df, -1)

    # Check the last CONFIRMATION_DAYS days all agree in the same direction
    recent_scores = [_score_at(df, -1 - k)[0] for k in range(CONFIRMATION_DAYS)]
    all_bullish = all(s >= SIGNAL_THRESHOLD for s in recent_scores)
    all_bearish = all(s <= -SIGNAL_THRESHOLD for s in recent_scores)

    if all_bullish:
        label = "BUY"
    elif all_bearish:
        label = "SELL"
    else:
        label = "HOLD"

    latest = df.iloc[-1]
    return {
        "signal": label,
        "score": latest_score,
        "reasons": reasons,
        "open": latest["Open"],
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
        dragmode="pan",   # dragging pans the chart by default (no more accidental box/lasso select)
    )
    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={
            "scrollZoom": True,                          # mouse wheel / trackpad pinch zooms in and out
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],  # these caused the "stuck lasso" issue — removed entirely
            "displaylogo": False,
        },
    )


def build_dashboard(results: list[dict]) -> str:
    """Assemble the full HTML dashboard page from per-ticker results."""
    signal_colors = {"BUY": "#1e8e3e", "SELL": "#d93025", "HOLD": "#e8a33d"}

    summary_rows = ""
    for r in results:
        color = signal_colors[r["signal"]]
        t = r["ticker"]
        summary_rows += f"""
        <tr>
          <td><strong>{t}</strong></td>
          <td>{CURRENCY_SYMBOL}{r['open']:.2f}</td>
          <td>{CURRENCY_SYMBOL}{r['close']:.2f}</td>
          <td><span style="background:{color};color:white;padding:4px 10px;
              border-radius:12px;font-weight:600;">{r['signal']}</span></td>
          <td style="font-size:0.85em;color:#555;">{'; '.join(r['reasons'])}</td>
          <td><input type="number" step="0.01" min="0" class="pos-input" id="buy_{t}"
              placeholder="e.g. {r['close']:.2f}" oninput="updatePL('{t}')"></td>
          <td><input type="number" step="1" min="0" class="pos-input qty-input" id="qty_{t}"
              placeholder="shares" oninput="updatePL('{t}')"></td>
          <td id="pl_{t}"><span style="color:#999;">—</span></td>
          <td id="sugg_{t}"><span style="color:#999;">—</span></td>
        </tr>"""

    chart_sections = ""
    for r in results:
        ai_html = ""
        if r.get("ai_analysis"):
            ai_html = f"""
        <div class="ai-analysis">
          <div class="ai-label">🤖 AI take on {r['ticker']}</div>
          <div>{r['ai_analysis']}</div>
          <div class="ai-caveat">AI-generated from the technical signal above (no fundamentals available for PSE stocks) — may be inaccurate, not financial advice.</div>
        </div>"""
        chart_sections += f"""
        <div class="chart-card">
          {ai_html}
          {r['chart_html']}
        </div>"""

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    current_prices_js = "{" + ", ".join(f'"{r["ticker"]}": {r["close"]}' for r in results) + "}"
    signals_js = "{" + ", ".join(f'"{r["ticker"]}": "{r["signal"]}"' for r in results) + "}"
    firebase_config_js = "{" + ", ".join(f'"{k}": "{v}"' for k, v in FIREBASE_CONFIG.items()) + "}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>PSEi Stock Signal Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.12.0/firebase-app-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.12.0/firebase-auth-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.12.0/firebase-firestore-compat.js"></script>
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
  .pos-input {{ width:90px; padding:6px 8px; border:1px solid #ddd; border-radius:4px; font-size:0.9em; }}
  .qty-input {{ width:70px; }}
  .position-note {{ margin-top:12px; padding:12px 16px; background:#eef4ff; border-left:4px solid #3b82f6;
                    font-size:0.82em; color:#444; border-radius:4px; }}
  .ai-analysis {{ margin-bottom:16px; padding:14px 16px; background:#f6f0ff; border-left:4px solid #8b5cf6;
                  border-radius:4px; font-size:0.9em; color:#333; line-height:1.5; }}
  .ai-label {{ font-weight:700; color:#6d28d9; margin-bottom:4px; }}
  .ai-caveat {{ margin-top:8px; font-size:0.78em; color:#888; }}
  .auth-bar {{ display:flex; align-items:center; gap:12px; margin-bottom:16px; }}
  .auth-btn {{ padding:8px 16px; border-radius:6px; border:1px solid #ddd; background:white;
              cursor:pointer; font-size:0.9em; font-weight:600; }}
  .auth-btn:hover {{ background:#f5f5f5; }}
  #userLabel {{ font-size:0.85em; color:#555; }}
</style>
</head>
<body>
  <h1>📊 PSEi Stock Signal Dashboard</h1>
  <div class="timestamp">Generated {now}</div>

  <div class="auth-bar">
    <button id="signInBtn" class="auth-btn" onclick="signIn()" style="display:none;">Sign in with Google to sync across devices</button>
    <button id="signOutBtn" class="auth-btn" onclick="signOutUser()" style="display:none;">Sign out</button>
    <span id="userLabel"></span>
  </div>

  <table>
    <tr>
      <th>Ticker</th><th>Open</th><th>Last Close</th><th>Signal</th><th>Why</th>
      <th>Your Buy Price</th><th>Qty</th><th>P/L</th><th>Suggested Action</th>
    </tr>
    {summary_rows}
  </table>

  <div class="position-note" id="positionNote">
    Enter your buy price when you buy (and optionally quantity) — leave it
    blank to clear it when you sell. Currently saved only in this browser;
    sign in with Google above to sync across devices instead.
  </div>

  {chart_sections}

  <div class="disclaimer">
    <strong>Not financial advice.</strong> These signals come from lagging technical
    indicators (SMA crossovers, RSI, MACD) applied mechanically to recent price
    history. They can and do produce false signals. Use this as one input among many,
    do your own research, and only invest what you can afford to lose.
  </div>

  <script>
    const currentPrices = {current_prices_js};
    const currentSignals = {signals_js};
    const stopLossPct = {STOP_LOSS_PCT};
    const takeProfitPct = {TAKE_PROFIT_PCT};
    const currencySymbol = "{CURRENCY_SYMBOL}";
    const firebaseConfig = {firebase_config_js};

    let currentUser = null;
    let userPositionsRef = null;
    let firebaseReady = false;

    try {{
      if (firebaseConfig.apiKey && firebaseConfig.apiKey !== "YOUR_API_KEY") {{
        firebase.initializeApp(firebaseConfig);
        firebaseReady = true;
      }}
    }} catch (e) {{
      console.warn("Firebase not configured — using local browser storage only.", e);
    }}

    function signIn() {{
      const provider = new firebase.auth.GoogleAuthProvider();
      firebase.auth().signInWithPopup(provider).catch(function(err) {{
        alert("Sign-in failed: " + err.message);
      }});
    }}

    function signOutUser() {{
      firebase.auth().signOut();
    }}

    function getSuggestion(ticker, pctChange) {{
      const signal = currentSignals[ticker];

      if (signal === 'SELL') {{
        return {{ text: 'Consider selling — signal turned bearish', color: '#d93025' }};
      }}
      if (signal === 'BUY') {{
        return {{ text: 'Hold — uptrend still active', color: '#1e8e3e' }};
      }}
      if (pctChange <= stopLossPct) {{
        return {{ text: 'Down ' + pctChange.toFixed(1) + '% — consider your stop-loss', color: '#d93025' }};
      }}
      if (pctChange >= takeProfitPct) {{
        return {{ text: 'Up ' + pctChange.toFixed(1) + '% — consider taking some profit', color: '#1e8e3e' }};
      }}
      return {{ text: 'Hold', color: '#e8a33d' }};
    }}

    function updatePL(ticker, shouldSave) {{
      if (shouldSave === undefined) shouldSave = true;
      const buyInput = document.getElementById('buy_' + ticker);
      const qtyInput = document.getElementById('qty_' + ticker);
      const plCell = document.getElementById('pl_' + ticker);
      const suggCell = document.getElementById('sugg_' + ticker);
      const buy = parseFloat(buyInput.value);
      const qty = parseFloat(qtyInput.value) || 0;
      const current = currentPrices[ticker];

      if (!buy || buy <= 0) {{
        plCell.innerHTML = '<span style="color:#999;">—</span>';
        suggCell.innerHTML = '<span style="color:#999;">—</span>';
        if (shouldSave) clearPosition(ticker);
        return;
      }}

      const pctChange = ((current - buy) / buy) * 100;
      const sign = pctChange >= 0 ? '+' : '';
      const color = pctChange >= 0 ? '#1e8e3e' : '#d93025';

      let html = '<span style="color:' + color + ';font-weight:600;">' +
                 sign + pctChange.toFixed(2) + '%</span>';

      if (qty > 0) {{
        const dollarChange = (current - buy) * qty;
        const dSign = dollarChange >= 0 ? '+' : '-';
        html += '<br><span style="color:' + color + ';font-size:0.85em;">' +
                dSign + currencySymbol + Math.abs(dollarChange).toFixed(2) + '</span>';
      }}

      plCell.innerHTML = html;

      const suggestion = getSuggestion(ticker, pctChange);
      suggCell.innerHTML = '<span style="color:' + suggestion.color + ';font-weight:600;">' + suggestion.text + '</span>';

      if (shouldSave) savePosition(ticker, buyInput.value, qtyInput.value);
    }}

    function savePosition(ticker, buy, qty) {{
      if (currentUser && userPositionsRef) {{
        const update = {{}};
        update[ticker] = {{ buy: buy, qty: qty }};
        userPositionsRef.set(update, {{ merge: true }}).catch(function(err) {{
          console.error("Cloud save failed, falling back to local storage:", err);
          localStorage.setItem('buyPrice_' + ticker, buy);
          localStorage.setItem('qty_' + ticker, qty);
        }});
      }} else {{
        localStorage.setItem('buyPrice_' + ticker, buy);
        localStorage.setItem('qty_' + ticker, qty);
      }}
    }}

    function clearPosition(ticker) {{
      if (currentUser && userPositionsRef) {{
        const update = {{}};
        update[ticker] = firebase.firestore.FieldValue.delete();
        userPositionsRef.set(update, {{ merge: true }}).catch(function(err) {{
          console.error("Cloud clear failed:", err);
        }});
      }} else {{
        localStorage.removeItem('buyPrice_' + ticker);
        localStorage.removeItem('qty_' + ticker);
      }}
    }}

    function loadPositionLocal(ticker) {{
      const savedBuy = localStorage.getItem('buyPrice_' + ticker);
      const savedQty = localStorage.getItem('qty_' + ticker);
      if (savedBuy) document.getElementById('buy_' + ticker).value = savedBuy;
      if (savedQty) document.getElementById('qty_' + ticker).value = savedQty;
      updatePL(ticker, false);
    }}

    function loadPositionsFromCloud() {{
      userPositionsRef.get().then(function(doc) {{
        const data = doc.exists ? doc.data() : {{}};
        Object.keys(currentPrices).forEach(function(ticker) {{
          const pos = data[ticker];
          if (pos) {{
            document.getElementById('buy_' + ticker).value = pos.buy;
            document.getElementById('qty_' + ticker).value = pos.qty;
          }}
          updatePL(ticker, false);
        }});
      }}).catch(function(err) {{
        console.error("Cloud load failed, falling back to local storage:", err);
        Object.keys(currentPrices).forEach(loadPositionLocal);
      }});
    }}

    document.addEventListener('DOMContentLoaded', function() {{
      if (firebaseReady) {{
        document.getElementById('signInBtn').style.display = 'inline-block';
        firebase.auth().onAuthStateChanged(function(user) {{
          currentUser = user;
          const signInBtn = document.getElementById('signInBtn');
          const signOutBtn = document.getElementById('signOutBtn');
          const userLabel = document.getElementById('userLabel');
          const note = document.getElementById('positionNote');
          if (user) {{
            signInBtn.style.display = 'none';
            signOutBtn.style.display = 'inline-block';
            userLabel.textContent = 'Synced as ' + user.displayName;
            note.textContent = 'Enter your buy price when you buy, and clear it when you sell — synced to your Google account across devices.';
            userPositionsRef = firebase.firestore().collection('positions').doc(user.uid);
            loadPositionsFromCloud();
          }} else {{
            signInBtn.style.display = 'inline-block';
            signOutBtn.style.display = 'none';
            userLabel.textContent = '';
            note.textContent = 'Enter your buy price when you buy (and optionally quantity) — leave it blank to clear it when you sell. Currently saved only in this browser; sign in with Google above to sync across devices instead.';
            userPositionsRef = null;
            Object.keys(currentPrices).forEach(loadPositionLocal);
          }}
        }});
      }} else {{
        Object.keys(currentPrices).forEach(loadPositionLocal);
      }}
    }});
  </script>
</body>
</html>"""


def generate_ai_analysis(ticker: str, signal_data: dict) -> str | None:
    """
    Ask Gemini for a short, plain-language take on this stock, based on the
    technical signal only (no fundamentals — those are paywalled for PSE
    stocks). Returns None if no API key is set, or if the request fails for
    any reason — this must never break the rest of the dashboard.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    prompt = f"""Based only on the data below, write a brief 2-3 sentence analysis of \
{ticker} (a Philippine Stock Exchange listed stock) for a retail investor's \
personal research dashboard. Mention both supportive and risk factors where \
relevant. Describe what the data shows rather than giving direct buy/sell \
instructions — the reader makes their own decision. No fundamental data \
(P/E, earnings, etc.) is available for this stock, so base this only on \
the technical signal below — say so rather than guessing at fundamentals.

Technical signal: {signal_data['signal']}
Reasons: {'; '.join(signal_data['reasons'])}"""

    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
            params={"key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"  (AI analysis failed for {ticker}: HTTP {resp.status_code} — {resp.text[:500]})", file=sys.stderr)
            return None
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"  (AI analysis failed for {ticker}: {e})", file=sys.stderr)
        return None


def main():
    results = []
    for ticker in WATCHLIST:
        print(f"Fetching {ticker}...")
        try:
            df = fetch_data(ticker)
            df = compute_indicators(df)
            sig = generate_signal(df)
            sig["ticker"] = ticker
            sig["chart_html"] = build_chart_html(ticker, df)

            if ENABLE_AI_ANALYSIS and os.environ.get("GEMINI_API_KEY"):
                sig["ai_analysis"] = generate_ai_analysis(ticker, sig)
            else:
                sig["ai_analysis"] = None

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
