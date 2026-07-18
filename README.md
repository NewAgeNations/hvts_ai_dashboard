<div align="center">

<img src="hvts_logo.png" width="110" alt="HVTS.AI Studio logo" />

# HVTS.AI Studio

**Multi-Timeframe Signal Intelligence for Cryptocurrency Markets**

A dark-themed, auto-refreshing Streamlit dashboard that fuses trend, momentum, and
market-structure signals across ten major crypto pairs — powered entirely by free,
public exchange data.

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.38%2B-FF4B4B)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-Educational%20Use-lightgrey)](#license)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)](#)

</div>

---

## Overview

HVTS.AI Studio is a real-time market-scanning dashboard built for traders who want a
single, decision-ready view of the crypto market across day, swing, and position
trading horizons. It takes raw OHLCV candles from **Gate.io's public spot API** — no
API keys, no exchange account, no authentication of any kind — and turns them into a
fused, weighted read on trend direction, momentum, market structure, and
discount-from-all-time-high, refreshed automatically on a timer.

It ships as three focused Python modules:

| Module | Responsibility |
|---|---|
| `app.py` | Streamlit UI, layout, theming, tab logic, and score aggregation |
| `data_feed.py` | Public OHLCV fetching from Gate.io, caching, and connectivity diagnostics |
| `indicators.py` | The full signal-engine — GMMA, ATH pivot zones, the fuzzy composite oracle, and the H4 advanced-indicator suite |

---

## Why Gate.io, not Binance

Earlier versions of this project scanned Binance Futures directly. Binance's public
market-data endpoints return `HTTP 451` ("Service unavailable from a restricted
location") for a large share of cloud-hosted IP ranges, which made the dashboard
unreliable when deployed outside a handful of regions. **Gate.io's public spot
endpoints carry no such geo-restriction**, so the data layer was rewritten around
Gate.io's `/spot/candlesticks` endpoint, keeping the "no API key, read-only, public
data only" design promise intact.

---

## Key Features

### 🔎 Fixed, Curated Universe
Rather than scanning hundreds of illiquid pairs, HVTS.AI Studio tracks a fixed list of
ten liquid majors, keeping every refresh fast and every signal statistically
meaningful:

`BTC/USDT · ETH/USDT · TRX/USDT · XRP/USDT · ADA/USDT · DOGE/USDT · POL/USDT · DOT/USDT · AVAX/USDT · BNB/USDT`

### 📡 Core Signal Engine

| Component | What it does |
|---|---|
| **GMMA** (Guppy Multiple Moving Average) | Six short + six long EMAs on 1H/4H/1D/1W — a fast read on trend direction and separation |
| **ATH Pivot Zone** | Maps current price against its all-time high into five discount bands, from *Above Buy Zone* to *Extreme Discount* |
| **Fuzzy Composite Oracle** | An ADX-regime-weighted fusion of Fibonacci-retracement bullishness, cubic polynomial-regression slope, and GMMA spread, evaluated across a fast/slow timeframe pair |
| **HVTS Composite Score** | A single −1…+1 score blending the Day / Swing / Position oracle reads, tilted by the sidebar's trading-style weighting |

### 📈 Advanced H4 Indicator Suite

Computed independently on the 4-hour timeframe for every symbol:

| Indicator | Signal Logic |
|---|---|
| **MACD** | Bullish when the MACD line sits above its signal line with a positive histogram (and the inverse for bearish) |
| **Williams %R** | Oversold-bullish below −80, overbought-bearish above −20 |
| **CRT** (Candle Range Theory) | Flags breakouts through the prior candle's high/low during a range-expansion phase |
| **SMC** (Smart Money Concept) | Detects a break of the most recent swing high or swing low |
| **VWAP** | Bullish/bearish when price sits more than 1% from the volume-weighted average price |
| **RVOL** | Current volume relative to its 20-period average — flags high (>1.5x) and moderate (1.2–1.5x) activity |

### 🧠 Bitcoin AI Signal (Neural Network Integration)
A dedicated tab surfaces live predictions from the companion **HVTS-NeuralNetwork**
system — a BiLSTM + Multi-Head Attention deep learning model — via a Supabase
backend. It displays trend classification, model confidence, expected returns and
target prices at multiple forecast horizons, and a rolling history of recent signals.
This tab requires `SUPABASE_URL` and `SUPABASE_KEY` to be configured; without them it
degrades gracefully with a setup notice instead of failing.

### 🗂 Dashboard Tabs

1. **🔥 Day Trading** — M15/M30 oracle read, confirmed by H1 GMMA
2. **📈 Swing Trading** — H1/H4 oracle read, confirmed by H4 & Daily GMMA
3. **🧭 Position Trading** — Daily/Weekly oracle read, gated by ATH discount zone
4. **🗂 Full Matrix** — every timeframe and signal side-by-side, ranked by HVTS Composite Score, exportable to CSV
5. **🔍 Symbol Deep Dive** — confidence gauges per horizon, advanced-indicator readout, and a candlestick chart with EMA ribbons and ATH zone markers
6. **📊 Advanced Signals** — dedicated table for MACD, Williams %R, CRT, SMC, VWAP, and RVOL
7. **🧠 Bitcoin AI Signal** — live neural-network trend, confidence, and target-price predictions for BTC/USDT

### ⚙️ Engineering Details
- **No API keys for market data** — Gate.io's public endpoints only
- **Threaded fetching** with per-symbol OHLCV bundling across six timeframes (15m/30m/1h/4h/1d/1w)
- **Smart caching** — 280s TTL on OHLCV pulls to stay well inside Gate.io's public rate limits
- **Transparent diagnostics** — per-symbol fetch errors and a live connectivity check surface directly in the UI rather than failing silently
- **Dependency-safe styling** — the HVTS Score heatmap is hand-rolled rather than using `Styler.background_gradient()`, so a missing `matplotlib` install can't crash the page
- **Dark, glass-morphic theme** — custom CSS with Space Grotesk / JetBrains Mono typography, gradient header, animated live-pill, and diverging red-to-green score coloring

---

## Installation

### Prerequisites
- Python 3.8+
- pip

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/hvts_ai_studio.git
cd hvts_ai_studio

# Install dependencies
pip install -r requirements.txt

# Run the dashboard
streamlit run app.py
```

The dashboard opens at `http://localhost:8501`.

### Dependencies

```
streamlit>=1.38
pandas>=2.0
numpy>=1.26
plotly>=5.20
streamlit-autorefresh>=1.0.1
supabase>=2.0.0
requests>=2.28.0
matplotlib>=3.7
```

### Optional: Bitcoin AI Signal tab

To populate the **Bitcoin AI Signal** tab, set the following as environment
variables or in `.streamlit/secrets.toml`:

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-anon-or-service-key"
```

The companion **HVTS-NeuralNetwork** service (a separate BiLSTM + Attention
autonomous trainer/predictor) writes its predictions to a `neural_signals` table in
Supabase, which this tab reads on a 60-second cache.

---

## Usage Guide

### Sidebar Controls
- **Auto-refresh** — toggle on/off, with a selectable interval from 30s to 5 minutes
- **Refresh now** — force an immediate cache clear and re-scan
- **Trading style weighting** — tilt the HVTS Composite Score toward **Day**,
  **Balanced**, or **Position** emphasis

### Reading the Signals

| Oracle Signal | Meaning |
|---|---|
| **STRONG BUY** | High-conviction bullish read |
| **BUY** | Moderately bullish |
| **NEUTRAL** | No clear directional edge |
| **SELL** | Moderately bearish |
| **STRONG SELL** | High-conviction bearish read |

| Action Call | Meaning |
|---|---|
| 🟢 High-Conviction Long | Strong bullish + deep discount from ATH |
| 🟡 Bullish, but extended | Bullish but trading rich versus its ATH |
| 🟢 Constructive | Moderately bullish |
| ⚪ Stand aside | Neutral |
| 🟠 Weakening | Moderately bearish |
| 🔴 Avoid / Short bias | Strongly bearish |

### KPI Strip
Symbols Analysed · Strong Bullish · Strong Bearish · Deep-Value Zone · Avg Confidence · Universe size — all recomputed on every refresh cycle.

---

## Architecture

```
hvts_ai_studio/
├── app.py              # Streamlit UI, theming, tabs, score aggregation
├── data_feed.py         # Gate.io public OHLCV fetching, caching, diagnostics
├── indicators.py        # Signal engine: GMMA, pivot zones, oracle, H4 advanced indicators
├── requirements.txt     # Python dependencies
├── assets/hvts_logo.png # Dashboard logo
└── README.md             # This documentation
```

### Data Flow

```
Gate.io Public Spot API  (/spot/candlesticks)
            │
            ▼
   fetch_bundles_threaded()      ← threaded, per-symbol, 6 timeframes
            │
            ▼
     build_master_table()        ← indicator + oracle computation per symbol
            │
            ▼
   composite_hvts_score()        ← style-weighted Day/Swing/Position blend
            │
            ▼
      Streamlit Tabs & Charts
```

---

## Troubleshooting

**No data / "Connectivity check to Gate.io failed"**
An HTTP 403/451 in the error detail means Gate.io's servers are rejecting requests
from your host's IP or region — this is not a bug in the code. Retrying won't help;
try a different network/host, or point `data_feed.py` at another exchange's public
API.

**Bitcoin AI Signal tab shows a warning**
`SUPABASE_URL` / `SUPABASE_KEY` are missing from your environment or
`.streamlit/secrets.toml`. The rest of the dashboard is unaffected.

**Slow refreshes**
Increase the auto-refresh interval in the sidebar; the fixed 10-symbol universe
already keeps this dashboard lightweight compared to a full-market scanner.

---

## Security & Data Handling

- **No API keys required** for market data — Gate.io public endpoints only
- **Read-only** — no trading, order placement, or account access of any kind
- **Local computation** — all indicator math runs client-side in the Streamlit process
- **No user data collected or stored** by the dashboard itself

---

## Disclaimer

Signals produced by HVTS.AI Studio are analytical research output only and do **not**
constitute financial advice. Cryptocurrency trading carries significant risk of loss.
Always conduct independent research and consider your own risk tolerance before
making trading decisions.

---

## License

This project is provided for research and educational purposes only.

---

<div align="center">

**HVTS.AI Studio** — Advanced multi-timeframe signal intelligence for cryptocurrency trading
Built on the HVTS signal stack by **GalaxyChain Technologies Ltd**

</div>