"""
HVTS.AI Studio - Public Data Feed (Gate.io)
============================================
Free, no-API-key OHLCV data from Gate.io's public spot API.
Uses only public endpoints (no authentication required).

Switched from Binance -> Gate.io because Binance's public API returns
HTTP 451 ("Service unavailable from a restricted location") for requests
from many cloud-hosted IP ranges. Gate.io's public market-data endpoints
do not apply that geo/IP restriction.
"""

import pandas as pd
import streamlit as st
import requests
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

# ============================================================================
# SYMBOL MAPPING (Internal -> Gate.io currency pair)
# ============================================================================
# Gate.io uses underscore-separated pairs like "BTC_USDT" for spot markets
SYMBOL_MAP = {
    "BTC/USDT": "BTC_USDT",
    "ETH/USDT": "ETH_USDT",
    "TRX/USDT": "TRX_USDT",
    "XRP/USDT": "XRP_USDT",
    "ADA/USDT": "ADA_USDT",
    "DOGE/USDT": "DOGE_USDT",
    "POL/USDT": "POL_USDT",      # Gate.io lists POL (formerly MATIC)
    "DOT/USDT": "DOT_USDT",
    "AVAX/USDT": "AVAX_USDT",
    "BNB/USDT": "BNB_USDT",
}

# Gate.io interval mapping. Gate.io has no native "1w" bucket - "7d" is the
# closest supported interval and is used for the weekly timeframe.
GATEIO_INTERVALS = {
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
    "1w": "7d",
}

# Permanently-invalid symbols only (bad symbol/timeframe mapping - not
# transient network errors). We deliberately do NOT blacklist on network/HTTP
# failures, since those are often transient (rate limit, timeout) and a
# symbol that failed once should still be retried on the next refresh.
FAILED_SYMBOLS = set()

# Diagnostics: last error seen per symbol, so the UI can explain *why* a
# symbol returned no data instead of failing silently.
LAST_ERROR: Dict[str, str] = {}

# Rate limiting (Gate.io's public endpoints are generously limited, but we
# still space requests out to be a good citizen)
LAST_REQUEST_TIME = 0
REQUEST_DELAY = 0.1  # 100ms between requests

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
})

GATEIO_BASE = "https://api.gateio.ws/api/v4"


def _rate_limit():
    """Space out requests a little."""
    global LAST_REQUEST_TIME
    elapsed = time.time() - LAST_REQUEST_TIME
    if elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)
    LAST_REQUEST_TIME = time.time()


@st.cache_data(ttl=280, show_spinner=False)
def fetch_ohlcv(symbol: str, timeframe: str, limit: int = 300) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data from Gate.io's public spot API.

    Args:
        symbol: Internal symbol (e.g., 'BTC/USDT')
        timeframe: One of '15m', '30m', '1h', '4h', '1d', '1w'
        limit: Number of candles to return (Gate.io caps at 1000)

    Returns:
        DataFrame with columns: open, high, low, close, volume
        Index: timestamp (datetime)
    """
    if symbol in FAILED_SYMBOLS:
        return None

    gateio_symbol = SYMBOL_MAP.get(symbol)
    if not gateio_symbol:
        FAILED_SYMBOLS.add(symbol)
        LAST_ERROR[symbol] = f"'{symbol}' has no entry in SYMBOL_MAP"
        return None

    interval = GATEIO_INTERVALS.get(timeframe)
    if not interval:
        LAST_ERROR[symbol] = f"timeframe '{timeframe}' has no entry in GATEIO_INTERVALS"
        return None

    url = f"{GATEIO_BASE}/spot/candlesticks"
    params = {
        "currency_pair": gateio_symbol,
        "interval": interval,
        "limit": min(limit, 1000),
    }

    try:
        _rate_limit()
        response = SESSION.get(url, params=params, timeout=10)

        if response.status_code != 200:
            try:
                body = response.json()
                detail = body.get("message", body.get("label", response.text[:200]))
            except Exception:
                detail = response.text[:200]
            LAST_ERROR[symbol] = f"HTTP {response.status_code}: {detail}"
            return None

        data = response.json()

        if not data:
            LAST_ERROR[symbol] = "empty response body"
            return None

        # Gate.io candlestick row format:
        # [timestamp(s), quote_volume, close, high, low, open, base_volume, closed?]
        df = pd.DataFrame(data, columns=[
            "timestamp", "quote_volume", "close", "high", "low", "open",
            "volume", "closed"
        ][:len(data[0])])

        df["timestamp"] = pd.to_datetime(df["timestamp"].astype(float).astype(int), unit="s")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)

        df = df[["timestamp", "open", "high", "low", "close", "volume"]]
        df.set_index("timestamp", inplace=True)
        df = df.sort_index()
        df = df.dropna()

        if df.empty:
            LAST_ERROR[symbol] = "all rows dropped as NaN after parsing"
            return None

        LAST_ERROR.pop(symbol, None)
        return df

    except requests.exceptions.Timeout:
        LAST_ERROR[symbol] = "request timed out (10s)"
        return None
    except requests.exceptions.ConnectionError as e:
        LAST_ERROR[symbol] = f"connection error: {e}"
        return None
    except Exception as e:
        LAST_ERROR[symbol] = f"{type(e).__name__}: {e}"
        return None


def get_last_errors() -> Dict[str, str]:
    """Return the most recent per-symbol fetch errors, for UI diagnostics."""
    return dict(LAST_ERROR)


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
        futures = {executor.submit(fetch_symbol_bundle, sym): sym for sym in symbols}
        for fut in as_completed(futures):
            sym = futures[fut]
            try:
                results[sym] = fut.result(timeout=30)
            except Exception as e:
                LAST_ERROR[sym] = f"thread error: {type(e).__name__}: {e}"
                results[sym] = {}
    return results


def fetch_bundles_batched(
    symbols: List[str],
    batch_size: int = 200,
    max_workers: int = 6
) -> Dict[str, Dict]:
    """
    Fetch bundles in batches to handle large lists (kept for compatibility).
    """
    results = {}
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i+batch_size]
        batch_results = fetch_bundles_threaded(batch, max_workers)
        results.update(batch_results)
    return results


def test_connection() -> Tuple[bool, str]:
    """
    Test if Gate.io's public API is reachable from this host.

    Returns (ok, detail).
    """
    try:
        response = SESSION.get(f"{GATEIO_BASE}/spot/time", timeout=10)
        if response.status_code == 200:
            return True, "OK"
        try:
            body = response.json()
            detail = body.get("message", body.get("label", response.text[:200]))
        except Exception:
            detail = response.text[:200]
        return False, f"HTTP {response.status_code}: {detail}"
    except requests.exceptions.Timeout:
        return False, "request timed out (10s)"
    except requests.exceptions.ConnectionError as e:
        return False, f"connection error: {e}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"