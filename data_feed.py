"""
HVTS.AI Studio - Public Data Feed (Binance)
============================================
Free, no‑API‑key OHLCV data from Binance public API.
Uses only public endpoints (no authentication required).
"""

import pandas as pd
import streamlit as st
import requests
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

# ============================================================================
# SYMBOL MAPPING (Internal -> Binance Symbol)
# ============================================================================
# Binance uses format like "BTCUSDT" for spot markets
SYMBOL_MAP = {
    "BTC/USDT": "BTCUSDT",
    "ETH/USDT": "ETHUSDT",
    "TRX/USDT": "TRXUSDT",
    "XRP/USDT": "XRPUSDT",
    "ADA/USDT": "ADAUSDT",
    "DOGE/USDT": "DOGEUSDT",
    "POL/USDT": "POLUSDT",       # Binance supports POL
    "DOT/USDT": "DOTUSDT",
    "AVAX/USDT": "AVAXUSDT",
    "BNB/USDT": "BNBUSDT",
}

# Binance interval mapping
BINANCE_INTERVALS = {
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
    "1w": "1w",
}

# Cache for failed symbols to avoid repeated failed requests
FAILED_SYMBOLS = set()

# Rate limiting (Binance allows 1200 requests per minute)
LAST_REQUEST_TIME = 0
REQUEST_DELAY = 0.1  # 100ms between requests


def _rate_limit():
    """Ensure we don't exceed Binance's rate limits."""
    global LAST_REQUEST_TIME
    elapsed = time.time() - LAST_REQUEST_TIME
    if elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)
    LAST_REQUEST_TIME = time.time()


@st.cache_data(ttl=280, show_spinner=False)
def fetch_ohlcv(symbol: str, timeframe: str, limit: int = 300) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data from Binance public API.
    
    Args:
        symbol: Internal symbol (e.g., 'BTC/USDT')
        timeframe: One of '15m', '30m', '1h', '4h', '1d', '1w'
        limit: Number of candles to return (max 1000)
    
    Returns:
        DataFrame with columns: open, high, low, close, volume
        Index: timestamp (datetime)
    """
    # Check if this symbol is known to fail
    if symbol in FAILED_SYMBOLS:
        return None
    
    # Get Binance symbol
    binance_symbol = SYMBOL_MAP.get(symbol)
    if not binance_symbol:
        FAILED_SYMBOLS.add(symbol)
        return None
    
    # Get interval
    interval = BINANCE_INTERVALS.get(timeframe)
    if not interval:
        FAILED_SYMBOLS.add(symbol)
        return None
    
    # Build URL (using spot API)
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": binance_symbol,
        "interval": interval,
        "limit": min(limit, 1000),
    }
    
    try:
        # Rate limit
        _rate_limit()
        
        # Make request (no API key needed)
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            FAILED_SYMBOLS.add(symbol)
            return None
        
        data = response.json()
        
        if not data:
            FAILED_SYMBOLS.add(symbol)
            return None
        
        # Binance returns: [timestamp, open, high, low, close, volume, ...]
        df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
        ])
        
        # Convert types
        df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="ms")
        df["open"] = df["open"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)
        
        # Keep only relevant columns
        df = df[["timestamp", "open", "high", "low", "close", "volume"]]
        
        # Set index
        df.set_index("timestamp", inplace=True)
        
        # Sort by timestamp (oldest first)
        df = df.sort_index()
        
        # Drop any NaN rows
        df = df.dropna()
        
        if df.empty:
            FAILED_SYMBOLS.add(symbol)
            return None
        
        return df
        
    except Exception as e:
        FAILED_SYMBOLS.add(symbol)
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


def fetch_bundles_threaded(symbols: List[str], max_workers: int = 6) -> Dict[str, Dict]:
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
                results[sym] = fut.result(timeout=30)
            except Exception:
                # On failure, store an empty dict so the symbol is skipped
                results[sym] = {}
    
    return results


def fetch_bundles_batched(
    symbols: List[str], 
    batch_size: int = 200, 
    max_workers: int = 6
) -> Dict[str, Dict]:
    """
    Fetch bundles in batches to handle large lists (kept for compatibility).
    
    Args:
        symbols: List of internal symbol names
        batch_size: Number of symbols per batch
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


def test_connection() -> bool:
    """Test if Binance API is accessible."""
    try:
        response = requests.get(
            "https://api.binance.com/api/v3/ping",
            timeout=10
        )
        return response.status_code == 200
    except Exception:
        return False


# ============================================================================
# LEGACY FUNCTIONS REMOVED
# ============================================================================
# The following functions from the old feed are removed:
# - fetch_all_tickers()
# - get_top_symbols_by_volume()
# - normalize_symbol()
# - is_excluded()
# - get_exchange()