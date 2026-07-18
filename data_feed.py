"""
HVTS.AI Studio - Public Data Feed (Yahoo Finance)
==================================================
Free, no‑API‑key OHLCV data from Yahoo Finance for crypto pairs.
Replaces Binance Futures data.
"""

import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

import yfinance as yf

# ============================================================================
# SYMBOL MAPPING (Internal -> Yahoo Ticker)
# ============================================================================
# Maps our internal symbol names to Yahoo Finance tickers.
# For POL (Polygon), Yahoo still uses MATIC-USD.
SYMBOL_MAP = {
    "BTC/USDT": "BTC-USD",
    "ETH/USDT": "ETH-USD",
    "TRX/USDT": "TRX-USD",
    "XRP/USDT": "XRP-USD",
    "ADA/USDT": "ADA-USD",
    "DOGE/USDT": "DOGE-USD",
    "POL/USDT": "MATIC-USD",      # Polygon (formerly MATIC)
    "DOT/USDT": "DOT-USD",
    "AVAX/USDT": "AVAX-USD",
    "BNB/USDT": "BNB-USD",
}

# Yahoo Finance interval strings for each timeframe
YF_INTERVALS = {
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "1h",      # We'll resample 1h -> 4h
    "1d": "1d",
    "1w": "1wk",
}


def _to_yahoo_symbol(symbol: str) -> str:
    """
    Convert our internal symbol (e.g., 'BTC/USDT') to a Yahoo Finance ticker.
    If not found in the map, fallback to replacing '/' with '-'.
    """
    return SYMBOL_MAP.get(symbol, symbol.replace("/", "-"))


@st.cache_data(ttl=280, show_spinner=False)
def fetch_ohlcv(symbol: str, timeframe: str, limit: int = 300) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data from Yahoo Finance.
    
    Args:
        symbol: Internal symbol (e.g., 'BTC/USDT')
        timeframe: One of '15m', '30m', '1h', '4h', '1d', '1w'
        limit: Number of candles to return
    
    Returns:
        DataFrame with columns: open, high, low, close, volume
        Index: timestamp (datetime)
        Returns None if fetch fails or data is empty.
    """
    yf_symbol = _to_yahoo_symbol(symbol)
    interval = YF_INTERVALS.get(timeframe, "1h")

    # For 4h we need more 1h candles to resample
    if timeframe == "4h":
        fetch_limit = limit * 4 + 10   # extra buffer
    else:
        fetch_limit = limit

    # Determine how many days of history to fetch
    # This helps avoid downloading excessive data
    if interval in ["15m", "30m", "1h"]:
        # estimate minutes per candle
        if interval == "15m":
            minutes = 15
        elif interval == "30m":
            minutes = 30
        else:  # 1h
            minutes = 60
        total_minutes = fetch_limit * minutes + 200
        days = total_minutes / (24 * 60)
        period = f"{int(days) + 2}d"
    elif interval == "1d":
        period = f"{fetch_limit + 14}d"
    elif interval == "1wk":
        period = f"{fetch_limit * 7 + 30}d"
    else:
        period = "max"  # fallback

    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=period, interval=interval)

        if df.empty:
            return None

        # Normalise column names to lowercase
        df.columns = [c.lower() for c in df.columns]

        # Ensure volume column exists
        if 'volume' not in df.columns:
            df['volume'] = 0

        # For 4h, resample from 1h
        if timeframe == "4h":
            # Resample using 4-hour offset
            df_resampled = df.resample('4H').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            df = df_resampled

        # Keep only the last 'limit' candles
        df = df.iloc[-limit:]

        # Reset index to make timestamp a column, then set it back as index
        # This ensures the index is a proper datetime index
        if df.index.name is None or df.index.name == '':
            df.index.name = 'timestamp'
        df = df.reset_index()
        if 'date' in df.columns:
            df = df.rename(columns={'date': 'timestamp'})
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)

        # Drop any rows with NaN
        df = df.dropna()

        if df.empty:
            return None

        return df

    except Exception as e:
        # Silently fail – the caller will handle None
        print(f"Error fetching {yf_symbol} {timeframe}: {e}")
        return None


def fetch_symbol_bundle(symbol: str) -> Dict[str, Optional[pd.DataFrame]]:
    """
    Fetch all timeframes for a single symbol.
    
    Returns a dict with timeframe keys and DataFrame values.
    """
    frames = {}
    for tf, limit in [
        ("15m", 300),
        ("30m", 300),
        ("1h", 300),
        ("4h", 300),
        ("1d", 400),
        ("1w", 260),
    ]:
        frames[tf] = fetch_ohlcv(symbol, tf, limit)
    return frames


def fetch_bundles_threaded(symbols: List[str], max_workers: int = 8) -> Dict[str, Dict]:
    """
    Fetch all timeframes for multiple symbols using thread pooling.
    
    Args:
        symbols: List of internal symbol names
        max_workers: Maximum number of concurrent threads
    
    Returns:
        Dictionary mapping symbol -> {timeframe: DataFrame}
    """
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = {executor.submit(fetch_symbol_bundle, sym): sym for sym in symbols}
        
        # Process completed futures
        for fut in as_completed(futures):
            sym = futures[fut]
            try:
                results[sym] = fut.result(timeout=45)
            except Exception:
                # On failure, store an empty dict so the symbol is skipped
                results[sym] = {}
    
    return results


def fetch_bundles_batched(
    symbols: List[str], 
    batch_size: int = 200, 
    max_workers: int = 8
) -> Dict[str, Dict]:
    """
    Fetch bundles in batches to handle large lists (kept for compatibility).
    
    Args:
        symbols: List of internal symbol names
        batch_size: Number of symbols per batch (not critical for 10)
        max_workers: Maximum threads per batch
    
    Returns:
        Dictionary mapping symbol -> {timeframe: DataFrame}
    """
    results = {}
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i+batch_size]
        batch_results = fetch_bundles_threaded(batch, max_workers)
        results.update(batch_results)
    return results


# ============================================================================
# LEGACY FUNCTIONS REMOVED (no longer needed)
# ============================================================================
# The following functions from the old Binance feed are removed:
# - fetch_all_tickers()
# - get_top_symbols_by_volume()
# - normalize_symbol()
# - is_excluded()
# - get_exchange()
#
# They are no longer used because we now use a fixed symbol list.