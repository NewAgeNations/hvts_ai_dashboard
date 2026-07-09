# HVTS.AI Studio — Binance Futures Signal Dashboard

A high-performance Streamlit dashboard that scans **500+** Binance Futures (USDT-margined) symbols using only **public** market data (no API keys) and turns them into decision-ready calls for **day trading**, **swing trading**, and **position trading**.

---

## 🚀 Features

### Core Signal Engine

| Component | Description |
|-----------|-------------|
| **GMMA** | Guppy Multiple Moving Average on 1H / 4H / 1D / 1W — trend direction |
| **ATH Pivot Zone** | Discount-from-all-time-high zone mapping (Above Buy → Strong Support → Reversal → Accumulation → Extreme Discount) |
| **Fuzzy Fib + Poly + ADX Oracle** | SuperTrendOracle/MicroHedge style fusion on multiple timeframe pairs |
| **HVTS Composite Score** | Weighted blend of all three oracle reads with user-controlled tilt |

### Advanced Indicators (NEW)

All advanced indicators computed on the **4-hour timeframe**:

| Indicator | Description | Signal Logic |
|-----------|-------------|--------------|
| **MACD (H4)** | Moving Average Convergence Divergence | Bullish: MACD > Signal & histogram positive |
| **Williams %R (H4)** | Momentum oscillator | Oversold Bullish: < -80 / Overbought Bearish: > -20 |
| **CRT (H4)** | Candle Range Theory | Breakout detection during expansion phases |
| **SMC (H4)** | Smart Money Concept | Break of recent swing high/low |
| **VWAP (H4)** | Volume-Weighted Average Price | Bullish: >1% above / Bearish: <1% below |
| **RVOL (H4)** | Relative Volume | High: >1.5x / Moderate: 1.2-1.5x / Low: <1.2x |

### Dashboard Tabs

1. **🔥 Day Trading** — M15/M30 Oracle + H1 GMMA confirmation
2. **📈 Swing Trading** — H1/H4 Oracle + H4 & Daily GMMA confirmation
3. **🧭 Position Trading** — Daily/Weekly Oracle + ATH discount zone
4. **🗂 Full Matrix** — All signals side-by-side, ranked by HVTS Composite Score, exportable to CSV
5. **🔍 Symbol Deep Dive** — Gauges + candlestick chart with EMA ribbons and ATH zone markers
6. **📊 Advanced Signals** — Dedicated tab for all H4 advanced indicators

### Performance Optimizations

| Feature | Specification |
|---------|---------------|
| **Max Symbols** | 500+ (configurable) |
| **Batch Processing** | Automatic batching for large symbol sets |
| **Thread Pool** | 16 concurrent workers |
| **Caching** | Smart TTLs (90s for tickers, 280s for OHLCV) |
| **Timeouts** | 30-second timeout per symbol |

---

## 📦 Installation

### Prerequisites

- Python 3.8+
- pip

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/hvts_ai_dashboard.git
cd hvts_ai_dashboard

# Install dependencies
pip install -r requirements.txt

# Run the dashboard
streamlit run app.py
```

### Requirements

```
streamlit>=1.38
ccxt>=4.3
pandas>=2.0
numpy>=1.26
plotly>=5.20
streamlit-autorefresh>=1.0.1
```

---

## 🎮 Usage Guide

### Sidebar Controls

#### Universe Selection
- **Top by 24h Volume**: Scan top N symbols by volume (10-500 symbols)
- **Custom Watchlist**: Paste your own symbols (e.g., `BTC/USDT, ETH/USDT, SOL/USDT`)

#### Volume Filter
- Minimum 24h volume threshold (default: 1,000,000 USDT)
- Filter out low-volume pairs for better performance

#### Refresh Settings
- Auto-refresh toggle with selectable interval (30s – 5min)
- Manual refresh button for immediate re-scan

#### Trading Style Weighting
- **Day**: Emphasizes short-term (15m/30m) signals
- **Balanced**: Equal weighting across all timeframes
- **Position**: Emphasizes long-term (1D/1W) signals

---

## 📊 Understanding the Signals

### Oracle Signals (Day/Swing/Position)

| Signal | Meaning |
|--------|---------|
| **STRONG BUY** | High conviction bullish signal |
| **BUY** | Moderately bullish |
| **NEUTRAL** | No clear direction |
| **SELL** | Moderately bearish |
| **STRONG SELL** | High conviction bearish signal |

### Advanced Signals (H4)

| Signal | Meaning |
|--------|---------|
| **bullish** | Bullish bias |
| **bearish** | Bearish bias |
| **neutral** | No clear bias |
| **oversold_bullish** | Oversold → potential bullish reversal |
| **overbought_bearish** | Overbought → potential bearish reversal |

### Action Calls

| Action | Meaning |
|--------|---------|
| 🟢 High-Conviction Long | Strong bullish + deep-value zone |
| 🟡 Bullish, but extended | Bullish but overextended from ATH |
| 🟢 Constructive | Moderately bullish |
| ⚪ Stand aside | Neutral |
| 🟠 Weakening | Moderately bearish |
| 🔴 Avoid / Short bias | Strongly bearish |

### KPIs Displayed

| Metric | Description |
|--------|-------------|
| Symbols Scanned | Number of symbols successfully analyzed |
| Strong Bullish | Symbols with HVTS Score ≥ 0.5 |
| Strong Bearish | Symbols with HVTS Score ≤ -0.5 |
| Deep-Value Zone | Symbols in Accumulation or Extreme Discount zones |
| Avg Confidence | Average confidence across all signals |
| Market Coverage | Percentage of Binance Futures market covered |

---

## 🏗️ Architecture

### File Structure

```
hvts_ai_dashboard/
├── app.py              # Main Streamlit application
├── data_feed.py        # Data fetching and caching layer
├── indicators.py       # Indicator engine with all signal logic
├── requirements.txt    # Python dependencies
└── README.md          # This documentation
```

### Data Flow

```
┌─────────────────┐
│  Binance Futures │
│  Public API      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  fetch_all_     │  90s cache
│  tickers()      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  get_top_       │  Volume filtering
│  symbols_by_    │
│  volume()       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  fetch_bundles_ │  Batch processing
│  batched()      │  Thread pooling
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  build_master_  │  Signal computation
│  table()        │  Indicator engine
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Streamlit UI   │  Dashboard display
│  Tabs & Charts  │
└─────────────────┘
```

### Indicator Engine Modules

**`indicators.py`** includes:

1. **GMMA** — Guppy Multiple Moving Average
2. **ATH Pivot Zone** — Discount from all-time-high
3. **Fibonacci Bullishness** — Smooth interpolation
4. **Polynomial Regression** — Slope analysis
5. **Wilder's ADX** — Trend strength indicator
6. **Composite Oracle** — Fuzzy logic fusion
7. **Advanced Indicators** (NEW):
   - Williams %R
   - MACD
   - CRT (Candle Range Theory)
   - SMC (Smart Money Concept)
   - VWAP
   - RVOL

---

## ⚡ Performance Notes

### Symbol Universe Size
- **Default max**: 500 symbols (configurable)
- **Recommended**: 100-200 symbols for optimal performance
- **Large scans**: 300-500 symbols may take 30-60 seconds

### Batch Processing
- **Automatic batching**: Symbols processed in batches of 200
- **Thread pooling**: 16 concurrent workers for efficient fetching
- **Caching**: All data cached with smart TTLs

### Optimization Tips
1. Use **Custom Watchlist** for focused scanning (faster)
2. Increase **min volume threshold** to filter out illiquid pairs
3. Adjust **auto-refresh interval** based on your needs
4. Use **Top by Volume** with reasonable N (100-200) for balance
5. Lower symbol count during volatile market conditions

---

## 🔧 Troubleshooting

### No symbols matched your filters
- Lower the minimum volume threshold
- Select more symbols (increase top N or expand watchlist)
- Click "Refresh now" to force a fresh data pull

### Slow performance
- Reduce the number of symbols scanned
- Increase auto-refresh interval
- Use a smaller universe (custom watchlist instead of top N)
- Increase minimum volume threshold

### Missing advanced indicators
- Ensure 4-hour data is available for the symbol
- Check that the symbol has sufficient historical data (min 50 bars)
- Some newer pairs may not have enough history

### Rate limiting errors
- Increase auto-refresh interval
- Reduce number of symbols
- Use custom watchlist with fewer symbols

### Memory issues
- Reduce batch size in `fetch_bundles_batched()`
- Use fewer symbols
- Restart the Streamlit server

---

## 🛡️ Security

- **No API keys required** — all data from public endpoints
- **Read-only** — no trading or account access
- **Local processing** — all computations performed locally
- **No data storage** — no user data collected or stored

---

## 📝 Notes

- Data is fetched from Binance Futures' **public** endpoints only
- Signals are analytical output for research purposes, **not financial advice**
- Symbols with insufficient data are automatically skipped
- All indicators are computed on the fly with each refresh
- The dashboard respects Binance's rate limits automatically

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

### Areas for Improvement
- Additional timeframe support
- More advanced indicators
- Custom indicator configuration
- Alert system integration
- Backtesting capabilities

---

## 📄 License

This project is for research and educational purposes only. Trading cryptocurrencies carries significant risk. Always do your own research before making trading decisions.

---

**HVTS.AI Studio** — Advanced multi-timeframe signal intelligence for cryptocurrency trading

---

## 🔗 Quick Links

- **Dashboard**: `http://localhost:8501` (after running)
- **Binance Futures**: [https://www.binance.com/en/futures](https://www.binance.com/en/futures)
- **CCXT Documentation**: [https://docs.ccxt.com/](https://docs.ccxt.com/)
- **Streamlit Documentation**: [https://docs.streamlit.io/](https://docs.streamlit.io/)

---

## 📊 Example Screenshots

### KPI Strip
Shows key metrics at a glance: symbols scanned, bullish/bearish counts, deep-value zones, and market coverage.

### Full Matrix
All signals side-by-side with color-coded indicators and HVTS Composite Score ranking.

### Symbol Deep Dive
Detailed view with gauge indicators, candlestick chart, and advanced indicator metrics.

### Advanced Signals Tab
Dedicated view for MACD, Williams %R, CRT, SMC, VWAP, and RVOL indicators.

---

**Last Updated**: 2026-07-09
**Version**: 2.0
**Status**: Production Ready
```