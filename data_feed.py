"""
HVTS.AI Studio - Public Data Feed
=================================
Reads ONLY public Binance Futures market data via ccxt (no API keys).
Optimized for large symbol sets (500+ symbols) with batching and thread pooling.
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
    """
    Initialize and return Binance USDT-M perpetual futures exchange object.
    No API keys required - public endpoints only.
    """
    return ccxt.binanceusdm({
        "enableRateLimit": True,
        "timeout": 20000,
        "apiKey": "",
        "secret": "",
    })


def normalize_symbol(symbol: str) -> str:
    """
    Normalize symbol string by removing :USDT suffix if present.
    
    Args:
        symbol: Raw symbol string (e.g., "BTC/USDT:USDT" or "BTC/USDT")
    
    Returns:
        Normalized symbol (e.g., "BTC/USDT")
    """
    if symbol.endswith(":USDT"):
        return symbol[:-5]
    return symbol


def is_excluded(symbol: str) -> bool:
    """
    Check if a symbol should be excluded based on quote asset.
    
    Args:
        symbol: Symbol string to check
    
    Returns:
        True if symbol should be excluded, False otherwise
    """
    base = normalize_symbol(symbol).split("/")[0]
    return base in EXCLUDED_QUOTE_ASSETS


@st.cache_data(ttl=90, show_spinner=False)
def fetch_all_tickers() -> Dict[str, Dict]:
    """
    Fetch all tickers from Binance Futures and filter for USDT pairs only.
    Cached for 90 seconds to reduce API calls.
    
    Returns:
        Dictionary of ticker data keyed by symbol
    """
    ex = get_exchange()
    try:
        tickers = ex.fetch_tickers()
        # Filter to only USDT pairs and exclude problematic symbols
        filtered = {}
        for k, v in tickers.items():
            if "/USDT" in k and not is_excluded(k):
                filtered[k] = v
        return filtered
    except Exception as e:
        st.error(f"Error fetching tickers: {e}")
        return {}


@st.cache_data(ttl=280, show_spinner=False)
def fetch_ohlcv(symbol: str, timeframe: str, limit: int = 300) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data for a symbol and timeframe.
    Cached for 280 seconds to balance freshness and performance.
    
    Args:
        symbol: Trading pair (e.g., "BTC/USDT")
        timeframe: Timeframe string (e.g., "1h", "4h", "1d")
        limit: Number of candles to fetch
    
    Returns:
        DataFrame with OHLCV data or None if fetch fails
    """
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
    """
    Get top N symbols by 24h volume with optimized filtering.
    Supports up to 500+ symbols efficiently.
    
    Args:
        tickers: Dictionary of ticker data
        min_volume: Minimum 24h volume threshold
        top_n: Number of top symbols to return
    
    Returns:
        List of normalized symbol strings
    """
    rows = []
    for raw_symbol, data in tickers.items():
        if "/USDT" not in raw_symbol or is_excluded(raw_symbol):
            continue
        
        vol = data.get("quoteVolume", 0) or 0
        if vol >= min_volume:
            rows.append((raw_symbol, vol))
    
    # Sort by volume descending and limit
    rows.sort(key=lambda r: -r[1])
    return [normalize_symbol(r[0]) for r in rows[:top_n]]


def fetch_symbol_bundle(symbol: str) -> Dict[str, Optional[pd.DataFrame]]:
    """
    Fetch all timeframes needed for a single symbol's full signal matrix.
    
    Args:
        symbol: Trading pair (e.g., "BTC/USDT")
    
    Returns:
        Dictionary with timeframe keys and DataFrame values
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


def fetch_bundles_threaded(symbols: List[str], max_workers: int = 16) -> Dict[str, Dict]:
    """
    Fetch all timeframes for multiple symbols using thread pooling.
    Optimized for parallel execution with configurable worker count.
    
    Args:
        symbols: List of trading pairs
        max_workers: Maximum number of concurrent threads
    
    Returns:
        Dictionary mapping symbols to their timeframe data
    """
    results = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = {executor.submit(fetch_symbol_bundle, sym): sym for sym in symbols}
        
        # Process completed futures
        for fut in as_completed(futures):
            sym = futures[fut]
            try:
                results[sym] = fut.result(timeout=30)  # 30 second timeout per symbol
            except Exception as e:
                # Log error but continue with other symbols
                results[sym] = {}
    
    return results


def fetch_bundles_batched(symbols: List[str], batch_size: int = 200, max_workers: int = 16) -> Dict[str, Dict]:
    """
    Fetch bundles in batches to handle very large symbol lists (500+).
    Prevents timeout and memory issues with large datasets.
    
    Args:
        symbols: List of trading pairs
        batch_size: Number of symbols to process per batch
        max_workers: Maximum number of concurrent threads per batch
    
    Returns:
        Dictionary mapping symbols to their timeframe data
    """
    results = {}
    total_batches = (len(symbols) + batch_size - 1) // batch_size
    
    # Show progress for large batches
    if total_batches > 1:
        st.info(f"📊 Processing {len(symbols)} symbols in {total_batches} batches...")
    
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        
        # Show progress for each batch
        if total_batches > 1:
            st.text(f"Processing batch {batch_num}/{total_batches} ({len(batch)} symbols)...")
        
        batch_results = fetch_bundles_threaded(batch, max_workers)
        results.update(batch_results)
        
        # Small delay between batches to avoid rate limiting
        if i + batch_size < len(symbols):
            time.sleep(0.5)
    
    return results


def get_market_coverage(symbols: List[str]) -> Dict[str, any]:
    """
    Get market coverage statistics for the current symbol set.
    
    Args:
        symbols: List of trading pairs
    
    Returns:
        Dictionary with coverage statistics
    """
    total_futures_pairs = 500  # Approximate total USDT pairs on Binance Futures
    
    return {
        "total_symbols": len(symbols),
        "market_coverage_pct": (len(symbols) / total_futures_pairs) * 100,
        "estimated_pairs": total_futures_pairs
    }