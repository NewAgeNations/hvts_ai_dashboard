"""
HVTS.AI Studio - Public Data Feed
=================================
Reads ONLY public Binance Futures market data via ccxt (no API keys).
"""

import time
import pandas as pd
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

import ccxt

EXCLUDED_QUOTE_ASSETS = {
    "USDC", "TUSD", "BUSD", "DAI", "USDP", "FDUSD", "AEUR",
    "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "CNH", "NZD",
    "ZAR", "TRY", "BRL", "MXN", "SGD", "HKD", "KRW", "RUB",
    "UAH", "PLN", "CZK", "SEK", "NOK", "DKK", "ILS", "NGN",
    "PHP", "IDR", "INR", "VND",
}


def get_exchange():
    return ccxt.binanceusdm({
        "enableRateLimit": True,
        "timeout": 20000,
        "apiKey": "",
        "secret": "",
    })


def normalize_symbol(symbol: str) -> str:
    if symbol.endswith(":USDT"):
        return symbol[:-5]
    return symbol


def is_excluded(symbol: str) -> bool:
    base = normalize_symbol(symbol).split("/")[0]
    return base in EXCLUDED_QUOTE_ASSETS


@st.cache_data(ttl=90, show_spinner=False)
def fetch_all_tickers() -> Dict[str, Dict]:
    ex = get_exchange()
    try:
        return ex.fetch_tickers()
    except Exception:
        return {}


@st.cache_data(ttl=280, show_spinner=False)
def fetch_ohlcv(symbol: str, timeframe: str, limit: int = 300) -> Optional[pd.DataFrame]:
    ex = get_exchange()
    try:
        ohlcv = ex.fetch_ohlcv(symbol, timeframe, limit=limit)
        if not ohlcv or len(ohlcv) < 5:
            return None
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        return df
    except Exception:
        return None


def get_top_symbols_by_volume(tickers: Dict[str, Dict], min_volume: float, top_n: int) -> List[str]:
    rows = []
    for raw_symbol, data in tickers.items():
        if "/USDT" not in raw_symbol or is_excluded(raw_symbol):
            continue
        vol = data.get("quoteVolume", 0) or 0
        if vol >= min_volume:
            rows.append((raw_symbol, vol))
    rows.sort(key=lambda r: -r[1])
    return [normalize_symbol(r[0]) for r in rows[:top_n]]


def fetch_symbol_bundle(symbol: str) -> Dict[str, Optional[pd.DataFrame]]:
    """Fetch all timeframes needed for one symbol's full signal matrix."""
    frames = {}
    for tf, limit in [
        ("15m", 300), ("30m", 300), ("1h", 300),
        ("4h", 300), ("1d", 400), ("1w", 260),
    ]:
        frames[tf] = fetch_ohlcv(symbol, tf, limit)
    return frames


def fetch_bundles_threaded(symbols: List[str], max_workers: int = 8) -> Dict[str, Dict]:
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_symbol_bundle, sym): sym for sym in symbols}
        for fut in as_completed(futures):
            sym = futures[fut]
            try:
                results[sym] = fut.result()
            except Exception:
                results[sym] = {}
    return results
