"""
HVTS.AI Studio - Indicator Engine
=================================
Self-contained signal engine adapted from the HVTS signal stack
(GMMA / Pivot-Zone / MicroHedge & SuperTrend Oracle style Fib+Poly+ADX fusion)
for live multi-symbol scanning on Binance Futures public market data.

No API keys required - reads only public OHLCV + ticker data via ccxt.
"""

import math
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ============================================================================
# GMMA (Guppy Multiple Moving Average)
# ============================================================================
GMMA_SHORT = [4, 7, 10, 13, 16, 20]
GMMA_LONG = [30, 36, 42, 48, 54, 60]


def gmma_signal(df: pd.DataFrame) -> Tuple[str, float]:
    """Returns (signal, normalized_spread) where signal in bullish/bearish/neutral."""
    if df is None or len(df) < max(GMMA_LONG) + 1:
        return "neutral", 0.0
    close = df["close"]
    short_avg = np.mean([close.ewm(span=p, adjust=False).mean().iloc[-1] for p in GMMA_SHORT])
    long_avg = np.mean([close.ewm(span=p, adjust=False).mean().iloc[-1] for p in GMMA_LONG])
    price = close.iloc[-1]
    if price == 0:
        return "neutral", 0.0
    spread = (short_avg - long_avg) / price
    if short_avg > long_avg:
        sig = "bullish"
    elif short_avg < long_avg:
        sig = "bearish"
    else:
        sig = "neutral"
    return sig, float(spread)


# ============================================================================
# ATH-based Pivot Zones
# ============================================================================
ZONE_ABOVE_BUY = "Above Buy Zone"
ZONE_STRONG_SUP = "Strong Support"
ZONE_REVERSAL = "Reversal Zone"
ZONE_ACCUMULATION = "Accumulation Zone"
ZONE_EXTREME = "Extreme Discount"

ZONE_ORDER = {
    ZONE_ABOVE_BUY: 0,
    ZONE_STRONG_SUP: 1,
    ZONE_REVERSAL: 2,
    ZONE_ACCUMULATION: 3,
    ZONE_EXTREME: 4,
}

ZONE_COLORS = {
    ZONE_ABOVE_BUY: "#8b95a5",
    ZONE_STRONG_SUP: "#5b8def",
    ZONE_REVERSAL: "#f5a524",
    ZONE_ACCUMULATION: "#17c964",
    ZONE_EXTREME: "#00d4ff",
}


def pivot_zone(price: float, ath: float) -> Tuple[str, float]:
    """Returns (zone_name, discount_pct_from_ath)."""
    if not ath or ath <= 0 or not price or price <= 0:
        return "Unknown", 0.0
    discount = (1.0 - price / ath) * 100.0
    if discount >= 90.0:
        zone = ZONE_EXTREME
    elif discount >= 75.0:
        zone = ZONE_ACCUMULATION
    elif discount >= 50.0:
        zone = ZONE_REVERSAL
    elif discount >= 25.0:
        zone = ZONE_STRONG_SUP
    else:
        zone = ZONE_ABOVE_BUY
    return zone, float(discount)


# ============================================================================
# Fibonacci bullishness (smooth interpolation, 0..1)
# ============================================================================
def fib_bullishness(df: pd.DataFrame, lookback: int) -> float:
    if df is None or len(df) < lookback:
        return 0.5
    recent = df.iloc[-lookback:]
    high = recent["high"].max()
    low = recent["low"].min()
    close = recent["close"].iloc[-1]
    if high == low:
        return 0.5
    r = (close - low) / (high - low)
    fib_levels = [0.000, 0.236, 0.382, 0.500, 0.618, 0.764, 1.000]
    bull_scores = [0.000, 0.100, 0.300, 0.500, 0.700, 0.900, 1.000]
    return float(np.interp(r, fib_levels, bull_scores))


# ============================================================================
# Polynomial regression (degree 3) slope bullishness (0..1)
# ============================================================================
def poly_bullishness(df: pd.DataFrame, lookback: int) -> float:
    if df is None or len(df) < lookback:
        return 0.5
    closes = df["close"].values[-lookback:]
    highs = df["high"].values[-lookback:]
    lows = df["low"].values[-lookback:]
    x = np.arange(len(closes))
    try:
        coeffs = np.polyfit(x, closes, 3)
    except Exception:
        return 0.5
    poly = np.poly1d(coeffs)
    deriv = np.polyder(poly)
    slope = deriv(len(closes) - 1)
    avg_range = np.mean(highs - lows)
    if avg_range == 0:
        return 0.5
    norm_slope = slope / avg_range
    return float(0.5 + 0.5 * math.tanh(norm_slope * 3))


# ============================================================================
# Wilder's ADX
# ============================================================================
def adx(df: pd.DataFrame, period: int = 14) -> float:
    if df is None or len(df) < period + 2:
        return 20.0
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    n = len(close)
    tr = np.zeros(n)
    dm_plus = np.zeros(n)
    dm_minus = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
        up = high[i] - high[i - 1]
        down = low[i - 1] - low[i]
        dm_plus[i] = up if (up > down and up > 0) else 0.0
        dm_minus[i] = down if (down > up and down > 0) else 0.0

    def wilder_smooth(arr, p):
        out = np.zeros(len(arr))
        if p >= len(arr):
            return out
        out[p] = arr[1 : p + 1].mean()
        for i in range(p + 1, len(arr)):
            out[i] = out[i - 1] * (p - 1) / p + arr[i] / p
        return out

    atr = wilder_smooth(tr, period)
    dp = wilder_smooth(dm_plus, period)
    dm = wilder_smooth(dm_minus, period)
    with np.errstate(invalid="ignore", divide="ignore"):
        di_plus = np.where(atr > 0, 100.0 * dp / atr, 0.0)
        di_minus = np.where(atr > 0, 100.0 * dm / atr, 0.0)
        di_sum = di_plus + di_minus
        dx = np.where(di_sum > 0, 100.0 * np.abs(di_plus - di_minus) / di_sum, 0.0)
    adx_arr = wilder_smooth(dx, period)
    valid = adx_arr[adx_arr > 0]
    return float(valid[-1]) if len(valid) > 0 else 20.0


# ============================================================================
# Fuzzy composite oracle (Fib + Poly + GMMA, ADX-regime weighted)
# ============================================================================
BUY_TH = 0.4
STRONG_BUY_TH = 0.6
SELL_TH = -0.4
STRONG_SELL_TH = -0.6
STRENGTH_TH = 0.3


@dataclass
class OracleResult:
    net_score: float
    strength: float
    confidence: float
    signal: str
    components: Dict[str, float] = field(default_factory=dict)


SIGNAL_COLORS = {
    "STRONG BUY": "#17c964",
    "BUY": "#7de3a3",
    "NEUTRAL": "#8b95a5",
    "SELL": "#f88fa3",
    "STRONG SELL": "#f31260",
}


def composite_oracle(df_fast: pd.DataFrame, df_slow: pd.DataFrame,
                      fib_lb_fast=20, fib_lb_slow=12,
                      poly_lb_fast=40, poly_lb_slow=24) -> OracleResult:
    """
    Generic two-timeframe fuzzy oracle (used for both the M5/M15 "day trading"
    read and the H4/D1 "swing/position" read - just pass different frames).
    """
    fib_fast = fib_bullishness(df_fast, fib_lb_fast)
    fib_slow = fib_bullishness(df_slow, fib_lb_slow)
    poly_fast = poly_bullishness(df_fast, poly_lb_fast)
    poly_slow = poly_bullishness(df_slow, poly_lb_slow)
    gmma_sig, gmma_spread = gmma_signal(df_slow)
    gmma_score = 1.0 / (1.0 + math.exp(-5.0 * gmma_spread))

    adx_fast = adx(df_fast)
    adx_slow = adx(df_slow)
    adx_avg = (adx_fast + adx_slow) / 2.0
    regime = 1.0 / (1.0 + math.exp(-0.20 * (adx_avg - 25.0)))

    w_fib = 1.0 - 0.30 * regime
    w_poly = 0.70 + 0.30 * regime
    w_gmma = 0.80

    def sigmoid(x):
        return 1.0 / (1.0 + math.exp(-5.0 * (x - 0.5)))

    mu = [sigmoid(x) for x in [fib_fast, fib_slow, poly_fast, poly_slow, gmma_score]]
    weights = [w_fib, w_fib, w_poly, w_poly, w_gmma]
    total_w = sum(weights)
    avg_bull = sum(w * m for w, m in zip(weights, mu)) / total_w
    avg_bear = sum(w * (1 - m) for w, m in zip(weights, mu)) / total_w
    net_score = avg_bull - avg_bear

    adx_multiplier = max(0.40, min(1.50, adx_avg / 25.0))
    strength = min(1.0, abs(net_score) * adx_multiplier)
    confidence = strength * 100.0

    if net_score >= STRONG_BUY_TH and strength >= STRENGTH_TH:
        signal = "STRONG BUY"
    elif net_score >= BUY_TH:
        signal = "BUY"
    elif net_score <= STRONG_SELL_TH and strength >= STRENGTH_TH:
        signal = "STRONG SELL"
    elif net_score <= SELL_TH:
        signal = "SELL"
    else:
        signal = "NEUTRAL"

    return OracleResult(
        net_score=net_score,
        strength=strength,
        confidence=confidence,
        signal=signal,
        components={
            "fib_fast": fib_fast, "fib_slow": fib_slow,
            "poly_fast": poly_fast, "poly_slow": poly_slow,
            "gmma": gmma_score, "gmma_signal": gmma_sig,
            "adx_fast": adx_fast, "adx_slow": adx_slow, "regime": regime,
        },
    )


# ============================================================================
# Volume filter
# ============================================================================
def passes_volume(volume_usdt: float, threshold: float) -> bool:
    return (volume_usdt or 0) >= threshold


# ============================================================================
# NEW: Advanced Indicators extracted from HVTSBitcoinOracle.py
# ============================================================================

def williams_r(df: pd.DataFrame, period: int = 14) -> str:
    """
    Williams %R signal.
    
    Returns:
        - 'oversold_bullish': %R below -80 (potential bullish reversal)
        - 'overbought_bearish': %R above -20 (potential bearish reversal)
        - 'neutral': otherwise
    """
    if df is None or len(df) < period:
        return "neutral"
    high = df['high'].rolling(period).max()
    low = df['low'].rolling(period).min()
    close = df['close']
    wr = -100 * (high - close) / (high - low)
    current_wr = wr.iloc[-1]
    if pd.isna(current_wr):
        return "neutral"
    if current_wr < -80:
        return "oversold_bullish"
    elif current_wr > -20:
        return "overbought_bearish"
    else:
        return "neutral"


def macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> str:
    """
    MACD (Moving Average Convergence Divergence) signal.
    
    Returns:
        - 'bullish': MACD line above signal line and histogram positive
        - 'bearish': MACD line below signal line and histogram negative
        - 'neutral': otherwise
    """
    if df is None or len(df) < slow + signal:
        return "neutral"
    close = df['close']
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    
    if pd.isna(macd_line.iloc[-1]) or pd.isna(signal_line.iloc[-1]):
        return "neutral"
    
    if macd_line.iloc[-1] > signal_line.iloc[-1] and histogram.iloc[-1] > 0:
        return "bullish"
    elif macd_line.iloc[-1] < signal_line.iloc[-1] and histogram.iloc[-1] < 0:
        return "bearish"
    return "neutral"


def crt(df: pd.DataFrame, lookback: int = 20) -> str:
    """
    Candle Range Theory (CRT) - detects expansion breakouts.
    
    Returns:
        - 'bullish': price breaks above previous high during expansion
        - 'bearish': price breaks below previous low during expansion
        - 'neutral': no breakout or contraction/normal range
    """
    if df is None or len(df) < lookback + 2:
        return "neutral"
    ranges = df['high'] - df['low']
    avg_range = ranges.iloc[-lookback:].mean()
    last_range = ranges.iloc[-1]
    
    if pd.isna(avg_range) or pd.isna(last_range):
        return "neutral"
    
    if last_range > avg_range * 1.2:
        state = "expansion"
    elif last_range < avg_range * 0.8:
        state = "contraction"
    else:
        state = "normal"
    
    prev_high = df['high'].iloc[-2]
    prev_low = df['low'].iloc[-2]
    close = df['close'].iloc[-1]
    
    if close > prev_high and state == "expansion":
        return "bullish"
    elif close < prev_low and state == "expansion":
        return "bearish"
    return "neutral"


def smc(df: pd.DataFrame) -> str:
    """
    Smart Money Concept (SMC) - detects break of recent swing points.
    
    Returns:
        - 'bullish': price breaks above most recent swing high
        - 'bearish': price breaks below most recent swing low
        - 'neutral': otherwise
    """
    if df is None or len(df) < 10:
        return "neutral"
    
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    
    swing_highs = []
    swing_lows = []
    
    for i in range(2, len(close) - 2):
        if (high[i] > high[i-1] and high[i] > high[i-2] and 
            high[i] > high[i+1] and high[i] > high[i+2]):
            swing_highs.append(high[i])
        if (low[i] < low[i-1] and low[i] < low[i-2] and 
            low[i] < low[i+1] and low[i] < low[i+2]):
            swing_lows.append(low[i])
    
    if not swing_highs and not swing_lows:
        return "neutral"
    
    current_price = close[-1]
    
    if swing_highs and current_price > swing_highs[-1]:
        return "bullish"
    elif swing_lows and current_price < swing_lows[-1]:
        return "bearish"
    return "neutral"


def vwap(df: pd.DataFrame, period: int = 50) -> str:
    """
    Volume-Weighted Average Price (VWAP) signal.
    
    Returns:
        - 'bullish': price > VWAP by 1% or more
        - 'bearish': price < VWAP by 1% or more
        - 'neutral': price within 1% of VWAP
    """
    if df is None or len(df) < period:
        return "neutral"
    
    typical = (df['high'] + df['low'] + df['close']) / 3
    volume = df.get('volume', None)
    
    if volume is None:
        # Fallback to simple moving average if volume not available
        vwap_val = typical.rolling(period).mean()
    else:
        vwap_val = (typical * volume).rolling(period).sum() / volume.rolling(period).sum()
    
    current_price = df['close'].iloc[-1]
    current_vwap = vwap_val.iloc[-1]
    
    if pd.isna(current_vwap):
        return "neutral"
    
    if current_price > current_vwap * 1.01:
        return "bullish"
    elif current_price < current_vwap * 0.99:
        return "bearish"
    return "neutral"


def rvol(df: pd.DataFrame, period: int = 20) -> float:
    """
    Relative Volume (RVOL) - ratio of current volume to average volume.
    
    Returns:
        - float: volume ratio (e.g., 1.5 means 50% above average)
    """
    if df is None or len(df) < period:
        return 1.0
    
    volume = df.get('volume', None)
    if volume is None:
        return 1.0
    
    avg_vol = volume.iloc[-period:].mean()
    cur_vol = volume.iloc[-1]
    
    if pd.isna(avg_vol) or pd.isna(cur_vol) or avg_vol == 0:
        return 1.0
    
    return float(cur_vol / avg_vol)


# ============================================================================
# Combined Advanced Indicator function for easy use in app.py
# ============================================================================

def get_advanced_indicators(df_4h: pd.DataFrame) -> Dict[str, any]:
    """
    Compute all advanced indicators on 4H timeframe.
    
    Returns a dictionary with all indicator values.
    """
    if df_4h is None or len(df_4h) < 50:
        return {
            'macd': 'neutral',
            'williams_r': 'neutral',
            'crt': 'neutral',
            'smc': 'neutral',
            'vwap': 'neutral',
            'rvol': 1.0
        }
    
    return {
        'macd': macd(df_4h),
        'williams_r': williams_r(df_4h),
        'crt': crt(df_4h),
        'smc': smc(df_4h),
        'vwap': vwap(df_4h),
        'rvol': rvol(df_4h)
    }


# ============================================================================
# Signal mapping utilities
# ============================================================================

def normalize_signal(signal_str: str) -> str:
    """
    Normalize various signal strings to consistent format.
    """
    if not signal_str:
        return "neutral"
    
    signal_lower = signal_str.lower()
    
    if "bull" in signal_lower or "buy" in signal_lower:
        return "bullish"
    elif "bear" in signal_lower or "sell" in signal_lower:
        return "bearish"
    else:
        return "neutral"


def get_signal_color(signal_str: str) -> str:
    """
    Get color for signal display.
    """
    signal_normalized = normalize_signal(signal_str)
    
    if signal_normalized == "bullish":
        return "#1fd67a"  # GREEN
    elif signal_normalized == "bearish":
        return "#f5455c"  # RED
    else:
        return "#8a93ab"  # TEXT_DIM