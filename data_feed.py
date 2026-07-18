"""
HVTS.AI Studio - Public Data Feed (Yahoo Finance)
==================================================
Simplified and robust version with POL-USD fix.
"""

import pandas as pd
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
import yfinance as yf

# ============================================================================
# SYMBOL MAPPING - Updated with POL-USD
# ============================================================================
SYMBOL_MAP = {
    "BTC/USDT": "BTC-USD",
    "ETH/USDT": "ETH-USD",
    "TRX/USDT": "TRX-USD",
    "XRP/USDT": "XRP-USD",
    "ADA/USDT": "ADA-USD",
    "DOGE/USDT": "DOGE-USD",
    "POL/USDT": "POL-USD",        # Changed from MATIC-USD
    "DOT/USDT": "DOT-USD",
    "AVAX/USDT": "AVAX-USD",
    "BNB/USDT": "BNB-USD",
}

# Timeframe mappings
INTERVAL_MAP = {"15m": "15m", "30m": "30m", "1h": "1h", "4h": "1h", "1d": "1d", "1w": "1wk"}
PERIOD_MAP = {"15m": "7d", "30m": "7d", "1h": "7d", "4h": "7d", "1d": "1mo", "1w": "3mo"}

# Symbols that are known to fail (to skip them quickly)
FAILED_SYMBOLS = set()


@st.cache_data(ttl=280, show_spinner=False)
def fetch_ohlcv(symbol: str, timeframe: str, limit: int = 300) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data from Yahoo Finance with error handling.
    """
    # Check if this symbol is known to fail
    if symbol in FAILED_SYMBOLS:
        return None
    
    yf_symbol = SYMBOL_MAP.get(symbol)
    if not yf_symbol:
        return None
    
    interval = INTERVAL_MAP.get(timeframe, "1h")
    period = PERIOD_MAP.get(timeframe, "7d")
    
    try:
        # Download with robust settings
        df = yf.download(
            yf_symbol,
            period=period,
            interval=interval,
            auto_adjust=False,
            progress=False,
            threads=False,
            ignore_tz=True
        )
        
        # If empty, mark as failed and return
        if df.empty:
            FAILED_SYMBOLS.add(symbol)
            return None
        
        # Normalise columns
        df.columns = [c.lower() for c in df.columns]
        
        # For 4h, resample from 1h
        if timeframe == "4h":
            df = df.resample('4H').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
        
        # Limit rows
        df = df.iloc[-limit:]
        df.index.name = 'timestamp'
        
        return df
        
    except Exception as e:
        # Mark as failed so we skip it next time
        FAILED_SYMBOLS.add(symbol)
        return None


def fetch_symbol_bundle(symbol: str) -> Dict[str, Optional[pd.DataFrame]]:
    """Fetch all timeframes for a symbol."""
    frames = {}
    for tf, limit in [("15m", 300), ("30m", 300), ("1h", 300), ("4h", 300), ("1d", 400), ("1w", 260)]:
        frames[tf] = fetch_ohlcv(symbol, tf, limit)
    return frames


def fetch_bundles_threaded(symbols: List[str], max_workers: int = 8) -> Dict[str, Dict]:
    """Fetch bundles in parallel."""
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_symbol_bundle, sym): sym for sym in symbols}
        for fut in as_completed(futures):
            sym = futures[fut]
            try:
                results[sym] = fut.result(timeout=45)
            except Exception:
                results[sym] = {}
    return results


def fetch_bundles_batched(symbols: List[str], batch_size: int = 200, max_workers: int = 8) -> Dict[str, Dict]:
    """Batch processing (kept for compatibility)."""
    results = {}
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i+batch_size]
        batch_results = fetch_bundles_threaded(batch, max_workers)
        results.update(batch_results)
    return results